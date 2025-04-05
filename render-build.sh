#!/bin/bash
set -e

echo "Running Render build script..."

# Render doesn't allow apt-get installs during build (read-only filesystem)
# We'll rely on pre-built wheels and Render's Python environment

# Upgrade pip and install wheel/setuptools first
pip install --upgrade pip setuptools wheel cython

# Print Python version for debugging
python --version
echo "Platform info:"
python -c "import platform; print(platform.platform()); print('Python implementation:', platform.python_implementation())"

# Install dependencies in two phases to ensure proper resolution
# First install scientific packages
echo "Installing scientific packages..."
pip install --prefer-binary --only-binary=numpy,scipy,pandas,scikit-learn numpy==1.24.4 scipy==1.10.1 pandas==2.0.3 scikit-learn==1.1.3 joblib==1.3.2

# Then install the rest
echo "Installing remaining packages..."
pip install --prefer-binary -r requirements.txt

# Verify critical packages installed correctly
echo "Verifying installations:"
python -c "import numpy; print(f'numpy version: {numpy.__version__}')"
python -c "import scipy; print(f'scipy version: {scipy.__version__}')"
python -c "import sklearn; print(f'scikit-learn version: {sklearn.__version__}')"
python -c "import pandas; print(f'pandas version: {pandas.__version__}')"
python -c "import nltk; print(f'nltk version: {nltk.__version__}')"
python -c "import coremltools; print(f'coremltools version: {coremltools.__version__}')"

# Prepare NLTK data - specify download directory
echo "Downloading NLTK data..."
NLTK_DIR="./nltk_data"
mkdir -p $NLTK_DIR
python -c "import nltk; nltk.download('punkt', download_dir='$NLTK_DIR', quiet=True); nltk.download('stopwords', download_dir='$NLTK_DIR', quiet=True); nltk.download('wordnet', download_dir='$NLTK_DIR', quiet=True); print('NLTK resources installed in', '$NLTK_DIR')"

# Make scripts executable
chmod +x entrypoint.sh
chmod +x refresh_dropbox_token.sh

# Check if we need to update the config with hardcoded tokens
if [ -n "$DROPBOX_APP_KEY" ] && [ -n "$DROPBOX_APP_SECRET" ]; then
    echo "Updating config.py with Dropbox app credentials..."
    # Use sed to replace the values in config.py
    sed -i "s/DROPBOX_APP_KEY = os.getenv(\"DROPBOX_APP_KEY\", \"YOUR_APP_KEY\")/DROPBOX_APP_KEY = os.getenv(\"DROPBOX_APP_KEY\", \"$DROPBOX_APP_KEY\")/" config.py
    sed -i "s/DROPBOX_APP_SECRET = os.getenv(\"DROPBOX_APP_SECRET\", \"YOUR_APP_SECRET\")/DROPBOX_APP_SECRET = os.getenv(\"DROPBOX_APP_SECRET\", \"$DROPBOX_APP_SECRET\")/" config.py
    echo "Credentials updated in config.py"
fi

# Generate initial tokens if possible
echo "Running initial Dropbox token refresh..."
./refresh_dropbox_token.sh || echo "Initial token refresh skipped or failed"

echo "Build completed successfully"
