# OpenAI Learning Monorepo

A small, practical collection of OpenAI API experiments and demos.
It includes a production‑style Weather app, plus a series of Agent101 levels and simple TutorAI scripts.

## Structure
- `WeatherAI` - Python app with CLI/Streamlit UI, tests, Dockerfile, and CI
- `Agent101AI/agent-101-level-1..6` - step-by-step agent demos (SQLite To-Do, planning, reflection)
- `RestuarantNameGenerator` - Streamlit + LangChain mini-app that proposes a themed restaurant concept and menu
- `StockAI` - MCP stdio server exposing stock quote/history tools plus a small OpenAI-powered CLI agent
- `TutorAI` - small triage/sanity demo scripts

## Prerequisites
- Python 3.9+
- Set an OpenAI API key in your environment when using online agent features:
  - Windows (PowerShell): `setx OPENAI_API_KEY "sk-..."`
  - macOS/Linux: `export OPENAI_API_KEY="sk-..."`

## WeatherAI
- Create venv and install:
  - `python -m venv .venv && . .venv/Scripts/activate` (Windows PowerShell)
  - `pip install -r WeatherAI/requirements.txt`
- CLI:
  - `python WeatherAI/weather_ai/cli.py --help`
- Streamlit:
  - `streamlit run WeatherAI/streamlit_app.py`
- Tests:
  - `python -m pytest -q WeatherAI`

## Agent101AI
- Levels live under `Agent101AI/agent-101-level-*`.
- Each level is runnable directly, for example:
  - `cd Agent101AI/agent-101-level-1 && python agent_todo.py`
- Notes:
  - The demos persist tasks in a local SQLite DB (`todos.db`) in the level folder.
  - Some levels can run fully offline; online agent mode uses your `OPENAI_API_KEY`.

## TutorAI
- Quick scripts:
  - `python TutorAI/triage_demo.py`
  - `python TutorAI/sanity.py`

## RestuarantNameGenerator
- Streamlit front-end (`main.py`) calls LangChain against `gpt-4o-mini` to generate a catchy restaurant name plus five menu items for the selected cuisine.
- Dependencies: `streamlit`, `langchain-openai`, and `langchain-core`. Install them in a venv (either reuse the repo root venv or `cd RestuarantNameGenerator && python -m venv .venv && . .venv/Scripts/activate && pip install streamlit langchain-openai langchain-core`).
- API key handling: supply your OpenAI key via `secret_key.py` (see the existing example) or set the `OPENAI_API_KEY` environment variable before launching Streamlit.
- Run locally with `streamlit run RestuarantNameGenerator/main.py`, then pick a cuisine from the sidebar to see the generated concept and menu list.

## Development
- .gitignore ignores venvs, caches, IDE files, logs, and SQLite DBs.
- Keep local virtual environments inside each project if you prefer, or use a single venv at repo root.
- If you hit encoding artifacts in older READMEs, they’ve been normalized to UTF‑8 in this revision.
