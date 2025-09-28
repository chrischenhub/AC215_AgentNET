#!/bin/bash
set -euo pipefail

if [ -f "/app/.env" ]; then
  set -a
  source /app/.env
  set +a
fi

mkdir -p /app/DB/chroma_store

if [ "$#" -eq 0 ]; then
  set -- /bin/bash
fi

exec "$@"
