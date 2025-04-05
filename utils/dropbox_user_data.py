"""
User data storage utilities for Dropbox integration.

This module provides functions for storing and retrieving user interaction
data in Dropbox, ensuring all user data is preserved across deployments.
"""

import io
import json
import logging
import os
import time
from datetime import datetime
from typing import Dict, List, Any, Optional

import dropbox
import config

logger = logging.getLogger(__name__)

def ensure_user_data_folder() -> bool:
    """
    Ensure the user_data folder exists in Dropbox.
    
    Returns:
        bool: True if folder exists or was created
    """
    if not config.DROPBOX_ENABLED:
        logger.warning("Dropbox not enabled - cannot ensure user_data folder")
        return False
        
    try:
        from utils.dropbox_storage import get_dropbox_storage
        dropbox_storage = get_dropbox_storage()
        
        # Check if folder exists
        user_data_folder = "user_data"
        try:
            dropbox_storage.dbx.files_get_metadata(f"/{user_data_folder}")
            logger.info(f"User data folder exists: /{user_data_folder}")
            return True
        except Exception:
            # Create folder if it doesn't exist
            try:
                dropbox_storage.dbx.files_create_folder_v2(f"/{user_data_folder}")
                logger.info(f"Created user data folder: /{user_data_folder}")
                return True
            except Exception as e:
                logger.error(f"Error creating user data folder: {e}")
                return False
                
    except Exception as e:
        logger.error(f"Error ensuring user data folder: {e}")
        return False

def store_interactions_to_dropbox(data: Dict[str, Any]) -> bool:
    """
    Store interaction data from devices to Dropbox user_data folder.
    
    Args:
        data: Dictionary containing device info and interactions
        
    Returns:
        bool: True if successfully stored
    """
    if not config.DROPBOX_ENABLED:
        logger.warning("Dropbox not enabled - cannot store user data")
        return False
        
    try:
        # Ensure user_data folder exists
        if not ensure_user_data_folder():
            logger.error("Failed to ensure user_data folder exists")
            return False
            
        from utils.dropbox_storage import get_dropbox_storage
        dropbox_storage = get_dropbox_storage()
        
        # Extract device ID from data
        device_id = data.get('deviceId', 'unknown')
        
        # Create a folder for this device if needed
        device_folder = f"user_data/{device_id}"
        try:
            try:
                dropbox_storage.dbx.files_get_metadata(f"/{device_folder}")
            except Exception:
                try:
                    dropbox_storage.dbx.files_create_folder_v2(f"/{device_folder}")
                    logger.info(f"Created device folder: /{device_folder}")
                except Exception as e:
                    logger.error(f"Error creating device folder {device_folder}: {e}")
                    # Continue anyway - we'll use the main user_data folder
                    device_folder = "user_data"
        except Exception as e:
            logger.error(f"Error checking/creating device folder: {e}")
            # Fallback to main user_data folder
            device_folder = "user_data"
            
        # Generate a unique filename based on timestamp
        timestamp = int(time.time())
        filename = f"interactions_{device_id}_{timestamp}.json"
        
        # Add metadata to help with analysis
        enriched_data = data.copy()
        enriched_data['_meta'] = {
            'stored_date': datetime.now().isoformat(),
            'source': 'api_upload',
            'storage_version': '1.0'
        }
        
        # Convert to JSON and save
        json_data = json.dumps(enriched_data, indent=2)
        buffer = io.BytesIO(json_data.encode('utf-8'))
        
        # Upload to Dropbox
        dropbox_path = f"/{device_folder}/{filename}"
        upload_result = dropbox_storage.dbx.files_upload(
            buffer.getvalue(), 
            dropbox_path, 
            mode=dropbox.files.WriteMode.overwrite
        )
        
        logger.info(f"Stored interactions to Dropbox: {dropbox_path}")
        return True
        
    except Exception as e:
        logger.error(f"Error storing interactions to Dropbox: {e}")
        return False

def list_user_data_files() -> List[Dict[str, Any]]:
    """
    List all user data files in the user_data folder.
    
    Returns:
        List of dictionaries with file information
    """
    if not config.DROPBOX_ENABLED:
        logger.warning("Dropbox not enabled - cannot list user data")
        return []
        
    try:
        from utils.dropbox_storage import get_dropbox_storage
        dropbox_storage = get_dropbox_storage()
        
        # Ensure user_data folder exists
        ensure_user_data_folder()
        
        user_data_files = []
        
        # List files in user_data folder
        try:
            result = dropbox_storage.dbx.files_list_folder("/user_data", recursive=True)
            
            # Process files
            for entry in result.entries:
                if isinstance(entry, dropbox.files.FileMetadata) and entry.path_lower.endswith('.json'):
                    user_data_files.append({
                        'path': entry.path_display,
                        'name': entry.name,
                        'size': entry.size,
                        'modified': entry.server_modified.isoformat()
                    })
                    
            # Continue listing if there are more files
            while result.has_more:
                result = dropbox_storage.dbx.files_list_folder_continue(result.cursor)
                for entry in result.entries:
                    if isinstance(entry, dropbox.files.FileMetadata) and entry.path_lower.endswith('.json'):
                        user_data_files.append({
                            'path': entry.path_display,
                            'name': entry.name,
                            'size': entry.size,
                            'modified': entry.server_modified.isoformat()
                        })
                        
        except Exception as e:
            logger.error(f"Error listing user data files: {e}")
            
        logger.info(f"Found {len(user_data_files)} user data files in Dropbox")
        return user_data_files
        
    except Exception as e:
        logger.error(f"Error listing user data files: {e}")
        return []

def load_user_data_for_training() -> List[Dict[str, Any]]:
    """
    Load all user data files for training.
    
    Returns:
        List of interaction dictionaries
    """
    if not config.DROPBOX_ENABLED:
        logger.warning("Dropbox not enabled - cannot load user data")
        return []
        
    try:
        from utils.dropbox_storage import get_dropbox_storage
        dropbox_storage = get_dropbox_storage()
        
        # Get list of user data files
        user_data_files = list_user_data_files()
        
        # Load all interaction data
        all_interactions = []
        
        for file_info in user_data_files:
            try:
                # Download file
                result = dropbox_storage.dbx.files_download(file_info['path'])
                
                # Parse JSON
                content = result[1].content
                data = json.loads(content.decode('utf-8'))
                
                # Extract interactions
                if 'interactions' in data:
                    all_interactions.extend(data['interactions'])
                    
            except Exception as e:
                logger.error(f"Error loading user data file {file_info['path']}: {e}")
                
        logger.info(f"Loaded {len(all_interactions)} interactions from user data files")
        return all_interactions
        
    except Exception as e:
        logger.error(f"Error loading user data for training: {e}")
        return []
