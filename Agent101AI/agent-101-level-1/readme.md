# ðŸ§  Agent-101: Your First Agentic AI (OpenAI Responses + Python)

This project is a **minimal working AI agent** that understands natural language
and performs real actions using **tools (functions)** â€” not just chat.

Unlike a normal chatbot, this agent can:
âœ… Interpret your request  
âœ… Decide which tool (function) to use  
âœ… Execute real code  
âœ… Store & retrieve data from a local database  
âœ… Persist state between runs

---

## ðŸš€ What this Agent Does

This is a **To-Do List Agent** that:
- Adds tasks (e.g., â€œadd buy milk tomorrow 5pmâ€)
- Lists pending tasks
- Marks tasks as complete

Tasks are saved in a **SQLite database**, so they remain even if you close the program.

---

## ðŸ§© How it Works (Simple Explanation)

| Part | Role |
|-----|------|
| OpenAI Responses API | The brain â€“ decides what to do |
| Python functions | The agentâ€™s â€œhandsâ€ (tools) |
| SQLite DB | Long-term memory |
| Natural language | You talk normally; no code required |

When you say:

add buy milk tomorrow 5pm

The model decides:
â†’ â€œI should call add_task()â€  
â†’ It passes arguments  
â†’ Python executes the function  
â†’ Response is shown back to user  
â†’ Task is persisted in the DB

---

## ðŸ›  Tech Stack

| Tech | Purpose |
|------|---------|
| Python 3 | base runtime |
| OpenAI Responses API | agent orchestration |
| SQLite | local state & persistence |
| Function Calling | enables â€œtool useâ€ |
| Fallback local summary | compatible with older SDKs |

---

## ðŸ“¦ Installation

```bash
# Clone your repo (already done)
git clone https://github.com/niraj-meshram/OpenAI.git
cd OpenAI/Agent101AI/agent-101-level-1

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
 â”œâ”€â”€ agent_todo.py   # the main agent
 â””â”€â”€ README.md       # documentation

| Level | Feature                                                   |
| ----- | --------------------------------------------------------- |
| 2     | Natural language â†’ real date parsing (â€œnext Mondayâ€, etc) |
| 3     | Multiple tools (calendar, email, web search)              |
| 4     | Long-term memory & personalization                        |
| 5     | Background actions (cron-like scheduling)                 |
| 6     | Multi-agent workflows                                     |
| 7     | UI / web-based interface                                  |


Created by Niraj Meshram
Guided setup & agent design using OpenAI Responses API


