#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
IMAGE_NAME="${IMAGE_NAME:-agentnet-dvc}"
DOCKERFILE="${DOCKERFILE:-Dockerfile.dvc-cli}"
BUCKET="${GCS_BUCKET_NAME:-agentnet215}"

# Default credentials location; override by exporting GOOGLE_APPLICATION_CREDENTIALS
DEFAULT_CREDS="$ROOT_DIR/src/models/secrets/service-account.json"
CREDS_PATH="${GOOGLE_APPLICATION_CREDENTIALS:-$DEFAULT_CREDS}"

CREDS_ARGS=()
if [[ -f "$CREDS_PATH" ]]; then
  CREDS_ARGS=(-v "${CREDS_PATH}":/secrets/service-account.json:ro -e GOOGLE_APPLICATION_CREDENTIALS=/secrets/service-account.json)
else
  echo "WARNING: credentials file not found at ${CREDS_PATH}. Continuing without mounting credentials."
fi

echo "Building image '${IMAGE_NAME}' from ${DOCKERFILE}"
docker build -t "${IMAGE_NAME}" -f "${ROOT_DIR}/${DOCKERFILE}" "${ROOT_DIR}"

echo "Starting shell container (repo mounted at /app)"
docker run --rm -ti \
  -v "${ROOT_DIR}":/app \
  "${CREDS_ARGS[@]}" \
  -e GCS_BUCKET_NAME="${BUCKET}" \
  --cap-add SYS_ADMIN \
  --device /dev/fuse \
  "${IMAGE_NAME}" \
  /bin/bash
