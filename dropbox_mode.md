# Dropbox-Only Mode for Render Deployments

This document explains how the application is configured to use Dropbox as the exclusive storage mechanism, eliminating the need for any local file storage on Render.com.

## Overview

The Backdoor AI Learning Server has been adapted to operate in a "Dropbox-only" mode where:

1. No local files are stored on Render's filesystem
2. The database is kept in memory with Dropbox synchronization
3. All NLTK resources are loaded directly from Dropbox
4. All models are streamed directly from Dropbox

## Key Components

### 1. In-Memory Database

- Uses SQLite's in-memory database feature (`:memory:`)
- Synchronizes with Dropbox on startup and at regular intervals
- Transactions are performed in memory for speed and then synced to Dropbox for persistence

### 2. NLTK Resources

- NLTK resources are stored in a `nltk_data` folder in Dropbox
- Resources are downloaded to memory buffers when needed instead of to disk
- A custom resource provider streams resources directly from Dropbox

### 3. Model Storage

- All models (both system and user-uploaded) are stored in Dropbox
- Models are streamed directly from Dropbox to memory when needed
- No local caching of models is performed

### 4. Flask Endpoints

- Models are served directly from memory buffers or via Dropbox direct links
- No temporary files are created during API operations
- All uploads are streamed directly to Dropbox

## Configuration

To enable Dropbox-only mode (enabled by default), ensure these environment variables are set:

```
DROPBOX_ENABLED=true
STORAGE_MODE=dropbox
```

## Benefits

1. **Render Compatibility**: Eliminates issues with Render's read-only filesystem
2. **Zero Local Storage**: No files are written to local disk
3. **Persistence**: All data is safely stored in Dropbox
4. **Memory Efficiency**: Only loads what's needed into memory

## Technical Implementation

The implementation uses several techniques to avoid local file storage:

1. **Memory Buffers**: Uses `io.BytesIO` for in-memory file operations
2. **Streaming**: Uses direct streaming from Dropbox where possible
3. **SQLite Memory Mode**: Uses SQLite's `:memory:` database feature
4. **Dropbox SDK**: Uses the Dropbox API for all storage operations

## Monitoring

The health endpoint (/health) provides detailed information about the system state, including:

- Database status (in-memory with Dropbox sync)
- Dropbox connection status
- Memory usage statistics
- Model counts

This allows you to monitor the application's health and memory usage in real-time.

## Required Dropbox Structure

When using Dropbox-only mode, the following folder structure is created in your Dropbox:

```
/backdoor_models/        (Main models folder)
├── uploaded/            (User uploaded models)
├── tmp/                 (Temporary processing files)
/nltk_data/              (NLTK resources)
├── tokenizers/          
├── corpora/             
├── taggers/             
/app_data/               (Application data)
├── temp/                (Temporary files)
```

## Memory Considerations

When running in Dropbox-only mode, memory usage is carefully managed:

1. Database operations are performed in memory with periodic syncs to Dropbox
2. Only models being actively processed are loaded into memory
3. Resources are streamed directly when possible, avoiding full loads
4. Temporary resources are released when no longer needed

For Render.com deployments, it's recommended to use at least 512MB of RAM to ensure smooth operation with in-memory database management.
