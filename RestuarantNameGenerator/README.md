# Restaurant Name Generator

Small Streamlit app that uses LangChain and the OpenAI `gpt-4o-mini` model to brainstorm a restaurant concept for the cuisine you choose.

## Features
- Sidebar cuisine picker (Indian, Italian, Mexican, Arabic, American by default)
- Generates a single catchy restaurant name plus five menu items
- Parallel LangChain pipelines so the name and menu arrive together

## Setup
1. `cd RestuarantNameGenerator`
2. Create/activate a virtual environment (example for PowerShell):
   ```powershell
   python -m venv .venv
   . .venv/Scripts/activate
   pip install streamlit langchain-openai langchain-core
   ```
3. Provide your OpenAI API key:
   - Either edit `secret_key.py` to return the key (see existing placeholder)
   - Or set `OPENAI_API_KEY` in the environment before launching Streamlit

## Run
```powershell
streamlit run main.py
```
Pick a cuisine from the sidebar to see the generated restaurant name and comma-separated menu rendered as a bulleted list.

## Notes
- `langchain_helper.py` wires up the prompts and handles the API calls.
- Streamlit keeps state minimal, so you can refresh to explore different cuisines quickly.
