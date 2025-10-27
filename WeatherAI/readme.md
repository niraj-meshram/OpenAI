# WeatherAI Agent App

An interactive AI-powered weather agent built with the OpenAI Agents SDK and Streamlit.
Ask for current weather, tomorrow’s forecast, or a 6‑month climate history & outlook for any city worldwide.

---

## Features
- Interactive web UI (Streamlit widgets)
- Uses OpenAI Agents SDK (`@function_tool`) for intelligent tool calling
- 6‑Month Trend Tool — retrieves past and next 6‑month temperature averages
- Supports both °C and °F
- Ready for deployment (Streamlit Cloud, Render, or Docker)

---

## Project Structure

- `streamlit_app.py` — Main Streamlit interface
- `weather_agent.py` — Agent definition & tools (`get_forecast`, `get_six_month_trend`)
- `interactive_cli.py` — CLI version for terminal use
- `app.py` — One‑shot CLI example
- `requirements.txt`
- `README.md`

---

## Requirements
- Python 3.9+
- OpenAI account with API key

---

## Local Setup

```bash
# 1) Create and activate a virtual env
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate

# 2) Install dependencies
pip install -r requirements.txt

# 3) Set your API key
# PowerShell (current shell)
$env:OPENAI_API_KEY="sk-..."
# Or persist for future shells
setx OPENAI_API_KEY "sk-..."

# 4) Run the app
streamlit run streamlit_app.py
```

Open your browser at http://localhost:8501

---

## Deployment

Streamlit Cloud
- Push this repo to GitHub
- Create a new app pointing to `streamlit_app.py`
- Add a Secret `OPENAI_API_KEY = sk-...`

Docker
```bash
docker build -t weather-agent .
docker run -e OPENAI_API_KEY=sk-... -p 8501:8501 weather-agent
```

---

## Example Queries
- Phoenix
- Salt Lake City tomorrow
- Denver trend
- New York past 6 and next 6

---

## License

MIT License © 2025 Niraj Meshram

