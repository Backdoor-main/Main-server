"""
Dropbox-backed temporary file utilities.

This module provides utilities for creating and managing temporary files
that are synced with Dropbox, ensuring data persistence across deployments.
"""

import io
import os
import tempfile
import uuid
import logging
from typing import Optional, Dict, Any, BinaryIO, Union

import config

logger = logging.getLogger(__name__)

class DropboxTempFile:
    """A temporary file that syncs with Dropbox storage."""
    
    def __init__(self, prefix: str = "temp", suffix: str = "", folder: str = "temp_files"):
        """
        Initialize a Dropbox-backed temporary file.
        
        Args:
            prefix: Prefix for the filename
            suffix: Suffix for the filename (e.g., ".txt", ".model")
            folder: Folder in Dropbox to store the file
        """
        self.prefix = prefix
        self.suffix = suffix
        self.folder = folder
        self.filename = f"{prefix}_{uuid.uuid4().hex}{suffix}"
        self.dropbox_path = f"{folder}/{self.filename}"
        self.buffer = io.BytesIO()
        self.closed = False
        self.uploaded = False
        self._local_temp_file = None
        
        # Initialize Dropbox if enabled
        self._init_dropbox()
    
    def _init_dropbox(self):
        """Initialize Dropbox connectivity."""
        if not hasattr(config, 'DROPBOX_ENABLED') or not config.DROPBOX_ENABLED:
            logger.warning("Dropbox not enabled - falling back to local temp file")
            self._local_temp_file = tempfile.NamedTemporaryFile(
                prefix=self.prefix, 
                suffix=self.suffix, 
                delete=False
            )
            return
            
        try:
            # Import here to avoid circular imports
            from utils.dropbox_storage import get_dropbox_storage
            self.dropbox_storage = get_dropbox_storage()
            
            # Ensure temp folder exists
            try:
                folder_path = f"/{self.folder}"
                try:
                    self.dropbox_storage.dbx.files_get_metadata(folder_path)
                except Exception:
                    # Create folder if it doesn't exist
                    logger.info(f"Creating Dropbox temp folder: {folder_path}")
                    self.dropbox_storage.dbx.files_create_folder_v2(folder_path)
            except Exception as e:
                logger.error(f"Error ensuring temp folder exists: {e}")
                # Fall back to local temp file
                self._local_temp_file = tempfile.NamedTemporaryFile(
                    prefix=self.prefix, 
                    suffix=self.suffix, 
                    delete=False
                )
                
        except Exception as e:
            logger.error(f"Error initializing Dropbox for temp file: {e}")
            # Fall back to local temp file
            self._local_temp_file = tempfile.NamedTemporaryFile(
                prefix=self.prefix, 
                suffix=self.suffix, 
                delete=False
            )
    
    def write(self, data: Union[bytes, str]) -> int:
        """
        Write data to the temporary file.
        
        Args:
            data: Data to write (bytes or string)
            
        Returns:
            int: Number of bytes written
        """
        if self.closed:
            raise ValueError("I/O operation on closed file")
            
        if isinstance(data, str):
            data = data.encode('utf-8')
            
        if self._local_temp_file:
            return self._local_temp_file.write(data)
        else:
            return self.buffer.write(data)
    
    def read(self, size: Optional[int] = None) -> bytes:
        """
        Read data from the temporary file.
        
        Args:
            size: Number of bytes to read (None for all)
            
        Returns:
            bytes: Data read from file
        """
        if self.closed:
            raise ValueError("I/O operation on closed file")
            
        if self._local_temp_file:
            return self._local_temp_file.read(size)
        else:
            if size is not None:
                return self.buffer.read(size)
            else:
                return self.buffer.read()
    
    def seek(self, offset: int, whence: int = 0) -> int:
        """
        Change stream position.
        
        Args:
            offset: Offset relative to position indicated by whence
            whence: Position reference (0=start, 1=current, 2=end)
            
        Returns:
            int: New absolute position
        """
        if self.closed:
            raise ValueError("I/O operation on closed file")
            
        if self._local_temp_file:
            return self._local_temp_file.seek(offset, whence)
        else:
            return self.buffer.seek(offset, whence)
    
    def tell(self) -> int:
        """
        Return current stream position.
        
        Returns:
            int: Current position
        """
        if self.closed:
            raise ValueError("I/O operation on closed file")
            
        if self._local_temp_file:
            return self._local_temp_file.tell()
        else:
            return self.buffer.tell()
    
    def flush(self) -> None:
        """Flush the write buffers."""
        if self.closed:
            raise ValueError("I/O operation on closed file")
            
        if self._local_temp_file:
            self._local_temp_file.flush()
        # Nothing to do for BytesIO buffer
    
    def close(self) -> None:
        """Close the file and upload to Dropbox if not already done."""
        if self.closed:
            return
            
        if self._local_temp_file:
            # First flush and close the local file
            self._local_temp_file.flush()
            self._local_temp_file.close()
            
            # Try to upload to Dropbox if it's enabled
            if hasattr(config, 'DROPBOX_ENABLED') and config.DROPBOX_ENABLED:
                try:
                    from utils.dropbox_storage import get_dropbox_storage
                    dropbox_storage = get_dropbox_storage()
                    
                    # Upload the local file to Dropbox
                    with open(self._local_temp_file.name, 'rb') as f:
                        data = f.read()
                        result = dropbox_storage.upload_model(
                            data, 
                            self.filename, 
                            self.folder
                        )
                        
                        if result and result.get('success'):
                            logger.info(f"Uploaded temp file to Dropbox: {self.dropbox_path}")
                            self.uploaded = True
                        else:
                            logger.warning(f"Failed to upload temp file to Dropbox: {result.get('error', 'Unknown error')}")
                except Exception as e:
                    logger.error(f"Error uploading temp file to Dropbox: {e}")
        else:
            # Upload the buffer to Dropbox
            try:
                if hasattr(self, 'dropbox_storage'):
                    self.buffer.seek(0)
                    result = self.dropbox_storage.upload_model(
                        self.buffer, 
                        self.filename, 
                        self.folder
                    )
                    
                    if result and result.get('success'):
                        logger.info(f"Uploaded temp file to Dropbox: {self.dropbox_path}")
                        self.uploaded = True
                    else:
                        logger.warning(f"Failed to upload temp file to Dropbox: {result.get('error', 'Unknown error')}")
            except Exception as e:
                logger.error(f"Error uploading temp file to Dropbox: {e}")
        
        self.closed = True
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
        if self._local_temp_file and os.path.exists(self._local_temp_file.name):
            try:
                os.unlink(self._local_temp_file.name)
            except Exception as e:
                logger.warning(f"Error removing temp file: {e}")
    
    @property
    def name(self) -> str:
        """Get the name of the temporary file."""
        if self._local_temp_file:
            return self._local_temp_file.name
        else:
            return self.filename
    
    def get_dropbox_url(self) -> Optional[str]:
        """
        Get a direct download URL for the Dropbox file.
        
        Returns:
            Optional[str]: URL or None if unavailable
        """
        if not self.uploaded or not hasattr(self, 'dropbox_storage'):
            return None
            
        try:
            model_info = self.dropbox_storage.get_model_stream(self.filename, folder=self.folder)
            if model_info and model_info.get('success'):
                return model_info.get('download_url')
        except Exception as e:
            logger.error(f"Error getting Dropbox URL: {e}")
        
        return None

def create_temp_file(prefix: str = "temp", suffix: str = "", folder: str = "temp_files") -> DropboxTempFile:
    """
    Create a temporary file backed by Dropbox storage.
    
    Args:
        prefix: Prefix for the filename
        suffix: Suffix for the filename
        folder: Folder in Dropbox to store the file
        
    Returns:
        DropboxTempFile: The temporary file object
    """
    return DropboxTempFile(prefix, suffix, folder)

def get_temp_file_url(filename: str, folder: str = "temp_files") -> Optional[str]:
    """
    Get a direct download URL for a temp file in Dropbox.
    
    Args:
        filename: Name of the file
        folder: Folder in Dropbox where the file is stored
        
    Returns:
        Optional[str]: URL or None if unavailable
    """
    if not hasattr(config, 'DROPBOX_ENABLED') or not config.DROPBOX_ENABLED:
        return None
        
    try:
        from utils.dropbox_storage import get_dropbox_storage
        dropbox_storage = get_dropbox_storage()
        
        model_info = dropbox_storage.get_model_stream(filename, folder=folder)
        if model_info and model_info.get('success'):
            return model_info.get('download_url')
    except Exception as e:
        logger.error(f"Error getting temp file URL: {e}")
    
    return None
