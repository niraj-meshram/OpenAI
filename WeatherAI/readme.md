# WeatherAI Agent App

Agentic weather app using the OpenAI Agents SDK + Streamlit.
Ask for today/tomorrow’s weather or a 6‑month climate history and seasonal outlook. UI supports °C/°F with conversions.

---

## Features
- Agent tools: forecast and 6‑month trend via `@function_tool`
- Streamlit UI: natural summaries with emoji, metrics, charts, CSV downloads
- Unit-aware: strictly honors °C/°F selection everywhere
- Caching: memoized calls for responsive UI

---

## Architecture
- Package: `weather_ai` (agentic structure)
  - `agents/weather_agent.py` — Agent definition + tools (`get_forecast`, `get_six_month_trend`)
  - `tools/api.py` — HTTP/IO with timeouts, geocoding, forecast, climatology
  - `utils/units.py` — Conversions and display helpers
  - `ui/app.py` — Streamlit UI composition
- App entry: `streamlit_app.py` (thin wrapper calling `weather_ai.ui.app.render()`)
- CLI: `weather_ai/cli.py` (one‑shot; optional interactive mode)
- Tests: `tests/` (units conversion and formatting)

---

## Requirements
- Python 3.9+
- Env var: `OPENAI_API_KEY` (read on startup; Windows registry auto-load supported)

---

## Local Setup

```bash
python -m venv .venv
.venv\Scripts\activate  # PowerShell
pip install -r requirements.txt

# API key
$env:OPENAI_API_KEY="sk-..."        # current shell
setx OPENAI_API_KEY "sk-..."        # persistent (new shells)

# Run Streamlit (respects env STREAMLIT_SERVER_PORT or CLI --server.port)
streamlit run streamlit_app.py
```

Open: http://localhost:8501

---

## CLI

```bash
python -m weather_ai.cli "weather in Phoenix today"
```

---

## Deployment

Docker (GitHub Container Registry)
```bash
docker build -t ghcr.io/<your-org-or-user>/weather-ai:latest .
docker run -e OPENAI_API_KEY=sk-... -e PORT=8501 -p 8501:8501 ghcr.io/<your-org-or-user>/weather-ai:latest
# The container entry respects env PORT and HOST, defaults 8501/0.0.0.0
```

Healthcheck
- The container exposes a health endpoint used by Docker HEALTHCHECK at `/_stcore/health`.
- Example: `docker inspect --format='{{json .State.Health}}' <container>` to view health status.

---

## Security Notes
- Network calls use request timeouts
- Input validated and sanitized (city)
- API key only read from env/Windows user env (no hardcoding)

---

## License

MIT License © 2025 Niraj Meshram
