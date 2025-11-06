# Agent-101 — Level 5 (Planning + Reflection + Hybrid Autonomy)

This level upgrades the agent from a simple “command executor” to an **autonomous planner** with **lightweight memory** and **self-reflection**. The agent can now interpret **high-level goals**, decompose them into multiple tasks, save them to the SQLite DB, and reflect on its actions for gradual improvement.

---

## 🔥 New Capabilities in Level-5

| Feature | Description |
|--------|-------------|
| ✅ Goal Planning (`plan <goal>`) | Breaks a high-level instruction into actionable subtasks |
| ✅ Hybrid Mode | Uses GPT when available, otherwise falls back to rule-based planning |
| ✅ Reflection Memory | Stores short “lessons” when planning or completing tasks |
| ✅ `reflect` Command | View recent learnings |
| ✅ Persistent Memory | Stored in `agent_memory.json` |
| ✅ Mode Awareness | (online/offline) can later be displayed to user |

---

## 📁 Project Structure

agent-101-level-5/
├── agent_todo.py # main entrypoint (CLI + agent path)
├── planner.py # hybrid goal decomposition (GPT + fallback)
├── reflection.py # minimal memory + append-only log
├── agent_memory.json # lightweight persistent memory
├── todos.db # sqlite database (tasks + reminders)
└── README.md # you are here


---

## 🧠 Architecture Overview

User
│
├─ "add/complete/update/list" → standard to-do logic (Level 4)
│
├─ "plan ..." ──────► planner.py
│ │
│ ├─ GPT mode (if installed + OPENAI_API_KEY)
│ └─ local fallback (no network)
│
├─ tasks inserted into todos.db
│
└─ reflection.py logs "planned N tasks" + "completed task X"


---

## 🧪 Usage

### Plan a high-level goal

Creates multiple tasks (hybrid planner).

### View reflections

Shows recent takeaways from planning / completion.

### Other examples

add pay bill tomorrow 5pm
ls -t
complete task 1
reflect


---

## 🌐 Hybrid Mode

| Condition | Behavior |
|----------|----------|
| `openai` not installed or `OPENAI_API_KEY` missing | Offline CLI-only fallback |
| `openai` installed + key provided | Planner may use GPT for richer subtasks |

(Mode indicator coming in Level 5.1 patch)

---

## ⚙️ Running

```bash
python agent_todo.py

Optional (online agent mode):

pip install openai
export OPENAI_API_KEY=your_key_here
python agent_todo.py

| Milestone                       | Completed        |
| ------------------------------- | ---------------- |
| CRUD Tasks + Filtering          | ✅ (from Level 4) |
| Local + Online dual mode        | ✅                |
| Goal → subtasks planning        | ✅                |
| Reflection / memory             | ✅                |
| Hybrid execution (offline safe) | ✅                |
| Agent readiness for Level 6     | ✅                |
