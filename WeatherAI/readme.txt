# WeatherAI Agent App

Agentic weather app using the OpenAI Agents SDK + Streamlit.
Ask for today/tomorrowâ€™s weather or a 6â€‘month climate history and seasonal outlook. UI supports Â°C/Â°F with conversions.

---

## Features
- Agent tools: forecast and 6â€‘month trend via `@function_tool`
- Streamlit UI: natural summaries with emoji, metrics, charts, CSV downloads
- Unit-aware: strictly honors Â°C/Â°F selection everywhere
- Caching: memoized calls for responsive UI

---

## Architecture
- Package: `weather_ai` (agentic structure)
  - `agents/weather_agent.py` â€“ Agent definition + tools (`get_forecast`, `get_six_month_trend`)
  - `tools/api.py` â€“ HTTP/IO with timeouts, geocoding, forecast, climatology
  - `utils/units.py` â€“ Conversions and display helpers
  - `ui/app.py` â€“ Streamlit UI composition
- App entry: `streamlit_app.py` (thin wrapper calling `weather_ai.ui.app.render()`)
- CLI: `weather_ai/cli.py` (oneâ€‘shot; optional interactive mode)
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

# Run Streamlit
streamlit run streamlit_app.py
```

Open: http://localhost:8501

---

## CLI

```bash
python -m weather_ai.cli "weather in Phoenix today"
```

---

## Security Notes
- Network calls use request timeouts
- Input validated and sanitized (city)
- API key only read from env/Windows user env (no hardcoding)

---

## License

MIT License Â© 2025 Niraj Meshram


