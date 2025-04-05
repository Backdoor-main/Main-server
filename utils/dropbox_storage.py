"""
Dropbox integration for Backdoor AI server.

This module provides functionality to:
- Store and retrieve SQLite database files on Dropbox
- Upload and download ML model files
- Handle authentication and synchronization
"""

import os
import io
import tempfile
import time
import threading
import logging
import json
import dropbox
from dropbox.exceptions import ApiError, AuthError
from dropbox.files import WriteMode
from datetime import datetime
from typing import Dict, Any, Optional, List, Tuple

logger = logging.getLogger(__name__)

class DropboxStorage:
    """Handles Dropbox storage operations for the Backdoor AI server."""
    
    def __init__(self, access_token: str = None, refresh_token: str = None, 
                 app_key: str = None, app_secret: str = None,
                 db_filename: str = "interactions.db", 
                 models_folder_name: str = "backdoor_models"):
        """
        Initialize Dropbox storage with OAuth2 support.
        
        Args:
            access_token: OAuth2 access token for Dropbox API
            refresh_token: OAuth2 refresh token to get new access tokens
            app_key: Dropbox app key for OAuth2 flow
            app_secret: Dropbox app secret for OAuth2 flow
            db_filename: Name of the database file in Dropbox
            models_folder_name: Name of the folder to store models in
        """
        # OAuth credentials
        self.access_token = access_token
        self.refresh_token = refresh_token
        self.app_key = app_key
        self.app_secret = app_secret
        
        # Storage settings
        self.db_filename = db_filename
        self.models_folder_name = models_folder_name
        
        # Authentication state
        self.auth_retries = 0
        self.max_retries = 3  # Default, can be overridden from config
        self.retry_delay = 5  # seconds between retries
        self.last_token_refresh = 0
        
        # File tracking
        self.model_files = {}  # Mapping of model names to paths
        
        # Local storage paths
        self.temp_dir = tempfile.gettempdir()
        self.local_db_path = os.path.join(self.temp_dir, db_filename)
        
        # Sync state
        self.last_db_sync = 0
        self.last_models_sync = 0
        self.db_sync_interval = 60  # Seconds
        self.models_sync_interval = 300  # Seconds
        
        # Thread safety
        self.lock = threading.RLock()
        self.auth_lock = threading.RLock()
        
        # Configure authentication retry settings from config if available
        try:
            import config
            if hasattr(config, 'DROPBOX_MAX_RETRIES'):
                self.max_retries = config.DROPBOX_MAX_RETRIES
            if hasattr(config, 'DROPBOX_RETRY_DELAY'):
                self.retry_delay = config.DROPBOX_RETRY_DELAY
        except ImportError:
            pass
        
        # Connect to Dropbox with authentication and retry logic
        self.dbx = self._authenticate()
        
        # Initialize resources
        if self.dbx:
            self._initialize()
        
    def _authenticate(self) -> Optional[dropbox.Dropbox]:
        """
        Authenticate with Dropbox using OAuth2 with refresh token support.
        
        Returns:
            dropbox.Dropbox: Authenticated Dropbox instance or None if authentication fails
        """
        with self.auth_lock:
            # Check if we should try a refresh first
            if self.access_token and self.refresh_token and self.app_key and self.app_secret:
                return self._authenticate_with_refresh()
            elif self.access_token:
                return self._authenticate_with_token()
            else:
                logger.error("No authentication credentials available for Dropbox")
                return None
                
    def _authenticate_with_token(self) -> Optional[dropbox.Dropbox]:
        """
        Authenticate with just an access token (legacy mode).
        
        Returns:
            dropbox.Dropbox: Authenticated instance or None
        """
        try:
            # Use the centralized token manager for authentication
            try:
                # Import the token manager
                from utils.token_manager import get_token_manager
                
                # Get the token manager instance
                token_manager = get_token_manager()
                
                # Get a valid access token (refreshes automatically if needed)
                valid_token = token_manager.get_valid_access_token()
                
                if valid_token:
                    # Update our local access token
                    self.access_token = valid_token
                    logger.info("Retrieved valid access token from token manager")
                else:
                    logger.warning("Token manager could not provide a valid access token")
                    
            except ImportError:
                logger.warning("Could not import token manager, falling back to local tokens")
                # Try to reload tokens from file as a fallback
                try:
                    token_path = os.path.join(os.getcwd(), "dropbox_tokens.json")
                    if os.path.exists(token_path):
                        with open(token_path, "r") as f:
                            tokens = json.load(f)
                        if "access_token" in tokens:
                            self.access_token = tokens["access_token"]
                            logger.info("Updated access token from token file")
                            if "refresh_token" in tokens:
                                self.refresh_token = tokens["refresh_token"]
                                logger.info("Updated refresh token from token file")
                except Exception as e:
                    logger.warning(f"Error loading tokens from file: {e}")
            try:
                # If we have a web server running, display OAuth guidance
                render_service_name = os.environ.get('RENDER_SERVICE_NAME', 'backdoor-ai')
                oauth_url = f"https://{render_service_name}.onrender.com/oauth/dropbox/authorize"
                logger.info(f"To complete OAuth setup, visit: {oauth_url}")
            except Exception:
                pass  # No need to handle this error
            
            # Initialize Dropbox client with access token and app credentials
            if self.app_key and self.app_secret:
                logger.info("Creating Dropbox client with full OAuth2 credentials")
                dbx = dropbox.Dropbox(
                    oauth2_access_token=self.access_token,
                    app_key=self.app_key,
                    app_secret=self.app_secret
                )
            else:
                logger.info("Creating Dropbox client with access token only")
                dbx = dropbox.Dropbox(self.access_token)
                
            # Verify the token works
            dbx.users_get_current_account()
            logger.info("Successfully authenticated with Dropbox using access token")
            self.auth_retries = 0  # Reset retry counter on success
            return dbx
                
        except AuthError as e:
            # If we have refresh capabilities, try that instead
            if "expired_access_token" in str(e) and self.refresh_token and self.app_key and self.app_secret:
                logger.warning("Access token expired, attempting refresh...")
                return self._refresh_access_token()
            else:
                logger.error(f"Dropbox authentication failed: {e}")
                self._handle_auth_failure(e)
                return None
                
        except Exception as e:
            logger.error(f"Dropbox initialization error: {e}")
            self._handle_auth_failure(e)
            return None
            
    def _authenticate_with_refresh(self) -> Optional[dropbox.Dropbox]:
        """
        Authenticate with full OAuth2 refresh capability.
        
        Returns:
            dropbox.Dropbox: Authenticated instance or None
        """
        try:
            # First try the access token
            if self.access_token:
                try:
                    # Create with both app_key and app_secret for proper OAuth support
                    if self.app_key and self.app_secret:
                        dbx = dropbox.Dropbox(
                            oauth2_access_token=self.access_token,
                            app_key=self.app_key,
                            app_secret=self.app_secret
                        )
                    else:
                        dbx = dropbox.Dropbox(self.access_token)
                        
                    # Quick check of token validity
                    dbx.users_get_current_account()
                    logger.info("Successfully authenticated with existing access token")
                    self.auth_retries = 0  # Reset retry counter on success
                    return dbx
                except AuthError as ae:
                    if "expired_access_token" in str(ae):
                        logger.info("Access token expired, refreshing...")
                    else:
                        logger.warning(f"Access token error: {ae}")
                except Exception as e:
                    logger.warning(f"Error checking access token: {e}")
            
            # Also try loading from token file if we can't use our access token
            try:
                token_path = os.path.join(os.getcwd(), "dropbox_tokens.json")
                if os.path.exists(token_path):
                    with open(token_path, "r") as f:
                        tokens = json.load(f)
                    if "access_token" in tokens:
                        logger.info("Found access token in dropbox_tokens.json")
                        token = tokens["access_token"]
                        # Try to authenticate with this token
                        try:
                            if self.app_key and self.app_secret:
                                dbx = dropbox.Dropbox(
                                    oauth2_access_token=token,
                                    app_key=self.app_key,
                                    app_secret=self.app_secret
                                )
                            else:
                                dbx = dropbox.Dropbox(token)
                            # Test it
                            dbx.users_get_current_account()
                            logger.info("Successfully authenticated with token from file")
                            self.access_token = token
                            return dbx
                        except Exception:
                            # Token from file didn't work, continue to refresh
                            pass
            except Exception as e:
                logger.warning(f"Error checking token file: {e}")
            
            # If we got here, we need to refresh the token
            return self._refresh_access_token()
                
        except Exception as e:
            logger.error(f"Dropbox authentication error: {e}")
            self._handle_auth_failure(e)
            return None
            
    def _refresh_access_token(self) -> Optional[dropbox.Dropbox]:
        """
        Refresh the OAuth2 access token using the refresh token.
        
        Returns:
            dropbox.Dropbox: New authenticated instance or None
        """
        try:
            # Don't attempt refresh too frequently
            current_time = time.time()
            if current_time - self.last_token_refresh < 60:  # At most once per minute
                logger.warning("Token refresh attempted too frequently, waiting...")
                time.sleep(2)  # Small delay to prevent tight loops
                return None
                
            logger.info("Refreshing Dropbox access token")
            self.last_token_refresh = current_time
            
            # Get a new access token using the refresh token
            import requests
            token_url = "https://api.dropboxapi.com/oauth2/token"
            data = {
                "grant_type": "refresh_token",
                "refresh_token": self.refresh_token,
                "client_id": self.app_key,
                "client_secret": self.app_secret
            }
            
            logger.info(f"Requesting new token with client_id={self.app_key}")
            response = requests.post(token_url, data=data)
            if response.status_code == 200:
                token_data = response.json()
                self.access_token = token_data["access_token"]
                
                # Update token in environment for future runs
                os.environ["DROPBOX_ACCESS_TOKEN"] = self.access_token
                
                # Save the token to file for persistence
                try:
                    # Calculate expiry time
                    if "expires_in" in token_data:
                        expires_in = token_data["expires_in"]
                        expiry_time = datetime.now() + timedelta(seconds=expires_in)
                        expiry_iso = expiry_time.isoformat()
                    else:
                        # Default to 4 hours if not specified
                        expiry_time = datetime.now() + timedelta(hours=4)
                        expiry_iso = expiry_time.isoformat()
                        
                    # Create tokens dict
                    tokens = {
                        "access_token": self.access_token,
                        "refresh_token": self.refresh_token,
                        "expiry_time": expiry_iso
                    }
                    
                    # Save to file
                    with open("dropbox_tokens.json", "w") as f:
                        json.dump(tokens, f, indent=2)
                    logger.info("Saved refreshed tokens to dropbox_tokens.json")
                except Exception as e:
                    logger.warning(f"Could not save tokens to file: {e}")
                
                # Save to config if possible
                try:
                    import config
                    config.DROPBOX_ACCESS_TOKEN = self.access_token
                    # Set token expiry if available
                    if "expires_in" in token_data:
                        expiry_time = datetime.now() + timedelta(seconds=token_data["expires_in"])
                        config.DROPBOX_TOKEN_EXPIRY = expiry_time.isoformat()
                except (ImportError, AttributeError):
                    pass
                
                # Create a new Dropbox instance with the refreshed token
                logger.info("Successfully refreshed Dropbox access token")
                
                # Initialize Dropbox with the new token
                dbx = dropbox.Dropbox(self.access_token)
                # Verify it works
                dbx.users_get_current_account()
                self.auth_retries = 0  # Reset retry counter on success
                return dbx
            else:
                logger.error(f"Token refresh failed: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"Error refreshing access token: {e}")
            return None
            
    def _handle_auth_failure(self, error: Exception) -> None:
        """
        Handle authentication failures with retries.
        
        Args:
            error: The exception that occurred
        """
        self.auth_retries += 1
        
        if self.auth_retries <= self.max_retries:
            retry_delay = self.retry_delay * self.auth_retries  # Exponential backoff
            logger.warning(f"Authentication failed, retrying in {retry_delay} seconds (attempt {self.auth_retries}/{self.max_retries})")
            time.sleep(retry_delay)
            
            # Try to re-authenticate
            if self.refresh_token and self.app_key and self.app_secret:
                self.dbx = self._authenticate_with_refresh()
            elif self.access_token:
                self.dbx = self._authenticate_with_token()
        else:
            logger.error(f"Authentication failed after {self.max_retries} retries")
            
            # For extreme scenarios, try to reconnect with legacy API key
            try:
                import config
                if hasattr(config, 'DROPBOX_API_KEY') and config.DROPBOX_API_KEY != self.access_token:
                    logger.info("Attempting authentication with legacy API key as last resort")
                    self.access_token = config.DROPBOX_API_KEY
                    self.dbx = self._authenticate_with_token()
            except ImportError:
                pass
            
    def _initialize(self) -> None:
        """Initialize Dropbox resources (find or create DB file and models folder)."""
        try:
            # Check if models folder exists, create if it doesn't
            self._find_or_create_models_folder()
            
            # Download database if it exists
            self._download_db()
                
            # Sync model file list
            self._sync_model_files()
            
            logger.info("Dropbox storage initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize Dropbox storage: {e}")
            raise
    
    def _download_db(self) -> bool:
        """
        Download the database from Dropbox.
        
        Returns:
            bool: True if download was successful, False otherwise
        """
        db_path = f"/{self.db_filename}"
        try:
            # Check if file exists on Dropbox
            try:
                self.dbx.files_get_metadata(db_path)
                file_exists = True
            except ApiError as e:
                if e.error.is_path() and e.error.get_path().is_not_found():
                    file_exists = False
                else:
                    raise
            
            if file_exists:
                # Download file
                self.dbx.files_download_to_file(self.local_db_path, db_path)
                self.last_db_sync = time.time()
                
                logger.info(f"Downloaded database from Dropbox: {self.local_db_path}")
                return True
            else:
                logger.info(f"Database file '{self.db_filename}' not found in Dropbox, will create on first upload")
                return False
            
        except Exception as e:
            logger.error(f"Error downloading database: {e}")
            return False
    
    def _find_or_create_models_folder(self) -> bool:
        """
        Find or create the models folder in Dropbox.
        
        Returns:
            bool: True if folder was found or created, False otherwise
        """
        folder_path = f"/{self.models_folder_name}"
        try:
            # Check if folder exists
            try:
                self.dbx.files_get_metadata(folder_path)
                logger.info(f"Found models folder in Dropbox: {folder_path}")
                return True
            except ApiError as e:
                if e.error.is_path() and e.error.get_path().is_not_found():
                    # Create folder if it doesn't exist
                    self.dbx.files_create_folder_v2(folder_path)
                    logger.info(f"Created models folder in Dropbox: {folder_path}")
                    return True
                else:
                    raise
            
        except Exception as e:
            logger.error(f"Error finding or creating models folder: {e}")
            return False
    
    def _sync_model_files(self) -> bool:
        """
        Sync the list of model files from Dropbox.
        
        Returns:
            bool: True if sync was successful, False otherwise
        """
        folder_path = f"/{self.models_folder_name}"
        try:
            try:
                # List all files in the models folder
                result = self.dbx.files_list_folder(folder_path)
                
                # Update model files map
                self.model_files = {}
                for entry in result.entries:
                    if isinstance(entry, dropbox.files.FileMetadata) and entry.name.endswith('.mlmodel'):
                        self.model_files[entry.name] = entry.path_display
                
                # Continue listing if there are more files
                while result.has_more:
                    result = self.dbx.files_list_folder_continue(result.cursor)
                    for entry in result.entries:
                        if isinstance(entry, dropbox.files.FileMetadata) and entry.name.endswith('.mlmodel'):
                            self.model_files[entry.name] = entry.path_display
                
                self.last_models_sync = time.time()
                
                logger.info(f"Synced {len(self.model_files)} model files from Dropbox")
                return True
            
            except ApiError as e:
                if e.error.is_path() and e.error.get_path().is_not_found():
                    # Create the folder if it doesn't exist
                    self._find_or_create_models_folder()
                    # Models folder was empty or didn't exist
                    self.model_files = {}
                    self.last_models_sync = time.time()
                    return True
                else:
                    raise
                
        except Exception as e:
            logger.error(f"Error syncing model files: {e}")
            return False
    
    def get_db_path(self) -> str:
        """
        Get the local path to the database file, downloading it from Dropbox if needed.
        
        Returns:
            str: Path to the local database file
        """
        with self.lock:
            # Check if we need to sync from Dropbox
            current_time = time.time()
            if current_time - self.last_db_sync > self.db_sync_interval:
                self._download_db()
            
            return self.local_db_path
            
    def download_db_to_memory(self) -> Dict[str, Any]:
        """
        Download the database from Dropbox directly to memory.
        
        Returns:
            Dict with db_buffer, success fields
        """
        with self.lock:
            db_path = f"/{self.db_filename}"
            try:
                # Check if file exists on Dropbox
                try:
                    self.dbx.files_get_metadata(db_path)
                    file_exists = True
                except ApiError as e:
                    if e.error.is_path() and e.error.get_path().is_not_found():
                        file_exists = False
                    else:
                        raise
                
                if file_exists:
                    # Download file to memory
                    result = self.dbx.files_download(db_path)
                    
                    # Extract the bytes and store in a buffer
                    content = result[1].content
                    buffer = io.BytesIO(content)
                    
                    self.last_db_sync = time.time()
                    logger.info(f"Downloaded database from Dropbox to memory buffer")
                    
                    return {
                        'success': True,
                        'db_buffer': buffer,
                        'size': len(content)
                    }
                else:
                    logger.info(f"Database file '{self.db_filename}' not found in Dropbox")
                    return {
                        'success': False,
                        'error': 'Database not found'
                    }
                
            except Exception as e:
                logger.error(f"Error downloading database to memory: {e}")
                return {
                    'success': False,
                    'error': str(e)
                }
    
    def upload_db(self) -> bool:
        """
        Upload the database to Dropbox.
        
        Returns:
            bool: True if upload was successful, False otherwise
        """
        with self.lock:
            if not os.path.exists(self.local_db_path):
                logger.warning(f"Cannot upload database: File not found at {self.local_db_path}")
                return False
                
            try:
                # Upload file with overwrite mode
                with open(self.local_db_path, 'rb') as f:
                    self.dbx.files_upload(f.read(), f"/{self.db_filename}", 
                                         mode=WriteMode.overwrite)
                
                self.last_db_sync = time.time()
                
                logger.info(f"Uploaded database to Dropbox: /{self.db_filename}")
                return True
                
            except Exception as e:
                logger.error(f"Error uploading database: {e}")
                return False
                
    def upload_db_from_memory(self, buffer: io.BytesIO) -> Dict[str, Any]:
        """
        Upload database from a memory buffer to Dropbox.
        
        Args:
            buffer: BytesIO buffer containing the database data
            
        Returns:
            Dict with success/error information
        """
        with self.lock:
            try:
                # Reset buffer position
                buffer.seek(0)
                
                # Upload file with overwrite mode
                self.dbx.files_upload(buffer.read(), f"/{self.db_filename}", 
                                     mode=WriteMode.overwrite)
                
                self.last_db_sync = time.time()
                
                logger.info(f"Uploaded in-memory database to Dropbox: /{self.db_filename}")
                return {
                    'success': True
                }
                
            except Exception as e:
                logger.error(f"Error uploading in-memory database: {e}")
                return {
                    'success': False,
                    'error': str(e)
                }
    
    def upload_model(self, data_or_path, model_name: str, folder: str = None) -> Dict[str, Any]:
        """
        Upload a model file to Dropbox.
        
        Args:
            data_or_path: Either a file path, binary data, or file-like object
            model_name: Name to use for the model in Dropbox
            folder: Optional specific folder to use, defaults to models_folder_name
            
        Returns:
            Dict with model information (success, name, path, etc.)
        """
        with self.lock:
            # Determine the folder to upload to
            upload_folder = folder if folder else self.models_folder_name
            
            dropbox_path = f"/{upload_folder}/{model_name}"
            file_data = None
            file_size = 0
            
            try:
                # Determine how to read the data based on the type of data_or_path
                if isinstance(data_or_path, str):
                    # It's a file path
                    if not os.path.exists(data_or_path):
                        logger.warning(f"Cannot upload model: File not found at {data_or_path}")
                        return {'success': False, 'error': 'File not found'}
                    
                    # Read the file
                    with open(data_or_path, 'rb') as f:
                        file_data = f.read()
                        file_size = len(file_data)
                
                elif hasattr(data_or_path, 'read'):
                    # It's a file-like object (e.g., BytesIO)
                    # Make sure we're at the beginning
                    if hasattr(data_or_path, 'seek'):
                        data_or_path.seek(0)
                    file_data = data_or_path.read()
                    file_size = len(file_data)
                
                else:
                    # Assume it's binary data
                    file_data = data_or_path
                    file_size = len(file_data)
                
                # Ensure the folder exists
                try:
                    folder_path = f"/{upload_folder}"
                    try:
                        self.dbx.files_get_metadata(folder_path)
                    except Exception:
                        # Create folder if it doesn't exist
                        logger.info(f"Creating folder: {folder_path}")
                        self.dbx.files_create_folder_v2(folder_path)
                except Exception as e:
                    logger.error(f"Error ensuring folder exists: {e}")
                    # Continue anyway - the upload will fail if folder doesn't exist
                
                # Upload to Dropbox
                upload_result = self.dbx.files_upload(file_data, dropbox_path, 
                                                    mode=WriteMode.overwrite)
                
                # Update model files map
                self.model_files[model_name] = dropbox_path
                
                # Create shared link for the file
                shared_link = self.dbx.sharing_create_shared_link_with_settings(dropbox_path)
                
                # Convert shared link to direct download link
                download_url = shared_link.url.replace('?dl=0', '?dl=1')
                
                # Get metadata for response
                result = {
                    'success': True,
                    'name': model_name,
                    'path': dropbox_path,
                    'size': file_size,
                    'upload_time': datetime.now().isoformat(),
                    'download_url': download_url
                }
                
                logger.info(f"Uploaded model {model_name} to Dropbox: {dropbox_path}")
                return result
                
            except Exception as e:
                logger.error(f"Error uploading model {model_name}: {e}")
                return {'success': False, 'error': str(e)}
    
    def get_model_stream(self, model_name: str, folder: str = None) -> Dict[str, Any]:
        """
        Get a streaming download URL for a model file in Dropbox.
        
        Args:
            model_name: Name of the model file
            folder: Optional specific folder to look in, defaults to models_folder_name
            
        Returns:
            Dict with success, download_url, size, path fields
        """
        with self.lock:
            # Sync model files if needed
            current_time = time.time()
            if current_time - self.last_models_sync > self.models_sync_interval:
                self._sync_model_files()
            
            # Determine the folder to look in - including base_model folder
            search_folder = folder if folder else self.models_folder_name
            
            # Check base_model folder if it's not found in regular folder
            if not self.model_files.get(model_name):
                # First try base_model folder for BASE_MODEL_NAME
                try:
                    import config
                    if model_name == getattr(config, 'BASE_MODEL_NAME', 'model_1.0.0.mlmodel'):
                        base_model_folder = getattr(config, 'DROPBOX_BASE_MODEL_FOLDER', 'base_model')
                        logger.info(f"Looking for base model in {base_model_folder} folder")
                        # Check if model exists in base_model folder
                        try:
                            base_model_path = f"/{base_model_folder}/{model_name}"
                            self.dbx.files_get_metadata(base_model_path)
                            # If we get here, the model exists in base_model folder
                            self.model_files[model_name] = base_model_path
                            logger.info(f"Found base model at {base_model_path}")
                        except Exception as e:
                            logger.warning(f"Base model not found in base_model folder: {e}")
                except ImportError:
                    pass
            
            # Find model path
            dropbox_path = self.model_files.get(model_name)
            if not dropbox_path:
                # Try to find by constructing path
                dropbox_path = f"/{search_folder}/{model_name}"
                logger.info(f"Looking for model at {dropbox_path}")
                try:
                    self.dbx.files_get_metadata(dropbox_path)
                    # If we get here, the model exists - add to cache
                    self.model_files[model_name] = dropbox_path
                except Exception:
                    logger.warning(f"Model {model_name} not found at {dropbox_path}")
                    return {'success': False, 'error': 'Model not found'}
            
            try:
                # Create shared link for direct download
                shared_link = self.dbx.sharing_create_shared_link_with_settings(dropbox_path)
                
                # Convert to direct download link
                download_url = shared_link.url.replace('?dl=0', '?dl=1')
                
                # Get metadata
                metadata = self.dbx.files_get_metadata(dropbox_path)
                
                logger.info(f"Created streaming download URL for {model_name}")
                
                return {
                    'success': True,
                    'download_url': download_url,
                    'size': metadata.size,
                    'path': dropbox_path
                }
                
            except Exception as e:
                logger.error(f"Error creating model stream for {model_name}: {e}")
                return {'success': False, 'error': str(e)}
    
    def download_model_to_memory(self, model_name: str, folder: str = None) -> Dict[str, Any]:
        """
        Download a model file from Dropbox to memory.
        
        Args:
            model_name: Name of the model file to download
            folder: Optional specific folder to look in, defaults to models_folder_name
            
        Returns:
            Dict with success, model_buffer, size fields
        """
        with self.lock:
            # Sync model files if needed
            current_time = time.time()
            if current_time - self.last_models_sync > self.models_sync_interval:
                self._sync_model_files()
            
            # Determine the folder to look in
            search_folder = folder if folder else self.models_folder_name
            
            # Find model path
            dropbox_path = self.model_files.get(model_name)
            if not dropbox_path:
                # Try to find by constructing path
                dropbox_path = f"/{search_folder}/{model_name}"
                logger.info(f"Looking for model at {dropbox_path}")
                
            try:
                # Check if the file exists
                try:
                    self.dbx.files_get_metadata(dropbox_path)
                except Exception:
                    logger.warning(f"Model {model_name} not found at {dropbox_path}")
                    return {'success': False, 'error': 'Model not found'}
                
                # Download file to memory
                result = self.dbx.files_download(dropbox_path)
                
                # Get content and create buffer
                content = result[1].content
                buffer = io.BytesIO(content)
                buffer.seek(0)
                
                logger.info(f"Downloaded model {model_name} from Dropbox to memory")
                
                return {
                    'success': True,
                    'model_buffer': buffer,
                    'size': len(content),
                    'path': dropbox_path
                }
                
            except Exception as e:
                logger.error(f"Error downloading model {model_name} to memory: {e}")
                return {'success': False, 'error': str(e)}
    
    def download_model(self, model_name: str, local_path: str = None) -> Dict[str, Any]:
        """
        Download a model file from Dropbox.
        
        Args:
            model_name: Name of the model file in Dropbox
            local_path: Path where to save the model (if None, uses temp directory)
            
        Returns:
            Dict with model information (success, local_path)
        """
        with self.lock:
            # Sync model files if needed
            current_time = time.time()
            if current_time - self.last_models_sync > self.models_sync_interval:
                self._sync_model_files()
            
            # Find model path
            dropbox_path = self.model_files.get(model_name)
            if not dropbox_path:
                logger.warning(f"Model {model_name} not found in Dropbox")
                return {'success': False, 'error': 'Model not found'}
            
            # Set local path if not provided
            if not local_path:
                local_path = os.path.join(self.temp_dir, model_name)
            
            try:
                # Download file
                self.dbx.files_download_to_file(local_path, dropbox_path)
                
                result = {
                    'success': True,
                    'local_path': local_path,
                    'name': model_name,
                    'size': os.path.getsize(local_path),
                    'download_time': datetime.now().isoformat()
                }
                
                logger.info(f"Downloaded model {model_name} from Dropbox: {local_path}")
                return result
                
            except Exception as e:
                logger.error(f"Error downloading model {model_name}: {e}")
                return {'success': False, 'error': str(e)}
    
    def list_models(self) -> List[Dict[str, Any]]:
        """
        Get a list of all model files in Dropbox.
        
        Returns:
            List of model information dictionaries
        """
        with self.lock:
            # Sync model files
            self._sync_model_files()
            
            if not self.model_files:
                return []
                
            try:
                # Get details for each model
                models = []
                for name, path in self.model_files.items():
                    try:
                        metadata = self.dbx.files_get_metadata(path)
                        shared_link = self.dbx.sharing_create_shared_link_with_settings(path)
                        download_url = shared_link.url.replace('?dl=0', '?dl=1')
                        
                        models.append({
                            'name': name,
                            'path': path,
                            'size': metadata.size,
                            'modified_date': metadata.server_modified.isoformat(),
                            'download_url': download_url
                        })
                    except Exception as e:
                        logger.error(f"Error getting metadata for model {name}: {e}")
                
                return models
                
            except Exception as e:
                logger.error(f"Error listing models: {e}")
                return []
    
    def delete_model(self, model_name: str) -> bool:
        """
        Delete a model file from Dropbox.
        
        Args:
            model_name: Name of the model file to delete
            
        Returns:
            bool: True if deletion was successful, False otherwise
        """
        with self.lock:
            # Find model path
            dropbox_path = self.model_files.get(model_name)
            if not dropbox_path:
                logger.warning(f"Cannot delete: Model {model_name} not found in Dropbox")
                return False
            
            try:
                # Delete file
                self.dbx.files_delete_v2(dropbox_path)
                
                # Update model files map
                del self.model_files[model_name]
                
                logger.info(f"Deleted model {model_name} from Dropbox")
                return True
                
            except Exception as e:
                logger.error(f"Error deleting model {model_name}: {e}")
                return False

# Module-level singleton instance
_dropbox_storage = None
_initialization_lock = threading.RLock()

def init_dropbox_storage(api_key: str = None, db_filename: str = "interactions.db", 
                        models_folder_name: str = "backdoor_models", 
                        access_token: str = None, refresh_token: str = None,
                        app_key: str = None, app_secret: str = None) -> Optional['DropboxStorage']:
    """
    Initialize Dropbox storage with OAuth2 support.
    
    Args:
        api_key: Legacy Dropbox API key (used as access_token if access_token not provided)
        db_filename: Name of the database file in Dropbox
        models_folder_name: Name of the folder to store models in
        access_token: OAuth2 access token (preferred over api_key)
        refresh_token: OAuth2 refresh token for getting new access tokens
        app_key: Dropbox app key for OAuth2 flow
        app_secret: Dropbox app secret for OAuth2 flow
        
    Returns:
        DropboxStorage: The initialized storage instance or None if initialization fails
    """
    # Ensure tempfile is available
    import sys
    import tempfile
    if 'tempfile' not in sys.modules:
        sys.modules['tempfile'] = tempfile
    global _dropbox_storage
    
    # Use the centralized token manager to ensure we have valid tokens
    try:
        # Import the token manager
        from utils.token_manager import get_token_manager
        
        # Get the token manager instance
        token_manager = get_token_manager()
        
        # Get a valid access token (refreshes automatically if needed)
        valid_token = token_manager.get_valid_access_token()
        
        if valid_token:
            # Use the valid token from the token manager
            access_token = valid_token
            logger.info("Using valid access token from token manager")
            
            # Get the refresh token too, if a valid one exists
            if token_manager.refresh_token and token_manager.refresh_token != "YOUR_REFRESH_TOKEN":
                refresh_token = token_manager.refresh_token
                
    except ImportError:
        logger.warning("Token manager not available, using provided tokens")
        
        # Run automatic token refresh script as fallback
        try:
            import subprocess
            import sys
            if os.path.exists("refresh_token_auto.py"):
                logger.info("Running automatic token refresh script")
                result = subprocess.run(
                    [sys.executable, "refresh_token_auto.py"],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                if result.returncode == 0:
                    logger.info("Token refresh successful")
                else:
                    logger.warning("Token refresh script returned non-zero exit code")
        except Exception as e:
            logger.warning(f"Error running token refresh script: {e}")
    
    with _initialization_lock:
        # If we already have an instance and it's working, return it
        if _dropbox_storage is not None and hasattr(_dropbox_storage, 'dbx'):
            # Check if the connection is working
            try:
                # Quick verification that the token is still valid
                _dropbox_storage.dbx.users_get_current_account()
                logger.debug("Reusing existing Dropbox connection")
                return _dropbox_storage
            except Exception:
                logger.info("Existing Dropbox connection is invalid, reinitializing")
                _dropbox_storage = None
        
        # Get credentials from config if not provided
        if access_token is None and refresh_token is None and app_key is None and app_secret is None:
            try:
                import config
                access_token = getattr(config, 'DROPBOX_ACCESS_TOKEN', api_key)
                refresh_token = getattr(config, 'DROPBOX_REFRESH_TOKEN', None)
                app_key = getattr(config, 'DROPBOX_APP_KEY', None)
                app_secret = getattr(config, 'DROPBOX_APP_SECRET', None)
                
                # Check for token expiry
                token_expiry = getattr(config, 'DROPBOX_TOKEN_EXPIRY', None)
                if token_expiry:
                    try:
                        expiry_time = datetime.fromisoformat(token_expiry)
                        if expiry_time <= datetime.now():
                            logger.warning("Access token has expired according to config")
                            
                            # Try to refresh if we have the capability
                            if refresh_token and app_key and app_secret:
                                from utils.dropbox_oauth import refresh_access_token
                                logger.info("Attempting to refresh token automatically")
                                result = refresh_access_token(app_key, app_secret, refresh_token)
                                if result.get("success", False):
                                    access_token = result["access_token"]
                                    logger.info("Successfully refreshed access token")
                                else:
                                    logger.error("Failed to refresh token: " + result.get("error", "Unknown error"))
                    except (ValueError, ImportError) as e:
                        logger.warning(f"Error checking token expiry: {e}")
            except ImportError:
                # Fall back to using api_key as access_token
                access_token = api_key
        elif access_token is None:
            # If only access_token is None but other OAuth params provided, use api_key as access_token
            access_token = api_key
        
        try:
            # Create storage with the best authentication method available
            if refresh_token and app_key and app_secret:
                logger.info("Initializing Dropbox with OAuth2 refresh capabilities")
                _dropbox_storage = DropboxStorage(access_token, refresh_token, app_key, app_secret,
                                                db_filename, models_folder_name)
            else:
                logger.info("Initializing Dropbox with access token only (no refresh capability)")
                _dropbox_storage = DropboxStorage(access_token=access_token, db_filename=db_filename,
                                               models_folder_name=models_folder_name)
            
            # Verify the connection is working
            if _dropbox_storage and not hasattr(_dropbox_storage, 'dbx'):
                logger.error("Dropbox initialization failed - no connection established")
                _dropbox_storage = None
                
            return _dropbox_storage
        except Exception as e:
            logger.error(f"Error initializing Dropbox storage: {e}")
            _dropbox_storage = None
            return None

def get_dropbox_storage():
    """
    Get the Dropbox storage instance.
    
    Returns:
        DropboxStorage: The singleton storage instance
        
    Raises:
        RuntimeError: If dropbox storage hasn't been initialized
    """
    if _dropbox_storage is None:
        # Provide a helpful error message
        logger.error(
            "Dropbox storage not initialized. To use Dropbox storage, you need to: "
            "1. Make sure DROPBOX_ENABLED=True in config.py "
            "2. Set DROPBOX_REFRESH_TOKEN in config.py or use setup_oauth.py "
            "3. Restart the application after setting the refresh token"
        )
        raise RuntimeError("Dropbox storage not initialized. Call init_dropbox_storage() first.")
    
    # Check if the client is properly authenticated
    if not hasattr(_dropbox_storage, 'dbx') or _dropbox_storage.dbx is None:
        try:
            # Try to refresh authentication using token manager
            from utils.token_manager import get_token_manager
            token_manager = get_token_manager()
            
            # Check if we have a refresh token
            if token_manager.refresh_token:
                logger.info("Attempting to refresh Dropbox authentication using token manager")
                # Force token refresh
                if token_manager.refresh_token_if_needed():
                    # Try to initialize again with the new token
                    logger.info("Token refreshed, reinitializing Dropbox storage")
                    return init_dropbox_storage()
        except ImportError:
            pass
            
        logger.error(
            "Dropbox client not authenticated. Set DROPBOX_REFRESH_TOKEN in config.py "
            "or run setup_oauth.py to configure authentication."
        )
        raise RuntimeError("Dropbox client not authenticated.")
    
    return _dropbox_storage
