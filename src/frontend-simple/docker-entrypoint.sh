#!/usr/bin/env sh
set -e

APP_DIR="/usr/share/agentnet-frontend"
PORT="${PORT:-8080}"
API_BASE_URL="${API_BASE_URL:-http://localhost:8000/api}"

cat > "${APP_DIR}/config.js" <<EOF
window.AGENTNET_CONFIG = {
  apiBaseUrl: "${API_BASE_URL}"
};
EOF

exec http-server "${APP_DIR}" -p "${PORT}" -a "0.0.0.0" -c-1
