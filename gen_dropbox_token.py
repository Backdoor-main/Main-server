#!/usr/bin/env python3
"""
Dropbox OAuth2 token generator script.

This script helps generate and refresh OAuth2 tokens for the Dropbox API
by walking through the OAuth2 flow. It saves the tokens and can be used
to refresh expired tokens.

Usage:
  python gen_dropbox_token.py --generate  # Generate new tokens
  python gen_dropbox_token.py --refresh   # Refresh existing tokens
  python gen_dropbox_token.py --check     # Check token status
"""

import os
import sys
import argparse
import json
from datetime import datetime

# Add the current directory to the path for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Import the OAuth2 utilities
try:
    from utils.dropbox_oauth import (
        generate_auth_url, exchange_code_for_tokens,
        refresh_access_token, save_token_info, load_token_info,
        is_token_valid, check_and_refresh_if_needed
    )
except ImportError:
    print("Error: Cannot import Dropbox OAuth utilities.")
    print("Make sure you're running this script from the project root directory.")
    sys.exit(1)

def generate_new_tokens(app_key, app_secret):
    """Generate new tokens through the OAuth2 flow."""
    # Generate the authorization URL
    auth_url = generate_auth_url(app_key)
    
    print("\n=== Dropbox OAuth2 Authorization ===")
    print("1. Go to this URL in your browser:")
    print(f"\n{auth_url}\n")
    print("2. Click 'Allow' to grant access to your Dropbox account")
    print("3. You'll be redirected to a URL. Copy the 'code' parameter from the URL")
    
    # Get the authorization code from the user
    auth_code = input("\nEnter the authorization code: ")
    
    if not auth_code:
        print("Error: No authorization code provided.")
        return False
    
    # Exchange the code for tokens
    print("\nExchanging authorization code for tokens...")
    tokens = exchange_code_for_tokens(app_key, app_secret, auth_code)
    
    if not tokens.get("success", False):
        print(f"Error: {tokens.get('error', 'Failed to exchange code for tokens')}")
        return False
    
    # Save the tokens
    token_file = "dropbox_tokens.json"
    save_token_info(tokens, token_file)
    
    print("\n=== Success! ===")
    print(f"Access Token: {tokens['access_token'][:10]}...{tokens['access_token'][-10:]}")
    if "refresh_token" in tokens:
        print(f"Refresh Token: {tokens['refresh_token'][:5]}...{tokens['refresh_token'][-5:]}")
    if "expiry_time" in tokens:
        print(f"Expires: {tokens['expiry_time']}")
    
    # Update the config.py file if it exists
    update_config_file(tokens)
    
    print(f"\nTokens saved to {token_file}")
    print("You can now use these tokens with the application.")
    
    return True

def refresh_tokens(app_key, app_secret):
    """Refresh an existing access token using a refresh token."""
    # Load existing tokens
    token_file = "dropbox_tokens.json"
    tokens = load_token_info(token_file)
    
    if not tokens:
        print(f"Error: No token file found at {token_file}")
        return False
    
    if "refresh_token" not in tokens:
        print("Error: No refresh token found in the token file.")
        return False
    
    # Refresh the access token
    print("Refreshing access token...")
    result = refresh_access_token(app_key, app_secret, tokens["refresh_token"])
    
    if not result.get("success", False):
        print(f"Error: {result.get('error', 'Failed to refresh token')}")
        return False
    
    # Update tokens with new access token and expiry
    tokens["access_token"] = result["access_token"]
    if "expiry_time" in result:
        tokens["expiry_time"] = result["expiry_time"]
    
    # Save the updated tokens
    save_token_info(tokens, token_file)
    
    # Update the config.py file
    update_config_file(tokens)
    
    print("\n=== Token Refreshed! ===")
    print(f"New Access Token: {tokens['access_token'][:10]}...{tokens['access_token'][-10:]}")
    if "expiry_time" in tokens:
        print(f"Expires: {tokens['expiry_time']}")
    
    print(f"\nUpdated tokens saved to {token_file}")
    
    return True

def check_token_status():
    """Check the status of the current tokens."""
    # Load existing tokens
    token_file = "dropbox_tokens.json"
    tokens = load_token_info(token_file)
    
    if not tokens:
        print(f"Error: No token file found at {token_file}")
        return False
    
    print("\n=== Token Status ===")
    
    # Print token details
    if "access_token" in tokens:
        print(f"Access Token: {tokens['access_token'][:10]}...{tokens['access_token'][-10:]}")
    else:
        print("Access Token: Not found")
    
    if "refresh_token" in tokens:
        print(f"Refresh Token: {tokens['refresh_token'][:5]}...{tokens['refresh_token'][-5:]}")
    else:
        print("Refresh Token: Not found")
    
    # Check expiry time
    if "expiry_time" in tokens:
        expiry_time = datetime.fromisoformat(tokens["expiry_time"])
        now = datetime.now()
        
        if expiry_time > now:
            time_left = expiry_time - now
            print(f"Expires in: {time_left.total_seconds() / 60:.1f} minutes")
        else:
            print("Status: EXPIRED")
    else:
        print("Expiry Time: Unknown")
    
    # Check if the access token is still valid
    if "access_token" in tokens:
        valid = is_token_valid(tokens["access_token"])
        print(f"Token Valid: {'Yes' if valid else 'No'}")
    
    print("\nTo refresh the token, run: python gen_dropbox_token.py --refresh")
    
    return True

def update_config_file(tokens):
    """Update the config.py file with the new tokens."""
    config_file = "config.py"
    
    if not os.path.exists(config_file):
        print(f"Warning: {config_file} not found. Skipping config update.")
        return False
    
    try:
        with open(config_file, 'r') as f:
            config_lines = f.readlines()
        
        # Update the token values in the config file
        updated_lines = []
        access_token_updated = False
        refresh_token_updated = False
        expiry_updated = False
        
        for line in config_lines:
            if "DROPBOX_ACCESS_TOKEN" in line and "=" in line and not access_token_updated:
                updated_lines.append(f'DROPBOX_ACCESS_TOKEN = os.getenv("DROPBOX_ACCESS_TOKEN", "{tokens["access_token"]}")\n')
                access_token_updated = True
            elif "DROPBOX_REFRESH_TOKEN" in line and "=" in line and not refresh_token_updated and "refresh_token" in tokens:
                updated_lines.append(f'DROPBOX_REFRESH_TOKEN = os.getenv("DROPBOX_REFRESH_TOKEN", "{tokens["refresh_token"]}")\n')
                refresh_token_updated = True
            elif "DROPBOX_TOKEN_EXPIRY" in line and "=" in line and not expiry_updated and "expiry_time" in tokens:
                updated_lines.append(f'DROPBOX_TOKEN_EXPIRY = os.getenv("DROPBOX_TOKEN_EXPIRY", "{tokens["expiry_time"]}")\n')
                expiry_updated = True
            else:
                updated_lines.append(line)
        
        # Write the updated config file
        with open(config_file, 'w') as f:
            f.writelines(updated_lines)
        
        print(f"Updated {config_file} with new token values.")
        return True
        
    except Exception as e:
        print(f"Error updating config file: {e}")
        return False

def main():
    """Main function to parse arguments and run the appropriate action."""
    parser = argparse.ArgumentParser(description='Dropbox OAuth2 Token Generator')
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--generate', action='store_true', help='Generate new tokens')
    group.add_argument('--refresh', action='store_true', help='Refresh existing tokens')
    group.add_argument('--check', action='store_true', help='Check token status')
    
    args = parser.parse_args()
    
    # Get app key and secret from environment or config
    app_key = os.getenv("DROPBOX_APP_KEY")
    app_secret = os.getenv("DROPBOX_APP_SECRET")
    
    # Try to get from config if not in environment
    if not app_key or not app_secret:
        try:
            import config
            app_key = getattr(config, "DROPBOX_APP_KEY", app_key)
            app_secret = getattr(config, "DROPBOX_APP_SECRET", app_secret)
        except ImportError:
            pass
    
    # Prompt for app key and secret if not found
    if not app_key:
        app_key = input("Enter your Dropbox App Key: ")
    if not app_secret:
        app_secret = input("Enter your Dropbox App Secret: ")
    
    if not app_key or not app_secret:
        print("Error: App Key and App Secret are required.")
        return 1
    
    # Run the requested action
    if args.generate:
        success = generate_new_tokens(app_key, app_secret)
    elif args.refresh:
        success = refresh_tokens(app_key, app_secret)
    elif args.check:
        success = check_token_status()
    
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())
