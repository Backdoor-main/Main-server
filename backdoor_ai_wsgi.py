import sys
import os
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger(__name__)

# Determine project home directory - works on different platforms
if 'RENDER_DISK_PATH' in os.environ:
    project_home = os.environ.get('RENDER_DISK_PATH')
    logger.info(f"Running on Render with path: {project_home}")
elif 'KOYEB_DEPLOYMENT' in os.environ:
    project_home = '/app'  # Koyeb Docker container working directory
    logger.info(f"Running on Koyeb with path: {project_home}")
else:
    # Default fallback for other platforms
    project_home = os.path.dirname(os.path.abspath(__file__))
    logger.info(f"Running on custom platform with path: {project_home}")

if project_home not in sys.path:
    sys.path = [project_home] + sys.path

try:
    from app import app as application
    logger.info("Successfully imported Flask application")
except Exception as e:
    logger.error(f"Failed to import Flask application: {e}")
    raise