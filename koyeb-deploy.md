# Koyeb Deployment Guide

This guide explains how to deploy the Backdoor AI Learning Server on Koyeb using Docker.

## Option 1: Using Dockerfile (Recommended)

This is the preferred approach as it handles the system dependencies properly.

1. Ensure you have the [Koyeb CLI](https://www.koyeb.com/docs/cli/installation) installed
2. No need to create a Dropbox API key secret as it's now hardcoded in the application
3. Deploy the application:
   ```
   koyeb app create --name backdoor-ai --git github.com/Backdoor-main/Main-server --git-branch main --git-builder-image docker
   ```

## Option 2: Using koyeb.yaml

If you prefer to use the koyeb.yaml configuration file:

1. Deploy with koyeb.yaml:
   ```
   koyeb app create --name backdoor-ai --git github.com/Backdoor-main/Main-server --git-branch main
   ```
2. Ensure you've created the dropbox-api-key secret as shown above.

## Option 3: Using Build Script (Alternative)

If Docker deployment isn't working, you can try using the build script:

1. Edit koyeb.yaml to use the build script:
   ```yaml
   service:
     # ...
     definition:
       type: buildpack
       buildCommand: "chmod +x koyeb-build.sh && ./koyeb-build.sh"
       startCommand: "./entrypoint.sh"
   ```
2. Deploy as in Option 2.

## Troubleshooting

If you encounter the "No module named 'distutils'" error, it's usually because Python distutils is missing. Our updated Dockerfile adds this package.

Common issues and solutions:

1. **Missing distutils**:
   - Make sure python3-distutils is installed
   - Use the Docker deployment method, which includes all dependencies

2. **Build failures**:
   - Check the build logs for specific errors
   - Try increasing the CPU/memory in koyeb.yaml if builds are timing out

3. **Runtime errors**:
   - Verify your Dropbox API key is set correctly
   - Check if the NLTK data is downloading correctly
   - Ensure directories have proper permissions (we use /tmp for this)

## Monitoring

Monitor your deployment with:
```
koyeb service logs backdoor-ai
```

Access your application at `https://backdoor-ai-<your-org>.koyeb.app`
