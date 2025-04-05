#!/bin/bash
set -e

echo "Running Koyeb build script..."

# Ensure we have python3-distutils installed
echo "Installing system dependencies..."
apt-get update
apt-get install -y --no-install-recommends \
    python3-distutils \
    python3-setuptools \
    build-essential \
    python3-dev

# Print Python version for debugging
python --version
echo "Platform info:"
python -c "import sys, platform; print(f'Python {sys.version}'); print(f'Platform: {platform.platform()}')"

# Ensure pip is available and up to date
echo "Upgrading pip and basic tools..."
python -m ensurepip --upgrade || echo "ensurepip not available, continuing..."
python -m pip install --upgrade pip setuptools wheel

# Install Cython and build tools
echo "Installing build tools..."
python -m pip install cython

# Install scientific packages first to ensure proper version resolution
echo "Installing scientific packages..."
python -m pip install --prefer-binary --no-build-isolation \
    numpy==1.24.4 \
    scipy==1.10.1 \
    pandas==2.0.3 \
    scikit-learn==1.1.3 \
    joblib==1.3.2

# Then install the rest
echo "Installing remaining packages..."
python -m pip install --prefer-binary -r requirements.txt

# Verify critical packages installed correctly
echo "Verifying installations:"
python -c "import sys; print(f'Python version: {sys.version}')"
python -c "import numpy; print(f'numpy version: {numpy.__version__}')"
python -c "import scipy; print(f'scipy version: {scipy.__version__}')"
python -c "import sklearn; print(f'scikit-learn version: {sklearn.__version__}')"
python -c "import pandas; print(f'pandas version: {pandas.__version__}')"
python -c "import nltk; print(f'nltk version: {nltk.__version__}')"
python -c "import coremltools; print(f'coremltools version: {coremltools.__version__}')"

# Prepare NLTK data with explicit directory
echo "Downloading NLTK data..."
NLTK_DIR="/tmp/nltk_data"
mkdir -p $NLTK_DIR
python -c "import nltk; nltk.download('punkt', download_dir='$NLTK_DIR', quiet=True); nltk.download('stopwords', download_dir='$NLTK_DIR', quiet=True); nltk.download('wordnet', download_dir='$NLTK_DIR', quiet=True); print('NLTK resources installed in', '$NLTK_DIR')"

# Make the entrypoint executable
chmod +x entrypoint.sh

echo "Build completed successfully"
