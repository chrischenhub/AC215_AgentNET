#!/usr/bin/env bash
set -euo pipefail

# --- Helpers ---------------------------------------------------------------
log() { printf "[entrypoint] %s\n" "$*"; }

APP_ROOT=${APP_ROOT:-/app}
APP_DIR=${APP_DIR:-${APP_MODELS_DIR:-$APP_ROOT/src/models}}
GCS_BUCKET=${GCS_BUCKET_NAME:-agentnet215}
GCS_DATA_DIR=${GCS_DATA_DIR:-mcp_data_json}
GCS_CHROMA_DIR=${GCS_CHROMA_DIR:-chroma_store}
GCS_MOUNT_BASE=${GCS_MOUNT_BASE:-/mnt/gcs}
DATA_DIR="$APP_DIR/data_mcpinfo"
CHROMA_DIR="$APP_DIR/GCB"

source_env_file() {
  local f="$1"
  if [[ -f "$f" ]]; then
    log "Loading env file: $f"
    set -a
    # shellcheck disable=SC1090
    source "$f"
    set +a
  fi
}

maybe_pip_install() {
  local req=""
  local cache_dir="$APP_DIR/.cache"
  local stamp="$cache_dir/requirements.sha256"

  for candidate in "$APP_DIR/requirements.txt" "$APP_ROOT/requirements.txt"; do
    if [[ -f "$candidate" ]]; then
      req="$candidate"
      break
    fi
  done

  mkdir -p "$cache_dir"

  if [[ -n "$req" ]]; then
    local cur
    cur="$(sha256sum "$req" | awk '{print $1}')"

    if [[ ! -f "$stamp" ]] || [[ "$(<"$stamp")" != "$cur" ]]; then
      log "Detected new/changed requirements.txt at $req - installing Python deps..."
      python -m pip install --no-cache-dir -r "$req"
      echo "$cur" > "$stamp"
      log "Python deps installed."
    else
      log "requirements.txt unchanged - skipping pip install."
    fi
  else
    log "No requirements.txt found under $APP_DIR or $APP_ROOT - skipping pip install."
  fi
}

# --- Load environment ------------------------------------------------------
# Load .env files if present (compose also supports env_file, this is additive)
source_env_file "$APP_ROOT/.env"
source_env_file "$APP_ROOT/.env.local"
source_env_file "$APP_DIR/.env"
source_env_file "$APP_DIR/.env.local"

# --- Helpers for gcsfuse mounts -------------------------------------------
cleanup_mounts() {
  for target in "$DATA_DIR" "$CHROMA_DIR"; do
    if mountpoint -q "$target"; then
      fusermount -u "$target" 2>/dev/null || umount "$target" 2>/dev/null || true
    fi
    rm -rf "${target:?}/"*
  done
}

mount_gcs_subdir() {
  local subdir="$1"
  local target="$2"

  if ! command -v gcsfuse >/dev/null 2>&1; then
    log "WARN: gcsfuse not installed; skipping mount for $subdir"
    return
  fi
  if [[ -z "$GCS_BUCKET" ]]; then
    log "WARN: GCS_BUCKET_NAME not set; skipping mount for $subdir"
    return
  fi
  if [[ ! -f "${GOOGLE_APPLICATION_CREDENTIALS:-}" ]]; then
    log "WARN: GOOGLE_APPLICATION_CREDENTIALS not found; skipping mount for $subdir"
    return
  fi

  mkdir -p "$target" "$GCS_MOUNT_BASE"
  rm -rf "${target:?}/"*

  if gcsfuse -o allow_other --only-dir "$subdir" --key-file="$GOOGLE_APPLICATION_CREDENTIALS" "$GCS_BUCKET" "$target"; then
    log "Mounted gs://${GCS_BUCKET}/${subdir} to $target"
  else
    log "WARN: Failed to mount gs://${GCS_BUCKET}/${subdir}; leaving $target empty."
  fi
}

trap cleanup_mounts EXIT

# --- Ensure runtime dirs exist --------------------------------------------
mkdir -p "$APP_DIR/logs"

# Mount data and chroma stores (cleaned on exit)
mount_gcs_subdir "$GCS_DATA_DIR" "$DATA_DIR"
mount_gcs_subdir "$GCS_CHROMA_DIR" "$CHROMA_DIR"

# --- Developer context (helpful diagnostics) ------------------------------
log "Python: $(python --version 2>/dev/null || echo 'not found')"
log "Node: $(node -v 2>/dev/null || echo 'not found'), npm: $(npm -v 2>/dev/null || echo 'not found')"
log "Working dir: $(pwd)"
log "App dir: $APP_DIR"
log "User: $(id -u):$(id -g)"

# --- Auto-install deps on host edits (hot dev) -----------------------------
maybe_pip_install

# --- Warnings for likely-missing keys (non-fatal) --------------------------
[[ -z "${OPENAI_API_KEY:-}" ]] && log "WARN: OPENAI_API_KEY is not set."
[[ -z "${SMITHERY_API_KEY:-}" ]] && log "WARN: SMITHERY_API_KEY is not set."

# --- Default command -------------------------------------------------------
if [[ "$#" -eq 0 ]]; then
  set -- /bin/bash
fi

exec "$@"
