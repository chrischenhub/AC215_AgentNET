#!/bin/bash

echo "Container is running!!!"
echo "Architecture: $(uname -m)"
echo "Environment ready! Virtual environment activated."
echo "Python version: $(python --version)"
echo "UV version: $(uv --version)"

# Ensure Python dependencies (pulumi_gcp, etc.) are present inside the container.
# Re-syncing here guarantees modules like pulumi_gcp.compute are installed even if the image was built earlier.
uv sync --frozen || {
    echo "uv sync failed; attempting pip fallback for pulumi_gcp"
    pip install --no-cache-dir pulumi-gcp>=9.3.0
}

# Authenticate gcloud using service account
gcloud auth activate-service-account --key-file $GOOGLE_APPLICATION_CREDENTIALS
gcloud config set project $GCP_PROJECT
# login to artifact-registry
gcloud auth configure-docker us-central1-docker.pkg.dev --quiet
# Check if the bucket exists
if ! gsutil ls -b $PULUMI_BUCKET >/dev/null 2>&1; then
    echo "Bucket does not exist. Creating..."
    gsutil mb -p $GCP_PROJECT $PULUMI_BUCKET
else
    echo "Bucket already exists. Skipping creation."
fi

echo "Logging into Pulumi using GCS bucket: $PULUMI_BUCKET"
pulumi login $PULUMI_BUCKET

# List available stacks
echo "Available Pulumi stacks in GCS:"
gsutil ls $PULUMI_BUCKET/.pulumi/stacks/  || echo "No stacks found."

# Run Bash for interactive mode
/bin/bash
