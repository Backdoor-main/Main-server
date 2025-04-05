# Backdoor AI Learning Server

A Flask-based server for collecting user interaction data, training NLP models, and serving CoreML models to client devices.

## Features

- Collects user interaction data for NLP intent classification
- Allows users to upload CoreML models
- Creates ensemble models combining input from multiple users
- Provides API endpoints for model download and statistics
- Supports multiple storage backends (Dropbox, Google Drive, local filesystem)
- Compatible with various deployment platforms (Render.com, Koyeb.com)

## Deployment Options

### Render.com Deployment

1. Fork or clone this repository
2. Set up a new Web Service on Render pointing to your repository
3. Configure the required environment variables:
   - `DROPBOX_API_KEY` - Required for Dropbox storage
   - `DROPBOX_ENABLED` - Set to "true" to enable Dropbox storage

The service is configured to use Render's free tier by default.

### Koyeb.com Deployment

1. Fork or clone this repository
2. Create a new Koyeb application from your repository
3. Use the included `koyeb.yaml` for configuration
4. Configure the required environment variables:
   - `DROPBOX_API_KEY` - Required for Dropbox storage
   - `DROPBOX_ENABLED` - Set to "true" to enable Dropbox storage

Alternatively, you can deploy using the Dockerfile:
```
docker build -t backdoor-ai .
docker run -p 10000:10000 -e DROPBOX_API_KEY=your_key backdoor-ai
```

## API Endpoints

- `POST /api/ai/learn` - Receive learning data from client devices
- `POST /api/ai/upload-model` - Allow users to upload their trained models
- `GET /api/ai/models/<version>` - Download a specific model version
- `GET /api/ai/latest-model` - Get information about the latest model
- `GET /api/ai/stats` - Get system statistics
- `GET /health` - Health check endpoint

## Configuration

The server can be configured using environment variables:

### Core Settings
- `PORT` - Server port (default: 10000)
- `STORAGE_MODE` - Storage backend: "dropbox", "google_drive", or "local" (default: "dropbox")
- `MEMORY_OPTIMIZED` - Enable memory optimization for constrained environments (default: "true")

### Dropbox Storage
- `DROPBOX_ENABLED` - Enable Dropbox storage (default: "true")
- `DROPBOX_API_KEY` - Dropbox API key
- `DROPBOX_DB_FILENAME` - Database filename in Dropbox (default: "backdoor_ai_db.db")
- `DROPBOX_MODELS_FOLDER` - Models folder in Dropbox (default: "backdoor_models")

### Google Drive Storage
- `GOOGLE_DRIVE_ENABLED` - Enable Google Drive storage (default: "false")
- `GOOGLE_CREDENTIALS_PATH` - Path to Google credentials JSON file (default: "google_credentials.json")

### Model Training
- `MIN_TRAINING_DATA` - Minimum samples required for training (default: 50)
- `MAX_MODELS_TO_KEEP` - Number of model versions to keep (default: 5)
- `BASE_MODEL_WEIGHT` - Weight of base model in ensemble (default: 2.0)
- `USER_MODEL_WEIGHT` - Weight of user models in ensemble (default: 1.0)

## Local Development

1. Clone the repository
2. Create a virtual environment and install dependencies:
   ```
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```
3. Run the server:
   ```
   python app.py
   ```

## Data & Model Security

- All user data is stored in a SQLite database
- By default, the database and models are stored in Dropbox for persistence
- The server can be configured to store data locally if needed
- Models are versioned and retained based on the `MAX_MODELS_TO_KEEP` setting

## Technical Requirements

- Python 3.11+ (required for coremltools compatibility)
- A Dropbox account and API key (recommended)
- Free or paid tier on Render.com or Koyeb.com

## Memory Optimization

For deployment on platforms with memory constraints:

1. Set `MEMORY_OPTIMIZED=true` to enable memory-saving features
2. Adjust `MAX_UPLOAD_SIZE_MB` to limit the size of model uploads
3. Set `CONCURRENT_TRAINING_ENABLED=false` to disable concurrent model training
