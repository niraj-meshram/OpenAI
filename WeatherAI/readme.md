# 🌦️ WeatherAI Agent App

An interactive **AI-powered weather agent** built with the **OpenAI Agents SDK** and **Streamlit**.  
Ask for current weather, tomorrow’s forecast, or a 6-month climate history & outlook for any city worldwide.

---

## 🚀 Features
- **Interactive web UI** (Streamlit widgets)
- Uses **OpenAI Agents SDK** (`@function_tool`) for intelligent tool calling
- **6-Month Trend Tool** — retrieves past & next 6-month temperature averages
- Supports both **°C and °F**
- Ready for **deployment** (Streamlit Cloud, Render, or Docker)

---

## 🧩 Project Structure

├── streamlit_app.py # Main Streamlit interface
├── weather_agent.py # Agent definition & tools (get_forecast, get_six_month_trend)
├── interactive_cli.py # CLI version for terminal use
├── requirements.txt
├── README.md
└── .gitignore


---

## 🧰 Requirements
- Python **3.9+**
- OpenAI account with API key

---

## 🧪 Local Setup

```bash
# 1. Clone the repo
git clone https://github.com/<your-username>/WeatherAI.git
cd WeatherAI

# 2. Create and activate venv
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Add your API key
setx OPENAI_API_KEY "sk-..."      # (Windows PowerShell)
# or export OPENAI_API_KEY="sk-..." on macOS/Linux

# 5. Run the app
streamlit run streamlit_app.py

Open your browser → http://localhost:8501

☁️ Deployment
Option 1: Streamlit Cloud

Push this repo to GitHub.

Visit https://share.streamlit.io

New App → connect your repo → choose streamlit_app.py

In “Secrets” panel, add

OPENAI_API_KEY = sk-xxxx

streamlit run streamlit_app.py --server.port $PORT --server.address 0.0.0.0

docker build -t weather-agent .
docker run -e OPENAI_API_KEY=sk-... -p 8501:8501 weather-agent

💡 Example Queries

Phoenix

Salt Lake City tomorrow

Denver trend

New York past 6 and next 6

📜 License

MIT License © 2025 Niraj Meshram