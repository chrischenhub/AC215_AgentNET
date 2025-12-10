#!/usr/bin/env bash
set -euo pipefail

log() { printf "[dvc-entrypoint] %s\n" "$*"; }

APP_ROOT=${APP_ROOT:-/app}
BUCKET="${GCS_BUCKET_NAME:-agentnet215}"
GCS_ONLY_DIR="${GCS_ONLY_DIR:-mcp_data_json}"
MOUNT_POINT="${GCS_MOUNT_POINT:-/mnt/gcs_data}"
TARGET_DIR="${DATA_MCPINFO_DIR:-$APP_ROOT/src/models/data_mcpinfo}"

if [[ -f "${GOOGLE_APPLICATION_CREDENTIALS:-}" ]]; then
  log "Activating service account with ${GOOGLE_APPLICATION_CREDENTIALS}"
  gcloud auth activate-service-account --key-file="$GOOGLE_APPLICATION_CREDENTIALS" >/dev/null 2>&1 || \
    log "WARN: gcloud auth failed; continuing without gcloud"
else
  log "No GOOGLE_APPLICATION_CREDENTIALS provided; gcloud auth skipped."
fi

if command -v gcsfuse >/dev/null 2>&1 && [[ -n "$BUCKET" ]]; then
  mkdir -p "$MOUNT_POINT"
  log "Mounting gs://${BUCKET}/${GCS_ONLY_DIR} to $MOUNT_POINT"
  GCS_DIR_FLAG=()
  if [[ -n "$GCS_ONLY_DIR" ]]; then
    GCS_DIR_FLAG=(--only-dir "$GCS_ONLY_DIR")
  fi
  if ! gcsfuse -o allow_other "${GCS_DIR_FLAG[@]}" --key-file="${GOOGLE_APPLICATION_CREDENTIALS:-}" "$BUCKET" "$MOUNT_POINT"; then
    log "WARN: gcsfuse mount failed (bucket may be unavailable or missing permissions)."
  else
    mkdir -p "$TARGET_DIR"
    if mount --bind "$MOUNT_POINT" "$TARGET_DIR"; then
      log "Bound $MOUNT_POINT to $TARGET_DIR"
    else
      log "WARN: bind mount to $TARGET_DIR failed."
    fi
  fi
else
  log "gcsfuse not available or bucket name empty; skipping mount."
fi

# Mark the repo as safe to avoid git ownership complaints inside the container
git config --global --add safe.directory "$APP_ROOT" >/dev/null 2>&1 || \
  log "WARN: unable to mark $APP_ROOT as a safe git directory"

cd "$APP_ROOT"
log "Working directory: $(pwd)"

exec "$@"
