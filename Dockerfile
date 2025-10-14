# syntax=docker/dockerfile:1.7
FROM python:3.12-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    POETRY_VIRTUALENVS_CREATE=0

# ---------- OS deps ----------
# Keep Node.js (useful if you later test stdio MCPs via npx), plus build tools for native wheels
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl ca-certificates gnupg build-essential git pkg-config \
 && mkdir -p /etc/apt/keyrings \
 && curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key \
      | gpg --dearmor -o /etc/apt/keyrings/nodesource.gpg \
 && echo "deb [signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_20.x nodistro main" \
      > /etc/apt/sources.list.d/nodesource.list \
 && apt-get update && apt-get install -y nodejs \
 && node -v && npm -v \
 && rm -rf /var/lib/apt/lists/*

# ---------- Python deps (layer-cached) ----------
# Install numpy first (often speeds up later builds), then the rest.
COPY requirements.txt /app/requirements.txt
RUN pip install --upgrade pip wheel \
 && pip install --no-cache-dir numpy \
 && pip install --no-cache-dir -r /app/requirements.txt

# NOTE: We do NOT COPY your source code here.
# We'll bind-mount the repo at runtime so edits are reflected instantly.

# ---------- Entrypoint ----------
COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]
CMD ["/bin/bash"]
