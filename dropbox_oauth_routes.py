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
    
    # Try to use the token manager first
    try:
        from utils.token_manager import get_token_manager
        token_manager = get_token_manager()
        
        # Update the token manager with the new tokens
        if "access_token" in tokens:
            token_manager.access_token = tokens["access_token"]
        if "refresh_token" in tokens:
            token_manager.refresh_token = tokens["refresh_token"]
        if "expiry_time" in tokens:
            token_manager.expiry_time = tokens["expiry_time"]
            
        # Let the token manager save the tokens
        token_manager._save_tokens()
        logger.info("Tokens saved via token manager")
        return True
    except ImportError:
        logger.warning("Token manager not available, using direct file save")
    
    # Fallback to direct file save if token manager not available
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
        
        # Get token values (with defaults to prevent errors)
        access_token = tokens.get('access_token', 'No access token generated')
        refresh_token = tokens.get('refresh_token', 'No refresh token generated')
        expiry_time = tokens.get('expiry_time', 'Unknown')
        
        # Return token display page with copy buttons
        return f"""
        <html>
            <head>
                <title>Dropbox OAuth Tokens</title>
                <style>
                    body {{ font-family: monospace; margin: 50px; background-color: #f5f5f5; }}
                    .container {{ max-width: 800px; margin: 0 auto; background-color: white; padding: 30px; border-radius: 10px; box-shadow: 0 0 10px rgba(0,0,0,0.1); }}
                    h1 {{ color: #0061fe; margin-top: 0; text-align: center; }}
                    h2 {{ color: #666; margin-top: 30px; }}
                    .token-box {{ background-color: #f7f7f7; padding: 15px; border: 1px solid #ddd; border-radius: 5px; margin: 10px 0; overflow-wrap: break-word; word-break: break-all; font-size: 14px; }}
                    .token-label {{ font-weight: bold; color: #333; margin: 20px 0 5px 0; font-size: 16px; }}
                    .token-note {{ font-size: 12px; color: #666; margin-top: 5px; }}
                    .copy-btn {{ background-color: #0061fe; color: white; border: none; padding: 8px 15px; border-radius: 5px; cursor: pointer; margin-top: 10px; font-weight: bold; }}
                    .copy-btn:hover {{ background-color: #004dca; }}
                    .success-badge {{ display: inline-block; background-color: #4CAF50; color: white; padding: 8px 15px; border-radius: 20px; margin-bottom: 20px; }}
                </style>
                <script>
                    function copyToClipboard(elementId) {{
                        const element = document.getElementById(elementId);
                        const text = element.textContent;
                        navigator.clipboard.writeText(text).then(() => {{
                            const button = document.querySelector(`#${{elementId}}-container .copy-btn`);
                            const originalText = button.textContent;
                            button.textContent = 'Copied!';
                            button.style.backgroundColor = '#4CAF50';
                            setTimeout(() => {{
                                button.textContent = originalText;
                                button.style.backgroundColor = '#0061fe';
                            }}, 2000);
                        }});
                    }}
                </script>
            </head>
            <body>
                <div class="container">
                    <h1>Dropbox OAuth Tokens</h1>
                    <div style="text-align: center;"><span class="success-badge">Authentication Successful!</span></div>
                    
                    <div id="refresh-token-container">
                        <div class="token-label">REFRESH TOKEN:</div>
                        <div class="token-note">(Use this to hard-code in your application for generating new access tokens)</div>
                        <div id="refresh-token" class="token-box">{refresh_token}</div>
                        <button class="copy-btn" onclick="copyToClipboard('refresh-token')">Copy Refresh Token</button>
                    </div>
                    
                    <div id="access-token-container">
                        <div class="token-label">ACCESS TOKEN:</div>
                        <div class="token-note">(This is the current session token, expires in a few hours)</div>
                        <div id="access-token" class="token-box">{access_token}</div>
                        <button class="copy-btn" onclick="copyToClipboard('access-token')">Copy Access Token</button>
                    </div>
                    
                    <div>
                        <div class="token-label">EXPIRY TIME:</div>
                        <div class="token-box">{expiry_time}</div>
                    </div>
                    
                    <h2>Next Steps:</h2>
                    <p>These tokens have been saved to your application. You can now use the refresh token to update your configuration.</p>
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
    Check the status of Dropbox OAuth tokens and return them.
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
    
    # Get the actual tokens
    access_token = tokens.get("access_token", None)
    refresh_token = tokens.get("refresh_token", None)
    
    # Check if we have valid tokens
    has_access_token = "access_token" in tokens and tokens["access_token"]
    has_refresh_token = "refresh_token" in tokens and tokens["refresh_token"]
    
    # Check expiry time
    token_expired = False
    expires_in = None
    expiry_time = None
    if "expiry_time" in tokens:
        try:
            expiry_time = tokens["expiry_time"]
            expiry_dt = datetime.fromisoformat(expiry_time)
            if expiry_dt <= datetime.now():
                token_expired = True
            else:
                # Calculate remaining time
                remaining = expiry_dt - datetime.now()
                expires_in = remaining.total_seconds()
        except Exception as e:
            logger.error(f"Error checking token expiry: {e}")
    
    # Return plain tokens and status
    return jsonify({
        "access_token": access_token,
        "refresh_token": refresh_token,
        "has_access_token": has_access_token,
        "has_refresh_token": has_refresh_token,
        "token_expired": token_expired,
        "expiry_time": expiry_time,
        "expires_in_seconds": expires_in
    })
