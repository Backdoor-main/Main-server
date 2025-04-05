"""
Storage Factory module for Backdoor AI Learning Server

This module provides an abstraction layer to handle different storage backends
(local, Dropbox, Google Drive) through a unified interface.
"""

import logging
import os
from typing import Dict, Any, Optional, List, Union, BinaryIO

logger = logging.getLogger(__name__)

# Import config
import config

# Storage backends
_storage_backends = {}

class StorageInterface:
    """Interface that all storage implementations must follow"""
    
    def get_db_path(self) -> str:
        """Get local path to the database file"""
        raise NotImplementedError
    
    def upload_db(self) -> bool:
        """Upload the database to remote storage"""
        raise NotImplementedError
    
    def upload_model(self, data_or_path: Union[str, bytes, BinaryIO], model_name: str) -> Dict[str, Any]:
        """Upload a model file to storage"""
        raise NotImplementedError
    
    def download_model(self, model_name: str, local_path: Optional[str] = None) -> Dict[str, Any]:
        """Download a model file from storage"""
        raise NotImplementedError
    
    def list_models(self) -> List[Dict[str, Any]]:
        """List all model files in storage"""
        raise NotImplementedError
    
    def delete_model(self, model_name: str) -> bool:
        """Delete a model file from storage"""
        raise NotImplementedError
    
    def download_model_to_memory(self, model_name: str) -> Dict[str, Any]:
        """Download a model to memory buffer"""
        raise NotImplementedError
    
    def get_model_stream(self, model_name: str) -> Dict[str, Any]:
        """Get streaming info for a model"""
        raise NotImplementedError

def initialize_storage():
    """Initialize storage backends based on configuration"""
    global _storage_backends
    
    # Import necessary modules first to avoid errors
    try:
        import tempfile
    except ImportError as e:
        logger.error(f"Failed to import required module tempfile: {e}")
        # Create a basic temporary directory function as fallback
        import random, string, os
        def mkdtemp():
            dirname = ''.join(random.choice(string.ascii_letters) for _ in range(10))
            path = os.path.join('/tmp', dirname)
            os.makedirs(path, exist_ok=True)
            return path
        tempfile = type('tempfile', (), {'mkdtemp': mkdtemp})
    
    # Initialize Dropbox storage if enabled
    dropbox_initialized = False
    if config.DROPBOX_ENABLED:
        try:
            from utils.dropbox_storage import init_dropbox_storage
            
            # Use full OAuth parameters if available
            try:
                access_token = getattr(config, 'DROPBOX_ACCESS_TOKEN', None)
                refresh_token = getattr(config, 'DROPBOX_REFRESH_TOKEN', None)
                app_key = getattr(config, 'DROPBOX_APP_KEY', None)
                app_secret = getattr(config, 'DROPBOX_APP_SECRET', None)
                
                # Check if we have placeholder values and log a warning
                if (access_token == "YOUR_ACCESS_TOKEN" and refresh_token == "YOUR_REFRESH_TOKEN") or \
                   (app_key == "YOUR_APP_KEY" or app_secret == "YOUR_APP_SECRET"):
                    logger.warning(
                        "Dropbox credentials not properly configured. "
                        "Please follow the instructions in SETUP_DROPBOX.md to set up OAuth tokens. "
                        "Using local storage instead."
                    )
                
                dropbox_storage = init_dropbox_storage(
                    api_key=config.DROPBOX_API_KEY,
                    db_filename=config.DROPBOX_DB_FILENAME,
                    models_folder_name=config.DROPBOX_MODELS_FOLDER,
                    access_token=access_token,
                    refresh_token=refresh_token,
                    app_key=app_key,
                    app_secret=app_secret
                )
            except Exception:
                # Fall back to basic initialization if OAuth params are not available
                dropbox_storage = init_dropbox_storage(
                    config.DROPBOX_API_KEY,
                    config.DROPBOX_DB_FILENAME,
                    config.DROPBOX_MODELS_FOLDER
                )
            
            # Verify we have a valid storage instance with authenticated client
            if dropbox_storage and hasattr(dropbox_storage, 'dbx') and dropbox_storage.dbx is not None:
                _storage_backends['dropbox'] = dropbox_storage
                logger.info("Dropbox storage initialized and authenticated")
                dropbox_initialized = True
            else:
                logger.warning(
                    "Dropbox storage initialization failed or authentication error. "
                    "Using local storage instead. To use Dropbox, please follow the "
                    "instructions in SETUP_DROPBOX.md."
                )
                
        except Exception as e:
            logger.error(f"Failed to initialize Dropbox storage: {e}")
    
    # Initialize Google Drive storage if enabled
    if config.GOOGLE_DRIVE_ENABLED:
        try:
            from utils.drive_storage import init_drive_storage
            drive_storage = init_drive_storage(
                config.GOOGLE_CREDENTIALS_PATH,
                config.GOOGLE_DRIVE_DB_FILENAME,
                config.GOOGLE_DRIVE_MODELS_FOLDER
            )
            _storage_backends['google_drive'] = drive_storage
            logger.info("Google Drive storage initialized")
        except Exception as e:
            logger.error(f"Failed to initialize Google Drive storage: {e}")
    
    # Always initialize local storage as fallback
    try:
        from utils.local_storage import init_local_storage
        
        # Ensure we have valid paths for local storage
        db_path = config.DB_PATH
        model_dir = config.MODEL_DIR
        
        # If we're using memory DB path, create a real file path for local storage
        if db_path.startswith("memory:"):
            try:
                temp_dir = tempfile.mkdtemp()
                db_path = os.path.join(temp_dir, "local_fallback.db")
                logger.info(f"Using temporary file for local storage fallback: {db_path}")
            except Exception as te:
                logger.error(f"Error creating temp directory: {te}")
                # Use a direct path as fallback
                db_path = "/tmp/local_fallback.db"
        
        # Initialize local storage with validated paths
        local_storage = init_local_storage(db_path, model_dir)
        _storage_backends['local'] = local_storage
        logger.info("Local storage initialized")
        
        # If Dropbox was supposed to be used but failed, update config
        if config.STORAGE_MODE == 'dropbox' and not dropbox_initialized:
            if hasattr(config, 'STORAGE_MODE'):
                config.STORAGE_MODE = 'local'
                logger.info("Updated config to use local storage mode due to Dropbox auth failure")
            
    except Exception as e:
        logger.error(f"Failed to initialize local storage: {e}")
        
        # Create an in-memory fallback as last resort
        try:
            from utils.memory_db import init_memory_db
            memory_db = init_memory_db()
            _storage_backends['memory'] = memory_db
            logger.warning("Using in-memory storage as emergency fallback")
        except Exception as me:
            logger.critical(f"Even in-memory fallback failed: {me}")

def get_storage(storage_type: Optional[str] = None) -> StorageInterface:
    """
    Get a storage backend of the specified type
    
    Args:
        storage_type: Type of storage to get ('dropbox', 'google_drive', 'local')
                     If None, uses configured default from config.STORAGE_MODE
    
    Returns:
        StorageInterface implementation
    
    Raises:
        RuntimeError: If requested storage is not available
    """
    # Initialize if not already done
    if not _storage_backends:
        initialize_storage()
    
    # Use configured default if not specified
    if storage_type is None:
        storage_type = config.STORAGE_MODE
    
    # If Dropbox is requested but not available or not authenticated, log specific helpful message
    if storage_type == 'dropbox' and (
        'dropbox' not in _storage_backends or 
        not hasattr(_storage_backends['dropbox'], 'dbx') or
        _storage_backends['dropbox'].dbx is None
    ):
        logger.warning(
            "Dropbox storage requested but not properly authenticated! "
            "To use Dropbox storage, you need to set up OAuth tokens. "
            "1. Create a Dropbox app at https://www.dropbox.com/developers/apps "
            "2. Run 'python gen_dropbox_token.py --generate' with your app key and secret "
            "3. Make sure your app has 'files.content.read' and 'files.content.write' permissions"
        )
    
    # Check if requested storage is available
    if storage_type in _storage_backends:
        storage = _storage_backends[storage_type]
        # Additional check for Dropbox to ensure valid authentication
        if storage_type == 'dropbox' and (not hasattr(storage, 'dbx') or storage.dbx is None):
            logger.warning("Dropbox storage found but client is not authenticated, falling back to local storage")
            if 'local' in _storage_backends:
                return _storage_backends['local']
        return storage
    
    # Fall back to local storage
    if 'local' in _storage_backends:
        logger.warning(f"Requested storage '{storage_type}' not available, falling back to local storage")
        return _storage_backends['local']
    
    # Memory fallback if local isn't available
    if 'memory' in _storage_backends:
        logger.warning(f"Falling back to emergency in-memory storage (data will be lost on restart)")
        return _storage_backends['memory']
    
    # If no storage is available, raise an error
    logger.critical("No storage backends available. Application will not function correctly.")
    raise RuntimeError(f"No storage backends available. Requested: {storage_type}")
