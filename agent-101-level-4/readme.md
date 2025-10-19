Agent-101: Level 4 — To-Do Agent (CRUD + Filters + Reminders)

A tiny but capable console agent that manages a to-do list with:

✅ Complete CRUD: add / list / update / complete / delete

🗂️ Smart filters: today, this_week, overdue, open, done

⏰ Reminders: schedule, list, cancel (fires in the console)

🧰 Agentic mode using the OpenAI Responses API (tools/functions)

🧪 No-deps natural language date parser (today/tomorrow/next Mon/in 2h/10/21 4pm…)

🧱 Solid engineering: SQLite WAL, typed helpers, input validation, structured logs, graceful background scheduler

Works offline (no API key) using a local CLI fallback, and online (agent mode) with your OpenAI key.


# Agent-101: Level 3 — To-Do Agent (CRUD + Filters + Reminders)

A tiny but capable **console agent** that manages a to-do list with:

* ✅ **Complete CRUD**: add / list / update / complete / delete
* 🗂️ **Smart filters**: `today`, `this_week`, `overdue`, `open`, `done`
* ⏰ **Reminders**: schedule, list, cancel (fires in the console)
* 🧰 **Agentic mode** using the **OpenAI Responses API** (tools/functions)
* 🧪 **No-deps natural language date parser** (today/tomorrow/next Mon/`in 2h`/`10/21 4pm`…)
* 🧱 **Solid engineering**: SQLite WAL, typed helpers, input validation, structured logs, graceful background scheduler

Works **offline** (no API key) using a local CLI fallback, and **online** (agent mode) with your OpenAI key.

---

## Table of contents

1. [Quick start](#quick-start)
2. [Usage (CLI)](#usage-cli)
3. [Agent mode (OpenAI Responses API)](#agent-mode-openai-responses-api)
4. [Reminders](#reminders)
5. [Filtering / views](#filtering--views)
6. [Examples](#examples)
7. [Configuration](#configuration)
8. [Data model](#data-model)
9. [Design & reliability](#design--reliability)
10. [Testing](#testing)
11. [Troubleshooting](#troubleshooting)
12. [FAQ](#faq)
13. [Roadmap](#roadmap)
14. [License](#license)

---

## Quick start

> Requires Python 3.10+.

```bash
# 1) Clone your repo
git clone https://github.com/niraj-meshram/OpenAI.git
cd OpenAI/agent-101-Level-2  # or your folder containing agent_todo.py

# 2) (Optional) create venv
python -m venv .venv
# Windows PowerShell:
.\.venv\Scripts\Activate.ps1
# macOS/Linux:
source .venv/bin/activate

# 3) Run (offline mode works without an API key)
python agent_todo.py
```

**Agent (online) mode** (optional):

```powershell
# PowerShell (Windows)
$env:OPENAI_API_KEY="YOUR_KEY"
$env:AGENT_MODEL="gpt-4o-mini"        # optional
python agent_todo.py
```

You should see:

```
To-Do Agent ready. Try:
- add buy milk tomorrow 5pm
- set reminder for task 1 at today 6pm
- list reminders
- list today | list this week | list overdue
- update task 1 title buy oat milk
- update task 1 due Friday 6pm
- complete task 1
- delete task 1
Type 'exit' to quit.
```

---

## Usage (CLI)

The CLI understands natural language. These work in **offline fallback** and **agent mode**.

### Basics

```
add buy milk tomorrow 5pm
list
complete task 1
delete task 1
update task 2 title buy oat milk
update task 2 due next monday 8am
```

### Filters

```
list today
list this week
list overdue
list done
list open
```

### Reminders

```
set reminder for task 2 at in 30 minutes
list reminders
snooze reminder 1 by 10 minutes
cancel reminder 1
```

> The reminder scheduler runs in the background and prints a 🔔 line when a reminder fires.

---

## Agent mode (OpenAI Responses API)

If `OPENAI_API_KEY` is set, the app runs an **agent** that can call these local tools:

* `add_task(title, due?)`
* `list_tasks(show_done?)`
* `list_tasks_filtered(scope)`
* `complete_task(task_id)`
* `update_task(task_id, title?, due?)`
* `delete_task(task_id)`
* `set_reminder(task_id, remind_at)`
* `cancel_reminder(reminder_id)`
* `list_reminders(only_pending?)`
* `parse_when(text)` → returns ISO-UTC

When you type “add … tomorrow 5pm”, the model will call `parse_when` first, then `add_task` with the parsed ISO-UTC due. If the model doesn’t return text, the app still prints a sensible confirmation (so the CLI never feels silent).

---

## Reminders

* Stored in a `reminders` table: `(id, task_id, remind_at ISO-UTC, sent)`
* A daemon thread polls every `SCHEDULER_POLL_SECONDS` (default **15s**)
* When `remind_at <= now` and `sent=0`, it:

  * prints `🔔 REMINDER: Task #N — <title> (at <iso>)`
  * marks the reminder `sent=1`
* You can **cancel** or **snooze** reminders:

  * `cancel reminder 3`
  * `snooze reminder 3 by 10 minutes`

> This version prints to the console; swap the print for a desktop/mobile notifier if you like.

---

## Filtering / views

`list_tasks_filtered(scope)` supports:

* `open` – incomplete tasks
* `done` – completed
* `all` – both
* `today` – due in today’s UTC window (00:00–24:00)
* `this_week` – due within Monday..Sunday of the current week (UTC)
* `overdue` – due < now (and not done)

**Notes**

* Dates are stored/compared in **UTC**.
* Tasks with no `due` are **excluded** from date-range filters.

---

## Examples

Creating & listing:

```
YOU: add sprint review next friday 10am
ASSISTANT: Task added ✅

YOU: list this week
⬜ 2. sprint review — due in 3d 4h
```

Completing & updating:

```
YOU: complete task 2
ASSISTANT: Task completed ✅

YOU: update task 2 title sprint review (product + eng)
ASSISTANT: Task updated ✏️
```

Reminders:

```
YOU: set reminder for task 2 at in 15 minutes
ASSISTANT: Reminder set ⏰

...after ~15 min...
🔔 REMINDER: Task #2 — sprint review (product + eng) (at 2025-10-19T16:45:00+00:00)
```

---

## Configuration

Set via environment variables (all optional unless noted):

| Variable                 | Default       | Meaning                                 |
| ------------------------ | ------------- | --------------------------------------- |
| `OPENAI_API_KEY`         | *(unset)*     | Enables **agent** mode (Responses API). |
| `AGENT_MODEL`            | `gpt-4o-mini` | Model for agent mode.                   |
| `TODO_DB_PATH`           | `todos.db`    | SQLite file path.                       |
| `LOG_LEVEL`              | `INFO`        | `DEBUG` | `INFO` | `WARNING` | `ERROR`. |
| `SCHEDULER_POLL_SECONDS` | `15`          | Reminder poll interval (seconds).       |

**PowerShell** (Windows):

```powershell
$env:OPENAI_API_KEY="YOUR_KEY"
$env:AGENT_MODEL="gpt-4o-mini"
$env:LOG_LEVEL="DEBUG"
$env:SCHEDULER_POLL_SECONDS="10"
python agent_todo.py
```

---

## Data model

### `tasks`

| column       | type       | notes                         |
| ------------ | ---------- | ----------------------------- |
| `id`         | INTEGER PK | autoincrement                 |
| `title`      | TEXT       | sanitized (max 200 chars)     |
| `due`        | TEXT       | ISO-8601 UTC string or `NULL` |
| `done`       | INTEGER    | 0/1                           |
| `created_at` | TEXT       | SQLite default timestamp      |

### `reminders`

| column       | type       | notes                      |
| ------------ | ---------- | -------------------------- |
| `id`         | INTEGER PK | autoincrement              |
| `task_id`    | INTEGER    | FK → `tasks(id)` (CASCADE) |
| `remind_at`  | TEXT       | ISO-8601 UTC string        |
| `sent`       | INTEGER    | 0 pending, 1 sent          |
| `created_at` | TEXT       | SQLite default timestamp   |

> DB runs in **WAL** mode, autocommit on, foreign keys on.

---

## Design & reliability

* **UTC everywhere**: parsing -> ISO-UTC -> DB. Filters use UTC day/week windows for deterministic behavior.
* **Validation**:

  * Title sanitized and truncated to 200 chars.
  * `task_id` validated and > 0.
  * `due`/`remind_at` normalized to ISO-UTC; warnings surfaced:

    * `due_is_past` → still saved (helpful for logging past events), but we tag it.
    * `due_parse_failed` → saved without due/remind or rejected (for reminders).
* **No-deps parser**: supports:

  * `today 5pm`, `tomorrow 9:30`
  * `next monday 8am`, `monday 10am`
  * `in 2 hours`, `in 3 days`, `in 1 week`
  * `2025-10-20 14:00`, `10/21 4pm`, `0915`, `11:00`
  * Time-only in the past rolls to **tomorrow**.
* **Background scheduler**: a small daemon thread that checks due reminders and prints alerts; stops cleanly on exit.

---

## Testing

### Unit tests (parser + DB snippets)

```bash
python agent_todo.py test
# Expect: All tests passed.
```

### Manual smoke

1. Start clean:

   ```powershell
   Remove-Item .\todos.db -ErrorAction Ignore
   python agent_todo.py
   ```
2. Run:

   ```
   add buy milk tomorrow 5pm
   list
   update task 1 title buy oat milk
   set reminder for task 1 at in 1 minute
   list reminders
   # Wait ~1 minute to see 🔔
   complete task 1
   delete task 1
   ```

---

## Troubleshooting

* **“No model output / nothing printed”**
  The app has fallbacks. If agent mode fails (network/key), it will still print confirmations. Set `LOG_LEVEL=DEBUG` to see details.

* **Reminders not firing**
  Check the console timer: `SCHEDULER_POLL_SECONDS` (default 15s). Ensure your system clock is correct. Reminders are stored/fired in **UTC**.

* **Windows PowerShell quoting**
  When passing strings with spaces, quote them:
  `add "review Q4 goals" tomorrow 5pm`

* **DB in Git**
  Ensure your repo `.gitignore` excludes: `todos.db`, `.venv/`, `.idea/`, etc.

---

## FAQ

**Q: Do I need an API key?**
A: No. Offline CLI fallback works entirely locally. An API key enables the “agent” behavior (model decides which tool to call).

**Q: Can I change storage?**
A: Yes. Point `TODO_DB_PATH` to another path or adapt the small SQLite helpers.

**Q: How accurate is the natural parser?**
A: It’s intentionally small and dependency-free. If you need i18n or complex recurrence, plug in `dateparser`/`pytz` or a proper recurrence library.

**Q: Can reminders notify outside the console?**
A: Swap the `print()` in the scheduler for desktop notifications, email, or a webhook. The design isolates reminder firing so it’s easy to extend.

---

## Roadmap

* Repeating reminders (every day/week)
* Human-friendly local timezone display (configurable)
* Export/import (JSON)
* Optional `dateparser` integration for richer NL dates
* HTTP/REST wrapper for a minimal API

---

## License

MIT (or your repo’s preferred license).
Feel free to copy, hack, and ship.
