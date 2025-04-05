"""
Model orchestration module for Backdoor AI learning system.

This module handles the coordination between different model sources:
- Base model management
- User-uploaded model aggregation
- Model versioning and updates
"""

import os
import io
import logging
import json
import time
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple

import config

logger = logging.getLogger(__name__)

def update_base_model(model_buffer: io.BytesIO, version: str) -> bool:
    """
    Update the base model in the dedicated base_model folder.
    
    This function:
    1. Copies the model to base_model/model_latest.mlmodel
    2. Also stores a versioned copy at base_model/model_{version}.mlmodel
    
    Args:
        model_buffer: BytesIO buffer containing the model data
        version: Version string for the model
        
    Returns:
        bool: True if update was successful
    """
    if not config.DROPBOX_ENABLED:
        logger.warning("Dropbox not enabled - cannot update base model")
        return False
        
    try:
        from utils.dropbox_storage import get_dropbox_storage
        dropbox_storage = get_dropbox_storage()
        
        # Reset buffer position
        model_buffer.seek(0)
        
        # Upload as latest model
        latest_result = dropbox_storage.upload_model(
            model_buffer, 
            "model_latest.mlmodel",
            config.DROPBOX_BASE_MODEL_FOLDER
        )
        
        if not latest_result.get('success'):
            logger.error(f"Failed to upload latest model: {latest_result.get('error')}")
            return False
            
        # Also upload as versioned model
        model_buffer.seek(0)
        versioned_name = f"model_{version}.mlmodel"
        versioned_result = dropbox_storage.upload_model(
            model_buffer,
            versioned_name,
            config.DROPBOX_BASE_MODEL_FOLDER
        )
        
        if not versioned_result.get('success'):
            logger.warning(f"Failed to upload versioned model: {versioned_result.get('error')}")
            # Continue anyway - the latest model was uploaded successfully
        
        logger.info(f"Successfully updated base model to version {version}")
        
        # Clear model cache to force reload with new version
        try:
            from utils.model_download import clear_model_cache
            clear_model_cache()
            logger.info("Cleared model cache to ensure latest base model is used")
        except Exception as e:
            logger.warning(f"Could not clear model cache: {e}")
        
        return True
        
    except Exception as e:
        logger.error(f"Error updating base model: {e}")
        return False

def get_uploaded_models() -> List[Dict[str, Any]]:
    """
    Get list of all user-uploaded models from backdoor_models/uploaded.
    
    Returns:
        List of dictionaries with model information
    """
    if not config.DROPBOX_ENABLED:
        logger.warning("Dropbox not enabled - cannot get uploaded models")
        return []
        
    try:
        from utils.dropbox_storage import get_dropbox_storage
        dropbox_storage = get_dropbox_storage()
        
        # First ensure the uploaded models directory exists
        try:
            uploaded_folder = f"/{config.DROPBOX_MODELS_FOLDER}/uploaded"
            try:
                dropbox_storage.dbx.files_get_metadata(uploaded_folder)
            except Exception:
                # Create folder if it doesn't exist
                logger.info(f"Creating uploaded models folder: {uploaded_folder}")
                dropbox_storage.dbx.files_create_folder_v2(uploaded_folder)
        except Exception as e:
            logger.error(f"Error ensuring uploaded folder exists: {e}")
            # Continue anyway
        
        # List all models
        all_models = dropbox_storage.list_models()
        
        # Filter to just uploaded models
        uploaded_models = []
        for model in all_models:
            path = model.get('path', '')
            if '/uploaded/' in path and path.endswith('.mlmodel'):
                # Extract device ID from filename if possible
                name = model.get('name', '')
                device_id = 'unknown'
                
                # Try to extract device ID from name (format: model_deviceXXXX.mlmodel)
                if name.startswith('model_device') and name.endswith('.mlmodel'):
                    device_id = name[len('model_device'):-len('.mlmodel')]
                
                # Add to result
                uploaded_models.append({
                    'id': name,
                    'device_id': device_id,
                    'path': path,
                    'file_path': f"dropbox:{path}",
                    'download_url': model.get('download_url'),
                    'size': model.get('size', 0),
                    'modified_date': model.get('modified_date', '')
                })
        
        logger.info(f"Found {len(uploaded_models)} uploaded models")
        return uploaded_models
        
    except Exception as e:
        logger.error(f"Error getting uploaded models: {e}")
        return []

def generate_model_version() -> str:
    """
    Generate a new model version string.
    
    Format: 1.0.YYYYMMDD.COUNTER
    
    Returns:
        str: New version string
    """
    # Get date part
    date_part = datetime.now().strftime("%Y%m%d")
    
    # Generate version with timestamp
    timestamp = int(time.time())
    version = f"{config.MODEL_VERSION_PREFIX}{date_part}.{timestamp}"
    
    return version

def create_training_summary(trained_model_info: Dict[str, Any], 
                         prev_model_info: Dict[str, Any] = None,
                         training_data_stats: Dict[str, Any] = None,
                         incorporated_models: List[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Create a comprehensive summary of model training results.
    
    This includes:
    - Basic model metadata (version, date, etc.)
    - Performance metrics
    - Comparison with previous model
    - Details about incorporated models
    - Training data statistics
    
    Args:
        trained_model_info: Dictionary with model training info
        prev_model_info: Dictionary with previous model info (for comparison)
        training_data_stats: Statistics about the training data
        incorporated_models: Details about models incorporated into the ensemble
        
    Returns:
        Dict with JSON-serializable training summary
    """
    version = trained_model_info.get('version', 'unknown')
    current_accuracy = trained_model_info.get('accuracy', 0)
    
    # Basic model information
    summary = {
        'version': version,
        'training_date': datetime.now().isoformat(),
        'model_type': 'ensemble' if trained_model_info.get('is_ensemble', False) else 'standard',
        'performance': {
            'accuracy': current_accuracy,
            'training_data_size': trained_model_info.get('training_data_size', 0),
        },
        'classes': trained_model_info.get('classes', []),
    }
    
    # Add comparison with previous model if available
    if prev_model_info:
        prev_accuracy = prev_model_info.get('accuracy', 0)
        accuracy_change = current_accuracy - prev_accuracy
        
        summary['comparison'] = {
            'previous_version': prev_model_info.get('version', 'unknown'),
            'accuracy_change': float(f"{accuracy_change:.4f}"),
            'accuracy_change_percent': float(f"{(accuracy_change / max(prev_accuracy, 0.001)) * 100:.2f}"),
            'improvement': accuracy_change > 0,
        }
    
    # Add training data statistics if available
    if training_data_stats:
        summary['training_data'] = training_data_stats
    
    # Add information about incorporated models
    if incorporated_models:
        summary['incorporated_models'] = []
        for model in incorporated_models:
            model_info = {
                'id': model.get('id', 'unknown'),
                'device_id': model.get('device_id', 'unknown'),
                'size': model.get('size', 0),
                'weight': model.get('weight', 1.0),
            }
            if 'accuracy' in model:
                model_info['accuracy'] = model.get('accuracy', 0)
            
            summary['incorporated_models'].append(model_info)
        
        summary['incorporated_model_count'] = len(incorporated_models)
    
    # Add model architecture information if available
    if 'model_architecture' in trained_model_info:
        summary['model_architecture'] = trained_model_info.get('model_architecture')
    
    # Add key metrics that changed during training
    changes = []
    
    # Compare with previous model
    if prev_model_info:
        # Accuracy change
        if current_accuracy > prev_accuracy:
            changes.append(f"Increased accuracy from {prev_accuracy:.4f} to {current_accuracy:.4f} (+{current_accuracy - prev_accuracy:.4f})")
        elif current_accuracy < prev_accuracy:
            changes.append(f"Decreased accuracy from {prev_accuracy:.4f} to {current_accuracy:.4f} ({current_accuracy - prev_accuracy:.4f})")
        
        # Model type change
        prev_is_ensemble = prev_model_info.get('is_ensemble', False)
        current_is_ensemble = trained_model_info.get('is_ensemble', False)
        if prev_is_ensemble != current_is_ensemble:
            if current_is_ensemble:
                changes.append("Changed model type from standard to ensemble")
            else:
                changes.append("Changed model type from ensemble to standard")
        
        # Training data size change
        prev_data_size = prev_model_info.get('training_data_size', 0)
        current_data_size = trained_model_info.get('training_data_size', 0)
        if current_data_size > prev_data_size:
            changes.append(f"Increased training data from {prev_data_size} to {current_data_size} samples (+{current_data_size - prev_data_size})")
    
    # Add information about incorporated models
    if incorporated_models:
        changes.append(f"Incorporated {len(incorporated_models)} user-submitted models")
        
    # If no specific changes were detected
    if not changes:
        changes.append("Retrained model with latest data")
    
    summary['changes'] = changes
    summary['summary_text'] = f"Model {version}: " + "; ".join(changes)
    
    return summary

def save_training_summary(summary: Dict[str, Any]) -> bool:
    """
    Save training summary to Dropbox in both base_model folder and model_info folder.
    
    Args:
        summary: Dictionary with training summary
        
    Returns:
        bool: True if successfully saved
    """
    if not config.DROPBOX_ENABLED:
        logger.warning("Dropbox not enabled - cannot save training summary")
        return False
        
    try:
        from utils.dropbox_storage import get_dropbox_storage
        dropbox_storage = get_dropbox_storage()
        
        # Convert to JSON
        summary_json = json.dumps(summary, indent=2)
        buffer = io.BytesIO(summary_json.encode('utf-8'))
        
        # Save as latest summary in base_model folder
        latest_result = dropbox_storage.upload_model(
            buffer,
            "latest_model_info.json",
            config.DROPBOX_BASE_MODEL_FOLDER
        )
        
        if not latest_result.get('success'):
            logger.error(f"Failed to upload latest model info: {latest_result.get('error')}")
            return False
            
        # Also save as versioned summary in base_model folder
        buffer.seek(0)
        version = summary.get('version', 'unknown')
        versioned_result = dropbox_storage.upload_model(
            buffer,
            f"model_info_{version}.json",
            config.DROPBOX_BASE_MODEL_FOLDER
        )
        
        if not versioned_result.get('success'):
            logger.warning(f"Failed to upload versioned model info to base_model folder: {versioned_result.get('error')}")
        
        # Save to dedicated model_info folder with markdown formatting
        try:
            # Ensure model_info folder exists
            model_info_folder = "model_info"
            try:
                dropbox_storage.dbx.files_get_metadata(f"/{model_info_folder}")
            except Exception:
                try:
                    dropbox_storage.dbx.files_create_folder_v2(f"/{model_info_folder}")
                    logger.info(f"Created model_info folder in Dropbox")
                except Exception as e:
                    logger.error(f"Error creating model_info folder: {e}")
            
            # Generate a markdown report with better human readability
            md_content = generate_markdown_report(summary)
            md_buffer = io.BytesIO(md_content.encode('utf-8'))
            
            # Save markdown report to model_info folder
            model_info_result = dropbox_storage.upload_model(
                md_buffer,
                f"model_{version}_update.md",
                model_info_folder
            )
            
            if model_info_result.get('success'):
                logger.info(f"Saved detailed training report to model_info/model_{version}_update.md")
            else:
                logger.warning(f"Failed to save detailed training report: {model_info_result.get('error')}")
                
            # Also save raw JSON for programmatic access
            buffer.seek(0)
            json_result = dropbox_storage.upload_model(
                buffer,
                f"model_{version}_update.json",
                model_info_folder
            )
            
            if json_result.get('success'):
                logger.info(f"Saved JSON training data to model_info/model_{version}_update.json")
        except Exception as e:
            logger.error(f"Error saving to model_info folder: {e}")
        
        logger.info(f"Successfully saved training summary for version {version}")
        return True
        
    except Exception as e:
        logger.error(f"Error saving training summary: {e}")
        return False

def generate_markdown_report(summary: Dict[str, Any]) -> str:
    """
    Generate a human-readable markdown report from the training summary.
    
    Args:
        summary: Dictionary with training summary data
        
    Returns:
        str: Markdown formatted report
    """
    version = summary.get('version', 'unknown')
    training_date = summary.get('training_date', datetime.now().isoformat())
    
    # Try to format date nicely if possible
    try:
        date_obj = datetime.fromisoformat(training_date)
        formatted_date = date_obj.strftime("%B %d, %Y at %H:%M:%S")
    except Exception:
        formatted_date = training_date
    
    # Start building the markdown content
    md = [
        f"# Model Update Report: v{version}",
        f"**Generated:** {formatted_date}",
        "",
        "## Summary",
        ""
    ]
    
    # Add the main summary text
    summary_text = summary.get('summary_text', "Model was retrained with latest data.")
    md.append(f"{summary_text}")
    md.append("")
    
    # Add detailed changes
    changes = summary.get('changes', [])
    if changes:
        md.append("## Changes")
        md.append("")
        for change in changes:
            md.append(f"- {change}")
        md.append("")
    
    # Add performance metrics
    md.append("## Performance Metrics")
    md.append("")
    performance = summary.get('performance', {})
    md.append(f"- **Accuracy:** {performance.get('accuracy', 0):.4f}")
    md.append(f"- **Training Data Size:** {performance.get('training_data_size', 0)} samples")
    
    # Add comparison if available
    comparison = summary.get('comparison')
    if comparison:
        md.append("")
        md.append("## Comparison to Previous Model")
        md.append("")
        prev_version = comparison.get('previous_version', 'unknown')
        md.append(f"- **Previous Version:** {prev_version}")
        
        accuracy_change = comparison.get('accuracy_change', 0)
        if accuracy_change > 0:
            md.append(f"- **Accuracy Change:** +{accuracy_change:.4f} 🔼")
        elif accuracy_change < 0:
            md.append(f"- **Accuracy Change:** {accuracy_change:.4f} 🔽")
        else:
            md.append(f"- **Accuracy Change:** 0 (unchanged)")
            
        md.append(f"- **Percent Improvement:** {comparison.get('accuracy_change_percent', 0):.2f}%")
    
    # Add incorporated models info if available
    incorporated_models = summary.get('incorporated_models', [])
    if incorporated_models:
        md.append("")
        md.append("## Incorporated Models")
        md.append("")
        md.append(f"This model incorporates {len(incorporated_models)} user-submitted models:")
        md.append("")
        
        for i, model in enumerate(incorporated_models, 1):
            device_id = model.get('device_id', 'unknown')
            md.append(f"### Model {i}: Device {device_id}")
            if 'accuracy' in model:
                md.append(f"- **Accuracy:** {model.get('accuracy', 0):.4f}")
            md.append(f"- **Weight in Ensemble:** {model.get('weight', 1.0)}")
            if 'size' in model:
                size_kb = model.get('size', 0) / 1024
                md.append(f"- **Size:** {size_kb:.1f} KB")
            md.append("")
    
    # Add model architecture if available
    architecture = summary.get('model_architecture')
    if architecture:
        md.append("## Model Architecture")
        md.append("")
        md.append("```")
        md.append(json.dumps(architecture, indent=2))
        md.append("```")
    
    # Join all lines with newlines
    return "\n".join(md)