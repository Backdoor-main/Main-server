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

# Make the entrypoint executable
chmod +x entrypoint.sh

echo "Build completed successfully"
