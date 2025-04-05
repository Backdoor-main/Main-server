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
import logging
from pathlib import Path

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger(__name__)

# App credentials - can be overridden by environment variables
APP_KEY = os.getenv("DROPBOX_APP_KEY", "2bi422xpd3xd962")
APP_SECRET = os.getenv("DROPBOX_APP_SECRET", "j3yx0b41qdvfu86")

# Ensure we have valid credentials
if not APP_KEY or APP_KEY == "YOUR_APP_KEY":
    logger.error("Invalid APP_KEY. Please set DROPBOX_APP_KEY environment variable.")
    APP_KEY = "2bi422xpd3xd962"  # Fallback to hardcoded value

if not APP_SECRET or APP_SECRET == "YOUR_APP_SECRET":
    logger.error("Invalid APP_SECRET. Please set DROPBOX_APP_SECRET environment variable.")
    APP_SECRET = "j3yx0b41qdvfu86"  # Fallback to hardcoded value

# Attempt to also create a dummy refresh token if we don't have one
# This will let us get a real one
INITIAL_REFRESH_TOKEN = "dummy_refresh_token_for_app_auth"

def generate_new_tokens():
    """
    Create placeholder token file and provide OAuth setup instructions.
    
    Automatic token generation without user interaction is not reliable,
    so we create a placeholder and provide instructions instead.
    
    Returns:
        tuple: (success, message)
    """
    logger.info("Automatic token generation not possible - providing setup guidance")
    
    try:
        # Check if app key and secret are valid
        if not APP_KEY or APP_KEY == "YOUR_APP_KEY" or not APP_SECRET or APP_SECRET == "YOUR_APP_SECRET":
            logger.error(
                "Invalid app credentials. Please set up proper Dropbox app credentials. "
                "See SETUP_DROPBOX.md for instructions, or run gen_dropbox_token.py --generate "
                "to set up proper OAuth tokens."
            )
            return False, "Invalid app credentials"
        
        # Create a placeholder file with instructions
        tokens = {
            "app_key": APP_KEY,
            "app_secret": APP_SECRET,
            "needs_auth": True,
            "instructions": "Run gen_dropbox_token.py --generate to complete OAuth setup",
            "created_at": datetime.datetime.now().isoformat()
        }
        
        # Try to save to both standard location and /tmp as backup
        saved = False
        for path in [Path("dropbox_tokens.json"), Path("/tmp/dropbox_tokens.json")]:
            try:
                with open(path, "w") as f:
                    json.dump(tokens, f, indent=2)
                logger.info(f"Created placeholder token file at {path}")
                saved = True
            except Exception as e:
                logger.warning(f"Could not save token placeholder to {path}: {e}")
        
        if not saved:
            logger.warning("Could not save token placeholder file to any location")
        
        # Log clear instructions
        logger.warning(
            "\n==== DROPBOX AUTHENTICATION SETUP REQUIRED ====\n"
            "Automatic token generation is not possible without user interaction.\n"
            "To properly set up Dropbox integration:\n"
            "1. Run: python gen_dropbox_token.py --generate\n"
            "2. Follow the prompts to authorize the application\n"
            "3. This will generate the proper OAuth tokens needed for Dropbox access\n"
            "==== APPLICATION WILL USE LOCAL STORAGE UNTIL SETUP IS COMPLETE ====\n"
        )
        
        return False, "Automatic token generation not possible, manual setup required"
        
    except Exception as e:
        logger.error(f"Error creating token placeholder: {e}")
        return False, f"Error creating token placeholder: {e}"

def create_token_dir():
    """Create directory for token file if it doesn't exist."""
    try:
        # Try both the current directory and /tmp
        paths = [Path("."), Path("/tmp")]
        
        for path in paths:
            try:
                if not path.exists():
                    path.mkdir(parents=True)
                return path
            except Exception:
                continue
                
        # If we can't create directories, just return current directory
        return Path(".")
    except Exception as e:
        logger.error(f"Error creating token directory: {e}")
        return Path(".")

def refresh_token():
    """
    Check token status and refresh if needed.
    
    Returns:
        tuple: (success, message)
    """
    logger.info("Checking Dropbox token status...")
    
    # Make sure we have a place to store tokens
    token_dir = create_token_dir()
    token_path = token_dir / "dropbox_tokens.json"
    
    # Check if we have a token file
    if not token_path.exists():
        logger.info(f"No token file found at {token_path}")
        
        # Try loading from config first
        config_result = load_from_config()
        if config_result[0]:
            return config_result
            
        # If config didn't work, try generating new tokens
        return generate_new_tokens()
    
    # Load tokens from file
    try:
        with open(token_path, "r") as f:
            tokens = json.load(f)
        
        # Check if we have a refresh token
        if "refresh_token" not in tokens:
            logger.info("No refresh token found in token file")
            
            # Try config first
            config_result = load_from_config()
            if config_result[0]:
                return config_result
                
            # If that fails, try with app credentials
            return generate_new_tokens()
        
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
                    logger.info(f"Token valid for {minutes:.1f} minutes")
                    
                    # Update environment with existing token
                    if "access_token" in tokens:
                        os.environ["DROPBOX_ACCESS_TOKEN"] = tokens["access_token"]
                        
                        # Try to update config module
                        try:
                            import config
                            config.DROPBOX_ACCESS_TOKEN = tokens["access_token"]
                            logger.info("Updated config module with existing token")
                        except Exception:
                            pass
                    
                    return True, f"Token valid for {minutes:.1f} minutes"
            except (ValueError, TypeError):
                pass
        
        # If we get here, we need to refresh the token
        logger.info("Refreshing access token...")
        return refresh_access_token(refresh_token)
    
    except Exception as e:
        logger.error(f"Error checking token file: {e}")
        
        # Try config first
        config_result = load_from_config()
        if config_result[0]:
            return config_result
            
        # If config doesn't have it, try app credentials
        return generate_new_tokens()

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
                logger.info("Using refresh token from config")
                return refresh_access_token(config.DROPBOX_REFRESH_TOKEN)
                
        # If no refresh token but there is an access token, try using that
        if hasattr(config, "DROPBOX_ACCESS_TOKEN") and config.DROPBOX_ACCESS_TOKEN:
            if config.DROPBOX_ACCESS_TOKEN != "YOUR_ACCESS_TOKEN":
                logger.info("Using access token from config")
                
                # Store it in environment
                os.environ["DROPBOX_ACCESS_TOKEN"] = config.DROPBOX_ACCESS_TOKEN
                
                # Create token file with access token and dummy refresh token
                try:
                    tokens = {
                        "access_token": config.DROPBOX_ACCESS_TOKEN,
                        "refresh_token": INITIAL_REFRESH_TOKEN,
                        "expiry_time": (datetime.datetime.now() + datetime.timedelta(hours=1)).isoformat()
                    }
                    
                    with open("dropbox_tokens.json", "w") as f:
                        json.dump(tokens, f, indent=2)
                        
                    logger.info("Created token file from config access token")
                except Exception as e:
                    logger.error(f"Error creating token file: {e}")
                
                return True, "Using access token from config"
    except Exception as e:
        logger.error(f"Error loading from config: {e}")
    
    logger.warning("No refresh token available in config, will try app credentials")
    return False, "No refresh token available in config"

def refresh_access_token(refresh_token):
    """
    Refresh an access token using the refresh token.
    
    Args:
        refresh_token: The refresh token to use
        
    Returns:
        tuple: (success, message)
    """
    try:
        # Check for invalid refresh tokens
        if not refresh_token or refresh_token == "YOUR_REFRESH_TOKEN" or refresh_token == INITIAL_REFRESH_TOKEN:
            logger.warning("Invalid or dummy refresh token - cannot refresh automatically")
            return generate_new_tokens()  # Will provide setup instructions
        
        # Validate token format
        if len(refresh_token) < 10:
            logger.error("Refresh token is too short")
            return generate_new_tokens()
            
        # Get a new access token
        token_url = "https://api.dropboxapi.com/oauth2/token"
        data = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": APP_KEY,
            "client_secret": APP_SECRET
        }
        
        logger.info(f"Refreshing token with client_id={APP_KEY}")
        logger.debug(f"Refresh token (first 5 chars): {refresh_token[:5] if len(refresh_token) > 5 else 'too_short'}")
        
        response = requests.post(token_url, data=data)
        logger.debug(f"Token refresh response: {response.status_code}")
        
        if response.status_code != 200:
            logger.error(f"Token refresh failed: {response.status_code} - {response.text}")
            
            # Provide more helpful guidance based on error
            if "invalid_grant" in response.text:
                logger.error(
                    "Refresh token is invalid or expired. You need to run the full OAuth flow. "
                    "Run gen_dropbox_token.py --generate to set up new tokens."
                )
            elif "malformed" in response.text:
                logger.error(
                    "Refresh token is malformed. The token format is incorrect. "
                    "Run gen_dropbox_token.py --generate to generate proper tokens."
                )
            elif "invalid_request" in response.text:
                logger.error(
                    "Invalid request format. Check app key and app secret. "
                    "Run gen_dropbox_token.py --generate to ensure all credentials are correct."
                )
                
            # Return to manual setup guidance
            return generate_new_tokens()
        
        # Parse response
        token_data = response.json()
        access_token = token_data["access_token"]
        
        # Calculate expiry time
        expires_in = token_data.get("expires_in", 14400)  # Default 4 hours
        expiry_time = datetime.datetime.now() + datetime.timedelta(seconds=expires_in)
        expiry_iso = expiry_time.isoformat()
        
        # Update tokens file - try both current directory and /tmp
        tokens = {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "expiry_time": expiry_iso
        }
        
        # Try saving to both locations
        saved = False
        for path in [Path("dropbox_tokens.json"), Path("/tmp/dropbox_tokens.json")]:
            try:
                with open(path, "w") as f:
                    json.dump(tokens, f, indent=2)
                logger.info(f"Saved tokens to {path}")
                saved = True
            except Exception as e:
                logger.warning(f"Could not save tokens to {path}: {e}")
        
        if not saved:
            logger.warning("Could not save tokens to any location")
        
        # Update environment
        os.environ["DROPBOX_ACCESS_TOKEN"] = access_token
        
        # Try to update config module
        try:
            import config
            config.DROPBOX_ACCESS_TOKEN = access_token
            config.DROPBOX_TOKEN_EXPIRY = expiry_iso
            logger.info("Updated config module with new token")
        except Exception:
            pass
        
        logger.info(f"Successfully refreshed access token (expires: {expiry_iso})")
        mask_token = f"{access_token[:10]}...{access_token[-10:]}"
        logger.info(f"Token: {mask_token}")
        return True, f"Token refreshed successfully (expires: {expiry_iso})"
        
    except Exception as e:
        logger.error(f"Error refreshing token: {e}")
        
        # If refresh fails for any reason, try app credentials
        logger.info("Trying app credentials as fallback")
        return generate_new_tokens()

def create_direct_token():
    """
    Create a token directly using app authentication.
    This should work even without a refresh token.
    
    Returns:
        tuple: (success, message)
    """
    try:
        logger.info("Attempting direct app authentication...")
        
        # Try to use API token auth instead of OAuth flow
        import dropbox
        try:
            # Create a token for app authentication (app key + app secret)
            app_auth = f"{APP_KEY}:{APP_SECRET}"
            
            # Try to use app auth
            dbx = dropbox.Dropbox(app_auth)
            account = dbx.users_get_current_account()
            
            logger.info(f"Successfully authenticated as app: {account.email}")
            
            # Save this token
            token_path = Path("dropbox_tokens.json")
            tokens = {
                "access_token": app_auth,
                "refresh_token": INITIAL_REFRESH_TOKEN,
                "expiry_time": (datetime.datetime.now() + datetime.timedelta(hours=24)).isoformat()
            }
            
            with open(token_path, "w") as f:
                json.dump(tokens, f, indent=2)
            
            # Update environment
            os.environ["DROPBOX_ACCESS_TOKEN"] = app_auth
            
            # Try to update config
            try:
                import config
                config.DROPBOX_ACCESS_TOKEN = app_auth
                logger.info("Updated config module with app auth token")
            except Exception:
                pass
                
            return True, "Created app auth token successfully"
            
        except Exception as e:
            logger.error(f"Error with app authentication: {e}")
            return False, f"App authentication failed: {e}"
            
    except Exception as e:
        logger.error(f"Error creating direct token: {e}")
        return False, f"Error creating direct token: {e}"

def main():
    """Run the token refresh process."""
    logger.info("======== Dropbox Token Refresh Tool ========")
    logger.info(f"App Key: {APP_KEY[:4]}... App Secret: {APP_SECRET[:4]}...")
    
    # Check for built-in OAuth routes and provide guidance
    import sys  # Ensure sys is imported
    
    # Provide instructions for proper setup
    # Check if we're running in a web app context
    render_service_name = os.environ.get('RENDER_SERVICE_NAME')
    if render_service_name:
        oauth_url = f"https://{render_service_name}.onrender.com/oauth/dropbox/authorize"
        setup_url = f"https://{render_service_name}.onrender.com/dropbox-setup"
        logger.info(
            "NOTE: This application has built-in OAuth support!\n"
            f"Visit {setup_url} for setup instructions\n"
            f"Then visit {oauth_url} to complete the OAuth flow."
        )
    else:
        logger.info(
            "NOTE: For proper Dropbox authentication with OAuth tokens, you should run:\n"
            "    python gen_dropbox_token.py --generate\n"
            "This script will walk you through the OAuth authorization process."
        )
    
    # Try normal refresh
    success, message = refresh_token()
    
    if not success:
        logger.warning(f"Token refresh failed: {message}")
        
        # Don't try direct app auth anymore as it doesn't work reliably
        if render_service_name:
            # If we're on Render, suggest using the web OAuth flow
            logger.info(
                f"Please use the web OAuth flow by visiting {oauth_url}\n"
                "This will properly set up your authentication tokens."
            )
        # Check if fix script exists and recommend it
        elif os.path.exists("fix_dropbox_auth.sh"):
            logger.info(
                "You can try running the fix script to reset and repair your tokens:\n"
                "    bash fix_dropbox_auth.sh"
            )
    else:
        logger.info(f"Success: {message}")
        
    # Always return success to not block startup
    logger.info("Continuing with existing token or local storage")
    logger.info("==============================================")
    return 0

if __name__ == "__main__":
    sys.exit(main())
