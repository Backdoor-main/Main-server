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
    
    # Initialize Dropbox storage if enabled
    if config.DROPBOX_ENABLED:
        try:
            from utils.dropbox_storage import init_dropbox_storage
            dropbox_storage = init_dropbox_storage(
                config.DROPBOX_API_KEY,
                config.DROPBOX_DB_FILENAME,
                config.DROPBOX_MODELS_FOLDER
            )
            _storage_backends['dropbox'] = dropbox_storage
            logger.info("Dropbox storage initialized")
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
        local_storage = init_local_storage(
            config.DB_PATH,
            config.MODEL_DIR
        )
        _storage_backends['local'] = local_storage
        logger.info("Local storage initialized")
    except Exception as e:
        logger.error(f"Failed to initialize local storage: {e}")

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
    
    # Check if requested storage is available
    if storage_type in _storage_backends:
        return _storage_backends[storage_type]
    
    # Fall back to local storage
    if 'local' in _storage_backends:
        logger.warning(f"Requested storage '{storage_type}' not available, falling back to local storage")
        return _storage_backends['local']
    
    # If no storage is available, raise an error
    raise RuntimeError(f"No storage backends available. Requested: {storage_type}")
