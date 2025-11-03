# WeatherAI

Agentic weather app with Streamlit and the OpenAI Agents SDK. It answers quick weather questions for today/tomorrow and shows a 6‑month historical trend plus a seasonal baseline outlook using Open‑Meteo.

The UI is built with Streamlit. A simple CLI is included for agent-backed Q&A.

---

## Features

- Quick weather: max/min temperature and a code description for today or tomorrow.
- 6‑month trend: monthly averages for the past 6 months, plus a seasonal baseline for the next 6 months (10‑year monthly climatology).
- Streamlit UI: interactive tabs, charts, and CSV downloads.
- CLI: ask questions like “weather in Phoenix today”.

---

## Requirements

- Python 3.9+
- OpenAI API key in `OPENAI_API_KEY` (required for the Agents SDK)
- Internet access (uses Open‑Meteo public APIs; no key required)

---

## Quick Start

1) Create a virtual environment and install deps:

```bash
python -m venv .venv
. .venv/Scripts/activate  # Windows PowerShell: .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

2) Set your OpenAI key (pick one):

- Environment variable (recommended):
  - Windows (PowerShell): `setx OPENAI_API_KEY "sk-..."`
  - macOS/Linux: `export OPENAI_API_KEY="sk-..."`
- Streamlit secrets (optional): create `.streamlit/secrets.toml` with:
  ```toml
  OPENAI_API_KEY = "sk-..."
  ```
- Local `.env` file (optional, for local dev): add a line `OPENAI_API_KEY=sk-...`

3) Run the Streamlit app:

```bash
streamlit run streamlit_app.py
```

4) Or use the CLI:

```bash
python -m weather_ai.cli "weather in Phoenix today"
# If installed as a package (editable):
# pip install -e .
# weather-ai "weather in Phoenix today"
```

---

## Docker

Build and run with your key passed at runtime:

```bash
docker build -t weather-ai .
docker run --rm -e OPENAI_API_KEY=$OPENAI_API_KEY -p 8501:8501 weather-ai
```

The container exposes Streamlit on port `8501`. Healthcheck probes the internal Streamlit endpoint.

---

## Project Structure

- `streamlit_app.py` — Streamlit entry that renders the UI.
- `weather_ai/ui/app.py` — Streamlit UI logic and state.
- `weather_ai/tools/api.py` — Calls to Open‑Meteo (geocoding, forecast, archive) and aggregation.
- `weather_ai/agents/weather_agent.py` — Agent and tools wired via OpenAI Agents SDK.
- `weather_ai/utils/units.py` — Unit conversions and small formatting/helpers.
- `weather_ai/cli.py` — Minimal CLI using the agent runner.
- `tests/test_units.py` — Unit tests for conversions and formatting.
- `Dockerfile` — Multi‑stage image with healthcheck.
- `Makefile` — Helper targets for install, run, tests, and Docker.

---

## Make Targets

- `make venv` — Create `.venv` virtual environment.
- `make install` — Activate venv and install requirements.
- `make run` — Start Streamlit app.
- `make run-cli` — Example CLI invocation.
- `make test` — Run unit tests.
- `make docker-build` / `make docker-run` — Build and run the container.

---

## Notes & Limits

- Forecast data comes from Open‑Meteo’s public API. Trend/outlook uses monthly averages; the “next 6 months” reflects a seasonal baseline (not a deterministic forecast).
- The app requires `OPENAI_API_KEY` for the Agents SDK even though Open‑Meteo itself does not need a key.
- Timeouts are set on outbound requests. Inputs are sanitized.

---

## Troubleshooting

- Missing `OPENAI_API_KEY`:
  - Symptom: Streamlit shows a warning to set the key, or CLI errors from the Agents SDK.
  - Fix: set `OPENAI_API_KEY` via env var, `.streamlit/secrets.toml`, or a local `.env`. On Windows, `setx` applies to new shells; open a new terminal.

- Network errors/timeouts:
  - Corporate proxy: set `HTTP_PROXY`/`HTTPS_PROXY` in your environment. For Docker builds, pass build args `HTTP_PROXY`, `HTTPS_PROXY`, `PIP_INDEX_URL`, `PIP_EXTRA_INDEX_URL`, `PIP_TRUSTED_HOST` as needed (see Dockerfile).
  - API outages: data comes from Open‑Meteo; retry later if unreachable.

- Windows venv activation blocked:
  - Use PowerShell: `..\.venv\Scripts\Activate.ps1`. If blocked, run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` and retry, or use CMD: `..\.venv\Scripts\activate.bat`.

- Streamlit port already in use:
  - Run `streamlit run streamlit_app.py --server.port 8502`.

- CLI import error (e.g., `agents` not found):
  - Ensure deps installed: `pip install -r requirements.txt`. Optionally install package editable: `pip install -e .`.

---

## Development

- Code style: Black/Ruff configured in `pyproject.toml`.
- Python: 3.9+.
- To run tests: `python -m unittest -v` or `make test`.

---

## Security

This project does not store keys in the repo. At runtime, the app looks for the key in this order: environment variable, Streamlit secrets, then optional `.env`. See `SECURITY.md` for details.

