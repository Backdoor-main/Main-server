"""
Centralized token management for OAuth2 tokens.

This module provides a centralized way to manage OAuth2 tokens
for Dropbox and other services. It handles token refresh, storage,
and expiration tracking automatically.
"""

import os
import json
import time
import logging
import requests
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, Tuple

logger = logging.getLogger(__name__)

class TokenManager:
    """Centralized OAuth2 token management for Dropbox."""
    
    _instance = None  # Singleton instance
    
    def __new__(cls, *args, **kwargs):
        """Ensure singleton pattern for token management."""
        if cls._instance is None:
            cls._instance = super(TokenManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self, config=None):
        """
        Initialize the token manager with application config.
        
        Args:
            config: Application config module (falls back to importing config)
        """
        # Only initialize once due to singleton pattern
        if self._initialized:
            return
            
        # Import config if not provided
        if config is None:
            try:
                import config
                self.config = config
            except ImportError:
                logger.error("Could not import config module")
                self.config = None
        else:
            self.config = config
        
        # Essential configuration
        self.tokens_file = "dropbox_tokens.json"
        self.app_key = self._get_config("DROPBOX_APP_KEY")
        self.app_secret = self._get_config("DROPBOX_APP_SECRET")
        self.refresh_token = self._get_config("DROPBOX_REFRESH_TOKEN")
        
        # Optional configuration with defaults
        self.auto_refresh = self._get_config("DROPBOX_AUTO_REFRESH", True)
        self.refresh_threshold_seconds = 300  # Refresh 5 minutes before expiry
        
        # Token state
        self.access_token = self._get_config("DROPBOX_ACCESS_TOKEN")
        self.expiry_time = self._get_config("DROPBOX_TOKEN_EXPIRY")
        self.last_refresh_attempt = 0
        self.refresh_cooldown = 60  # Minimum seconds between refresh attempts
        
        # Load tokens from file
        self._load_tokens()
        
        # Try to refresh on initialization if needed
        if self.auto_refresh and self._should_refresh() and self.refresh_token:
            if self.refresh_token != "YOUR_REFRESH_TOKEN":
                logger.info("Refresh token found, refreshing access token on initialization")
                self.refresh_token_if_needed()
            else:
                logger.warning("Refresh token not set, please configure DROPBOX_REFRESH_TOKEN")
        
        self._initialized = True
        
        # Log the token status
        if self.refresh_token and self.refresh_token != "YOUR_REFRESH_TOKEN":
            if self.access_token:
                logger.info("Token manager initialized with valid refresh and access tokens")
            else:
                logger.info("Token manager initialized with refresh token only, will generate access token")
        else:
            logger.warning("Token manager initialized without a valid refresh token")
    
    def _get_config(self, key, default=None):
        """
        Get a configuration value safely.
        
        Args:
            key: The configuration key
            default: Default value if not found
            
        Returns:
            The configuration value or default
        """
        # First try environment variable
        env_value = os.environ.get(key)
        if env_value is not None:
            return env_value
            
        # Then try config module
        if self.config is not None:
            return getattr(self.config, key, default)
            
        # Fall back to default
        return default
    
    def _load_tokens(self):
        """Load tokens from the token file if it exists."""
        try:
            if os.path.exists(self.tokens_file):
                with open(self.tokens_file, 'r') as f:
                    tokens = json.load(f)
                
                # Update current tokens from file
                if "access_token" in tokens:
                    self.access_token = tokens["access_token"]
                if "refresh_token" in tokens and tokens["refresh_token"] != "YOUR_REFRESH_TOKEN":
                    self.refresh_token = tokens["refresh_token"]
                if "expiry_time" in tokens:
                    self.expiry_time = tokens["expiry_time"]
                    
                logger.info("Loaded tokens from file")
        except Exception as e:
            logger.error(f"Error loading tokens from file: {e}")
    
    def _save_tokens(self):
        """Save current tokens to the token file."""
        try:
            tokens = {
                "access_token": self.access_token,
                "refresh_token": self.refresh_token
            }
            
            if self.expiry_time:
                tokens["expiry_time"] = self.expiry_time
                
            with open(self.tokens_file, 'w') as f:
                json.dump(tokens, f, indent=2)
                
            logger.info("Saved tokens to file")
            
            # Update config module if available
            if self.config is not None:
                try:
                    if hasattr(self.config, "DROPBOX_ACCESS_TOKEN"):
                        self.config.DROPBOX_ACCESS_TOKEN = self.access_token
                    if hasattr(self.config, "DROPBOX_TOKEN_EXPIRY"):
                        self.config.DROPBOX_TOKEN_EXPIRY = self.expiry_time
                except Exception as e:
                    logger.warning(f"Error updating config module: {e}")
            
            # Always update environment variables
            os.environ["DROPBOX_ACCESS_TOKEN"] = self.access_token
            if self.expiry_time:
                os.environ["DROPBOX_TOKEN_EXPIRY"] = self.expiry_time
                
        except Exception as e:
            logger.error(f"Error saving tokens to file: {e}")
    
    def _should_refresh(self) -> bool:
        """
        Check if the access token should be refreshed.
        
        Returns:
            bool: True if refresh is needed
        """
        # If we don't have an access token but have a refresh token, refresh
        if not self.access_token and self.refresh_token:
            return True
            
        # Check if token is expired or will expire soon
        if self.expiry_time:
            try:
                expiry = datetime.fromisoformat(self.expiry_time)
                now = datetime.now()
                
                # Refresh if expired or expiring soon
                if expiry <= now:
                    logger.info("Token has expired")
                    return True
                    
                # Refresh if expiring within threshold
                seconds_to_expiry = (expiry - now).total_seconds()
                if seconds_to_expiry <= self.refresh_threshold_seconds:
                    logger.info(f"Token expires in {seconds_to_expiry:.1f} seconds, refreshing")
                    return True
            except (ValueError, TypeError) as e:
                logger.error(f"Error parsing expiry time: {e}")
                return True
        
        # If we have no expiry information but have both tokens, assume we need refresh
        if self.access_token and self.refresh_token and not self.expiry_time:
            logger.info("No expiry information, refreshing to be safe")
            return True
            
        return False
    
    def refresh_token_if_needed(self) -> bool:
        """
        Refresh the access token if needed.
        
        Returns:
            bool: True if refresh was successful or not needed
        """
        # Check if we're attempting refresh too frequently
        current_time = time.time()
        if current_time - self.last_refresh_attempt < self.refresh_cooldown:
            logger.debug("Skipping refresh, attempted too recently")
            return False
            
        self.last_refresh_attempt = current_time
        
        # Check if refresh is needed
        if not self._should_refresh():
            return True  # Token is still valid
            
        # Check if we have the necessary credentials
        if not self.refresh_token:
            logger.error("Cannot refresh token: No refresh token available")
            return False
            
        if not self.app_key or not self.app_secret:
            logger.error("Cannot refresh token: Missing app credentials")
            return False
            
        # Perform token refresh
        return self._refresh_access_token()
    
    def _refresh_access_token(self) -> bool:
        """
        Refresh the access token using the refresh token.
        
        Returns:
            bool: True if successful
        """
        logger.info("Refreshing access token...")
        
        try:
            # Request a new access token
            token_url = "https://api.dropboxapi.com/oauth2/token"
            data = {
                "grant_type": "refresh_token",
                "refresh_token": self.refresh_token,
                "client_id": self.app_key,
                "client_secret": self.app_secret
            }
            
            response = requests.post(token_url, data=data)
            if response.status_code != 200:
                logger.error(f"Token refresh failed: {response.status_code} - {response.text}")
                return False
                
            # Parse the response
            token_data = response.json()
            self.access_token = token_data["access_token"]
            
            # Calculate and store expiry time
            if "expires_in" in token_data:
                expires_in = token_data["expires_in"]
                expiry_time = datetime.now() + timedelta(seconds=expires_in)
                self.expiry_time = expiry_time.isoformat()
                
            # Save the updated tokens
            self._save_tokens()
            
            logger.info("Successfully refreshed access token")
            return True
            
        except Exception as e:
            logger.error(f"Error refreshing access token: {e}")
            return False
    
    def get_valid_access_token(self) -> Optional[str]:
        """
        Get a valid access token, refreshing if necessary.
        
        Returns:
            str: Valid access token or None if unavailable
        """
        # Try to refresh the token if needed
        if self.auto_refresh and self._should_refresh():
            self.refresh_token_if_needed()
            
        return self.access_token
    
    def get_token_info(self) -> Dict[str, Any]:
        """
        Get information about the current tokens.
        
        Returns:
            Dict with token status information
        """
        # Check expiry status
        is_expired = False
        expires_in = None
        
        if self.expiry_time:
            try:
                expiry = datetime.fromisoformat(self.expiry_time)
                now = datetime.now()
                
                if expiry <= now:
                    is_expired = True
                else:
                    expires_in = (expiry - now).total_seconds()
            except (ValueError, TypeError):
                is_expired = True
        
        return {
            "has_access_token": bool(self.access_token),
            "has_refresh_token": bool(self.refresh_token),
            "access_token": self.access_token,
            "token_expired": is_expired,
            "expiry_time": self.expiry_time,
            "expires_in_seconds": expires_in,
            "auto_refresh": self.auto_refresh
        }

# Initialize singleton instance
token_manager = TokenManager()

def get_token_manager() -> TokenManager:
    """
    Get the singleton TokenManager instance.
    
    Returns:
        TokenManager: The singleton instance
    """
    return token_manager
