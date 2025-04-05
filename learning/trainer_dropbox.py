"""
Functions for Dropbox-based model management in memory-only mode.
"""

import logging
from datetime import datetime
from typing import List, Dict, Any, Optional

import config

logger = logging.getLogger(__name__)

def clean_old_models_dropbox(keep_newest: int = config.MAX_MODELS_TO_KEEP) -> None:
    """
    Delete old model files from Dropbox to prevent storage issues
    
    Args:
        keep_newest: Number of most recent models to keep
    """
    try:
        # Get dropbox storage
        from utils.dropbox_storage import get_dropbox_storage
        dropbox_storage = get_dropbox_storage()
        
        # List all models
        model_list = dropbox_storage.list_models()
        
        # Filter to just the versioned models (not uploaded user models)
        model_files = []
        for model in model_list:
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
                        'path': model.get('path', ''),
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
            # Delete model from Dropbox
            try:
                result = dropbox_storage.delete_model(model['name'])
                if result:
                    logger.info(f"Deleted old model from Dropbox: {model['version']}")
                else:
                    logger.warning(f"Failed to delete model from Dropbox: {model['version']}")
            except Exception as e:
                logger.error(f"Error deleting model {model['version']} from Dropbox: {e}")
                
        logger.info(f"Cleaned up {len(models_to_delete)} old models, kept {keep_newest} newest")
    
    except Exception as e:
        logger.error(f"Error cleaning up old models from Dropbox: {e}")

def check_base_model_in_dropbox() -> bool:
    """
    Check if the base model exists in Dropbox.
    
    First checks in the base_model folder for model_latest.mlmodel,
    then falls back to checking in the traditional location for compatibility.
    
    Returns:
        bool: True if base model exists, False otherwise
    """
    try:
        # Get dropbox storage
        from utils.dropbox_storage import get_dropbox_storage
        dropbox_storage = get_dropbox_storage()
        
        # First check in the base_model folder
        try:
            base_model_folder = f"/{config.DROPBOX_BASE_MODEL_FOLDER}"
            latest_model_path = f"{base_model_folder}/model_latest.mlmodel"
            
            try:
                # Try to access the latest model
                dropbox_storage.dbx.files_get_metadata(latest_model_path)
                logger.info(f"Found latest base model at {latest_model_path}")
                return True
            except Exception:
                # Latest model not found, try specific version
                versioned_model_path = f"{base_model_folder}/{config.BASE_MODEL_NAME}"
                try:
                    dropbox_storage.dbx.files_get_metadata(versioned_model_path)
                    logger.info(f"Found versioned base model at {versioned_model_path}")
                    return True
                except Exception:
                    # Not found in base_model folder
                    pass
        except Exception as e:
            logger.error(f"Error checking base_model folder: {e}")
        
        # Fall back to checking traditional location
        # List all models
        model_list = dropbox_storage.list_models()
        
        # Check if base model exists in main models folder
        for model in model_list:
            if model.get('name') == config.BASE_MODEL_NAME:
                logger.info(f"Found base model {config.BASE_MODEL_NAME} in models folder")
                return True
                
        logger.warning(f"Base model not found in Dropbox (checked base_model folder and models folder)")
        return False
        
    except Exception as e:
        logger.error(f"Error checking for base model in Dropbox: {e}")
        return False

def ensure_base_model_folder() -> bool:
    """
    Ensure the base_model folder exists in Dropbox.
    
    Returns:
        bool: True if folder exists or was created
    """
    try:
        # Get dropbox storage
        from utils.dropbox_storage import get_dropbox_storage
        dropbox_storage = get_dropbox_storage()
        
        # Check if folder exists
        base_model_folder = f"/{config.DROPBOX_BASE_MODEL_FOLDER}"
        try:
            dropbox_storage.dbx.files_get_metadata(base_model_folder)
            logger.info(f"Base model folder exists: {base_model_folder}")
            return True
        except Exception:
            # Create folder if it doesn't exist
            try:
                dropbox_storage.dbx.files_create_folder_v2(base_model_folder)
                logger.info(f"Created base model folder: {base_model_folder}")
                return True
            except Exception as e:
                logger.error(f"Error creating base model folder: {e}")
                return False
                
    except Exception as e:
        logger.error(f"Error ensuring base model folder: {e}")
        return False
