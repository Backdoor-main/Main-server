#!/usr/bin/env python3
"""
Simple Dropbox token refresh script.

This standalone script refreshes Dropbox OAuth2 tokens using app credentials.
It's designed to be run during application startup to ensure valid tokens.
"""

import os
import sys
import json
import datetime
import requests

# App credentials - can be overridden by environment variables
APP_KEY = os.getenv("DROPBOX_APP_KEY", "2bi422xpd3xd962")
APP_SECRET = os.getenv("DROPBOX_APP_SECRET", "j3yx0b41qdvfu86")

def refresh_token():
    """
    Check token status and refresh if needed.
    
    Returns:
        tuple: (success, message)
    """
    print("Checking Dropbox token status...")
    
    # Check if we have a token file
    if not os.path.exists("dropbox_tokens.json"):
        print("No token file found")
        return load_from_config()
    
    # Load tokens from file
    try:
        with open("dropbox_tokens.json", "r") as f:
            tokens = json.load(f)
        
        # Check if we have a refresh token
        if "refresh_token" not in tokens:
            print("No refresh token found in token file")
            return load_from_config()
        
        refresh_token = tokens["refresh_token"]
        
        # Check if token is expired
        if "expiry_time" in tokens:
            try:
                expiry = datetime.datetime.fromisoformat(tokens["expiry_time"])
                now = datetime.datetime.now()
                if expiry > now:
                    # Token still valid
                    remaining = expiry - now
                    minutes = remaining.total_seconds() / 60
                    print(f"Token valid for {minutes:.1f} minutes")
                    return True, f"Token valid for {minutes:.1f} minutes"
            except (ValueError, TypeError):
                pass
        
        # If we get here, we need to refresh the token
        print("Refreshing access token...")
        return refresh_access_token(refresh_token)
    
    except Exception as e:
        print(f"Error checking token file: {e}")
        return load_from_config()

def load_from_config():
    """
    Try to load refresh token from config.
    
    Returns:
        tuple: (success, message)
    """
    try:
        import config
        if hasattr(config, "DROPBOX_REFRESH_TOKEN") and config.DROPBOX_REFRESH_TOKEN:
            if config.DROPBOX_REFRESH_TOKEN != "YOUR_REFRESH_TOKEN":
                print("Using refresh token from config")
                return refresh_access_token(config.DROPBOX_REFRESH_TOKEN)
    except Exception as e:
        print(f"Error loading from config: {e}")
    
    print("No refresh token available, cannot refresh automatically")
    return False, "No refresh token available"

def refresh_access_token(refresh_token):
    """
    Refresh an access token using the refresh token.
    
    Args:
        refresh_token: The refresh token to use
        
    Returns:
        tuple: (success, message)
    """
    try:
        # Get a new access token
        token_url = "https://api.dropboxapi.com/oauth2/token"
        data = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": APP_KEY,
            "client_secret": APP_SECRET
        }
        
        response = requests.post(token_url, data=data)
        if response.status_code != 200:
            print(f"Token refresh failed: {response.status_code}")
            print(f"Response: {response.text}")
            return False, f"Token refresh failed: {response.status_code}"
        
        # Parse response
        token_data = response.json()
        access_token = token_data["access_token"]
        
        # Calculate expiry time
        expires_in = token_data.get("expires_in", 14400)  # Default 4 hours
        expiry_time = datetime.datetime.now() + datetime.timedelta(seconds=expires_in)
        expiry_iso = expiry_time.isoformat()
        
        # Update tokens file
        tokens = {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "expiry_time": expiry_iso
        }
        
        with open("dropbox_tokens.json", "w") as f:
            json.dump(tokens, f, indent=2)
        
        # Update environment
        os.environ["DROPBOX_ACCESS_TOKEN"] = access_token
        
        # Try to update config module
        try:
            import config
            config.DROPBOX_ACCESS_TOKEN = access_token
            config.DROPBOX_TOKEN_EXPIRY = expiry_iso
            print("Updated config module with new token")
        except Exception:
            pass
        
        print(f"Successfully refreshed access token (expires: {expiry_iso})")
        mask_token = f"{access_token[:10]}...{access_token[-10:]}"
        print(f"Token: {mask_token}")
        return True, f"Token refreshed successfully (expires: {expiry_iso})"
        
    except Exception as e:
        print(f"Error refreshing token: {e}")
        return False, f"Error refreshing token: {e}"

def main():
    """Run the token refresh process."""
    success, message = refresh_token()
    if success:
        print(f"Success: {message}")
        return 0
    else:
        print(f"Warning: {message}")
        print("Continuing with existing token or local storage")
        return 0  # Still return success to not block startup

if __name__ == "__main__":
    sys.exit(main())
