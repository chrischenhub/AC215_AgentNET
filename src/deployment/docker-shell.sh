#!/bin/bash
set -euo pipefail

# Define some environment variables
export IMAGE_NAME="agentnet-deployment"
# Get the directory where this script is located (src/deployment)
export SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export BASE_DIR="$SCRIPT_DIR"
export WORKSPACE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)" # points to src/
export FRONTEND_DIR="$WORKSPACE_DIR/frontend-simple"
export SECRETS_DIR="$BASE_DIR/secrets"
export GCP_PROJECT="${GCP_PROJECT:-charlesproject-471117}" # Change to your GCP Project
export GCP_REGION="${GCP_REGION:-us-central1}"
export GCP_ZONE="${GCP_ZONE:-us-central1-a}"
export GOOGLE_APPLICATION_CREDENTIALS="${GOOGLE_APPLICATION_CREDENTIALS:-/secrets/deployment.json}"
export PULUMI_BUCKET="${PULUMI_BUCKET:-gs://${GCP_PROJECT}-pulumi-state-bucket}"

# Create local Pulumi plugins directory if it doesn't exist
mkdir -p "$BASE_DIR/pulumi-plugins"

# Check if container is already running
if docker ps --format "table {{.Names}}" | grep -q "^${IMAGE_NAME}$"; then
    echo "Container '${IMAGE_NAME}' is already running. Shelling into existing container..."
    docker exec -it "$IMAGE_NAME" /bin/bash ./docker-entrypoint.sh
else
    echo "Container '${IMAGE_NAME}' is not running. Building and starting new container..."

    # Build the image based on the Dockerfile
    docker build -t "$IMAGE_NAME" --platform=linux/amd64 -f "$BASE_DIR/Dockerfile" "$BASE_DIR"

    # Run the container
    docker run --rm --name "$IMAGE_NAME" -ti \
        -v /var/run/docker.sock:/var/run/docker.sock \
        -v "$BASE_DIR":/app \
        -v "$WORKSPACE_DIR":/workspace \
        -v "$WORKSPACE_DIR/models":/models \
        -v "$FRONTEND_DIR":/frontend-simple \
        -v "$SECRETS_DIR":/secrets \
        -v "$BASE_DIR/docker_config.json":/root/.docker/config.json \
        -v "$BASE_DIR/pulumi-plugins":/root/.pulumi/plugins \
        -e GOOGLE_APPLICATION_CREDENTIALS="$GOOGLE_APPLICATION_CREDENTIALS" \
        -e USE_GKE_GCLOUD_AUTH_PLUGIN=True \
        -e GCP_PROJECT="$GCP_PROJECT" \
        -e GCP_REGION="$GCP_REGION" \
        -e GCP_ZONE="$GCP_ZONE" \
        -e PULUMI_BUCKET="$PULUMI_BUCKET" \
        "$IMAGE_NAME"
fi
