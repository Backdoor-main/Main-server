"""
In-memory database utilities for Backdoor AI Learning Server.

This module provides utilities for working with SQLite in-memory databases
with Dropbox synchronization.
"""

import io
import sqlite3
import threading
import time
import logging
import os  # For checking environment variables directly
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

# Import configuration directly from environment to avoid circular imports
# We'll use the same defaults as in config.py
DROPBOX_ENABLED = os.getenv("DROPBOX_ENABLED", "True").lower() in ["true", "1", "yes"]
DROPBOX_DB_SYNC_INTERVAL = int(os.getenv("DROPBOX_DB_SYNC_INTERVAL", "60"))  # Seconds

# Log the configuration we're using
logger.info(f"Memory DB using DROPBOX_ENABLED={DROPBOX_ENABLED}")
logger.info(f"Memory DB using DROPBOX_DB_SYNC_INTERVAL={DROPBOX_DB_SYNC_INTERVAL}s")

# Global in-memory database connection
_in_memory_db = None
_in_memory_db_lock = threading.RLock()
_last_db_sync_time = 0

def init_memory_db() -> sqlite3.Connection:
    """
    Initialize the in-memory database and load from Dropbox if available.
    
    Returns:
        sqlite3.Connection: Connection to the in-memory database
    """
    global _in_memory_db, _last_db_sync_time
    
    with _in_memory_db_lock:
        if _in_memory_db is not None:
            logger.info("Returning existing in-memory database connection")
            return _in_memory_db
        
        logger.info("Creating new in-memory database")
        _in_memory_db = sqlite3.connect(':memory:', check_same_thread=False)
        
        # If Dropbox is enabled, try to load data from Dropbox
        if DROPBOX_ENABLED:
            try:
                # Delayed import to avoid circular import issues
                from utils.dropbox_storage import get_dropbox_storage
                
                try:
                    logger.info("Getting Dropbox storage instance")
                    dropbox_storage = get_dropbox_storage()
                    
                    logger.info("Downloading database from Dropbox to memory")
                    db_data = dropbox_storage.download_db_to_memory()
                    
                    if db_data and db_data.get('success'):
                        # Load database from buffer
                        buffer = db_data.get('db_buffer')
                        if buffer:
                            try:
                                # Import the SQL dump into memory - handle possible binary data
                                buffer.seek(0)
                                try:
                                    # First try UTF-8 decoding
                                    script = buffer.read().decode('utf-8')
                                    _in_memory_db.executescript(script)
                                    logger.info("Successfully loaded database from Dropbox into memory")
                                    _last_db_sync_time = time.time()
                                except UnicodeDecodeError:
                                    # If UTF-8 fails, try to handle as binary SQLite file
                                    buffer.seek(0)
                                    try:
                                        # Create a temporary file to store the binary data
                                        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
                                            temp_file.write(buffer.read())
                                            temp_path = temp_file.name
                                    
                                        # Use a try-except block to handle potential errors in the backup process
                                        try:
                                            # Use the sqlite backup API to copy from the file to in-memory DB
                                            temp_conn = sqlite3.connect(temp_path)
                                            # Verify both connections are valid
                                            if temp_conn and _in_memory_db:
                                                temp_conn.backup(_in_memory_db)
                                                temp_conn.close()
                                            else:
                                                logger.error("One of the database connections is None")
                                        except Exception as backup_error:
                                            logger.error(f"Error backing up database: {backup_error}")
                                
                                        # Make sure we always clean up the temporary file
                                        try:
                                            # Remove the temporary file
                                            if os.path.exists(temp_path):
                                                os.unlink(temp_path)
                                        except Exception as cleanup_error:
                                            logger.warning(f"Error cleaning up temp file: {cleanup_error}")
                                    
                                        logger.info("Successfully loaded binary database from Dropbox into memory")
                                        _last_db_sync_time = time.time()
                                    except Exception as binary_error:
                                        logger.error(f"Error loading binary database: {binary_error}")
                                        logger.info("Starting with fresh in-memory database")
                            except Exception as script_error:
                                logger.error(f"Error executing SQL script from Dropbox: {script_error}")
                                logger.info("Starting with fresh in-memory database")
                        else:
                            logger.warning("Downloaded database buffer from Dropbox was empty")
                    else:
                        error_msg = db_data.get('error', 'Unknown error') if db_data else 'No data returned'
                        logger.info(f"No existing database found in Dropbox ({error_msg}), starting with fresh database")
                except Exception as e:
                    logger.error(f"Error interacting with Dropbox storage: {e}")
                    logger.info("Starting with fresh in-memory database")
            except ImportError:
                logger.error("Could not import Dropbox storage module - check your installation")
                logger.info("Starting with fresh in-memory database")
            except Exception as e:
                logger.error(f"Unexpected error during Dropbox database initialization: {e}")
                logger.info("Starting with fresh in-memory database")
        else:
            logger.info("Dropbox storage disabled, using fresh in-memory database")
        
        return _in_memory_db

def sync_memory_db_to_dropbox() -> bool:
    """
    Sync the in-memory database to Dropbox.
    
    Returns:
        bool: True if sync was successful, False otherwise
    """
    global _last_db_sync_time
    
    if not DROPBOX_ENABLED:
        logger.debug("Dropbox sync skipped - Dropbox is disabled")
        return False
        
    if _in_memory_db is None:
        logger.warning("Cannot sync to Dropbox - in-memory database not initialized")
        return False
    
    # Only sync if enough time has passed since last sync
    current_time = time.time()
    if current_time - _last_db_sync_time < DROPBOX_DB_SYNC_INTERVAL:
        logger.debug(f"Dropbox sync skipped - synced recently ({current_time - _last_db_sync_time}s ago)")
        return False
    
    try:
        # Dump the database to a buffer
        logger.info("Preparing in-memory database for Dropbox sync")
        buffer = io.BytesIO()
        for line in _in_memory_db.iterdump():
            buffer.write(f"{line}\n".encode('utf-8'))
        
        # Upload to Dropbox
        try:
            # Delayed import to avoid circular imports
            from utils.dropbox_storage import get_dropbox_storage
            
            logger.info("Getting Dropbox storage for database sync")
            dropbox_storage = get_dropbox_storage()
            
            logger.info("Uploading database to Dropbox")
            result = dropbox_storage.upload_db_from_memory(buffer)
            
            if result and result.get('success'):
                logger.info("Successfully synced in-memory database to Dropbox")
                _last_db_sync_time = current_time
                return True
            else:
                error_msg = result.get('error', 'Unknown error') if result else 'No result returned'
                logger.error(f"Failed to sync database to Dropbox: {error_msg}")
                return False
        except ImportError as ie:
            logger.error(f"Could not import Dropbox storage for sync: {ie}")
            return False
        except Exception as e:
            logger.error(f"Error during Dropbox upload: {e}")
            return False
    except Exception as e:
        logger.error(f"Error preparing database for Dropbox sync: {e}")
        return False

def get_memory_db() -> sqlite3.Connection:
    """
    Get the global in-memory database connection.
    
    Returns:
        sqlite3.Connection: Connection to the in-memory database
    """
    if _in_memory_db is None:
        return init_memory_db()
    return _in_memory_db

def create_memory_db_copy() -> sqlite3.Connection:
    """
    Create a new in-memory database with a copy of the data from the global database.
    
    This is useful for creating isolated connections for thread safety.
    
    Returns:
        sqlite3.Connection: New connection to a copy of the database
    """
    if _in_memory_db is None:
        init_memory_db()
    
    with _in_memory_db_lock:
        # Create a new in-memory database
        new_db = sqlite3.connect(':memory:')
        
        # Copy the schema and data from the global database
        _in_memory_db.backup(new_db)
        
        return new_db

def commit_memory_db_copy(conn: sqlite3.Connection) -> bool:
    """
    Commit changes from a database copy back to the global database.
    
    Args:
        conn: Connection to a database copy
        
    Returns:
        bool: True if commit was successful
    """
    if _in_memory_db is None or conn is None:
        return False
    
    with _in_memory_db_lock:
        # Backup from the copy to the global database
        conn.backup(_in_memory_db)
        
        # Sync to Dropbox if needed
        sync_memory_db_to_dropbox()
        
        return True

def close_memory_db_copy(conn: sqlite3.Connection) -> None:
    """
    Close a database copy connection.
    
    Args:
        conn: Connection to close
    """
    if conn is not None:
        conn.close()
