#!/usr/bin/env bash
set -euo pipefail

# --- Helpers ---------------------------------------------------------------
log() { printf "[entrypoint] %s\n" "$*"; }

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
  local req="/app/requirements.txt"
  local cache_dir="/app/.cache"
  local stamp="$cache_dir/requirements.sha256"

  mkdir -p "$cache_dir"

  if [[ -f "$req" ]]; then
    local cur
    cur="$(sha256sum "$req" | awk '{print $1}')"

    if [[ ! -f "$stamp" ]] || [[ "$(<"$stamp")" != "$cur" ]]; then
      log "Detected new/changed requirements.txt — installing Python deps..."
      python -m pip install --no-cache-dir -r "$req"
      echo "$cur" > "$stamp"
      log "Python deps installed."
    else
      log "requirements.txt unchanged — skipping pip install."
    fi
  else
    log "No /app/requirements.txt found — skipping pip install."
  fi
}

# --- Load environment ------------------------------------------------------
# Load .env files if present (compose also supports env_file, this is additive)
source_env_file "/app/.env"
source_env_file "/app/.env.local"

# --- Ensure runtime dirs exist --------------------------------------------
mkdir -p /app/DB/chroma_store
mkdir -p /app/logs

# --- Developer context (helpful diagnostics) ------------------------------
log "Python: $(python --version 2>/dev/null || echo 'not found')"
log "Node: $(node -v 2>/dev/null || echo 'not found'), npm: $(npm -v 2>/dev/null || echo 'not found')"
log "Working dir: $(pwd)"
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
