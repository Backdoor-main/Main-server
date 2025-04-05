#!/usr/bin/env python3
"""
Simple script to add a Dropbox refresh token to your configuration.

Usage:
    python add_refresh_token.py YOUR_REFRESH_TOKEN

This script updates config.py and creates a tokens file with your refresh token.
"""

import os
import sys
import json
from datetime import datetime, timedelta

def update_config_with_token(refresh_token):
    """
    Update config.py with the provided refresh token.
    
    Args:
        refresh_token: The refresh token to add
        
    Returns:
        bool: True if successful
    """
    config_file = "config.py"
    
    if not os.path.exists(config_file):
        print(f"Error: {config_file} not found.")
        return False
    
    try:
        # Read the current config file
        with open(config_file, 'r') as f:
            config_lines = f.readlines()
        
        # Update the token values in the config file
        updated_lines = []
        refresh_token_updated = False
        
        for line in config_lines:
            if "DROPBOX_REFRESH_TOKEN" in line and "=" in line and not refresh_token_updated:
                updated_lines.append(f'DROPBOX_REFRESH_TOKEN = os.getenv("DROPBOX_REFRESH_TOKEN", "{refresh_token}")\n')
                refresh_token_updated = True
            else:
                updated_lines.append(line)
        
        # If DROPBOX_REFRESH_TOKEN not found, append it
        if not refresh_token_updated:
            # Find dropbox section
            dropbox_section_end = -1
            for i, line in enumerate(updated_lines):
                if "DROPBOX_" in line and i > dropbox_section_end:
                    dropbox_section_end = i
            
            if dropbox_section_end >= 0:
                # Insert after the last DROPBOX setting
                updated_lines.insert(dropbox_section_end + 1, f'DROPBOX_REFRESH_TOKEN = os.getenv("DROPBOX_REFRESH_TOKEN", "{refresh_token}")\n')
            else:
                # Just append to the end
                updated_lines.append(f'\n# Dropbox OAuth settings\nDROPBOX_REFRESH_TOKEN = os.getenv("DROPBOX_REFRESH_TOKEN", "{refresh_token}")\n')
        
        # Write the updated config file
        with open(config_file, 'w') as f:
            f.writelines(updated_lines)
        
        print(f"Updated {config_file} with refresh token.")
        return True
        
    except Exception as e:
        print(f"Error updating config file: {e}")
        return False

def create_token_file(refresh_token):
    """
    Create a token file with the refresh token.
    
    Args:
        refresh_token: The refresh token to save
        
    Returns:
        bool: True if successful
    """
    token_file = "dropbox_tokens.json"
    
    try:
        # Create a minimal token file with just the refresh token
        tokens = {
            "refresh_token": refresh_token,
            "expiry_time": (datetime.now() + timedelta(days=90)).isoformat()
        }
        
        with open(token_file, 'w') as f:
            json.dump(tokens, f, indent=2)
        
        print(f"Created {token_file} with refresh token.")
        return True
        
    except Exception as e:
        print(f"Error creating token file: {e}")
        return False

def main():
    """Main function."""
    # Check if we have a refresh token argument
    if len(sys.argv) < 2:
        print("Usage: python add_refresh_token.py YOUR_REFRESH_TOKEN")
        return 1
    
    refresh_token = sys.argv[1]
    
    # Validate refresh token format (basic check)
    if len(refresh_token) < 20:
        print("Error: Refresh token looks too short. Please provide a valid refresh token.")
        return 1
    
    # Update config.py
    config_updated = update_config_with_token(refresh_token)
    
    # Create token file
    token_file_created = create_token_file(refresh_token)
    
    if config_updated and token_file_created:
        print("Refresh token successfully added to your application.")
        # Make sure Dropbox is enabled
        print("\nNext steps:")
        print("1. Make sure DROPBOX_ENABLED = True in your config.py")
        print("2. Restart your application to use the new token")
        return 0
    else:
        print("There were some issues with adding the refresh token.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
