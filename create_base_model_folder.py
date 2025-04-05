#!/usr/bin/env python3
"""
Create base model folder in Dropbox and upload base model.

This script ensures the correct folder structure exists in Dropbox
and uploads the base model file to the proper location.
"""

import os
import io
import logging
import sys
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def main():
    """
    Create required folders and upload base model to Dropbox.
    
    Returns:
        int: 0 if successful, 1 if error
    """
    # Import configuration
    try:
        import config
        DROPBOX_ENABLED = getattr(config, 'DROPBOX_ENABLED', False)
        BASE_MODEL_NAME = getattr(config, 'BASE_MODEL_NAME', 'model_1.0.0.mlmodel')
        MODEL_DIR = getattr(config, 'MODEL_DIR', 'models')
        DROPBOX_BASE_MODEL_FOLDER = getattr(config, 'DROPBOX_BASE_MODEL_FOLDER', 'base_model')
        DROPBOX_MODELS_FOLDER = getattr(config, 'DROPBOX_MODELS_FOLDER', 'backdoor_models')
    except ImportError:
        logger.error("Could not import config module")
        return 1
    
    # Check if Dropbox is enabled
    if not DROPBOX_ENABLED:
        logger.error("Dropbox is not enabled in configuration")
        return 1
    
    # Get Dropbox storage
    try:
        from utils.dropbox_storage import get_dropbox_storage
        dropbox_storage = get_dropbox_storage()
    except Exception as e:
        logger.error(f"Failed to initialize Dropbox storage: {e}")
        return 1
    
    # Import Dropbox-specific classes
    try:
        import dropbox
        from dropbox.files import WriteMode
    except ImportError:
        logger.error("Could not import Dropbox module")
        return 1
    
    # Create all the required folders 
    folders_to_create = [
        DROPBOX_BASE_MODEL_FOLDER,  # base_model folder
        DROPBOX_MODELS_FOLDER,      # Main models folder
        f"{DROPBOX_MODELS_FOLDER}/trained",  # Trained models subfolder
        f"{DROPBOX_MODELS_FOLDER}/uploaded", # Uploaded models subfolder
        "nltk_data",                # NLTK resources folder
        "temp"                      # Temporary files folder
    ]
    
    for folder in folders_to_create:
        try:
            # Check if folder exists
            try:
                dropbox_storage.dbx.files_get_metadata(f"/{folder}")
                logger.info(f"Folder already exists: /{folder}")
            except Exception:
                # Create folder if it doesn't exist
                logger.info(f"Creating folder: /{folder}")
                dropbox_storage.dbx.files_create_folder(f"/{folder}")
        except Exception as e:
            logger.error(f"Error creating folder /{folder}: {e}")
    
    # Check if local base model exists
    local_model_path = os.path.join(MODEL_DIR, BASE_MODEL_NAME)
    if os.path.exists(local_model_path):
        # Upload base model to the base_model folder
        try:
            logger.info(f"Uploading base model to /{DROPBOX_BASE_MODEL_FOLDER}/{BASE_MODEL_NAME}")
            
            # Read model file
            with open(local_model_path, 'rb') as f:
                model_data = f.read()
            
            # Upload to Dropbox
            result = dropbox_storage.dbx.files_upload(
                model_data,
                f"/{DROPBOX_BASE_MODEL_FOLDER}/{BASE_MODEL_NAME}",
                mode=WriteMode.overwrite
            )
            
            logger.info(f"Successfully uploaded base model to /{DROPBOX_BASE_MODEL_FOLDER}/{BASE_MODEL_NAME}")
            
            # Update model_files map in storage
            dropbox_storage.model_files[BASE_MODEL_NAME] = f"/{DROPBOX_BASE_MODEL_FOLDER}/{BASE_MODEL_NAME}"
            
            # Create a shared link for verification
            shared_link = dropbox_storage.dbx.sharing_create_shared_link_with_settings(
                f"/{DROPBOX_BASE_MODEL_FOLDER}/{BASE_MODEL_NAME}"
            )
            download_url = shared_link.url.replace('?dl=0', '?dl=1')
            logger.info(f"Base model is now available at: {download_url}")
        except Exception as e:
            logger.error(f"Error uploading base model: {e}")
    else:
        logger.warning(f"Base model not found locally at {local_model_path}")
    
    # Initialize the database to ensure it has the correct structure
    try:
        import init_base_model_db
        init_base_model_db.init_db()
        logger.info("Database initialized with base model reference")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
    
    logger.info("Setup complete!")
    return 0

if __name__ == "__main__":
    sys.exit(main())
