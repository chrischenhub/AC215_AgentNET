#!/usr/bin/env bash
set -e -o pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
IMAGE_NAME="${IMAGE_NAME:-agentnet-dvc}"
DOCKERFILE="${DOCKERFILE:-Dockerfile.dvc-cli}"
BUCKET="${GCS_BUCKET_NAME:-agentnet215}"

if [[ "${DOCKERFILE}" != /* ]]; then
  if [[ -f "${SCRIPT_DIR}/${DOCKERFILE}" ]]; then
    DOCKERFILE="${SCRIPT_DIR}/${DOCKERFILE}"
  else
    DOCKERFILE="${REPO_ROOT}/${DOCKERFILE}"
  fi
fi

# Default credentials location; override by exporting GOOGLE_APPLICATION_CREDENTIALS
DEFAULT_CREDS="$REPO_ROOT/src/models/secrets/service-account.json"
CREDS_PATH="${GOOGLE_APPLICATION_CREDENTIALS:-$DEFAULT_CREDS}"

CREDS_ARGS=()
if [[ -f "$CREDS_PATH" ]]; then
  CREDS_ARGS=(-v "${CREDS_PATH}":/secrets/service-account.json:ro -e GOOGLE_APPLICATION_CREDENTIALS=/secrets/service-account.json)
else
  echo "WARNING: credentials file not found at ${CREDS_PATH}. Continuing without mounting credentials."
fi

echo "Building image '${IMAGE_NAME}' from ${DOCKERFILE}"
docker build -t "${IMAGE_NAME}" -f "${DOCKERFILE}" "${REPO_ROOT}"

echo "Starting shell container (repo mounted at /app)"
docker run --rm -ti \
  -v "${REPO_ROOT}":/app \
  "${CREDS_ARGS[@]}" \
  -e GCS_BUCKET_NAME="${BUCKET}" \
  --cap-add SYS_ADMIN \
  --device /dev/fuse \
  "${IMAGE_NAME}" \
  /bin/bash
