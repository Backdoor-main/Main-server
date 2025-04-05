#!/bin/bash
set -e

echo "Building Docker image for Koyeb deployment..."

docker build -t backdoor-ai:latest .

echo "Docker build completed successfully."
echo "To run locally: docker run -p 10000:10000 backdoor-ai:latest"
echo "To push to Koyeb, first tag and push to your container registry."
