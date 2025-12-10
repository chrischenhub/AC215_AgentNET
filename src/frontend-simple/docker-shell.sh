#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
IMAGE_NAME="${IMAGE_NAME:-agentnet-frontend}"
PORT="${PORT:-8080}"
API_BASE_URL="${API_BASE_URL:-http://localhost:8000/api}"

docker build -t "${IMAGE_NAME}" "${SCRIPT_DIR}"

docker run --rm -ti \
  -p "${PORT}:${PORT}" \
  -e PORT="${PORT}" \
  -e API_BASE_URL="${API_BASE_URL}" \
  "${IMAGE_NAME}"
