# ──────────────────────────────────────────────────────────────────────────────
# AETHER-X — Autonomous Constellation Manager
# Base: ubuntu:22.04  (hard requirement)
# Exposes: 8000 (API) + 3000 (frontend dev)
# ──────────────────────────────────────────────────────────────────────────────

FROM ubuntu:22.04

# ── System deps ───────────────────────────────────────────────────────────────
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3.11 python3.11-dev python3-pip \
    curl ca-certificates gnupg \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# ── Node.js 20 ────────────────────────────────────────────────────────────────
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# ── Python alias ──────────────────────────────────────────────────────────────
RUN update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.11 1 \
    && update-alternatives --install /usr/bin/pip pip /usr/bin/pip3 1

WORKDIR /app

# ── Backend: install Python deps ──────────────────────────────────────────────
COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

# ── Frontend: install npm deps and build ──────────────────────────────────────
COPY frontend/package*.json ./frontend/
RUN cd frontend && npm ci --prefer-offline

COPY frontend/ ./frontend/
RUN cd frontend && npm run build

# ── Copy backend source ───────────────────────────────────────────────────────
COPY backend/ ./backend/

# ── Startup script ────────────────────────────────────────────────────────────
COPY infra/start.sh ./start.sh
RUN chmod +x ./start.sh

# ── Serve frontend static files via FastAPI ───────────────────────────────────
RUN pip install --no-cache-dir aiofiles

EXPOSE 8000

ENV PYTHONPATH=/app/backend
ENV PYTHONUNBUFFERED=1

CMD ["./start.sh"]
