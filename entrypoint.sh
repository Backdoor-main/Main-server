#!/bin/bash
set -e

echo "Starting Backdoor AI Learning Server..."

# Operating in memory-only mode with no local storage on Render
echo "Setting up memory-only operation mode..."

if [ -n "$RENDER" ]; then
    echo "Running on Render platform - using memory-only mode"
    # Set environment variables to signal memory-only mode
    export MEMORY_ONLY_MODE="True"
    export NO_LOCAL_STORAGE="True"
    export USE_DROPBOX_STREAMING="True"
    
    # No directories needed - everything will stream from Dropbox
    echo "No local directories needed - running in pure memory mode"
elif [ -n "$KOYEB_DEPLOYMENT" ]; then
    echo "Running on Koyeb platform - using memory-only mode"
    # Set environment variables to signal memory-only mode
    export MEMORY_ONLY_MODE="True"
    export USE_DROPBOX_STREAMING="True"
else
    echo "Running in local/custom environment"
    # In local environment, use directories in current directory
    DATA_DIR="./data"
    MODELS_DIR="./models"
    NLTK_DATA_DIR="./nltk_data"
    
    # Create local directories only in development mode
    echo "Creating directories for local development..."
    mkdir -p "$DATA_DIR" "$MODELS_DIR" "$NLTK_DATA_DIR"
    
    # Export directories as environment variables
    export DATA_DIR MODELS_DIR NLTK_DATA_DIR
    
    # Show directory permissions for debugging
    echo "Directory information:"
    ls -la "$DATA_DIR" "$MODELS_DIR" "$NLTK_DATA_DIR" 2>/dev/null || echo "Could not list directories"
fi

# Set up NLTK for streaming access to resources
echo "Configuring NLTK for streaming access..."
python -c "
import os
import nltk
import sys

# Setup for memory-only operation
if os.environ.get('MEMORY_ONLY_MODE') == 'True':
    print('Setting up NLTK for memory-only operation with Dropbox')
    # NLTK will use our custom provider for resources
    # No resources will be downloaded to disk
    nltk.data.path.append('memory:')
    print(f'NLTK paths: {nltk.data.path}')
else:
    # Development mode - download resources locally
    nltk_data_dir = os.environ.get('NLTK_DATA_DIR', './nltk_data')
    nltk.data.path.append(nltk_data_dir)
    print(f'NLTK paths: {nltk.data.path}')
    nltk.download('punkt', download_dir=nltk_data_dir, quiet=True)
    nltk.download('stopwords', download_dir=nltk_data_dir, quiet=True)
    nltk.download('wordnet', download_dir=nltk_data_dir, quiet=True)
    print('NLTK resources installed successfully')
"

# Run health check to verify scikit-learn is working
echo "Verifying scikit-learn installation..."
python -c "import sklearn; print(f'scikit-learn version: {sklearn.__version__}')"

# Refresh Dropbox tokens before starting the application
echo "Running Dropbox token refresh..."
if [ -f "./refresh_token.py" ]; then
    # Try the standalone Python script first
    python ./refresh_token.py || echo "Python token refresh failed, continuing anyway"
elif [ -f "./refresh_dropbox_token.sh" ]; then
    # Fall back to shell script if Python script not found
    chmod +x ./refresh_dropbox_token.sh
    ./refresh_dropbox_token.sh || echo "Shell token refresh failed, continuing anyway"
else
    echo "Token refresh scripts not found, skipping"
fi

# Display summary of environment
echo "Environment summary:"
echo "DATA_DIR=$DATA_DIR"
echo "MODELS_DIR=$MODELS_DIR"
echo "NLTK_DATA_DIR=$NLTK_DATA_DIR"
echo "PORT=${PORT:-10000}"

# Choose how to run the application based on environment
if [ -n "$GUNICORN_WORKERS" ]; then
    echo "Starting application with Gunicorn..."
    exec gunicorn --bind 0.0.0.0:${PORT:-10000} --workers ${GUNICORN_WORKERS:-2} "app:app"
else
    echo "Starting application with Flask development server..."
    exec python app.py
fi
