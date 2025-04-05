"""
Utilities for downloading and caching models in memory.

This module provides functions for:
- Downloading models from Dropbox directly to memory
- Caching models in memory for faster access
- Streaming models efficiently without local storage
"""

import io
import logging
import threading
from typing import Dict, Any, Optional, Union

import config

logger = logging.getLogger(__name__)

# In-memory cache for models to avoid repeated downloads
_model_cache = {}
_model_cache_lock = threading.RLock()

def get_base_model_buffer() -> Optional[io.BytesIO]:
    """
    Get the base model as an in-memory buffer from Dropbox.
    
    Returns:
        BytesIO buffer containing the model data or None if not found
    """
    # Try to get from cache first
    with _model_cache_lock:
        if '1.0.0' in _model_cache:
            # Return a copy of the cached buffer to avoid threading issues
            buffer_data = _model_cache['1.0.0'].getvalue()
            buffer = io.BytesIO(buffer_data)
            logger.info("Serving base model from memory cache")
            return buffer
    
    # Not in cache, download from Dropbox
    if config.DROPBOX_ENABLED:
        try:
            from utils.dropbox_storage import get_dropbox_storage
            dropbox_storage = get_dropbox_storage()
            
            # Ensure we're looking in the correct folder
            model_name = config.BASE_MODEL_NAME
            
            # First try using streaming download
            try:
                # Check for the stream function to get a streaming download URL
                base_model_folder = getattr(config, 'DROPBOX_BASE_MODEL_FOLDER', 'base_model')
                logger.info(f"Looking for base model in {base_model_folder} folder")
                
                # Try to get streaming URL
                stream_info = dropbox_storage.get_model_stream(model_name)
                
                if stream_info and stream_info.get('success'):
                    # Download using the URL
                    import requests
                    download_url = stream_info.get('download_url')
                    logger.info(f"Downloading base model using streaming URL")
                    
                    response = requests.get(download_url, stream=True)
                    if response.status_code == 200:
                        # Create buffer and store in cache
                        buffer = io.BytesIO()
                        for chunk in response.iter_content(chunk_size=8192):
                            buffer.write(chunk)
                        
                        # Reset buffer position
                        buffer.seek(0)
                        
                        # Cache the buffer
                        with _model_cache_lock:
                            _model_cache['1.0.0'] = io.BytesIO(buffer.getvalue())
                        
                        logger.info(f"Successfully downloaded base model using streaming")
                        return buffer
                        
                    logger.warning(f"Failed to download base model using streaming URL")
            except Exception as e:
                logger.warning(f"Error using model streaming for base model: {e}")
            
            # Fall back to direct download if streaming failed
            logger.info(f"Trying to download base model directly to memory")
            
            # First try the default folder
            result = dropbox_storage.download_model_to_memory(model_name)
            
            # If not found, try the base_model folder
            if not result or not result.get('success'):
                logger.info(f"Base model not found in default folder, trying base_model folder")
                base_model_folder = getattr(config, 'DROPBOX_BASE_MODEL_FOLDER', 'base_model')
                result = dropbox_storage.download_model_to_memory(model_name, folder=base_model_folder)
            
            if result and result.get('success'):
                # Get the buffer and cache it
                buffer = result.get('model_buffer')
                if buffer:
                    # Cache for future use
                    with _model_cache_lock:
                        _model_cache['1.0.0'] = io.BytesIO(buffer.getvalue())
                    
                    # Return a copy of the buffer
                    buffer.seek(0)
                    logger.info("Successfully loaded base model from Dropbox")
                    return buffer
            
            logger.warning(f"Failed to download base model from Dropbox: {result.get('error', 'Unknown error')}")
            return None
            
        except Exception as e:
            logger.error(f"Error downloading base model from Dropbox: {e}")
            return None
    else:
        # Dropbox not enabled, try local file as fallback
        try:
            import os
            base_model_path = os.path.join(config.MODEL_DIR, config.BASE_MODEL_NAME)
            
            if os.path.exists(base_model_path):
                with open(base_model_path, 'rb') as f:
                    buffer = io.BytesIO(f.read())
                
                # Cache for future use
                with _model_cache_lock:
                    _model_cache['1.0.0'] = io.BytesIO(buffer.getvalue())
                
                buffer.seek(0)
                logger.info("Loaded base model from local file")
                return buffer
            else:
                logger.warning(f"Base model not found at {base_model_path}")
                return None
                
        except Exception as e:
            logger.error(f"Error loading base model from local file: {e}")
            return None

def clear_model_cache():
    """
    Clear the in-memory model cache.
    
    Call this to free up memory or force a fresh download.
    """
    with _model_cache_lock:
        _model_cache.clear()
        logger.info("Model cache cleared")

def get_model_buffer(version: str) -> Optional[io.BytesIO]:
    """
    Get any model version as an in-memory buffer, with caching.
    
    Args:
        version: Model version to get
        
    Returns:
        BytesIO buffer containing the model data or None if not found
    """
    # Handle base model specially
    if version == '1.0.0':
        return get_base_model_buffer()
        
    # Try to get from cache first
    with _model_cache_lock:
        if version in _model_cache:
            # Return a copy of the cached buffer to avoid threading issues
            buffer_data = _model_cache[version].getvalue()
            buffer = io.BytesIO(buffer_data)
            logger.info(f"Serving model {version} from memory cache")
            return buffer
    
    # Not in cache, download from Dropbox
    if config.DROPBOX_ENABLED:
        try:
            from utils.dropbox_storage import get_dropbox_storage
            dropbox_storage = get_dropbox_storage()
            
            # Construct model filename
            model_name = f"model_{version}.mlmodel"
            
            # First try using streaming download
            try:
                # Try to get streaming URL
                stream_info = dropbox_storage.get_model_stream(model_name)
                
                if stream_info and stream_info.get('success'):
                    # Download using the URL
                    import requests
                    download_url = stream_info.get('download_url')
                    logger.info(f"Downloading model {model_name} using streaming URL")
                    
                    response = requests.get(download_url, stream=True)
                    if response.status_code == 200:
                        # Create buffer and store in cache
                        buffer = io.BytesIO()
                        for chunk in response.iter_content(chunk_size=8192):
                            buffer.write(chunk)
                        
                        # Reset buffer position
                        buffer.seek(0)
                        
                        # Cache for future use if it's not too large (>50MB)
                        buffer_size = len(buffer.getvalue())
                        if buffer_size < 50 * 1024 * 1024:  # 50MB limit for cache
                            with _model_cache_lock:
                                _model_cache[version] = io.BytesIO(buffer.getvalue())
                        else:
                            logger.info(f"Model {version} too large ({buffer_size/1024/1024:.1f}MB) for memory cache")
                        
                        logger.info(f"Successfully downloaded model {version} using streaming")
                        return buffer
                        
                    logger.warning(f"Failed to download model {version} using streaming URL")
            except Exception as e:
                logger.warning(f"Error using model streaming: {e}")
            
            # Fall back to direct download if streaming failed
            # Try to download directly to memory
            logger.info(f"Falling back to direct download for model {model_name}")
            result = dropbox_storage.download_model_to_memory(model_name)
            
            if result and result.get('success'):
                # Get the buffer and cache it
                buffer = result.get('model_buffer')
                if buffer:
                    # Cache for future use if it's not too large (>50MB)
                    buffer_size = len(buffer.getvalue())
                    if buffer_size < 50 * 1024 * 1024:  # 50MB limit for cache
                        with _model_cache_lock:
                            _model_cache[version] = io.BytesIO(buffer.getvalue())
                    else:
                        logger.info(f"Model {version} too large ({buffer_size/1024/1024:.1f}MB) for memory cache")
                    
                    # Return a copy of the buffer
                    buffer.seek(0)
                    logger.info(f"Successfully loaded model {version} from Dropbox")
                    return buffer
            
            logger.warning(f"Failed to download model {version} from Dropbox: {result.get('error', 'Unknown error')}")
            return None
            
        except Exception as e:
            logger.error(f"Error downloading model {version} from Dropbox: {e}")
            return None
    else:
        # Dropbox not enabled, try local file as fallback
        try:
            import os
            from utils.db_helpers import get_model_path
            
            model_path = get_model_path(config.DB_PATH, version)
            if model_path and os.path.exists(model_path):
                with open(model_path, 'rb') as f:
                    buffer = io.BytesIO(f.read())
                
                # Cache for future use if it's not too large
                buffer_size = len(buffer.getvalue())
                if buffer_size < 50 * 1024 * 1024:  # 50MB limit for cache
                    with _model_cache_lock:
                        _model_cache[version] = io.BytesIO(buffer.getvalue())
                
                buffer.seek(0)
                logger.info(f"Loaded model {version} from local file")
                return buffer
            else:
                logger.warning(f"Model {version} not found at {model_path}")
                return None
                
        except Exception as e:
            logger.error(f"Error loading model {version} from local file: {e}")
            return None
