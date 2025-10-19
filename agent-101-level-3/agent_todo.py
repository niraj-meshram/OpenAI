#!/usr/bin/env python3
"""
Agent-101 — Level 3
Two-tool agent using OpenAI Responses API:
  1) SQLite to-do DB tool (add/list/complete)
  2) Natural-language date parser tool (parse_when) — NO external deps

Run:
  # PowerShell
  $env:OPENAI_API_KEY="YOUR_KEY"
  python agent_todo.py

Try:
  add buy milk tomorrow 5pm
  add dentist appointment next Monday 8am
  list my tasks
  complete task 1

Notes:
- Dependency-free date parsing (no external libs).
- Tools use Responses API's required top-level "name".
- Uses sys.stderr.write() (no print(file=...)).
- Test runner: python agent_todo.py test
"""

import os
import re
import sys
import json
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List, Optional, Tuple

# ----------------------------- OpenAI import ---------------------------- #
try:
    from openai import OpenAI  # type: ignore
    OPENAI_AVAILABLE = True
except ModuleNotFoundError:
    OPENAI_AVAILABLE = False
    sys.stderr.write("[WARN] Python package `openai` not found. Install with:\n")
    sys.stderr.write("    pip install --upgrade openai\n")

DB_PATH = os.environ.get("TODO_DB_PATH", "todos.db")
# Use a safe default; can override via env (e.g., gpt-4.1, gpt-4o, etc.)
MODEL = os.environ.get("AGENT_MODEL", "gpt-4o-mini")
TZ = timezone.utc  # store timestamps as UTC

# ----------------------------- SQLite layer ----------------------------- #

def init_db() -> None:
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            due TEXT,
            done INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    con.commit()
    con.close()


def add_task(title: str, due: Optional[str] = None) -> Dict[str, Any]:
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute("INSERT INTO tasks(title, due) VALUES (?, ?)", (title, due))
    con.commit()
    tid = cur.lastrowid
    con.close()
    return {"id": tid, "title": title, "due": due, "done": False}


def list_tasks(show_done: bool = True) -> List[Dict[str, Any]]:
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    if show_done:
        cur.execute(
            "SELECT id, title, due, done, created_at FROM tasks "
            "ORDER BY done, due IS NULL, due, id"
        )
    else:
        cur.execute(
            "SELECT id, title, due, done, created_at FROM tasks "
            "WHERE done = 0 ORDER BY due IS NULL, due, id"
        )
    rows = cur.fetchall()
    con.close()
    return [
        {"id": r[0], "title": r[1], "due": r[2], "done": bool(r[3]), "created_at": r[4]}
        for r in rows
    ]


def complete_task(task_id: int) -> Dict[str, Any]:
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute("UPDATE tasks SET done = 1 WHERE id = ?", (task_id,))
    con.commit()
    cur.execute(
        "SELECT id, title, due, done, created_at FROM tasks WHERE id = ?",
        (task_id,),
    )
    row = cur.fetchone()
    con.close()
    if row:
        return {
            "id": row[0],
            "title": row[1],
            "due": row[2],
            "done": bool(row[3]),
            "created_at": row[4],
        }
    return {"id": task_id, "updated": True}

# ----------------------- Natural date parsing tool ---------------------- #
# Parses phrases like:
#   - "today 5pm", "tomorrow 09:30", "next monday 8am"
#   - "in 2 hours", "in 3 days", "in 1 week"
#   - "2025-10-20 14:00", "10/21 4pm"
#   - "monday 10am" (next occurrence)
# Returns ISO 8601 UTC string and a human-readable summary.

WEEKDAYS = {
    'monday': 0, 'tuesday': 1, 'wednesday': 2, 'thursday': 3,
    'friday': 4, 'saturday': 5, 'sunday': 6
}

def _parse_time_part(t: str) -> Tuple[int, int]:
    t = t.strip().lower()
    # 5pm, 5:30pm, 17:00, 0900
    m = re.match(r"^(\d{1,2})(?::(\d{2}))?\s*(am|pm)?$", t)
    if m:
        hh = int(m.group(1))
        mm = int(m.group(2) or 0)
        ampm = m.group(3)
        if ampm:
            if hh == 12:
                hh = 0 if ampm == 'am' else 12
            elif ampm == 'pm':
                hh += 12
        return hh, mm
    m = re.match(r"^(\d{2})(\d{2})$", t)
    if m:
        return int(m.group(1)), int(m.group(2))
    raise ValueError("Unrecognized time format")


def _next_weekday(base: datetime, target_wd: int) -> datetime:
    days_ahead = (target_wd - base.weekday()) % 7
    if days_ahead == 0:
        days_ahead = 7
    return base + timedelta(days=days_ahead)


def parse_when(text: str, now: Optional[datetime] = None, local_tz: timezone = timezone.utc) -> Dict[str, Any]:
    if not now:
        now = datetime.now(tz=local_tz)
    s = text.strip().lower()

    # Relative phrases
    m = re.search(r"in\s+(\d+)\s*(minute|minutes|min|hour|hours|day|days|week|weeks)", s)
    if m:
        qty = int(m.group(1))
        unit = m.group(2)
        delta = {
            'minute': timedelta(minutes=qty), 'minutes': timedelta(minutes=qty), 'min': timedelta(minutes=qty),
            'hour': timedelta(hours=qty), 'hours': timedelta(hours=qty),
            'day': timedelta(days=qty), 'days': timedelta(days=qty),
            'week': timedelta(weeks=qty), 'weeks': timedelta(weeks=qty)
        }[unit]
        dt = now + delta
        return {
            'input': text,
            'iso_utc': dt.astimezone(timezone.utc).replace(microsecond=0).isoformat(),
            'pretty': dt.strftime('%a, %b %d at %H:%M %Z')
        }

    # today / tomorrow / weekday names with optional time
    if s.startswith('today') or s.startswith('tomorrow') or any(s.startswith(w) for w in WEEKDAYS):
        if s.startswith('today'):
            base = now
            rest = s.replace('today', '', 1).strip()
        elif s.startswith('tomorrow'):
            base = now + timedelta(days=1)
            rest = s.replace('tomorrow', '', 1).strip()
        else:
            for w, idx in WEEKDAYS.items():
                if s.startswith(w):
                    base = _next_weekday(now, idx)
                    rest = s.replace(w, '', 1).strip()
                    break
        hh, mm = (9, 0)  # default 09:00 if no time
        if rest:
            try:
                hh, mm = _parse_time_part(rest)
            except Exception:
                pass
        dt_local = base.replace(hour=hh, minute=mm, second=0, microsecond=0)
        return {
            'input': text,
            'iso_utc': dt_local.astimezone(timezone.utc).replace(microsecond=0).isoformat(),
            'pretty': dt_local.strftime('%a, %b %d at %H:%M %Z')
        }

    # next <weekday> <time>
    m = re.match(r"next\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\s+(.*)$", s)
    if m:
        wd = WEEKDAYS[m.group(1)]
        hh, mm = _parse_time_part(m.group(2))
        dt_local = _next_weekday(now, wd).replace(hour=hh, minute=mm, second=0, microsecond=0)
        return {
            'input': text,
            'iso_utc': dt_local.astimezone(timezone.utc).replace(microsecond=0).isoformat(),
            'pretty': dt_local.strftime('%a, %b %d at %H:%M %Z')
        }

    # Absolute: YYYY-MM-DD [HH[:MM]] or MM/DD [HH[:MM][am/pm]]
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})(?:\s+(\d{1,2})(?::(\d{2}))?)?", s)
    if m:
        year, month, day = map(int, m.group(1, 2, 3))
        hh = int(m.group(4) or 9)
        mm = int(m.group(5) or 0)
        dt_local = datetime(year, month, day, hh, mm, tzinfo=local_tz)
        return {
            'input': text,
            'iso_utc': dt_local.astimezone(timezone.utc).replace(microsecond=0).isoformat(),
            'pretty': dt_local.strftime('%a, %b %d at %H:%M %Z')
        }
    m = re.match(r"(\d{1,2})/(\d{1,2})(?:\s+(\d{1,2}(?::\d{2})?\s*(?:am|pm)?))?", s)
    if m:
        month, day = map(int, m.group(1, 2))
        year = now.year if (month, day) >= (now.month, now.day) else now.year + 1
        time_part = m.group(3)
        hh, mm = (9, 0)
        if time_part:
            hh, mm = _parse_time_part(time_part)
        dt_local = datetime(year, month, day, hh, mm, tzinfo=local_tz)
        return {
            'input': text,
            'iso_utc': dt_local.astimezone(timezone.utc).replace(microsecond=0).isoformat(),
            'pretty': dt_local.strftime('%a, %b %d at %H:%M %Z')
        }

    # Fallback: if only a time like "5pm" was given => today at that time
    try:
        hh, mm = _parse_time_part(s)
        dt_local = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
        if dt_local < now:
            dt_local += timedelta(days=1)
        return {
            'input': text,
            'iso_utc': dt_local.astimezone(timezone.utc).replace(microsecond=0).isoformat(),
            'pretty': dt_local.strftime('%a, %b %d at %H:%M %Z')
        }
    except Exception:
        pass

    raise ValueError("Could not parse date/time phrase")

# --------------------------- OpenAI orchestration ------------------------ #

SYSTEM_PROMPT = (
    "You are a concise To-Do assistant.\n"
    "- When the user asks to add a task, call add_task with a short title and, if present, a parsed ISO UTC due using parse_when.\n"
    "- If the user includes a natural date/time phrase, first call parse_when, then pass its iso_utc to add_task.\n"
    "- For \"list\" requests, call list_tasks.\n"
    "- For \"complete\" requests, call complete_task with the numeric id.\n"
    "- Prefer tool calls over free-text answers and keep language crisp.\n"
)

def build_tools_schema() -> List[Dict[str, Any]]:
    # For the Responses API, tool "name" must be TOP-LEVEL
    return [
        {
            "type": "function",
            "name": "add_task",
            "description": "Create a to-do item in the SQLite DB.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "due": {"type": ["string", "null"], "description": "ISO 8601 UTC datetime string or null"},
                },
                "required": ["title"],
                "additionalProperties": False,
            },
        },
        {
            "type": "function",
            "name": "list_tasks",
            "description": "Return all tasks (optionally filtering out completed ones).",
            "parameters": {
                "type": "object",
                "properties": {"show_done": {"type": "boolean", "default": True}},
                "required": [],
            },
        },
        {
            "type": "function",
            "name": "complete_task",
            "description": "Mark a task complete by id.",
            "parameters": {
                "type": "object",
                "properties": {"task_id": {"type": "integer"}},
                "required": ["task_id"],
            },
        },
        {
            "type": "function",
            "name": "parse_when",
            "description": "Parse a natural-language date/time phrase to ISO UTC.",
            "parameters": {"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]},
        },
    ]

# Tool bridge (executes the actual Python when model calls a tool)
TOOL_MAP = {
    "add_task": lambda **kw: add_task(**kw),
    "list_tasks": lambda **kw: list_tasks(**kw) if kw else list_tasks(),
    "complete_task": lambda **kw: complete_task(**kw),
    "parse_when": lambda **kw: parse_when(kw["text"], local_tz=timezone.utc),
}

def pretty_print_tasks(tasks: List[Dict[str, Any]]) -> str:
    if not tasks:
        return "No tasks yet."
    lines = []
    for t in tasks:
        status = "✅" if t.get("done") else "⬜"
        due = t.get("due")
        due_s = f" — due {due}" if due else ""
        lines.append(f"{status} {t['id']}. {t['title']}{due_s}")
    return "\n".join(lines)

# --------- Extra helpers so the CLI never feels silent even if model fails -------- #

def _warn_no_api_key():
    if not os.environ.get("OPENAI_API_KEY"):
        sys.stderr.write("[WARN] OPENAI_API_KEY is not set; requests will fail.\n")

def _local_heuristic_fallback(user_text: str) -> Optional[str]:
    """
    Very small non-LLM fallback so the CLI never feels 'silent'.
    Handles:
      - add <title> [when...]
      - list my tasks | list tasks | list
      - complete task <id>
    Returns a user-visible string or None if not handled.
    """
    s = user_text.strip().lower()

    # list
    if s in {"list", "list tasks", "list my tasks"}:
        tasks = list_tasks()
        return pretty_print_tasks(tasks)

    # complete task N
    m = re.match(r"(?:complete|finish|done)\s+task\s+(\d+)", s)
    if m:
        tid = int(m.group(1))
        complete_task(tid)
        return "Task completed ✅"

    # add ...
    if s.startswith("add "):
        raw = user_text[4:].strip()
        try:
            r = parse_when(raw)
            add_task(title=raw, due=r["iso_utc"])
            return "Task added ✅"
        except Exception:
            add_task(title=raw)
            return "Task added ✅"

    return None

def run_cli() -> None:
    # If running tests, skip the agent loop regardless of OpenAI availability
    if len(sys.argv) > 1 and sys.argv[1].lower() == "test":
        run_tests()
        return

    if not OPENAI_AVAILABLE:
        sys.stderr.write("[ERROR] The agent mode requires the `openai` package.\n")
        sys.stderr.write("Install it with:\n")
        sys.stderr.write("    pip install --upgrade openai\n")
        sys.stderr.write("Or run tests instead:\n")
        sys.stderr.write("    python agent_todo.py test\n")
        return

    client = OpenAI()
    _warn_no_api_key()
    init_db()

    print(
        "To-Do Agent (Level 3) ready. Try:\n"
        "- add buy milk tomorrow 5pm\n"
        "- add dentist appointment next Monday 8am\n"
        "- list my tasks\n"
        "- complete task 1\n"
    )

    msgs = [{"role": "system", "content": SYSTEM_PROMPT}]

    while True:
        try:
            user = input("YOU: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()  # newline
            break
        if not user:
            continue
        if user.lower() in {"quit", "exit"}:
            break

        msgs.append({"role": "user", "content": user})

        # First Responses API call
        try:
            resp = client.responses.create(
                model=MODEL,
                input=msgs,
                tools=build_tools_schema(),
            )
        except Exception as e:
            sys.stderr.write(f"[ERROR] initial call failed: {e}\n")
            fb = _local_heuristic_fallback(user)
            if fb is not None:
                print("\nASSISTANT:\n" + fb + "\n")
                continue
            else:
                sys.stderr.write("[HINT] Try: set AGENT_MODEL=gpt-4o-mini\n")
                continue

        # Handle tool calls & follow-up
        tool_outputs: List[Dict[str, Any]] = []
        assistant_msgs: List[Dict[str, Any]] = []

        for item in (resp.output or []):
            if item.type == "message":
                assistant_msgs.append({
                    "role": item.message.role,
                    "content": [c.model_dump() for c in (item.message.content or [])],
                    **({"tool_calls": [tc.model_dump() for tc in item.message.tool_calls]} if item.message.tool_calls else {})
                })

                if item.message.tool_calls:
                    for tc in item.message.tool_calls:
                        name = tc.function.name
                        args = json.loads(tc.function.arguments or "{}")
                        try:
                            result = TOOL_MAP[name](**args)
                            tool_outputs.append({
                                "role": "tool",
                                "tool_call_id": tc.id,
                                "name": name,
                                "content": json.dumps(result),
                            })
                        except Exception as e:
                            tool_outputs.append({
                                "role": "tool",
                                "tool_call_id": tc.id,
                                "name": name,
                                "content": json.dumps({"error": str(e)}),
                            })

        if tool_outputs:
            msgs.extend(assistant_msgs)
            msgs.extend(tool_outputs)

            # Follow-up call MUST include tools again
            try:
                follow = client.responses.create(
                    model=MODEL,
                    input=msgs,
                    tools=build_tools_schema(),
                )
                final_text = follow.output_text or ""
            except Exception as e:
                final_text = ""
                sys.stderr.write(f"[ERROR] follow-up call failed: {e}\n")

            # Fallbacks if the model gave no text (A+B behavior)
            if not final_text.strip():
                try:
                    last_calls = [t for t in tool_outputs]
                    if any(t.get("name") == "add_task" and not json.loads(t.get("content","{}")).get("error") for t in last_calls):
                        final_text = "Task added ✅"
                    elif any(t.get("name") == "complete_task" and not json.loads(t.get("content","{}")).get("error") for t in last_calls):
                        final_text = "Task completed ✅"
                    elif any(t.get("name") == "list_tasks" for t in last_calls):
                        for t in reversed(last_calls):
                            if t.get("name") == "list_tasks":
                                try:
                                    payload = json.loads(t.get("content","null"))
                                    if isinstance(payload, list):
                                        print("\nASSISTANT:\n" + pretty_print_tasks(payload) + "\n")
                                        final_text = ""
                                        break
                                except Exception:
                                    pass
                except Exception:
                    pass

            if final_text:
                try:
                    obj = json.loads(final_text)
                    if isinstance(obj, list):
                        print("\nASSISTANT:\n" + pretty_print_tasks(obj) + "\n")
                    else:
                        print("\nASSISTANT:\n" + final_text + "\n")
                except Exception:
                    print("\nASSISTANT:\n" + final_text + "\n")

        else:
            final_text = resp.output_text or ""
            if final_text.strip():
                print("\nASSISTANT:\n" + final_text + "\n")
            else:
                # No model text, no tools — local heuristic so CLI is never silent
                fb = _local_heuristic_fallback(user)
                if fb is not None:
                    print("\nASSISTANT:\n" + fb + "\n")
                else:
                    sys.stderr.write("[WARN] Model returned no content. Try a different model:\n")
                    sys.stderr.write("       set AGENT_MODEL=gpt-4o-mini\n")

# ------------------------------- Tests ---------------------------------- #

def _assert_eq(label: str, a, b) -> None:
    if a != b:
        raise AssertionError(f"{label}: expected {b!r}, got {a!r}")

def run_tests() -> None:
    print("Running tests...\n")
    base = datetime(2025, 10, 18, 12, 0, tzinfo=timezone.utc)

    # _parse_time_part
    _assert_eq("time 5pm", _parse_time_part("5pm"), (17, 0))
    _assert_eq("time 5:30pm", _parse_time_part("5:30pm"), (17, 30))
    _assert_eq("time 09:15", _parse_time_part("09:15"), (9, 15))
    _assert_eq("time 0915", _parse_time_part("0915"), (9, 15))

    # Relative phrases
    r = parse_when("in 2 hours", now=base, local_tz=timezone.utc)
    _assert_eq("in 2 hours", r["iso_utc"], (base + timedelta(hours=2)).replace(microsecond=0).isoformat())

    r = parse_when("in 3 days", now=base, local_tz=timezone.utc)
    _assert_eq("in 3 days", r["iso_utc"], (base + timedelta(days=3)).replace(microsecond=0).isoformat())

    # Today / tomorrow
    r = parse_when("today 5pm", now=base, local_tz=timezone.utc)
    _assert_eq("today 5pm", r["iso_utc"], base.replace(hour=17, minute=0, second=0, microsecond=0).isoformat())

    r = parse_when("tomorrow 09:30", now=base, local_tz=timezone.utc)
    _assert_eq("tomorrow 09:30", r["iso_utc"], (base + timedelta(days=1)).replace(hour=9, minute=30, second=0, microsecond=0).isoformat())

    # Next weekday (next Monday from Sat Oct 18, 2025 -> Mon Oct 20, 2025)
    r = parse_when("next monday 8am", now=base, local_tz=timezone.utc)
    expected = datetime(2025, 10, 20, 8, 0, tzinfo=timezone.utc).isoformat()
    _assert_eq("next monday 8am", r["iso_utc"], expected)

    # Absolute formats
    r = parse_when("2025-10-20 14:00", now=base, local_tz=timezone.utc)
    _assert_eq("YYYY-MM-DD HH:MM", r["iso_utc"], datetime(2025, 10, 20, 14, 0, tzinfo=timezone.utc).isoformat())

    r = parse_when("10/21 4pm", now=base, local_tz=timezone.utc)
    _assert_eq("MM/DD 4pm", r["iso_utc"], datetime(2025, 10, 21, 16, 0, tzinfo=timezone.utc).isoformat())

    r = parse_when("5pm", now=base, local_tz=timezone.utc)
    _assert_eq("time only today", r["iso_utc"], base.replace(hour=17, minute=0, second=0, microsecond=0).isoformat())

    # Additional tests
    r = parse_when("10/22", now=base, local_tz=timezone.utc)
    _assert_eq("MM/DD default 09:00", r["iso_utc"], datetime(2025, 10, 22, 9, 0, tzinfo=timezone.utc).isoformat())

    r = parse_when("11:00", now=base, local_tz=timezone.utc)
    _assert_eq("time earlier rolls forward", r["iso_utc"], datetime(2025, 10, 19, 11, 0, tzinfo=timezone.utc).isoformat())

    print("All tests passed.\n")

if __name__ == "__main__":
    run_cli()
