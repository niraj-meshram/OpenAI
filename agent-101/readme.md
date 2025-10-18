# 🧠 Agent-101: Your First Agentic AI (OpenAI Responses + Python)

This project is a **minimal working AI agent** that understands natural language
and performs real actions using **tools (functions)** — not just chat.

Unlike a normal chatbot, this agent can:
✅ Interpret your request  
✅ Decide which tool (function) to use  
✅ Execute real code  
✅ Store & retrieve data from a local database  
✅ Persist state between runs

---

## 🚀 What this Agent Does

This is a **To-Do List Agent** that:
- Adds tasks (e.g., “add buy milk tomorrow 5pm”)
- Lists pending tasks
- Marks tasks as complete

Tasks are saved in a **SQLite database**, so they remain even if you close the program.

---

## 🧩 How it Works (Simple Explanation)

| Part | Role |
|-----|------|
| OpenAI Responses API | The brain – decides what to do |
| Python functions | The agent’s “hands” (tools) |
| SQLite DB | Long-term memory |
| Natural language | You talk normally; no code required |

When you say:

add buy milk tomorrow 5pm

The model decides:
→ “I should call add_task()”  
→ It passes arguments  
→ Python executes the function  
→ Response is shown back to user  
→ Task is persisted in the DB

---

## 🛠 Tech Stack

| Tech | Purpose |
|------|---------|
| Python 3 | base runtime |
| OpenAI Responses API | agent orchestration |
| SQLite | local state & persistence |
| Function Calling | enables “tool use” |
| Fallback local summary | compatible with older SDKs |

---

## 📦 Installation

```bash
# Clone your repo (already done)
git clone https://github.com/niraj-meshram/OpenAI.git
cd OpenAI/agent-101

# (optional) create a virtual environment
python -m venv .venv
.\.venv\Scripts\activate  # Windows

# Install OpenAI SDK
pip install openai

setx OPENAI_API_KEY "your_api_key_here"

python agent_todo.py

add buy milk tomorrow 5pm
list my tasks
complete task 1

agent-101/
 ├── agent_todo.py   # the main agent
 └── README.md       # documentation

| Level | Feature                                                   |
| ----- | --------------------------------------------------------- |
| 2     | Natural language → real date parsing (“next Monday”, etc) |
| 3     | Multiple tools (calendar, email, web search)              |
| 4     | Long-term memory & personalization                        |
| 5     | Background actions (cron-like scheduling)                 |
| 6     | Multi-agent workflows                                     |
| 7     | UI / web-based interface                                  |


Created by Niraj Meshram
Guided setup & agent design using OpenAI Responses API