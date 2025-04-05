"""
Model streaming utilities for Backdoor AI.

This module provides functionality to:
- Stream models directly from Dropbox without loading into memory
- Provide minimal memory footprint for model inference
- Cache model metadata for efficient access
"""

import io
import os
import logging
import tempfile
import requests
import threading
from typing import Dict, Any, Optional, Union, BinaryIO, Tuple
import time

try:
    import config
    DROPBOX_ENABLED = getattr(config, 'DROPBOX_ENABLED', False)
    BASE_MODEL_NAME = getattr(config, 'BASE_MODEL_NAME', 'model_1.0.0.mlmodel')
    DROPBOX_BASE_FOLDER = getattr(config, 'DROPBOX_BASE_MODEL_FOLDER', 'base_model')
except ImportError:
    DROPBOX_ENABLED = False
    BASE_MODEL_NAME = 'model_1.0.0.mlmodel'
    DROPBOX_BASE_FOLDER = 'base_model'

logger = logging.getLogger(__name__)

# Cache for model URLs and metadata to avoid repeated lookups
_model_info_cache = {}
_model_info_timestamps = {}
_cache_lock = threading.RLock()
_CACHE_TTL = 3600  # 1 hour

class StreamingModelFile:
    """
    A file-like object that streams model data directly from Dropbox.
    
    This avoids loading the entire model into memory at once, 
    significantly reducing memory usage.
    """
    
    def __init__(self, url, chunk_size=1024*1024):
        """
        Initialize with the URL to stream from.
        
        Args:
            url: The direct download URL
            chunk_size: Size of chunks to download at once
        """
        self.url = url
        self.chunk_size = chunk_size
        self.position = 0
        self.buffer = io.BytesIO()
        self.buffer_start = 0
        self.buffer_end = 0
        self.content_length = None
        self.closed = False
        self._session = requests.Session()
        
        # Get content length
        try:
            response = self._session.head(self.url)
            self.content_length = int(response.headers.get('content-length', 0))
            logger.info(f"Model size: {self.content_length / 1024 / 1024:.2f} MB")
        except Exception as e:
            logger.warning(f"Could not determine content length: {e}")
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
    
    def close(self):
        """Close the file-like object and release resources."""
        if not self.closed:
            self.buffer.close()
            self._session.close()
            self.closed = True
    
    def read(self, size=-1):
        """
        Read up to size bytes from the object and return them.
        
        Args:
            size: Number of bytes to read. If negative, read until EOF.
            
        Returns:
            Bytes read from the file
        """
        if self.closed:
            raise ValueError("I/O operation on closed file")
            
        if size < 0:
            # Read until the end
            chunks = []
            chunk = self._read_chunk(self.chunk_size)
            while chunk:
                chunks.append(chunk)
                chunk = self._read_chunk(self.chunk_size)
            return b''.join(chunks)
        elif size == 0:
            return b''
        else:
            return self._read_chunk(size)
    
    def _read_chunk(self, size):
        """
        Read a chunk of data from the remote file.
        
        Args:
            size: Number of bytes to read
            
        Returns:
            Bytes read from the file
        """
        # If we have enough data in the buffer, return it
        if self.position >= self.buffer_start and self.position + size <= self.buffer_end:
            self.buffer.seek(self.position - self.buffer_start)
            data = self.buffer.read(size)
            self.position += len(data)
            return data
            
        # Otherwise, fetch a new chunk
        headers = {'Range': f'bytes={self.position}-{self.position + size - 1}'}
        try:
            response = self._session.get(self.url, headers=headers, stream=True)
            if response.status_code in (200, 206):  # OK or Partial Content
                data = response.content
                self.position += len(data)
                
                # Update buffer
                self.buffer = io.BytesIO(data)
                self.buffer_start = self.position - len(data)
                self.buffer_end = self.position
                
                return data
            else:
                logger.error(f"Failed to read from URL: {response.status_code}")
                return b''
        except Exception as e:
            logger.error(f"Error reading from URL: {e}")
            return b''
    
    def seek(self, offset, whence=0):
        """
        Change the stream position to the given offset.
        
        Args:
            offset: Offset relative to position indicated by whence
            whence: 0 = absolute, 1 = relative to current, 2 = relative to end
            
        Returns:
            The new position
        """
        if self.closed:
            raise ValueError("I/O operation on closed file")
            
        if whence == 0:  # absolute
            self.position = offset
        elif whence == 1:  # relative
            self.position += offset
        elif whence == 2:  # relative to end
            if self.content_length is not None:
                self.position = self.content_length + offset
            else:
                raise ValueError("Cannot seek from end - content length unknown")
        else:
            raise ValueError("Invalid whence value")
            
        return self.position
    
    def tell(self):
        """
        Return the current stream position.
        
        Returns:
            Current position
        """
        if self.closed:
            raise ValueError("I/O operation from closed file")
        return self.position

def get_model_info(model_name: str) -> Dict[str, Any]:
    """
    Get model information including streaming URL.
    
    Args:
        model_name: Name of the model file
        
    Returns:
        Dict with model information or None if not found
    """
    # Check cache first
    with _cache_lock:
        if model_name in _model_info_cache:
            # Check if cache is still valid
            timestamp = _model_info_timestamps.get(model_name, 0)
            if time.time() - timestamp < _CACHE_TTL:
                logger.info(f"Using cached model info for {model_name}")
                return _model_info_cache[model_name]
    
    # Not in cache or expired, get from Dropbox
    if not DROPBOX_ENABLED:
        logger.warning("Dropbox is not enabled, cannot get model info")
        return None
        
    try:
        from utils.dropbox_storage import get_dropbox_storage
        dropbox_storage = get_dropbox_storage()
        
        # First check in the base model folder if it's the base model
        if model_name == BASE_MODEL_NAME:
            base_model_folder = getattr(config, 'DROPBOX_BASE_MODEL_FOLDER', 'base_model')
            logger.info(f"Looking for base model in {base_model_folder} folder")
            result = dropbox_storage.get_model_stream(model_name, folder=base_model_folder)
            
            if result and result.get('success'):
                # Cache the result
                with _cache_lock:
                    _model_info_cache[model_name] = result
                    _model_info_timestamps[model_name] = time.time()
                return result
        
        # Try in the regular models folder
        result = dropbox_storage.get_model_stream(model_name)
        
        if result and result.get('success'):
            # Cache the result
            with _cache_lock:
                _model_info_cache[model_name] = result
                _model_info_timestamps[model_name] = time.time()
            return result
            
        logger.warning(f"Could not find model {model_name} in Dropbox")
        return None
        
    except Exception as e:
        logger.error(f"Error getting model info: {e}")
        return None

def get_model_stream(model_name: str) -> Optional[StreamingModelFile]:
    """
    Get a streaming file-like object for the model.
    
    This allows reading the model file without loading it entirely into memory.
    
    Args:
        model_name: Name of the model file
        
    Returns:
        StreamingModelFile object or None if not found
    """
    # Get model info with streaming URL
    model_info = get_model_info(model_name)
    
    if not model_info or not model_info.get('success'):
        logger.error(f"Failed to get model info for {model_name}")
        return None
        
    # Create streaming file object
    try:
        download_url = model_info.get('download_url')
        if not download_url:
            logger.error(f"No download URL for model {model_name}")
            return None
            
        logger.info(f"Creating streaming file for {model_name} - this will use minimal memory")
        return StreamingModelFile(download_url)
        
    except Exception as e:
        logger.error(f"Error creating streaming model file: {e}")
        return None

def get_base_model_stream() -> Optional[StreamingModelFile]:
    """
    Get a streaming file-like object for the base model.
    
    Returns:
        StreamingModelFile object or None if not found
    """
    logger.info(f"Getting streaming object for base model: {BASE_MODEL_NAME}")
    return get_model_stream(BASE_MODEL_NAME)

def clear_cache():
    """Clear the model info cache."""
    with _cache_lock:
        _model_info_cache.clear()
        _model_info_timestamps.clear()
    logger.info("Model info cache cleared")
