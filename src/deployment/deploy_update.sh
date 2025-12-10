#!/bin/bash
set -e

# This script is intended to be run inside the deployment docker container.

echo ">>> Updating deploy_images stack..."
cd deploy_images
pulumi up --stack dev --refresh -y

echo ">>> Updating deploy_k8s stack..."
cd ../deploy_k8s
pulumi up --stack dev --refresh -y

echo ">>> Deployment update complete!"
