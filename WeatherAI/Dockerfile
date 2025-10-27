FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

FROM base AS builder

COPY requirements.txt ./
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

FROM base AS runtime

# Install curl for healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Copy only sources (context reduced by .dockerignore)
COPY . .

EXPOSE 8501

# Healthcheck against Streamlit's internal endpoint
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=5 \
  CMD curl -fsS http://127.0.0.1:${PORT:-8501}/_stcore/health || exit 1

CMD ["sh", "-c", "streamlit run streamlit_app.py --server.port ${PORT:-8501} --server.address ${HOST:-0.0.0.0}"]
