"""
Local file system storage for Backdoor AI server.

This module provides a storage implementation using the local file system,
following the same interface as the cloud storage options.
"""

import os
import shutil
import tempfile
import time
import logging
import io
from datetime import datetime
from typing import Dict, Any, Optional, List, Union, BinaryIO

logger = logging.getLogger(__name__)

class LocalStorage:
    """Handles local file system storage operations for the Backdoor AI server."""
    
    def __init__(self, db_path: str, models_dir: str):
        """
        Initialize local file system storage.
        
        Args:
            db_path: Path to the SQLite database file
            models_dir: Directory to store model files
        """
        # Handle empty paths by using temporary directories
        if not db_path:
            temp_dir = tempfile.mkdtemp()
            self.db_path = os.path.join(temp_dir, "interactions.db")
            logger.warning(f"Empty db_path provided, using temporary file: {self.db_path}")
        else:
            self.db_path = db_path
            
        if not models_dir:
            temp_dir = tempfile.mkdtemp()
            self.models_dir = temp_dir
            logger.warning(f"Empty models_dir provided, using temporary directory: {self.models_dir}")
        else:
            self.models_dir = models_dir
        
        # Ensure directories exist
        try:
            if os.path.dirname(self.db_path):
                os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
            
            os.makedirs(self.models_dir, exist_ok=True)
            logger.info(f"Local storage initialized. DB: {self.db_path}, Models: {self.models_dir}")
        except Exception as e:
            logger.error(f"Error creating directories for local storage: {e}")
            # Create fallback temporary directories if needed
            if not os.path.exists(os.path.dirname(self.db_path)):
                temp_dir = tempfile.mkdtemp()
                self.db_path = os.path.join(temp_dir, "interactions.db")
                logger.warning(f"Using fallback temporary DB path: {self.db_path}")
            
            if not os.path.exists(self.models_dir):
                self.models_dir = tempfile.mkdtemp()
                logger.warning(f"Using fallback temporary models directory: {self.models_dir}")
    
    def get_db_path(self) -> str:
        """
        Get the path to the database file.
        
        Returns:
            str: Path to the local database file
        """
        return self.db_path
    
    def upload_db(self) -> bool:
        """
        For local storage, this is a no-op as the database is already local.
        
        Returns:
            bool: Always True for local storage
        """
        # No actual upload needed for local storage
        return True
    
    def upload_model(self, data_or_path: Union[str, bytes, BinaryIO], model_name: str) -> Dict[str, Any]:
        """
        Save a model file to local storage.
        
        Args:
            data_or_path: File path, binary data, or file-like object
            model_name: Name to save the model as
            
        Returns:
            Dict with model information
        """
        try:
            model_path = os.path.join(self.models_dir, model_name)
            
            # Handle different input types
            if isinstance(data_or_path, str):
                # It's a file path
                if os.path.exists(data_or_path):
                    shutil.copy(data_or_path, model_path)
                else:
                    return {'success': False, 'error': f'Source file not found: {data_or_path}'}
            
            elif hasattr(data_or_path, 'read'):
                # It's a file-like object
                with open(model_path, 'wb') as f:
                    # Reset position if possible
                    if hasattr(data_or_path, 'seek'):
                        data_or_path.seek(0)
                    # Copy content
                    f.write(data_or_path.read())
            
            else:
                # Assume it's binary data
                with open(model_path, 'wb') as f:
                    f.write(data_or_path)
            
            # Get file size
            file_size = os.path.getsize(model_path)
            
            return {
                'success': True,
                'name': model_name,
                'path': model_path,
                'size': file_size,
                'upload_time': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error uploading model {model_name}: {e}")
            return {'success': False, 'error': str(e)}
    
    def download_model(self, model_name: str, local_path: Optional[str] = None) -> Dict[str, Any]:
        """
        Copy a model file to a specified location.
        
        Args:
            model_name: Name of the model file
            local_path: Destination path (if None, returns the original path)
            
        Returns:
            Dict with model information
        """
        try:
            source_path = os.path.join(self.models_dir, model_name)
            
            if not os.path.exists(source_path):
                return {'success': False, 'error': f'Model not found: {model_name}'}
            
            # If local_path is not provided, just return the source path
            if local_path is None:
                return {
                    'success': True,
                    'local_path': source_path,
                    'name': model_name,
                    'size': os.path.getsize(source_path),
                    'download_time': datetime.now().isoformat()
                }
            
            # Copy the file to the requested location
            shutil.copy(source_path, local_path)
            
            return {
                'success': True,
                'local_path': local_path,
                'name': model_name,
                'size': os.path.getsize(local_path),
                'download_time': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error downloading model {model_name}: {e}")
            return {'success': False, 'error': str(e)}
    
    def list_models(self) -> List[Dict[str, Any]]:
        """
        Get a list of all model files in local storage.
        
        Returns:
            List of model information dictionaries
        """
        try:
            models = []
            
            for filename in os.listdir(self.models_dir):
                if filename.endswith('.mlmodel'):
                    file_path = os.path.join(self.models_dir, filename)
                    
                    models.append({
                        'name': filename,
                        'path': file_path,
                        'size': os.path.getsize(file_path),
                        'modified_date': datetime.fromtimestamp(os.path.getmtime(file_path)).isoformat()
                    })
            
            return models
            
        except Exception as e:
            logger.error(f"Error listing models: {e}")
            return []
    
    def delete_model(self, model_name: str) -> bool:
        """
        Delete a model file from local storage.
        
        Args:
            model_name: Name of the model file to delete
            
        Returns:
            bool: True if deletion was successful, False otherwise
        """
        try:
            file_path = os.path.join(self.models_dir, model_name)
            
            if not os.path.exists(file_path):
                logger.warning(f"Cannot delete: Model {model_name} not found")
                return False
            
            os.remove(file_path)
            logger.info(f"Deleted model {model_name} from local storage")
            return True
            
        except Exception as e:
            logger.error(f"Error deleting model {model_name}: {e}")
            return False
    
    def download_model_to_memory(self, model_name: str) -> Dict[str, Any]:
        """
        Load a model file into memory.
        
        Args:
            model_name: Name of the model file
            
        Returns:
            Dict with model buffer information
        """
        try:
            file_path = os.path.join(self.models_dir, model_name)
            
            if not os.path.exists(file_path):
                return {'success': False, 'error': f'Model not found: {model_name}'}
            
            # Read file into memory buffer
            with open(file_path, 'rb') as f:
                model_buffer = io.BytesIO(f.read())
            
            return {
                'success': True,
                'model_buffer': model_buffer,
                'name': model_name,
                'size': os.path.getsize(file_path),
                'download_time': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error loading model {model_name} to memory: {e}")
            return {'success': False, 'error': str(e)}
    
    def get_model_stream(self, model_name: str) -> Dict[str, Any]:
        """
        For local storage, direct streaming is not available.
        Uses file path instead.
        
        Args:
            model_name: Name of the model file
            
        Returns:
            Dict with model path information
        """
        try:
            file_path = os.path.join(self.models_dir, model_name)
            
            if not os.path.exists(file_path):
                return {'success': False, 'error': f'Model not found: {model_name}'}
            
            return {
                'success': True,
                'path': file_path,
                'name': model_name,
                'size': os.path.getsize(file_path),
                'local_file': True  # Indicates this is a local file, not a stream
            }
            
        except Exception as e:
            logger.error(f"Error getting model stream for {model_name}: {e}")
            return {'success': False, 'error': str(e)}

# Module-level singleton instance
_local_storage = None

def init_local_storage(db_path: str, models_dir: str):
    """
    Initialize local storage.
    
    Args:
        db_path: Path to the SQLite database file
        models_dir: Directory to store model files
        
    Returns:
        LocalStorage: The initialized storage instance
    """
    global _local_storage
    
    if _local_storage is None:
        _local_storage = LocalStorage(db_path, models_dir)
    
    return _local_storage

def get_local_storage():
    """
    Get the local storage instance.
    
    Returns:
        LocalStorage: The singleton storage instance
        
    Raises:
        RuntimeError: If local storage hasn't been initialized
    """
    if _local_storage is None:
        raise RuntimeError("Local storage not initialized. Call init_local_storage() first.")
    
    return _local_storage
