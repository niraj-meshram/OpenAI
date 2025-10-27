# 🧠 OpenAI Learning Repo

This repository is my personal playground for learning how to use the **OpenAI API** — step by step.  
It includes small practical examples (like a To-Do Agent) that demonstrate how function calling, tools, and the new `responses` API work.

---

## 📌 What this repo covers

| Topic | Status | Description |
|------|--------|-------------|
| ✅ API Setup & Keys | Done | How to create and load `OPENAI_API_KEY` |
| ✅ First API Call | Done | Basic text completion |
| ✅ Responses API | Done | Using `client.responses.create()` |
| ✅ Tool / Function Calling | Done | To-Do agent that reads/writes SQLite |
| 🔜 Agents & Memory | Planned | Multi-step conversations |
| 🔜 RAG Examples | Planned | Search + Local data |
| 🔜 Assistants API | Planned | Managed agent example |

---

## 🛠 Prerequisites

- Python 3.9+
- A valid OpenAI API key  
  > Get one from: https://platform.openai.com → Dashboard → API Keys  
  And store it in your environment:
  ```bash
  setx OPENAI_API_KEY "sk-xxxx"     # Windows