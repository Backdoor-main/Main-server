#!/bin/bash
set -e

echo "Building Docker image for Koyeb deployment..."

# Ensure we have Docker installed
if ! command -v docker &> /dev/null; then
    echo "Docker is not installed. Please install Docker first."
    exit 1
fi

# Build the Docker image
docker build -t backdoor-ai:latest .

echo "Docker build completed successfully."
echo "To test locally: docker run -p 10000:10000 backdoor-ai:latest"
echo ""
echo "To deploy to Koyeb:"
echo "1. Tag the image: docker tag backdoor-ai:latest registry.koyeb.com/your-username/backdoor-ai:latest"
echo "2. Push to registry: docker push registry.koyeb.com/your-username/backdoor-ai:latest"
echo "3. Deploy on Koyeb: koyeb app create backdoor-ai --docker registry.koyeb.com/your-username/backdoor-ai:latest --ports 10000:http"
