#!/bin/bash
set -e

# Dropbox Token Auto-Refresh Script
# This script automatically refreshes the Dropbox OAuth2 tokens
# during application startup using the app key and secret.

echo "Checking Dropbox token status..."

# App credentials - hardcoded but can be overridden with environment variables
APP_KEY=${DROPBOX_APP_KEY:-"2bi422xpd3xd962"}
APP_SECRET=${DROPBOX_APP_SECRET:-"j3yx0b41qdvfu86"}

# Check if we need to refresh the token
NEED_REFRESH=false

# Check if we have existing tokens
if [ -f "dropbox_tokens.json" ]; then
    echo "Found existing token file"
    
    # Check if tokens need refreshing using Python
    REFRESH_CHECK=$(python -c "
import json
import datetime
try:
    with open('dropbox_tokens.json', 'r') as f:
        tokens = json.load(f)
    
    if 'refresh_token' not in tokens:
        print('No refresh token found, need full OAuth flow')
        exit(1)

    if 'expiry_time' in tokens:
        expiry = datetime.datetime.fromisoformat(tokens['expiry_time'])
        now = datetime.datetime.now()
        if expiry <= now:
            print('Token expired, needs refresh')
            exit(1)
        else:
            # Calculate remaining time
            remaining = expiry - now
            print(f'Token valid for {remaining.total_seconds()/60:.1f} minutes')
            exit(0)
    else:
        print('No expiry time found, assuming refresh needed')
        exit(1)
except Exception as e:
    print(f'Error checking token: {e}')
    exit(1)
" 2>/dev/null)

    # Check the result
    if [ $? -ne 0 ]; then
        echo "Token needs refreshing: $REFRESH_CHECK"
        NEED_REFRESH=true
    else
        echo "Token status: $REFRESH_CHECK"
    fi
else
    echo "No existing token file found, will attempt to create new tokens"
    NEED_REFRESH=true
fi

# Refresh the token if needed
if [ "$NEED_REFRESH" = true ]; then
    echo "Refreshing Dropbox tokens..."

    # Use our token generator script in 'headless' mode
    # This requires a valid refresh_token already in the config or token file
    python -c "
import sys
import os
import json
import datetime
import requests

# Don't need to modify path for imports in inline code
# Just use direct imports when needed

# App credentials
app_key = '$APP_KEY'
app_secret = '$APP_SECRET'

try:
    # Try to load existing tokens first
    refresh_token = None
    try:
        # Try token file first
        if os.path.exists('dropbox_tokens.json'):
            with open('dropbox_tokens.json', 'r') as f:
                tokens = json.load(f)
                if 'refresh_token' in tokens:
                    refresh_token = tokens['refresh_token']
                    print('Using refresh token from token file')
    except Exception as e:
        print(f'Error loading token file: {e}')

    # Try config if no token file
    if not refresh_token:
        try:
            import config
            if hasattr(config, 'DROPBOX_REFRESH_TOKEN') and config.DROPBOX_REFRESH_TOKEN:
                refresh_token = config.DROPBOX_REFRESH_TOKEN
                print('Using refresh token from config')
        except (ImportError, AttributeError):
            pass

    # If we have a refresh token, use it to get a new access token
    if refresh_token:
        print('Refreshing access token...')
        
        # Get a new access token using the refresh token
        token_url = 'https://api.dropboxapi.com/oauth2/token'
        data = {
            'grant_type': 'refresh_token',
            'refresh_token': refresh_token,
            'client_id': app_key,
            'client_secret': app_secret
        }
        
        response = requests.post(token_url, data=data)
        if response.status_code == 200:
            token_data = response.json()
            access_token = token_data['access_token']
            
            # Calculate expiry time
            expires_in = token_data.get('expires_in', 14400)  # Default 4 hours
            expiry_time = datetime.datetime.now() + datetime.timedelta(seconds=expires_in)
            expiry_iso = expiry_time.isoformat()
            
            # Update the tokens file
            tokens = {
                'access_token': access_token,
                'refresh_token': refresh_token,
                'expiry_time': expiry_iso
            }
            with open('dropbox_tokens.json', 'w') as f:
                json.dump(tokens, f, indent=2)
            
            # Update environment variables
            os.environ['DROPBOX_ACCESS_TOKEN'] = access_token
            
            # Try to update config module as well
            try:
                import config
                config.DROPBOX_ACCESS_TOKEN = access_token
                print('Updated config.DROPBOX_ACCESS_TOKEN with new token')
            except (ImportError, AttributeError):
                pass
            
            print(f'Successfully refreshed access token (expires: {expiry_iso})')
            print(f'Token: {access_token[:10]}...{access_token[-10:]}')
            exit(0)
        else:
            print(f'Error refreshing token: {response.status_code} - {response.text}')
            exit(1)
    else:
        print('No refresh token available, cannot refresh automatically')
        exit(1)
except Exception as e:
    print(f'Error refreshing token: {e}')
    exit(1)
"

    # Check the result
    if [ $? -ne 0 ]; then
        echo "Warning: Failed to refresh Dropbox token automatically"
        echo "Using existing token or falling back to local storage"
    else
        echo "Dropbox token refresh successful!"
    fi
fi

# Make sure the script exits successfully even if token refresh failed
# The application should fall back to local storage in that case
exit 0
