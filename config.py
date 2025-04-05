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
# The API key is hardcoded here as requested to ensure it's always available
DROPBOX_API_KEY = os.getenv("DROPBOX_API_KEY", "sl.u.AFpjxIfGDWdCGwYCSTvEt1YB8hmlxHixh0P_Myj6eoz7BLFiAPVeFTqomrRC5hvteZrqFjqFhFj65JmRN0nQTiTafi-BY_hNWfwPs9u-wtBcY05yKFnvx1d47QLA7hrepXlIoHQKZ4T6xxaXfgYZLnI1dtDoYrQ1mhPjP93uC91rMfIp5tg6qEvmM2uFs85qap1kHsJ7OX7gaVN_p_BF5ADL2y0e4JbMToXJB2GTinqBlpr8E1D3TFP2GHRJ6iq7aRs3mVSh9NvaR2Qw4uFlR-FkBwCsFXOmqwxPw7J9uK4malLF75yS_TdDFZdH3567x8VB8l_pN801lZ9c29kgPkmLfpIW_5uFcmlzKpJDBAIhawGE4MoD1AuuR68iAWM0e_tfub-6HcCI9xJPKrnm-TdsXcVxp9GISKf-QPdo6PXseDMw_naMQpC8_VLdmty8fYMepFl5g1v7WX3ofA2vxvZZbTZCe2SindqcqJyAMSYFClrdJx4GiUc_Ay9qwtRYFdoOd5uB56sPxSc2SAT1nk07EhdRk92r2U4QQHdeDaafzHnKXevUWARzrr00Nz72cRuxC3h39SBjpE45pryrN47jVdxSOFHryCeq0pgVfLk4TaaKnxx2rL82gRztJxxIMHykQ3Otsg60lDNN2eR-hT-kbatNAgEJlUEeXAxCyBYTp_cErCeA1hOcYGnYTc14AuZ6cqO0iLsxvocgJIl1a-Cvod_ENuX5d739t-dVwQkqD0ZdKeFKecR5R36gymF4ZpGHczxxbXtSeeg_sNFYKFXVqnkJQBEv1aez02OK6L8vi4C7krNbDrf6759sdsglq4ryDhGh_dFEAr2aH2KYDl9qRV4jbjwJwGf752Q3huYeuoTSJOdG0ychi4O0VEVHTj-9DnviPNHmma0bOz7XgmB6BGpjeLWD7hG6aEAjPaXS5jL3qokCBKqBDAhOjZiQHhVkiRegKEmWzRm11zHgjlzo1JDMsP5Q5mj7T9lEhHdmX9Q6Pl7_DAPA4kFs7wJkawPi3mbpY2b2U3B84r443_NNRcIddMvNEMIdE0jS_1cG3RVyqomULZt2M9Z-Ti0IeaiQRcdc5yrCFi0GDVNDtxC1CdG26Y5FCyQPcEOCGrzOghfptu55Ed_uWOTkaV9qlxvPBOfnwqpccUqM4ZNnNw8XQ6MdT76aD6_yQdI5mTmJjllMuaaZonGlMKZhPCSM0KCdIgN6mxSatb-v0Of9tcjcaxcO_RxtkpXWan-10qCqNWBv0yp0Jst10TqpzVyFGzSd10cON3WLV_eypNZ6sjkgqZjmmvmyKcCEg9c5Tjth7BsZlC1KMHFXl6N4ui9jHOn-l3NByaVoq6NaKelSVxM2kkkxKNl5LAzGBMLjleXVRZ12SblDIdtQTPgccAA27jtb5Z4Srfx2QsGvvGQEIgnOfWEcXylXzYjbw34rFAeSmpb6A1b2GDcB4keHBLuNcs0")
DROPBOX_DB_FILENAME = os.getenv("DROPBOX_DB_FILENAME", "backdoor_ai_db.db")
DROPBOX_MODELS_FOLDER = os.getenv("DROPBOX_MODELS_FOLDER", "backdoor_models")

# Check for necessary credentials early
if DROPBOX_ENABLED and not DROPBOX_API_KEY:
    logger.warning("Dropbox is enabled but no API key available.")
    DROPBOX_ENABLED = False
else:
    # Log that we're using the hardcoded API key
    logger.info("Using hardcoded Dropbox API key for authentication")

# Determine deployment environment
IS_RENDER = os.getenv("RENDER", "").lower() in ["true", "1", "yes"]
IS_KOYEB = os.getenv("KOYEB_DEPLOYMENT", "").lower() in ["true", "1", "yes"]

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
