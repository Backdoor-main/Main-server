#!/usr/bin/env python3
"""
Script to quickly generate Dropbox tokens using app key and secret.

This lightweight script is a simplified version of gen_dropbox_token.py
that can be used during build or startup processes to initialize tokens
using only the app key and secret.
"""

import os
import sys
import json
import tempfile
import requests
from datetime import datetime, timedelta

# App credentials
APP_KEY = os.getenv('DROPBOX_APP_KEY', '2bi422xpd3xd962')
APP_SECRET = os.getenv('DROPBOX_APP_SECRET', 'j3yx0b41qdvfu86')

def check_token_status():
    """Check if we have a valid token file"""
    try:
        if not os.path.exists('dropbox_tokens.json'):
            return False, "Token file not found"
            
        with open('dropbox_tokens.json', 'r') as f:
            tokens = json.load(f)
            
        if 'refresh_token' not in tokens:
            return False, "No refresh token found"
            
        if 'expiry_time' in tokens:
            expiry_time = datetime.fromisoformat(tokens['expiry_time'])
            now = datetime.now()
            if expiry_time <= now:
                return False, "Token expired"
            else:
                minutes_left = (expiry_time - now).total_seconds() / 60
                return True, f"Token valid for {minutes_left:.1f} minutes"
        else:
            return False, "No expiry time found"
    except Exception as e:
        return False, f"Error checking tokens: {e}"

def refresh_token():
    """Refresh an access token using a refresh token"""
    try:
        # Load existing tokens
        if not os.path.exists('dropbox_tokens.json'):
            return False, "Token file not found, cannot refresh"
            
        with open('dropbox_tokens.json', 'r') as f:
            tokens = json.load(f)
        
        if 'refresh_token' not in tokens:
            return False, "No refresh token found, cannot refresh"
        
        refresh_token = tokens['refresh_token']
        
        # Request a new access token
        token_url = "https://api.dropboxapi.com/oauth2/token"
        data = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": APP_KEY,
            "client_secret": APP_SECRET
        }
        
        response = requests.post(token_url, data=data)
        if response.status_code != 200:
            return False, f"Token refresh failed: {response.status_code} - {response.text}"
        
        token_data = response.json()
        
        # Update tokens
        tokens['access_token'] = token_data['access_token']
        
        # Calculate expiry time
        if 'expires_in' in token_data:
            expires_in = token_data['expires_in']
            expiry_time = datetime.now() + timedelta(seconds=expires_in)
            tokens['expiry_time'] = expiry_time.isoformat()
        
        # Save the updated tokens
        with open('dropbox_tokens.json', 'w') as f:
            json.dump(tokens, f, indent=2)
            
        # Update environment variables
        os.environ['DROPBOX_ACCESS_TOKEN'] = tokens['access_token']
        
        # Update config if possible
        try:
            import config
            config.DROPBOX_ACCESS_TOKEN = tokens['access_token']
            if 'expiry_time' in tokens:
                config.DROPBOX_TOKEN_EXPIRY = tokens['expiry_time']
        except (ImportError, AttributeError):
            pass
        
        return True, f"Token refreshed successfully, valid until {tokens.get('expiry_time', 'unknown')}"
        
    except Exception as e:
        return False, f"Error refreshing token: {e}"

def main():
    """Main function - check and refresh tokens if needed"""
    print("Checking Dropbox token status...")
    
    valid, message = check_token_status()
    print(f"Token status: {message}")
    
    if not valid:
        print("Refreshing tokens...")
        success, refresh_message = refresh_token()
        if success:
            print(f"Success: {refresh_message}")
            return 0
        else:
            print(f"Error: {refresh_message}")
            print("Unable to refresh token automatically")
            print("Run gen_dropbox_token.py --generate manually to set up")
            return 1
    else:
        print("Token is valid, no refresh needed")
        return 0

if __name__ == "__main__":
    sys.exit(main())
