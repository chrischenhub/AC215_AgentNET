#!/bin/bash
set -euo pipefail

log() { printf "[deploy] %s\n" "$*"; }

REQUIRED_ENVS=(
  GOOGLE_APPLICATION_CREDENTIALS
  GCP_PROJECT
  GCP_REGION
  GCP_ZONE
  PULUMI_BUCKET
)
for var in "${REQUIRED_ENVS[@]}"; do
  if [[ -z "${!var:-}" ]]; then
    log "ERROR: $var is not set."
    exit 1
  fi
done

log "Container is running (arch: $(uname -m))"
log "Python: $(python --version 2>/dev/null || echo 'missing'), uv: $(uv --version 2>/dev/null || echo 'missing')"

# Ensure Python dependencies (pulumi_gcp, etc.) are present inside the container.
uv sync --frozen || {
    log "uv sync failed; attempting pip fallback for pulumi_gcp"
    pip install --no-cache-dir "pulumi-gcp>=9.3.0"
}

# Authenticate gcloud using service account
log "Activating gcloud service account"
gcloud auth activate-service-account --key-file "$GOOGLE_APPLICATION_CREDENTIALS"
gcloud config set project "$GCP_PROJECT"
gcloud config set compute/region "$GCP_REGION"
gcloud config set compute/zone "$GCP_ZONE"

# login to artifact-registry
log "Configuring Artifact Registry Docker auth for us-central1-docker.pkg.dev"
gcloud auth configure-docker us-central1-docker.pkg.dev --quiet

# Check if the Pulumi state bucket exists
if ! gsutil ls -b "$PULUMI_BUCKET" >/dev/null 2>&1; then
    log "Pulumi bucket does not exist. Creating..."
    gsutil mb -p "$GCP_PROJECT" "$PULUMI_BUCKET"
else
    log "Pulumi bucket already exists. Skipping creation."
fi

log "Logging into Pulumi using backend: $PULUMI_BUCKET"
pulumi login "$PULUMI_BUCKET"

# List available stacks
log "Available Pulumi stacks in GCS:"
gsutil ls "$PULUMI_BUCKET/.pulumi/stacks/"  || log "No stacks found."

cd /app
exec /bin/bash
