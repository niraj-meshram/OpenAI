# Security Overview

This project avoids bundling secrets or custom certificates and expects runtime configuration from safe sources.

## Secrets
- OPENAI_API_KEY is not hardcoded and is resolved at app startup in this order:
  1) OS environment variable `OPENAI_API_KEY` (preferred)
  2) Streamlit secrets (`.streamlit/secrets.toml`: OPENAI_API_KEY = "sk-...")
  3) Local `.env` file with a line `OPENAI_API_KEY=sk-...` (optional for local dev)
- No Windows registry auto-loading is used.
- Do not commit `.env` or any keys to the repository.

## Certificates
- No custom CAs or certificates are stored in the repo or injected by default.
- Docker image relies on the base OS trust store (`ca-certificates`).

## Networking
- External requests set explicit timeouts.
- Inputs (e.g., city names) are sanitized before use.

## Building Containers
- If your environment requires a proxy or private PyPI, pass valid build args (HTTP_PROXY/HTTPS_PROXY/PIP_INDEX_URL) during `podman build` and rely on your network perimeter to present a valid certificate chain.
- Avoid disabling TLS verification.

## Reporting
- If you discover a security issue, please report it privately to the maintainer rather than opening a public issue first.

