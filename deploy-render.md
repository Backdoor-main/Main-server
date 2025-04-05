# Render.com Deployment Instructions

This guide provides instructions for deploying the Backdoor AI Learning Server to Render.com.

## Deployment Steps

1. Fork or clone the repository to your GitHub account

2. Create a new Web Service on Render:
   - Connect your GitHub repository
   - Select the branch to deploy (usually `main`)
   - Choose "Python" as the environment
   - Set the build command: `python build-packages.py && chmod +x entrypoint.sh`
   - Set the start command: `./entrypoint.sh`
   - Choose the "Starter" plan (required for scientific packages)

3. Add environment variables:
   - `PYTHON_VERSION`: 3.11.11
   - `DROPBOX_ENABLED`: true
   - Note: Dropbox API key is now hardcoded in config.py
   - `DROPBOX_DB_FILENAME`: backdoor_ai_db.db
   - `DROPBOX_MODELS_FOLDER`: backdoor_models
   - `STORAGE_MODE`: dropbox
   - `GUNICORN_WORKERS`: 2
   - `NLTK_DATA`: /opt/render/project/nltk_data
   - `RENDER`: true
   - `MEMORY_OPTIMIZED`: true
   - `PIP_PREFER_BINARY`: 1

4. Configure a persistent disk:
   - Name: backdoor-ai-data
   - Mount path: /opt/render/project
   - Size: At least 1GB

## Important Notes for Render Deployment

1. Render doesn't allow `apt-get` commands during builds (read-only filesystem)
   - We use the `build-packages.py` script to handle dependencies properly
   - All packages must have binary wheels available for Python 3.11
   - We install packages in a specific order to avoid dependency conflicts

2. Scikit-learn version is critical:
   - We use scikit-learn 1.1.3 (not 1.1.2) because it has binary wheels for Python 3.11
   - This version should still be compatible with coremltools 7.0

3. Persistent disk is required for storing:
   - SQLite database (when not using Dropbox)
   - Trained models
   - NLTK data

## Troubleshooting

If you encounter deployment issues:

1. Check build logs for specific error messages
2. Verify your Dropbox API key is correct
3. Ensure you're using the "Starter" plan or higher to have enough memory
4. If scientific packages fail to install, try using the alternative build method:
   - Build command: `pip install --prefer-binary numpy==1.24.4 scipy==1.10.1 scikit-learn==1.1.3 && pip install -r requirements.txt && chmod +x entrypoint.sh`
5. Check the application logs after deployment for runtime errors

## Testing Your Deployment

After deployment, test the application by accessing:
- Health check endpoint: `https://your-app.onrender.com/health`
- Main API endpoint: `https://your-app.onrender.com/`
- If the health check returns status information, your deployment is working correctly
