# Koyeb Deployment Instructions

This guide provides instructions for deploying the Backdoor AI Learning Server to Koyeb.

## Option 1: Deploy using koyeb.yaml (recommended)

1. Make sure you have the [Koyeb CLI](https://www.koyeb.com/docs/cli/installation) installed
2. Login to your Koyeb account:
   ```
   koyeb login
   ```
3. Deploy using the koyeb.yaml configuration:
   ```
   koyeb app create --name backdoor-ai --ports 10000:http --git github.com/Backdoor-main/Main-server --git-branch main --git-builder-image docker
   ```
4. Add your Dropbox API key as a secret:
   ```
   koyeb secret create dropbox-api-key --value "YOUR_DROPBOX_API_KEY"
   ```

## Option 2: Deploy using Docker

1. Build the Docker image locally:
   ```
   ./build-docker.sh
   ```
2. Tag and push to your container registry:
   ```
   docker tag backdoor-ai:latest registry.koyeb.com/your-username/backdoor-ai:latest
   docker push registry.koyeb.com/your-username/backdoor-ai:latest
   ```
3. Deploy to Koyeb:
   ```
   koyeb app create backdoor-ai --docker registry.koyeb.com/your-username/backdoor-ai:latest --ports 10000:http
   ```
4. Add your Dropbox API key as a secret

## Monitoring Your Deployment

1. Check deployment status:
   ```
   koyeb service get backdoor-ai
   ```
2. View logs:
   ```
   koyeb service logs backdoor-ai
   ```
3. Access the health endpoint to verify the service is running:
   ```
   curl https://your-deployment-url.koyeb.app/health
   ```

## Troubleshooting

If you encounter issues with the deployment:

1. Check if the service has adequate resources (memory, CPU)
2. Verify your Dropbox API key is correctly configured
3. View detailed logs to identify any startup errors
4. Test locally using Docker to verify the application works before deploying
