#!/bin/bash
set -e

echo "Building Docker image for Koyeb deployment..."

# Make the token refresh script executable
chmod +x refresh_dropbox_token.sh

# Update config.py with hardcoded app credentials
echo "Updating config.py with Dropbox app credentials..."
APP_KEY=${DROPBOX_APP_KEY:-"2bi422xpd3xd962"}
APP_SECRET=${DROPBOX_APP_SECRET:-"j3yx0b41qdvfu86"}

# Use sed to replace the values in config.py
sed -i "s/DROPBOX_APP_KEY = os.getenv(\"DROPBOX_APP_KEY\", \"YOUR_APP_KEY\")/DROPBOX_APP_KEY = os.getenv(\"DROPBOX_APP_KEY\", \"$APP_KEY\")/" config.py
sed -i "s/DROPBOX_APP_SECRET = os.getenv(\"DROPBOX_APP_SECRET\", \"YOUR_APP_SECRET\")/DROPBOX_APP_SECRET = os.getenv(\"DROPBOX_APP_SECRET\", \"$APP_SECRET\")/" config.py

# Build the Docker image
docker build -t backdoor-ai:latest .

echo "Docker build completed successfully."
echo "To run locally: docker run -p 10000:10000 backdoor-ai:latest"
echo "To push to Koyeb, first tag and push to your container registry."
