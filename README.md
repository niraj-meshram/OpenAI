# 🧠 Agent-101 — Level 2: Natural-Language Due Dates (OpenAI Responses + SQLite)

Level 2 upgrades your Level 1 To-Do agent so it can understand due dates written in **natural language** (e.g., “tomorrow 5pm”, “next Monday 8am”), parse them into a **real timestamp**, and sort tasks by the actual time.

## 🚀 What’s new in Level 2

- ✅ **Natural-language date parsing** using `dateparser`
- ✅ New DB column **`due_at`** (ISO8601 datetime with timezone)
- ✅ Stores both:
  - `due` → the original text you typed
  - `due_at` → parsed machine-readable datetime
- ✅ Smarter listing: orders by `done`, then earliest `due_at`
- ✅ Robust extraction: if the model passes only a single string (e.g., “buy milk tomorrow 5pm”), the agent **auto-extracts** the due phrase from the title

> TL;DR — The agent now *understands time*, not just text.

---

## 🧩 Architecture snapshot

