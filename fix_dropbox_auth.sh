#!/bin/bash
# Quick fix script for Dropbox authentication issues

echo "Dropbox Authentication Fix Tool"
echo "=============================="

# Clean up any potentially corrupted tokens
echo "Cleaning up potential corrupted tokens..."
if [ -f "dropbox_tokens.json" ]; then
    echo "  Found dropbox_tokens.json - backing up and removing"
    cp dropbox_tokens.json dropbox_tokens.json.bak
    rm dropbox_tokens.json
fi

# Check if we have the token generator script
if [ -f "gen_dropbox_token.py" ]; then
    echo "Found gen_dropbox_token.py - this is the recommended way to set up tokens"
    echo ""
    echo "To properly set up Dropbox authentication:"
    echo "1. Run: python gen_dropbox_token.py --generate"
    echo "2. Follow the prompts to complete OAuth authorization"
    echo "3. Restart your application"
    echo ""
    echo "Would you like to run the token generator now? (y/n)"
    read -p "> " run_generator
    
    if [[ "$run_generator" =~ ^[Yy] ]]; then
        python gen_dropbox_token.py --generate
    else
        echo "Skipping token generation. You can run it manually later."
    fi
else
    echo "Token generator script (gen_dropbox_token.py) not found!"
    echo "Your Dropbox OAuth setup may be incomplete."
fi

# Create minimal config file to ensure local storage fallback works
cat > minimal_token.json << EOL
{
  "app_key": "2bi422xpd3xd962",
  "app_secret": "j3yx0b41qdvfu86",
  "needs_auth": true,
  "created_at": "$(date -u +"%Y-%m-%dT%H:%M:%SZ")",
  "instructions": "Run gen_dropbox_token.py --generate to complete OAuth setup"
}
EOL

if [ ! -f "dropbox_tokens.json" ]; then
    echo "Creating minimal token placeholder file"
    cp minimal_token.json dropbox_tokens.json
fi

echo ""
echo "Fix completed!"
echo "If you continue having issues:"
echo "1. Make sure your Dropbox app has the correct permissions"
echo "2. Check that your app key and secret are correct"
echo "3. The application will fall back to local storage until proper OAuth setup is completed"
echo ""
echo "To verify token status in the future, run: python gen_dropbox_token.py --check"
