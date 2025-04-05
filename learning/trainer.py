"""
Model training coordinator for the Backdoor AI learning system.

This module coordinates the training of new models, including:
- Determining when retraining should occur
- Loading and processing data for training
- Incorporating user-uploaded models
- Saving and cleaning up models
"""

import sqlite3
import pandas as pd
import numpy as np
import os
import json
import logging
import shutil
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple

# Local imports
from .intent_classifier import IntentClassifier
from .preprocessor import preprocess_text, ensure_nltk_resources
from utils.db_helpers import update_model_incorporation_status, get_pending_uploaded_models
import config

logger = logging.getLogger(__name__)

def should_retrain(db_path: str) -> bool:
    """
    Determine if model retraining should be triggered based on:
    1. Number of pending uploaded models
    2. Time since last training
    3. Number of new interactions since last training
    
    Args:
        db_path: Path to the SQLite database
        
    Returns:
        bool: True if retraining should be triggered
    """
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check number of pending uploaded models
        cursor.execute("SELECT COUNT(*) FROM uploaded_models WHERE incorporation_status = 'pending'")
        pending_models_count = cursor.fetchone()[0]
        
        # If we have enough pending models, retrain
        if pending_models_count >= config.RETRAINING_THRESHOLDS['pending_models']:
            logger.info(f"Retraining triggered: {pending_models_count} pending uploaded models")
            conn.close()
            return True
        
        # Check when the last model was trained
        cursor.execute("SELECT MAX(training_date) FROM model_versions")
        last_training = cursor.fetchone()[0]
        
        if last_training:
            last_training_date = datetime.fromisoformat(last_training)
            time_since_training = datetime.now() - last_training_date
            
            # If it's been more than threshold hours since last training and we have pending models
            if (time_since_training > timedelta(hours=config.RETRAINING_THRESHOLDS['hours_since_last_training']) 
                and pending_models_count > 0):
                logger.info(f"Retraining triggered: {pending_models_count} pending models and " 
                            f"{time_since_training.total_seconds() / 3600:.1f} hours since last training")
                conn.close()
                return True
            
        # Check if we have enough new interactions since last training
        if last_training:
            cursor.execute("SELECT COUNT(*) FROM interactions WHERE created_at > ?", (last_training,))
            new_interactions = cursor.fetchone()[0]
            
            # If we have threshold+ new interactions and at least one pending model
            if (new_interactions >= config.RETRAINING_THRESHOLDS['new_interactions'] 
                and pending_models_count > 0):
                logger.info(f"Retraining triggered: {pending_models_count} pending models and " 
                            f"{new_interactions} new interactions")
                conn.close()
                return True
        
        conn.close()
        return False
    
    except Exception as e:
        logger.error(f"Error checking if retraining is needed: {e}")
        return False

def trigger_retraining(db_path: str) -> Optional[str]:
    """
    Trigger a model retraining process
    
    Args:
        db_path: Path to the SQLite database
        
    Returns:
        Optional[str]: New model version if training succeeded, None otherwise
    """
    try:
        logger.info("Triggered manual model retraining")
        return train_new_model(db_path)
    except Exception as e:
        logger.error(f"Error during triggered retraining: {e}")
        return None

def clean_old_models(model_dir: str = None, keep_newest: int = config.MAX_MODELS_TO_KEEP) -> None:
    """
    Delete old model files to prevent disk space issues
    Works with any storage backend using the storage factory
    
    Args:
        model_dir: Directory containing model files (used for local storage only)
        keep_newest: Number of most recent models to keep
    """
    try:
        # Use storage factory to get appropriate storage backend
        from utils.storage_factory import get_storage
        storage = get_storage()
        
        # List all models from storage
        all_models = storage.list_models()
        
        # Filter to just the versioned models (not uploaded user models)
        model_files = []
        for model in all_models:
            filename = model.get('name', '')
            if filename.startswith("model_") and filename.endswith(".mlmodel"):
                # Don't delete the base model
                if filename == config.BASE_MODEL_NAME:
                    logger.info(f"Skipping base model {filename} during cleanup")
                    continue
                    
                version = filename.replace("model_", "").replace(".mlmodel", "")
                try:
                    # Extract timestamp from version (assuming format like 1.0.1712052481)
                    timestamp = int(version.split(".")[-1])
                    model_files.append({
                        'filename': filename,
                        'version': version,
                        'timestamp': timestamp,
                        'name': model.get('name', '')
                    })
                except (ValueError, IndexError):
                    # Skip files with unexpected version format
                    continue
                    
        # Skip cleanup if we don't have more than the keep limit
        if len(model_files) <= keep_newest:
            logger.info(f"No model cleanup needed - only {len(model_files)} models found")
            return
            
        # Sort by timestamp (newest first)
        model_files.sort(key=lambda x: x['timestamp'], reverse=True)
        
        # Keep the newest N models, delete the rest
        models_to_delete = model_files[keep_newest:]
        for model in models_to_delete:
            # Delete model
            try:
                result = storage.delete_model(model['name'])
                if result:
                    logger.info(f"Deleted old model: {model['version']}")
                else:
                    logger.warning(f"Failed to delete model: {model['version']}")
            except Exception as e:
                logger.error(f"Error deleting model {model['version']}: {e}")
                
            # For local storage, also clean up associated files if model_dir provided
            if model_dir:
                # Delete corresponding sklearn model
                sklearn_path = os.path.join(model_dir, f"intent_classifier_{model['version']}.joblib")
                if os.path.exists(sklearn_path):
                    os.remove(sklearn_path)
                    
                # Delete model info file
                info_path = os.path.join(model_dir, f"model_info_{model['version']}.json")
                if os.path.exists(info_path):
                    os.remove(info_path)
        
        logger.info(f"Cleaned up {len(models_to_delete)} old models, kept {keep_newest} newest")
    
    except Exception as e:
        logger.error(f"Error cleaning up old models: {e}")

def prepare_training_data(db_path: str) -> Optional[pd.DataFrame]:
    """
    Load and prepare data for model training from both database and Dropbox user_data
    
    Args:
        db_path: Path to the SQLite database
        
    Returns:
        DataFrame with prepared training data or None if data is insufficient
    """
    try:
        # Load interactions with feedback from database
        conn = sqlite3.connect(db_path)
        query = """
            SELECT i.*, f.rating, f.comment 
            FROM interactions i 
            LEFT JOIN feedback f ON i.id = f.interaction_id
        """
        df = pd.read_sql_query(query, conn)
        conn.close()
        
        logger.info(f"Loaded {len(df)} interactions from database")
        
        # If Dropbox is enabled, also load interactions from user_data folder
        if config.DROPBOX_ENABLED:
            try:
                from utils.dropbox_user_data import load_user_data_for_training
                
                # Load interactions from Dropbox
                dropbox_interactions = load_user_data_for_training()
                
                if dropbox_interactions:
                    logger.info(f"Loaded {len(dropbox_interactions)} additional interactions from Dropbox user_data")
                    
                    # Convert interactions to DataFrame
                    dropbox_df = pd.DataFrame(dropbox_interactions)
                    
                    # Make sure required columns exist
                    required_columns = ['id', 'device_id', 'timestamp', 'user_message', 'ai_response', 
                                       'detected_intent', 'confidence_score', 'model_version']
                    
                    # Check if we have all required columns
                    if all(col in dropbox_df.columns for col in required_columns):
                        # Add feedback columns with default values
                        if 'rating' not in dropbox_df.columns:
                            dropbox_df['rating'] = None
                        if 'comment' not in dropbox_df.columns:
                            dropbox_df['comment'] = None
                            
                        # Combine with main DataFrame
                        df = pd.concat([df, dropbox_df], ignore_index=True).drop_duplicates(subset=['id'])
                        logger.info(f"Combined data has {len(df)} total interactions")
                    else:
                        missing_cols = [col for col in required_columns if col not in dropbox_df.columns]
                        logger.warning(f"Dropbox data missing required columns: {missing_cols}")
            except Exception as e:
                logger.error(f"Error loading user data from Dropbox: {e}")
        
        # Check if we have enough data
        if len(df) < config.MIN_TRAINING_DATA:
            logger.warning(f"Not enough data for training. Need at least {config.MIN_TRAINING_DATA} interactions.")
            return None
            
        # Prepare sample weights based on feedback
        df['has_feedback'] = df['rating'].notnull()
        df['is_good_feedback'] = (df['rating'] >= 4) & df['has_feedback']
        
        # Assign weights to different types of samples
        df['weight'] = 1  # Base weight
        df.loc[df['has_feedback'], 'weight'] = 2  # Samples with any feedback
        df.loc[df['is_good_feedback'], 'weight'] = 3  # Samples with positive feedback
        
        return df
        
    except Exception as e:
        logger.error(f"Error preparing training data: {e}")
        return None

def train_new_model(db_path: str) -> str:
    """
    Train a new model using the latest data
    
    Args:
        db_path: Path to the SQLite database
        
    Returns:
        str: Version of the new model
    """
    logger.info("Starting model training process")
    
    # Ensure NLTK resources are available
    ensure_nltk_resources()
    
    # Load and prepare data
    df = prepare_training_data(db_path)
    if df is None:
        logger.warning("Could not prepare training data")
        return get_current_model_version()
    
    # Initialize classifier
    classifier = IntentClassifier()
    
    try:
        # Train the model
        logger.info(f"Training classifier on {len(df)} samples")
        training_results = classifier.train(
            data=df,
            user_message_col='user_message',
            intent_col='detected_intent',
            weight_col='weight'
        )
        
        model_version = training_results['model_version']
        logger.info(f"Base model trained with accuracy: {training_results['accuracy']:.4f}")
        
        # Get uploaded models to incorporate into ensemble
        uploaded_models = get_pending_uploaded_models(db_path)
        
        if uploaded_models:
            # Create ensemble model
            logger.info(f"Creating ensemble with {len(uploaded_models)} uploaded models")
            
            # Mark all models as processing
            for model in uploaded_models:
                update_model_incorporation_status(db_path, model['id'], 'processing')
            
            # Try to create ensemble
            ensemble_success = classifier.create_ensemble(
                uploaded_models=uploaded_models,
                base_weight=config.BASE_MODEL_WEIGHT
            )
            
            if ensemble_success:
                logger.info("Successfully created ensemble model")
                
                # Store ensemble info in database
                from utils.db_helpers import get_connection
                with get_connection(db_path) as conn:
                    cursor = conn.cursor()
                    
                    # Create ensemble models entry
                    cursor.execute('''
                        INSERT INTO ensemble_models 
                        (ensemble_version, description, component_models)
                        VALUES (?, ?, ?)
                    ''', (
                        model_version,
                        f"Ensemble model with {len(uploaded_models)} uploaded models",
                        json.dumps([{
                            'id': model['id'],
                            'device_id': model['device_id'],
                            'original_file': model.get('original_filename', 'unknown')
                        } for model in uploaded_models])
                    ))
                    conn.commit()
                
                # Update status for all incorporated models
                for model in uploaded_models:
                    update_model_incorporation_status(db_path, model['id'], 'incorporated', model_version)
            else:
                logger.warning("Failed to create ensemble model, using base model only")
                # Mark models as failed
                for model in uploaded_models:
                    update_model_incorporation_status(db_path, model['id'], 'failed')
        
        # Save the model locally first
        model_dir = config.MODEL_DIR
        os.makedirs(model_dir, exist_ok=True)
        
        model_info = classifier.save(model_dir)
        logger.info(f"Saved model {model_version} with accuracy {model_info['accuracy']:.4f}")
        
        # Store model metadata in database using the helper which will handle Dropbox upload
        from utils.db_helpers import store_model_version
        store_model_version(
            db_path,
            model_version,
            model_info['coreml_path'],
            float(model_info['accuracy']),
            model_info['training_data_size'],
            classifier.is_ensemble,
            list(classifier.component_models.items()) if hasattr(classifier, 'component_models') else None
        )
        
        # Clean up old models (local or Dropbox depending on config)
        if config.DROPBOX_ENABLED:
            from learning.trainer_dropbox import clean_old_models_dropbox
            clean_old_models_dropbox(config.MAX_MODELS_TO_KEEP)
        else:
            clean_old_models(model_dir)
            
        # Update the base model if running with Dropbox
        if config.DROPBOX_ENABLED:
            try:
                from learning.model_orchestrator import update_base_model, create_training_summary, save_training_summary
                
                # Get model buffer for the trained model
                model_path = model_info['coreml_path']
                if os.path.exists(model_path):
                    with open(model_path, 'rb') as f:
                        model_buffer = io.BytesIO(f.read())
                        
                    # Update the base model in Dropbox
                    update_success = update_base_model(model_buffer, model_version)
                    if update_success:
                        logger.info(f"Successfully updated base model to {model_version}")
                        
                        # Get previous model info for comparison if available
                        prev_model_info = None
                        try:
                            from utils.db_helpers import get_connection
                            with get_connection(db_path) as conn:
                                cursor = conn.cursor()
                                # Get the most recent model before this one
                                cursor.execute("""
                                    SELECT version, accuracy, training_data_size, is_ensemble, training_date
                                    FROM model_versions 
                                    WHERE version != ? 
                                    ORDER BY training_date DESC LIMIT 1
                                """, (model_version,))
                                row = cursor.fetchone()
                                if row:
                                    prev_model_info = {
                                        'version': row[0],
                                        'accuracy': row[1],
                                        'training_data_size': row[2],
                                        'is_ensemble': bool(row[3]),
                                        'training_date': row[4]
                                    }
                        except Exception as e:
                            logger.warning(f"Could not get previous model info: {e}")
                        
                        # Create training data statistics
                        training_data_stats = None
                        if df is not None:
                            try:
                                # Count samples by intent
                                intent_counts = df['detected_intent'].value_counts().to_dict()
                                # Count samples with feedback
                                feedback_count = df['has_feedback'].sum() if 'has_feedback' in df.columns else 0
                                # Count positive feedback
                                positive_feedback = df['is_good_feedback'].sum() if 'is_good_feedback' in df.columns else 0
                                
                                training_data_stats = {
                                    'total_samples': len(df),
                                    'intent_distribution': intent_counts,
                                    'feedback_samples': int(feedback_count),
                                    'positive_feedback': int(positive_feedback)
                                }
                            except Exception as e:
                                logger.warning(f"Could not compute training data stats: {e}")
                        
                        # Get info about incorporated models
                        incorporated_models = []
                        if uploaded_models:
                            # For Dropbox models
                            incorporated_models = [{
                                'id': model.get('id', 'unknown'),
                                'device_id': model.get('device_id', 'unknown'),
                                'size': model.get('size', 0),
                                'weight': config.USER_MODEL_WEIGHT
                            } for model in uploaded_models]
                        
                        # Save the training summary with comprehensive details
                        summary = create_training_summary(
                            model_info, 
                            prev_model_info, 
                            training_data_stats,
                            incorporated_models
                        )
                        save_training_summary(summary)
                    else:
                        logger.warning(f"Failed to update base model to {model_version}")
                else:
                    logger.warning(f"Could not find model file at {model_path} to update base model")
            except Exception as e:
                logger.error(f"Error updating base model: {e}")
        
        logger.info(f"New model version {model_version} created successfully")
        return model_version
        
    except Exception as e:
        logger.error(f"Error training new model: {e}")
        return get_current_model_version()

def get_current_model_version() -> str:
    """
    Get the current model version
    
    Returns:
        str: Current model version
    """
    info_path = os.path.join(config.MODEL_DIR, "latest_model.json")
    try:
        if os.path.exists(info_path):
            with open(info_path, 'r') as f:
                info = json.load(f)
            return info.get('version', '1.0.0')
    except Exception as e:
        logger.error(f"Error reading latest model info: {e}")
    
    return '1.0.0'  # Default fallback version