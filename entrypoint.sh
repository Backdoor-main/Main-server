#!/bin/bash
set -e

echo "Starting Backdoor AI Learning Server..."

# Set default directories for data, models, and NLTK data
DATA_DIR="/tmp/data"
MODELS_DIR="/tmp/models"
NLTK_DATA_DIR="/tmp/nltk_data"

# Check if we're running on a platform that requires environment setup
if [ -n "$KOYEB_DEPLOYMENT" ]; then
    echo "Running on Koyeb platform"
    # Koyeb uses /tmp as writable directory
    echo "Using directories in /tmp for Koyeb"
elif [ -n "$RENDER" ]; then
    echo "Running on Render platform"
    
    # Check if RENDER_DISK_PATH is set and accessible
    if [ -n "$RENDER_DISK_PATH" ] && [ -d "$RENDER_DISK_PATH" ] && [ -w "$RENDER_DISK_PATH" ]; then
        echo "Using persistent disk at $RENDER_DISK_PATH"
        DATA_DIR="${RENDER_DISK_PATH}/data"
        MODELS_DIR="${RENDER_DISK_PATH}/models"
        NLTK_DATA_DIR="${RENDER_DISK_PATH}/nltk_data"
    else
        echo "RENDER_DISK_PATH not accessible, using /tmp instead"
    fi
else
    echo "Running in local/custom environment"
    # In local environment, use directories in current directory
    DATA_DIR="./data"
    MODELS_DIR="./models"
    NLTK_DATA_DIR="./nltk_data"
fi

# Create required directories with error handling
echo "Creating required directories..."
mkdir -p "$DATA_DIR" 2>/dev/null || echo "Warning: Could not create $DATA_DIR, using /tmp"
mkdir -p "$MODELS_DIR" 2>/dev/null || echo "Warning: Could not create $MODELS_DIR, using /tmp"
mkdir -p "$NLTK_DATA_DIR" 2>/dev/null || echo "Warning: Could not create $NLTK_DATA_DIR, using /tmp"

# If any directories failed to create, fall back to /tmp
[ -d "$DATA_DIR" ] || DATA_DIR="/tmp/data" && mkdir -p "$DATA_DIR" 2>/dev/null
[ -d "$MODELS_DIR" ] || MODELS_DIR="/tmp/models" && mkdir -p "$MODELS_DIR" 2>/dev/null
[ -d "$NLTK_DATA_DIR" ] || NLTK_DATA_DIR="/tmp/nltk_data" && mkdir -p "$NLTK_DATA_DIR" 2>/dev/null

# Export directories as environment variables
export DATA_DIR MODELS_DIR NLTK_DATA_DIR

# Show directory permissions for debugging
echo "Directory information:"
ls -la /tmp /app "$DATA_DIR" "$MODELS_DIR" "$NLTK_DATA_DIR" 2>/dev/null || echo "Could not list directories"

# Install NLTK resources directly (safer approach)
echo "Installing NLTK resources..."
python -c "import nltk; nltk.data.path.append('$NLTK_DATA_DIR'); print(f'NLTK paths: {nltk.data.path}'); nltk.download('punkt', download_dir='$NLTK_DATA_DIR', quiet=True); nltk.download('stopwords', download_dir='$NLTK_DATA_DIR', quiet=True); nltk.download('wordnet', download_dir='$NLTK_DATA_DIR', quiet=True); print('NLTK resources installed successfully')"

# Run health check to verify scikit-learn is working
echo "Verifying scikit-learn installation..."
python -c "import sklearn; print(f'scikit-learn version: {sklearn.__version__}')"

# Refresh Dropbox tokens before starting the application
if [ -f "./refresh_dropbox_token.sh" ]; then
    echo "Running Dropbox token refresh..."
    chmod +x ./refresh_dropbox_token.sh
    ./refresh_dropbox_token.sh || echo "Token refresh failed, continuing anyway"
else
    echo "Dropbox token refresh script not found, skipping"
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
