"""
NLTK integration with Dropbox for Backdoor AI server.

This module provides functionality to:
- Download and manage NLTK resources from Dropbox
- Provide a custom resource provider for NLTK that uses Dropbox
"""

import os
import io
import zipfile
import logging
import tempfile
import nltk
from nltk.data import find
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)

class DropboxResourceProvider:
    """Custom resource provider for NLTK that uses Dropbox storage."""
    
    def __init__(self, dropbox_storage=None, nltk_folder="nltk_data"):
        """
        Initialize the Dropbox resource provider.
        
        Args:
            dropbox_storage: Instance of DropboxStorage
            nltk_folder: Folder name in Dropbox for NLTK resources
        """
        self.dropbox_storage = dropbox_storage
        self.nltk_folder = nltk_folder
        self.temp_dir = tempfile.gettempdir()
        
        # Resource cache to avoid repeated downloads
        self.resource_cache = {}
        
        # Import inside function to avoid circular imports
        if dropbox_storage is None:
            try:
                from utils.dropbox_storage import get_dropbox_storage
                self.dropbox_storage = get_dropbox_storage()
                logger.info("Initialized DropboxResourceProvider with existing Dropbox storage")
            except Exception as e:
                logger.error(f"Could not get Dropbox storage: {e}")
                self.dropbox_storage = None
    
    def find(self, resource_name: str) -> Optional[str]:
        """
        Find a resource in Dropbox.
        
        Args:
            resource_name: Name of the resource to find
            
        Returns:
            BytesIO buffer containing the resource data, or None if not found
        """
        # If we've already cached this resource, return the cached resource
        if resource_name in self.resource_cache:
            logger.debug(f"Found cached NLTK resource: {resource_name}")
            return self.resource_cache[resource_name]
        
        # Check if we have a valid Dropbox storage
        if not self.dropbox_storage:
            logger.warning("Cannot find resource - no Dropbox storage available")
            return None
        
        logger.info(f"Searching for NLTK resource in Dropbox: {resource_name}")
        
        # Construct path for resource in Dropbox
        resource_path = f"{self.nltk_folder}/{resource_name}"
        
        try:
            # Get streaming URL for the resource
            try:
                # Try to get a streaming URL first
                stream_info = self.dropbox_storage.get_model_stream(
                    resource_name,
                    folder=self.nltk_folder
                )
                
                if stream_info and stream_info.get('success'):
                    # Create an in-memory representation of the resource
                    # This is a virtual path that NLTK will recognize
                    import io
                    
                    # Create a unique identifier for this resource
                    resource_id = f"memory:{resource_name}"
                    
                    # Store the URL and other information in our cache
                    self.resource_cache[resource_name] = {
                        'type': 'stream',
                        'url': stream_info.get('download_url'),
                        'id': resource_id
                    }
                    
                    # Register a custom loader for this resource with NLTK
                    from nltk.data import CustomLoader
                    
                    class DropboxStreamLoader(CustomLoader):
                        def load(self, resource_url):
                            import requests
                            # Stream resource directly from Dropbox
                            response = requests.get(stream_info.get('download_url'))
                            if response.status_code == 200:
                                return io.BytesIO(response.content)
                            return None
                    
                    # Register our custom loader with NLTK
                    nltk.data.path.append(resource_id)
                    
                    logger.info(f"Registered streaming resource for NLTK: {resource_name}")
                    return resource_id
            except Exception as stream_error:
                logger.warning(f"Error setting up streaming for {resource_name}: {stream_error}")
            
            # Fall back to direct download to memory if streaming fails
            result = self.dropbox_storage.download_model_to_memory(
                resource_name, 
                folder=self.nltk_folder
            )
            
            if result and result.get('success'):
                # Get the buffer
                buffer = result.get('model_buffer')
                
                # Create an in-memory resource
                import io
                
                # Generate a unique identifier for this resource
                resource_id = f"memory:{resource_name}"
                
                # Store the buffer in cache
                self.resource_cache[resource_name] = {
                    'type': 'buffer',
                    'data': buffer,
                    'id': resource_id
                }
                
                logger.info(f"Downloaded NLTK resource from Dropbox: {resource_name}")
                return resource_id
                
            logger.warning(f"NLTK resource not found in Dropbox: {resource_name}")
            return None
            
        except Exception as e:
            logger.error(f"Error finding NLTK resource {resource_name}: {e}")
            return None
    
    def upload_resource(self, resource_path: str, resource_name: str) -> bool:
        """
        Upload an NLTK resource to Dropbox.
        
        Args:
            resource_path: Local path to the resource
            resource_name: Name to use in Dropbox
            
        Returns:
            bool: True if upload was successful, False otherwise
        """
        if not self.dropbox_storage:
            logger.warning("Cannot upload resource - no Dropbox storage available")
            return False
            
        logger.info(f"Uploading NLTK resource to Dropbox: {resource_name}")
        
        try:
            # Upload resource
            result = self.dropbox_storage.upload_model(
                resource_path, 
                resource_name, 
                folder=self.nltk_folder
            )
            
            if result and result.get('success'):
                logger.info(f"Uploaded NLTK resource to Dropbox: {resource_name}")
                return True
                
            logger.error(f"Failed to upload NLTK resource: {result.get('error', 'Unknown error')}")
            return False
            
        except Exception as e:
            logger.error(f"Error uploading NLTK resource {resource_name}: {e}")
            return False

def init_nltk_dropbox_resources(resources: List[str]) -> bool:
    """
    Initialize NLTK resources for use with Dropbox.
    
    This creates a custom resource provider that uses Dropbox for storage.
    
    Args:
        resources: List of NLTK resource names to ensure are available
        
    Returns:
        bool: True if initialization was successful, False otherwise
    """
    try:
        # Import inside function to avoid circular imports
        from utils.dropbox_storage import get_dropbox_storage
        
        # Get Dropbox storage instance
        dropbox_storage = get_dropbox_storage()
        
        # Create resource provider
        provider = DropboxResourceProvider(dropbox_storage)
        
        # Register custom finder with NLTK
        nltk.data.finder._resource_providers.append(provider)
        
        logger.info("Registered Dropbox resource provider with NLTK")
        
        # Ensure each resource is available
        for resource in resources:
            logger.info(f"Ensuring NLTK resource is available: {resource}")
            try:
                # Try to download the resource - this will use our custom provider if available
                nltk.download(resource, quiet=True)
            except Exception as e:
                logger.error(f"Failed to download NLTK resource {resource}: {e}")
        
        return True
        
    except Exception as e:
        logger.error(f"Failed to initialize NLTK resources with Dropbox: {e}")
        return False
