# Use Python 3.11 for compatibility with coremltools
FROM python:3.11.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies including python3-distutils
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    python3-dev \
    python3-distutils \
    python3-setuptools \
    build-essential \
    libatlas-base-dev \
    gfortran \
    libopenblas-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first to leverage Docker cache
COPY requirements.txt .

# Install basic build tools before any pip operations
RUN python -m ensurepip --upgrade || true
RUN python -m pip install --no-cache-dir --upgrade pip setuptools wheel

# Install Cython and other build tools
RUN python -m pip install --no-cache-dir cython

# Install scientific packages first to ensure proper version resolution
# Use --no-build-isolation to prevent pip from creating a new build environment
RUN python -m pip install --no-cache-dir --prefer-binary --no-build-isolation \
    numpy==1.24.4 \
    scipy==1.10.1 \
    pandas==2.0.3 \
    scikit-learn==1.1.3 \
    joblib==1.3.2

# Install remaining dependencies
RUN python -m pip install --no-cache-dir --prefer-binary -r requirements.txt

# Copy application code
COPY . .

# Create required directories
RUN mkdir -p /tmp/data /tmp/models /tmp/nltk_data

# Install NLTK data with explicit directory
RUN mkdir -p /app/nltk_data && \
    python -c "import nltk; nltk.data.path.append('/app/nltk_data'); nltk.download('punkt', download_dir='/app/nltk_data', quiet=True); nltk.download('stopwords', download_dir='/app/nltk_data', quiet=True); nltk.download('wordnet', download_dir='/app/nltk_data', quiet=True); print('NLTK resources installed successfully')"

# Verify installations
RUN python -c "import sys; print(f'Python version: {sys.version}')" && \
    python -c "import numpy; print(f'numpy version: {numpy.__version__}')" && \
    python -c "import sklearn; print(f'scikit-learn version: {sklearn.__version__}')" && \
    python -c "import coremltools; print(f'coremltools version: {coremltools.__version__}')"

# Expose port
EXPOSE 10000

# Copy and make entrypoint executable
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Run the application
CMD ["/entrypoint.sh"]
