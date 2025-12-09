# syntax=docker/dockerfile:1.7
FROM python:3.12-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    POETRY_VIRTUALENVS_CREATE=0 \
    APP_ROOT=/app \
    APP_MODELS_DIR=/app/src/models \
    GOOGLE_APPLICATION_CREDENTIALS=/app/src/models/secrets/service-account.json \
    GCS_BUCKET_NAME=agentnet215 \
    GCS_DATA_DIR=mcp_data_json \
    GCS_CHROMA_DIR=chroma_store

# ---------- OS deps ----------
# Keep Node.js (useful if you later test stdio MCPs via npx), plus build tools for native wheels
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl ca-certificates gnupg build-essential git pkg-config fuse3 \
 && mkdir -p /etc/apt/keyrings \
 && curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key \
      | gpg --dearmor -o /etc/apt/keyrings/nodesource.gpg \
 && echo "deb [signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_20.x nodistro main" \
      > /etc/apt/sources.list.d/nodesource.list \
 && apt-get update && apt-get install -y nodejs \
 && node -v && npm -v \
 && curl -fsSL https://packages.cloud.google.com/apt/doc/apt-key.gpg \
      | gpg --dearmor -o /etc/apt/trusted.gpg.d/google-cloud.gpg \
 && echo "deb [signed-by=/etc/apt/trusted.gpg.d/google-cloud.gpg] https://packages.cloud.google.com/apt cloud-sdk main" \
      > /etc/apt/sources.list.d/google-cloud-sdk.list \
 && export GCSFUSE_REPO="gcsfuse-$(. /etc/os-release && echo $VERSION_CODENAME)" \
 && echo "deb [signed-by=/etc/apt/trusted.gpg.d/google-cloud.gpg] https://packages.cloud.google.com/apt ${GCSFUSE_REPO} main" \
      > /etc/apt/sources.list.d/gcsfuse.list \
 && apt-get update \
 && apt-get install -y --no-install-recommends google-cloud-sdk gcsfuse \
 && echo "user_allow_other" >> /etc/fuse.conf \
 && rm -rf /var/lib/apt/lists/*

# ---------- Python deps (layer-cached) ----------
# Install numpy first (often speeds up later builds), then the rest.
# Note: paths are relative to build context (src/ directory)
COPY models/requirements.txt /app/src/models/requirements.txt
RUN pip install --upgrade pip wheel \
 && pip install --no-cache-dir numpy \
 && pip install --no-cache-dir -r /app/src/models/requirements.txt

# Application code
COPY models /app/src/models

# ---------- Entrypoint ----------
COPY models/docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh

# switch to
# RUN chmod +x /usr/local/bin/docker-entrypoint.sh if not working
RUN sed -i 's/\r$//' /usr/local/bin/docker-entrypoint.sh \
 && chmod +x /usr/local/bin/docker-entrypoint.sh

WORKDIR /app/src/models

ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]
