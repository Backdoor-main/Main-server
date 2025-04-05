"""
Dropbox OAuth2 utilities for Backdoor AI server.

This module provides functionality to:
- Generate OAuth2 tokens for Dropbox API
- Refresh expired tokens
- Store and manage token information
"""

import os
import json
import time
import logging
import requests
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, Tuple

logger = logging.getLogger(__name__)

def generate_auth_url(app_key: str, redirect_uri: str = "http://localhost") -> str:
    """
    Generate an authorization URL for Dropbox OAuth2 flow.
    
    Args:
        app_key: Dropbox app key
        redirect_uri: Redirect URI for OAuth flow
        
    Returns:
        str: URL to visit for authorization
    """
    # Generate the authorization URL
    auth_url = (
        f"https://www.dropbox.com/oauth2/authorize?"
        f"client_id={app_key}&"
        f"response_type=code&"
        f"redirect_uri={redirect_uri}&"
        f"token_access_type=offline"  # Request refresh token
    )
    
    return auth_url

def exchange_code_for_tokens(app_key: str, app_secret: str, auth_code: str,
                            redirect_uri: str = "http://localhost") -> Dict[str, Any]:
    """
    Exchange an authorization code for access and refresh tokens.
    
    Args:
        app_key: Dropbox app key
        app_secret: Dropbox app secret
        auth_code: Authorization code from the redirect
        redirect_uri: Redirect URI used in the auth request
        
    Returns:
        Dict with tokens and related information
    """
    token_url = "https://api.dropboxapi.com/oauth2/token"
    data = {
        "code": auth_code,
        "grant_type": "authorization_code",
        "client_id": app_key,
        "client_secret": app_secret,
        "redirect_uri": redirect_uri
    }
    
    try:
        response = requests.post(token_url, data=data)
        response.raise_for_status()
        token_data = response.json()
        
        # Calculate expiry time
        if "expires_in" in token_data:
            expires_in = token_data["expires_in"]
            expiry_time = datetime.now() + timedelta(seconds=expires_in)
            token_data["expiry_time"] = expiry_time.isoformat()
        
        # Return the token data (access_token, refresh_token, etc.)
        return {
            "success": True,
            "access_token": token_data.get("access_token"),
            "refresh_token": token_data.get("refresh_token"),
            "expiry_time": token_data.get("expiry_time"),
            "account_id": token_data.get("account_id"),
            "raw_response": token_data
        }
        
    except Exception as e:
        logger.error(f"Error exchanging auth code for tokens: {e}")
        return {
            "success": False,
            "error": str(e)
        }

def refresh_access_token(app_key: str, app_secret: str, refresh_token: str) -> Dict[str, Any]:
    """
    Refresh an access token using a refresh token.
    
    Args:
        app_key: Dropbox app key
        app_secret: Dropbox app secret
        refresh_token: Refresh token to use
        
    Returns:
        Dict with new access token and related information
    """
    token_url = "https://api.dropboxapi.com/oauth2/token"
    data = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "client_id": app_key,
        "client_secret": app_secret
    }
    
    try:
        response = requests.post(token_url, data=data)
        response.raise_for_status()
        token_data = response.json()
        
        # Calculate expiry time
        if "expires_in" in token_data:
            expires_in = token_data["expires_in"]
            expiry_time = datetime.now() + timedelta(seconds=expires_in)
            token_data["expiry_time"] = expiry_time.isoformat()
        
        # Update environment variables and config
        os.environ["DROPBOX_ACCESS_TOKEN"] = token_data["access_token"]
        
        # Try to update config module for future imports
        try:
            import config
            config.DROPBOX_ACCESS_TOKEN = token_data["access_token"]
            if "expiry_time" in token_data:
                config.DROPBOX_TOKEN_EXPIRY = token_data["expiry_time"]
        except (ImportError, AttributeError):
            pass
        
        return {
            "success": True,
            "access_token": token_data.get("access_token"),
            "expiry_time": token_data.get("expiry_time"),
            "raw_response": token_data
        }
        
    except Exception as e:
        logger.error(f"Error refreshing access token: {e}")
        return {
            "success": False,
            "error": str(e)
        }

def save_token_info(tokens: Dict[str, Any], filepath: str = "dropbox_tokens.json") -> bool:
    """
    Save token information to a file.
    
    Args:
        tokens: Token data to save
        filepath: Path to save the file
        
    Returns:
        bool: True if successful
    """
    try:
        # Create a sanitized version with sensitive data masked
        safe_tokens = tokens.copy()
        if "access_token" in safe_tokens:
            token = safe_tokens["access_token"]
            safe_tokens["access_token"] = f"{token[:10]}...{token[-10:]}"
        if "refresh_token" in safe_tokens:
            token = safe_tokens["refresh_token"]
            safe_tokens["refresh_token"] = f"{token[:5]}...{token[-5:]}"
        
        # Save the actual tokens
        with open(filepath, 'w') as f:
            json.dump(tokens, f, indent=2)
            
        logger.info(f"Saved token information to {filepath}")
        
        # Log sanitized version
        logger.info(f"Token info: {json.dumps(safe_tokens)}")
        
        return True
        
    except Exception as e:
        logger.error(f"Error saving token information: {e}")
        return False

def load_token_info(filepath: str = "dropbox_tokens.json") -> Dict[str, Any]:
    """
    Load token information from a file.
    
    Args:
        filepath: Path to the token file
        
    Returns:
        Dict with token information
    """
    try:
        if not os.path.exists(filepath):
            logger.warning(f"Token file not found: {filepath}")
            return {}
            
        with open(filepath, 'r') as f:
            tokens = json.load(f)
            
        # Check if access token has expired
        if "expiry_time" in tokens:
            try:
                expiry_time = datetime.fromisoformat(tokens["expiry_time"])
                if expiry_time <= datetime.now():
                    tokens["expired"] = True
                    logger.warning("Access token has expired")
                else:
                    tokens["expired"] = False
                    # Calculate remaining time
                    remaining = expiry_time - datetime.now()
                    tokens["expires_in_seconds"] = remaining.total_seconds()
                    logger.info(f"Access token valid for {remaining.total_seconds()/60:.1f} minutes")
            except Exception as e:
                logger.error(f"Error checking token expiry: {e}")
                
        return tokens
        
    except Exception as e:
        logger.error(f"Error loading token information: {e}")
        return {}

def is_token_valid(access_token: str) -> bool:
    """
    Check if an access token is still valid.
    
    Args:
        access_token: Access token to check
        
    Returns:
        bool: True if token is valid
    """
    try:
        import dropbox
        dbx = dropbox.Dropbox(access_token)
        # Make a test call to the API
        dbx.users_get_current_account()
        return True
    except Exception:
        return False
        
def check_and_refresh_if_needed(app_key: str, app_secret: str, 
                               access_token: str, refresh_token: str) -> Dict[str, Any]:
    """
    Check if the access token is valid and refresh if needed.
    
    Args:
        app_key: Dropbox app key
        app_secret: Dropbox app secret
        access_token: Current access token
        refresh_token: Refresh token
        
    Returns:
        Dict with token information
    """
    if is_token_valid(access_token):
        return {
            "success": True,
            "refreshed": False,
            "access_token": access_token,
            "message": "Access token is still valid"
        }
    
    # Token is not valid, refresh it
    logger.info("Access token invalid, refreshing...")
    result = refresh_access_token(app_key, app_secret, refresh_token)
    
    if result["success"]:
        result["refreshed"] = True
        result["message"] = "Access token refreshed successfully"
    else:
        result["refreshed"] = False
        
    return result
