# syntax=docker/dockerfile:1.4
FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

FROM base AS builder

RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates openssl \
    && rm -rf /var/lib/apt/lists/*

# Allow corporate proxies and pip config via build args
ARG HTTP_PROXY
ARG HTTPS_PROXY
ARG PIP_INDEX_URL
ARG PIP_EXTRA_INDEX_URL
ARG PIP_TRUSTED_HOST

ENV HTTP_PROXY=${HTTP_PROXY} \
    HTTPS_PROXY=${HTTPS_PROXY} \
    PIP_INDEX_URL=${PIP_INDEX_URL} \
    PIP_EXTRA_INDEX_URL=${PIP_EXTRA_INDEX_URL} \
    PIP_TRUSTED_HOST=${PIP_TRUSTED_HOST}


COPY requirements.txt ./
# Configure pip if proxy or custom index/trusted hosts are provided
RUN set -eux; \
    if [ -n "${PIP_INDEX_URL}" ]; then pip config set global.index-url "${PIP_INDEX_URL}"; fi; \
    if [ -n "${PIP_EXTRA_INDEX_URL}" ]; then pip config set global.extra-index-url "${PIP_EXTRA_INDEX_URL}"; fi; \
    if [ -n "${PIP_TRUSTED_HOST}" ]; then for h in ${PIP_TRUSTED_HOST}; do pip config set global.trusted-host "$h"; done; fi; \
    pip install --no-cache-dir --upgrade pip setuptools wheel; \
    pip install --no-cache-dir --default-timeout=60 --prefix=/install -r requirements.txt

FROM base AS runtime

# Install curl for healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Copy Python deps from builder stage
COPY --from=builder /install /usr/local

# Copy only sources (context reduced by .dockerignore)
COPY . .



EXPOSE 8501

# Healthcheck against Streamlit's internal endpoint
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=5 \
  CMD curl -fsS http://127.0.0.1:${PORT:-8501}/_stcore/health || exit 1

CMD ["sh", "-c", "streamlit run streamlit_app.py --server.port ${PORT:-8501} --server.address ${HOST:-0.0.0.0}"]
