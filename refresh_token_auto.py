#!/usr/bin/env python3
"""
Automatic token refresh utility for Dropbox integration.

This script uses the centralized token manager to refresh
tokens automatically when they expire.
"""

import os
import sys
import logging
import json
from datetime import datetime, timedelta

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger(__name__)

def main():
    """
    Main function to check and refresh token if needed.
    
    Returns:
        int: 0 if successful, 1 if error
    """
    logger.info("======== Automatic Token Refresh ========")
    
    try:
        # Import the token manager
        from utils.token_manager import get_token_manager
        
        # Get the token manager instance
        token_manager = get_token_manager()
        
        # Check token status
        token_info = token_manager.get_token_info()
        
        if token_info["has_refresh_token"]:
            logger.info("Refresh token found")
            
            if token_info["token_expired"] or not token_info["has_access_token"]:
                logger.info("Access token expired or missing - refreshing")
                success = token_manager.refresh_token_if_needed()
                
                if success:
                    logger.info("Successfully refreshed access token")
                    # Save updated token to config
                    try:
                        import config
                        config.DROPBOX_ACCESS_TOKEN = token_manager.access_token
                        config.DROPBOX_TOKEN_EXPIRY = token_manager.expiry_time
                        logger.info("Updated config with new token")
                    except (ImportError, AttributeError):
                        pass
                    return 0
                else:
                    logger.error("Failed to refresh access token")
                    return 1
            else:
                expires_in = token_info.get("expires_in_seconds", 0)
                if expires_in:
                    logger.info(f"Access token valid for {expires_in:.1f} more seconds")
                else:
                    logger.info("Access token appears to be valid")
                return 0
        else:
            logger.error("No refresh token available")
            logger.error("Please set up OAuth by running setup_oauth.py with your refresh token")
            return 1
            
    except ImportError:
        logger.error("Could not import token manager - please check installation")
        return 1
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return 1
        
if __name__ == "__main__":
    sys.exit(main())
