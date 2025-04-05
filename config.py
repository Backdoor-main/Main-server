"""
Configuration settings for the Backdoor AI Learning Server

This module handles configuration for various deployment platforms:
- Render.com
- Koyeb.com
- Local development
"""
import os
import logging
import tempfile

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger(__name__)

# Define storage mode and Dropbox settings first to avoid NameError
# Storage mode configuration
STORAGE_MODE = os.getenv("STORAGE_MODE", "dropbox")

# Dropbox Integration Settings - DEFINED EARLY to avoid NameError
DROPBOX_ENABLED = os.getenv("DROPBOX_ENABLED", "True").lower() in ["true", "1", "yes"]

# Dropbox OAuth2 Settings
# App key and secret for OAuth2 flow - needed for token refresh
DROPBOX_APP_KEY = os.getenv("DROPBOX_APP_KEY", "2bi422xpd3xd962")
DROPBOX_APP_SECRET = os.getenv("DROPBOX_APP_SECRET", "j3yx0b41qdvfu86")

# The access token - can be regenerated using refresh token
DROPBOX_ACCESS_TOKEN = os.getenv("DROPBOX_ACCESS_TOKEN", "YOUR_ACCESS_TOKEN")

# The refresh token - used to get new access tokens automatically
DROPBOX_REFRESH_TOKEN = os.getenv("DROPBOX_REFRESH_TOKEN", "RvyL03RE5qAAAAAAAAAAAVMVebvE7jDx8Okd0ploMzr85c6txvCRXpJAt30mxrKF") 

# Legacy API key - keeping for backwards compatibility
DROPBOX_API_KEY = os.getenv("DROPBOX_API_KEY", DROPBOX_ACCESS_TOKEN)

# Dropbox token refresh settings
DROPBOX_TOKEN_EXPIRY = os.getenv("DROPBOX_TOKEN_EXPIRY", None)  # ISO format datetime string when token expires
DROPBOX_AUTO_REFRESH = os.getenv("DROPBOX_AUTO_REFRESH", "True").lower() in ["true", "1", "yes"]

# Other Dropbox settings
DROPBOX_DB_FILENAME = os.getenv("DROPBOX_DB_FILENAME", "backdoor_ai_db.db")
DROPBOX_MODELS_FOLDER = os.getenv("DROPBOX_MODELS_FOLDER", "backdoor_models")

# Dropbox authentication retry settings
DROPBOX_MAX_RETRIES = int(os.getenv("DROPBOX_MAX_RETRIES", "3"))
DROPBOX_RETRY_DELAY = int(os.getenv("DROPBOX_RETRY_DELAY", "5"))  # seconds between retries

# Check for necessary credentials early
if DROPBOX_ENABLED:
    if DROPBOX_REFRESH_TOKEN != "YOUR_REFRESH_TOKEN":
        logger.info("Using Dropbox OAuth2 authentication with token manager - refresh token found")
        # The access token will be generated automatically by the token manager
    else:
        logger.warning("Dropbox is enabled but refresh token is not configured.")
        logger.warning("Please set DROPBOX_REFRESH_TOKEN in config.py or use setup_oauth.py")
        logger.warning("You only need to set the refresh token once, the rest is automatic")
        DROPBOX_ENABLED = False

# Determine deployment environment
IS_RENDER = os.getenv("RENDER", "").lower() in ["true", "1", "yes"]
IS_KOYEB = os.getenv("KOYEB_DEPLOYMENT", "").lower() in ["true", "1", "yes"]

# Memory-only mode for Render deployment
MEMORY_ONLY_MODE = os.getenv("MEMORY_ONLY_MODE", "False").lower() in ["true", "1", "yes"]
USE_DROPBOX_STREAMING = os.getenv("USE_DROPBOX_STREAMING", "False").lower() in ["true", "1", "yes"]
NO_LOCAL_STORAGE = os.getenv("NO_LOCAL_STORAGE", "False").lower() in ["true", "1", "yes"]

# If we're running on Render, enable memory-only mode by default
if IS_RENDER and not os.environ.get("DISABLE_MEMORY_ONLY_MODE"):
    MEMORY_ONLY_MODE = True
    USE_DROPBOX_STREAMING = True
    NO_LOCAL_STORAGE = True
    logger.info("Memory-only mode automatically enabled for Render deployment")

# Use environment variables if set, otherwise use platform-specific defaults
DATA_DIR = os.getenv("DATA_DIR", None)
MODEL_DIR = os.getenv("MODELS_DIR", None)
NLTK_DATA_PATH = os.getenv("NLTK_DATA_DIR", None)

# Set a base directory for all environments
if IS_RENDER:
    logger.info("Running on Render.com platform")
    PLATFORM = "render"
    # For Render, use /tmp or RENDER_DISK_PATH if available
    BASE_DIR = os.getenv("RENDER_DISK_PATH", "/tmp")
    # Use /tmp for Render.com if not set in environment
    if not DATA_DIR:
        DATA_DIR = os.path.join(BASE_DIR, "data")
    if not MODEL_DIR:
        MODEL_DIR = os.path.join(BASE_DIR, "models")
    if not NLTK_DATA_PATH:
        NLTK_DATA_PATH = os.path.join(BASE_DIR, "nltk_data")
elif IS_KOYEB:
    logger.info("Running on Koyeb.com platform")
    PLATFORM = "koyeb"
    # For Koyeb, use /tmp
    BASE_DIR = "/tmp"
    # Use /tmp for Koyeb if not set in environment
    if not DATA_DIR:
        DATA_DIR = os.path.join(BASE_DIR, "data")
    if not MODEL_DIR:
        MODEL_DIR = os.path.join(BASE_DIR, "models")
    if not NLTK_DATA_PATH:
        NLTK_DATA_PATH = os.path.join(BASE_DIR, "nltk_data")
else:
    logger.info("Running in local/custom environment")
    PLATFORM = "local"
    # Use local paths if not set in environment
    BASE_DIR = os.getenv("BASE_DIR", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    if not DATA_DIR:
        DATA_DIR = os.path.join(BASE_DIR, "data")
    if not MODEL_DIR:
        MODEL_DIR = os.path.join(BASE_DIR, "models")
    if not NLTK_DATA_PATH:
        NLTK_DATA_PATH = os.path.join(BASE_DIR, "nltk_data")

# Log the paths being used
logger.info(f"Using DATA_DIR: {DATA_DIR}")
logger.info(f"Using MODEL_DIR: {MODEL_DIR}")
logger.info(f"Using NLTK_DATA_PATH: {NLTK_DATA_PATH}")

# Server settings
PORT = int(os.getenv("PORT", 10000))

# Handle storage setup based on DROPBOX_ENABLED flag
if DROPBOX_ENABLED:
    # Check if we're in memory-only mode - this is the most efficient way to run on Render
    if MEMORY_ONLY_MODE:
        logger.info("Using memory-only mode with Dropbox - no local files or directories will be used")
        
        # No local storage - everything is streamed directly from Dropbox
        # For Render's memory constraints, this is crucial
        UPLOADED_MODELS_DIR = "memory:upload_models_refs"
        
        # In-memory database reference
        DB_PATH = "memory:interactions.db"
        
        # Patch tempfile module to use memory-only implementation
        if USE_DROPBOX_STREAMING:
            logger.info("Using Dropbox streaming for all resources - minimal memory footprint")
    else:
        logger.info("Using Dropbox for all storage - no local directories needed")
        
        # Define a temporary directory for any possible cases where a file path is required
        # But we won't actually create any directories here
        UPLOADED_MODELS_DIR = os.path.join("/tmp", "upload_models_refs")
        
        # Define in-memory database path (this is just a reference for compatibility)
        DB_PATH = "memory:interactions.db"
    
    # Define Dropbox paths to use for resources (these are only used as references)
    DROPBOX_NLTK_FOLDER = "nltk_data"
    # New organization for model storage
    DROPBOX_BASE_MODEL_FOLDER = "base_model"  # Dedicated folder for base model
    DROPBOX_MODELS_PATH = f"{DROPBOX_MODELS_FOLDER}/trained"  # For trained models 
    DROPBOX_UPLOADED_MODELS_PATH = f"{DROPBOX_MODELS_FOLDER}/uploaded"  # For user-uploaded models
    
    # Skip directory creation - everything uses memory with Dropbox sync
    logger.info("All data will be stored in Dropbox and accessed via memory buffers")
else:
    # Only create directories when not using Dropbox
    logger.info("Using local storage - creating local directories")
    
    # Define local file paths
    UPLOADED_MODELS_DIR = os.path.join(MODEL_DIR, "uploaded")
    
    # Ensure directories exist with error handling
    for directory in [DATA_DIR, MODEL_DIR, NLTK_DATA_PATH, UPLOADED_MODELS_DIR]:
        try:
            os.makedirs(directory, exist_ok=True)
            logger.info(f"Created directory: {directory}")
        except PermissionError:
            logger.warning(f"Permission denied creating directory: {directory}")
            # If this is a critical directory, we need to handle the error
            if directory == DATA_DIR:
                # Fallback to a temporary directory
                DATA_DIR = tempfile.mkdtemp()
                logger.info(f"Using temporary directory instead: {DATA_DIR}")
            elif directory == MODEL_DIR:
                MODEL_DIR = tempfile.mkdtemp()
                UPLOADED_MODELS_DIR = os.path.join(MODEL_DIR, "uploaded")
                os.makedirs(UPLOADED_MODELS_DIR, exist_ok=True)
                logger.info(f"Using temporary directory instead: {MODEL_DIR}")
        except Exception as e:
            logger.error(f"Error creating directory {directory}: {e}")

    # Database path for local storage
    DB_PATH = os.path.join(DATA_DIR, "interactions.db")

# NLTK Resources
NLTK_RESOURCES = ['punkt', 'stopwords', 'wordnet']

# Model training settings
MIN_TRAINING_DATA = int(os.getenv("MIN_TRAINING_DATA", "50"))
MAX_MODELS_TO_KEEP = int(os.getenv("MAX_MODELS_TO_KEEP", "5"))  # Keep only the most recent N models

# Training thresholds - can be tuned via environment variables
RETRAINING_THRESHOLDS = {
    'pending_models': int(os.getenv("THRESHOLD_PENDING_MODELS", "3")),
    'hours_since_last_training': int(os.getenv("THRESHOLD_HOURS", "12")),
    'new_interactions': int(os.getenv("THRESHOLD_INTERACTIONS", "100"))
}

# Text processing settings
MAX_FEATURES = int(os.getenv("MAX_FEATURES", "5000"))
NGRAM_RANGE = (1, 2)  # Bigram features

# Ensemble model settings
BASE_MODEL_WEIGHT = float(os.getenv("BASE_MODEL_WEIGHT", "2.0"))
USER_MODEL_WEIGHT = float(os.getenv("USER_MODEL_WEIGHT", "1.0"))

# Database lock timeout (seconds)
DB_LOCK_TIMEOUT = int(os.getenv("DB_LOCK_TIMEOUT", "60"))

# Model naming
MODEL_VERSION_PREFIX = os.getenv("MODEL_VERSION_PREFIX", "1.0.")

# Storage mode configuration
STORAGE_MODE = os.getenv("STORAGE_MODE", "dropbox")

# Dropbox Sync Settings (already defined DROPBOX_ENABLED and related settings at the top)
DROPBOX_DB_SYNC_INTERVAL = int(os.getenv("DROPBOX_DB_SYNC_INTERVAL", "60"))  # Seconds
DROPBOX_MODELS_SYNC_INTERVAL = int(os.getenv("DROPBOX_MODELS_SYNC_INTERVAL", "300"))  # Seconds

# Google Drive Integration Settings (optional)
GOOGLE_DRIVE_ENABLED = os.getenv("GOOGLE_DRIVE_ENABLED", "False").lower() in ["true", "1", "yes"]
GOOGLE_CREDENTIALS_PATH = os.getenv("GOOGLE_CREDENTIALS_PATH", "google_credentials.json")
GOOGLE_DRIVE_DB_FILENAME = os.getenv("GOOGLE_DRIVE_DB_FILENAME", "backdoor_ai_db.db")
GOOGLE_DRIVE_MODELS_FOLDER = os.getenv("GOOGLE_DRIVE_MODELS_FOLDER", "backdoor_models")

# Base model name (used to identify the model in storage)
BASE_MODEL_NAME = os.getenv("BASE_MODEL_NAME", "model_1.0.0.mlmodel")

# Memory management settings
# For platforms with memory constraints, tune these settings
MEMORY_OPTIMIZED = os.getenv("MEMORY_OPTIMIZED", "True").lower() in ["true", "1", "yes"]
MAX_UPLOAD_SIZE_MB = int(os.getenv("MAX_UPLOAD_SIZE_MB", "600"))  # Maximum file upload size in MB
CONCURRENT_TRAINING_ENABLED = os.getenv("CONCURRENT_TRAINING_ENABLED", "True").lower() in ["true", "1", "yes"]

# Temporary directory for processing
TMP_DIR = tempfile.gettempdir()

# Credentials check for Google Drive only (Dropbox checked earlier)
# No need to check Dropbox again here as we already did it at the top of the file

if GOOGLE_DRIVE_ENABLED and not os.path.exists(GOOGLE_CREDENTIALS_PATH):
    logger.warning(f"Google Drive is enabled but credentials file not found at {GOOGLE_CREDENTIALS_PATH}")
    GOOGLE_DRIVE_ENABLED = False

# Determine final storage mode
if STORAGE_MODE == "dropbox" and not DROPBOX_ENABLED:
    logger.warning("Dropbox storage requested but not enabled. Falling back to local storage.")
    STORAGE_MODE = "local"
elif STORAGE_MODE == "google_drive" and not GOOGLE_DRIVE_ENABLED:
    logger.warning("Google Drive storage requested but not enabled. Falling back to local storage.")
    STORAGE_MODE = "local"

# Final logging of configuration
logger.info(f"Using {STORAGE_MODE} storage mode")
logger.info(f"Root directory: {BASE_DIR}")
logger.info(f"Data directory: {DATA_DIR}")
logger.info(f"Models directory: {MODEL_DIR}")
logger.info(f"Database path: {DB_PATH}")
