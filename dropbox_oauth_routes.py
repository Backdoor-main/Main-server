"""
Dropbox OAuth routes for Flask application.

This module provides routes for the Dropbox OAuth flow:
- An initiation route that redirects to Dropbox for authorization
- A callback route that handles the OAuth code exchange
- Helper functions for token management
"""

from flask import Blueprint, request, redirect, url_for, jsonify, current_app
import os
import json
import logging
from datetime import datetime, timedelta
import requests

# Create logger
logger = logging.getLogger(__name__)

# Create blueprint
dropbox_oauth = Blueprint('dropbox_oauth', __name__)

def get_app_base_url():
    """Get the base URL for the application based on environment."""
    if os.environ.get('RENDER'):
        # Render.com service
        render_service_name = os.environ.get('RENDER_SERVICE_NAME', 'backdoor-ai')
        return f"https://{render_service_name}.onrender.com"
    else:
        # Local development
        return "http://localhost:10000"

def get_redirect_uri():
    """Get the full redirect URI for the OAuth callback."""
    base_url = get_app_base_url()
    return f"{base_url}/oauth/dropbox/callback"

def get_app_credentials():
    """Get the app key and secret from config or environment."""
    try:
        import config
        app_key = getattr(config, 'DROPBOX_APP_KEY', None)
        app_secret = getattr(config, 'DROPBOX_APP_SECRET', None)
    except ImportError:
        app_key = None
        app_secret = None
    
    # Fall back to environment variables
    app_key = app_key or os.environ.get('DROPBOX_APP_KEY')
    app_secret = app_secret or os.environ.get('DROPBOX_APP_SECRET')
    
    return app_key, app_secret

def save_tokens(tokens):
    """Save tokens to file and update config."""
    # Create a sanitized version for logging
    safe_tokens = tokens.copy()
    if "access_token" in safe_tokens:
        token = safe_tokens["access_token"]
        if token and len(token) > 20:
            safe_tokens["access_token"] = f"{token[:10]}...{token[-10:]}"
    if "refresh_token" in safe_tokens:
        token = safe_tokens["refresh_token"]
        if token and len(token) > 10:
            safe_tokens["refresh_token"] = f"{token[:5]}...{token[-5:]}"
    
    # Log token info (sanitized)
    logger.info(f"Saving tokens: {json.dumps(safe_tokens)}")
    
    # Save to file
    token_file = "dropbox_tokens.json"
    try:
        with open(token_file, 'w') as f:
            json.dump(tokens, f, indent=2)
        logger.info(f"Tokens saved to {token_file}")
    except Exception as e:
        logger.error(f"Error saving tokens to file: {e}")
    
    # Update environment variables
    if "access_token" in tokens:
        os.environ["DROPBOX_ACCESS_TOKEN"] = tokens["access_token"]
    if "refresh_token" in tokens:
        os.environ["DROPBOX_REFRESH_TOKEN"] = tokens["refresh_token"]
    
    # Update config module
    try:
        import config
        if "access_token" in tokens:
            config.DROPBOX_ACCESS_TOKEN = tokens["access_token"]
        if "refresh_token" in tokens:
            config.DROPBOX_REFRESH_TOKEN = tokens["refresh_token"]
        if "expiry_time" in tokens:
            config.DROPBOX_TOKEN_EXPIRY = tokens["expiry_time"]
        logger.info("Updated config with new tokens")
    except (ImportError, AttributeError) as e:
        logger.warning(f"Could not update config: {e}")
    
    return True

@dropbox_oauth.route('/oauth/dropbox/authorize')
def authorize():
    """
    Start the OAuth flow by redirecting to Dropbox.
    """
    app_key, app_secret = get_app_credentials()
    if not app_key or not app_secret:
        return jsonify({
            "error": "Missing app credentials",
            "message": "Dropbox app key and secret are required"
        }), 400
    
    # Get the redirect URI
    redirect_uri = get_redirect_uri()
    
    # Generate the auth URL
    auth_url = (
        f"https://www.dropbox.com/oauth2/authorize?"
        f"client_id={app_key}&"
        f"response_type=code&"
        f"redirect_uri={redirect_uri}&"
        f"token_access_type=offline"  # Request refresh token
    )
    
    logger.info(f"Redirecting to Dropbox authorization: {auth_url}")
    return redirect(auth_url)

@dropbox_oauth.route('/oauth/dropbox/callback')
def callback():
    """
    Handle the callback from Dropbox after authorization.
    """
    # Get the authorization code
    auth_code = request.args.get('code')
    if not auth_code:
        logger.error("No authorization code in callback")
        return jsonify({
            "error": "Missing authorization code",
            "message": "No code parameter in callback"
        }), 400
    
    # Get app credentials
    app_key, app_secret = get_app_credentials()
    if not app_key or not app_secret:
        return jsonify({
            "error": "Missing app credentials",
            "message": "Dropbox app key and secret are required"
        }), 400
    
    # Get the redirect URI
    redirect_uri = get_redirect_uri()
    
    # Exchange code for tokens
    token_url = "https://api.dropboxapi.com/oauth2/token"
    data = {
        "code": auth_code,
        "grant_type": "authorization_code",
        "client_id": app_key,
        "client_secret": app_secret,
        "redirect_uri": redirect_uri
    }
    
    try:
        logger.info("Exchanging authorization code for tokens")
        response = requests.post(token_url, data=data)
        response.raise_for_status()
        token_data = response.json()
        
        # Calculate expiry time
        if "expires_in" in token_data:
            expires_in = token_data["expires_in"]
            expiry_time = datetime.now() + timedelta(seconds=expires_in)
            token_data["expiry_time"] = expiry_time.isoformat()
        
        # Create tokens dict
        tokens = {
            "access_token": token_data.get("access_token"),
            "refresh_token": token_data.get("refresh_token"),
            "expiry_time": token_data.get("expiry_time"),
            "account_id": token_data.get("account_id")
        }
        
        # Save tokens
        save_tokens(tokens)
        
        # Return success page
        return f"""
        <html>
            <head>
                <title>Dropbox Authorization Successful</title>
                <style>
                    body {{ font-family: Arial, sans-serif; margin: 50px; }}
                    .success {{ color: green; }}
                    .container {{ max-width: 600px; margin: 0 auto; }}
                </style>
            </head>
            <body>
                <div class="container">
                    <h1 class="success">Authorization Successful!</h1>
                    <p>Your Dropbox account has been successfully connected.</p>
                    <p>You can now close this window and return to your application.</p>
                    <h2>Token Information</h2>
                    <ul>
                        <li>Access Token: {tokens['access_token'][:10]}...{tokens['access_token'][-10:]}</li>
                        <li>Refresh Token: {tokens['refresh_token'][:5]}...{tokens['refresh_token'][-5:]}</li>
                        <li>Expiry: {tokens.get('expiry_time', 'Unknown')}</li>
                    </ul>
                    <p>Your application is now configured to use Dropbox storage.</p>
                </div>
            </body>
        </html>
        """
        
    except Exception as e:
        logger.error(f"Error exchanging code for tokens: {e}")
        return jsonify({
            "error": "Token exchange failed",
            "message": str(e)
        }), 500

@dropbox_oauth.route('/oauth/dropbox/status')
def status():
    """
    Check the status of Dropbox OAuth tokens.
    """
    # Try to load tokens from file
    token_file = "dropbox_tokens.json"
    tokens = {}
    try:
        if os.path.exists(token_file):
            with open(token_file, 'r') as f:
                tokens = json.load(f)
    except Exception as e:
        logger.error(f"Error loading tokens: {e}")
    
    # Check if we have valid tokens
    has_access_token = "access_token" in tokens and tokens["access_token"]
    has_refresh_token = "refresh_token" in tokens and tokens["refresh_token"]
    
    # Check expiry time
    token_expired = False
    expires_in = None
    if "expiry_time" in tokens:
        try:
            expiry_time = datetime.fromisoformat(tokens["expiry_time"])
            if expiry_time <= datetime.now():
                token_expired = True
            else:
                # Calculate remaining time
                remaining = expiry_time - datetime.now()
                expires_in = remaining.total_seconds()
        except Exception as e:
            logger.error(f"Error checking token expiry: {e}")
    
    # Get redirect URI
    redirect_uri = get_redirect_uri()
    
    return jsonify({
        "has_access_token": has_access_token,
        "has_refresh_token": has_refresh_token,
        "token_expired": token_expired,
        "expires_in_seconds": expires_in,
        "redirect_uri": redirect_uri,
        "authorize_url": url_for('dropbox_oauth.authorize', _external=True)
    })
