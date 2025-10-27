PY=python

.PHONY: venv install test run run-cli fmt docker-build docker-run

venv:
	$(PY) -m venv .venv

install:
	. .venv/Scripts/activate 2>/dev/null || . .venv/bin/activate; pip install -r requirements.txt

test:
	$(PY) -m unittest discover -s tests -v

run:
	streamlit run streamlit_app.py

run-cli:
	$(PY) -m weather_ai.cli "weather in Phoenix today"

docker-build:
	docker build -t weather-ai .

docker-run:
	docker run --rm -e OPENAI_API_KEY=$$OPENAI_API_KEY -p 8501:8501 weather-ai

