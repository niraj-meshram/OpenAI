#!/usr/bin/env python3
"""
Agent-101 — Level 3 (CRUD + Reliability + Filters + Reminders + Eng Quality + UX Polish)

Adds:
  - Local timezone display (set LOCAL_TZ env, default America/Denver)
  - Minimal ANSI colors (overdue/red, completed/green check)
  - Help screen (`help` / `?`)
  - `ls` aliases: -a(all) -t(today) -w(week) -o(overdue) -d(done) -p(open)
  - Safer delete: confirm unless `--yes`
  - Robust Responses API parsing (supports SDKs that expose message fields at item.message.* or item.*)
  - Help short-circuit (prints help without calling the API)

Run:
  # PowerShell
  $env:OPENAI_API_KEY="YOUR_KEY"        # optional; CLI fallback works without it
  $env:LOCAL_TZ="America/Denver"        # optional; for local display
  $env:LOG_LEVEL="INFO"
  python agent_todo.py
"""

from __future__ import annotations

import os
import re
import sys
import json
import time
import sqlite3
import logging
import threading
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List, Optional, Tuple
from zoneinfo import ZoneInfo
from planner import plan as planner_plan
from reflection import get_reflections


# ----------------------------- OpenAI import ---------------------------- #
try:
    from openai import OpenAI  # type: ignore
    OPENAI_AVAILABLE = True
except ModuleNotFoundError:
    OPENAI_AVAILABLE = False

# ----------------------------- Config ---------------------------------- #

DB_PATH = os.environ.get("TODO_DB_PATH", "todos.db")
MODEL = os.environ.get("AGENT_MODEL", "gpt-4o-mini")
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()
SCHED_POLL = int(os.environ.get("SCHEDULER_POLL_SECONDS", "15"))

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s %(levelname)s %(message)s",
)
log = logging.getLogger("agent-todo")
def _agent_mode() -> str:
    """
    Returns 'ONLINE' if the OpenAI SDK is importable AND OPENAI_API_KEY is set,
    otherwise 'OFFLINE'.
    """
    online = OPENAI_AVAILABLE and bool(os.environ.get("OPENAI_API_KEY"))
    return "ONLINE" if online else "OFFLINE"

TZ = timezone.utc  # store/compute in UTC


# ---- Local timezone for display (no external deps) ----
LOCAL_TZ_NAME = os.environ.get("LOCAL_TZ")  # optional override

try:
    from zoneinfo import ZoneInfo
except Exception:
    ZoneInfo = None  # will fall back below

def _detect_local_tz():
    # Use system local tzinfo (works on Windows without tzdata)
    try:
        return datetime.now().astimezone().tzinfo
    except Exception:
        return timezone.utc

if LOCAL_TZ_NAME and ZoneInfo:
    try:
        LOCAL_TZ = ZoneInfo(LOCAL_TZ_NAME)
    except Exception:
        LOCAL_TZ = _detect_local_tz() or timezone.utc
else:
    # No name provided or ZoneInfo unavailable — use system local tz
    LOCAL_TZ = _detect_local_tz() or timezone.utc


def _fmt_local(iso_utc: str) -> str:
    """Return a short local-time display, e.g. 'Sun 11:00'."""
    try:
        dt_utc = datetime.fromisoformat(iso_utc)
        if dt_utc.tzinfo is None:
            dt_utc = dt_utc.replace(tzinfo=TZ)
        dt_local = dt_utc.astimezone(LOCAL_TZ)
        return dt_local.strftime("%a %H:%M")
    except Exception:
        return iso_utc

# ANSI helpers (optional, safe on most modern terminals)
RED = "\x1b[31m"; GREEN = "\x1b[32m"; YELLOW = "\x1b[33m"; DIM = "\x1b[2m"; RESET = "\x1b[0m"

# ----------------------------- DB Helpers ------------------------------ #

def get_db() -> sqlite3.Connection:
    con = sqlite3.connect(DB_PATH, timeout=15, isolation_level=None)  # autocommit
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA foreign_keys=ON")
    return con

def init_db() -> None:
    with get_db() as con:
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
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS reminders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id INTEGER NOT NULL,
                remind_at TEXT NOT NULL,         -- ISO-UTC
                sent INTEGER DEFAULT 0,          -- 0 = pending, 1 = fired
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(task_id) REFERENCES tasks(id) ON DELETE CASCADE
            )
            """
        )

# ----------------------------- Tasks CRUD ------------------------------ #

def add_task(title: str, due: Optional[str] = None) -> Dict[str, Any]:
    with get_db() as con:
        cur = con.cursor()
        cur.execute("INSERT INTO tasks(title, due) VALUES (?, ?)", (title, due))
        tid = cur.lastrowid
    return {"id": tid, "title": title, "due": due, "done": False}

def list_tasks(show_done: bool = True) -> List[Dict[str, Any]]:
    with get_db() as con:
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
    return [
        {"id": r[0], "title": r[1], "due": r[2], "done": bool(r[3]), "created_at": r[4]}
        for r in rows
    ]

def complete_task(task_id: int) -> Dict[str, Any]:
    with get_db() as con:
        cur = con.cursor()
        cur.execute("UPDATE tasks SET done = 1 WHERE id = ?", (task_id,))
        cur.execute(
            "SELECT id, title, due, done, created_at FROM tasks WHERE id = ?",
            (task_id,),
        )
        row = cur.fetchone()
    if row:
        return {
            "id": row[0],
            "title": row[1],
            "due": row[2],
            "done": bool(row[3]),
            "created_at": row[4],
        }
    return {"id": task_id, "updated": True}

def update_task(task_id: int, title: Optional[str] = None, due: Optional[str] = None) -> Dict[str, Any]:
    with get_db() as con:
        cur = con.cursor()
        sets, params = [], []
        if title is not None:
            sets.append("title=?"); params.append(title)
        if due is not None:
            sets.append("due=?"); params.append(due)
        if not sets:
            return {"updated": 0}
        params.append(task_id)
        cur.execute(f"UPDATE tasks SET {', '.join(sets)} WHERE id=?", params)
        changed = cur.rowcount
    return {"updated": changed}

def delete_task(task_id: int) -> Dict[str, Any]:
    with get_db() as con:
        cur = con.cursor()
        cur.execute("DELETE FROM tasks WHERE id=?", (task_id,))
        changed = cur.rowcount
    return {"deleted": changed}

# ----------------------------- Reminders -------------------------------- #

def set_reminder(task_id: int, remind_at_iso: str) -> Dict[str, Any]:
    with get_db() as con:
        cur = con.cursor()
        cur.execute("SELECT id FROM tasks WHERE id=?", (task_id,))
        if cur.fetchone() is None:
            return {"error": "task_not_found"}
        cur.execute(
            "INSERT INTO reminders(task_id, remind_at) VALUES (?, ?)",
            (task_id, remind_at_iso),
        )
        rid = cur.lastrowid
    return {"id": rid, "task_id": task_id, "remind_at": remind_at_iso, "sent": 0}

def cancel_reminder(reminder_id: int) -> Dict[str, Any]:
    with get_db() as con:
        cur = con.cursor()
        cur.execute("DELETE FROM reminders WHERE id=?", (reminder_id,))
        changed = cur.rowcount
    return {"deleted": changed}

def list_reminders(only_pending: bool = True) -> List[Dict[str, Any]]:
    with get_db() as con:
        cur = con.cursor()
        sql = (
            "SELECT r.id, r.task_id, r.remind_at, r.sent, t.title "
            "FROM reminders r JOIN tasks t ON r.task_id=t.id "
        )
        if only_pending:
            sql += "WHERE r.sent=0 "
        sql += "ORDER BY r.sent, r.remind_at, r.id"
        rows = cur.execute(sql).fetchall()
    return [
        {"id": r[0], "task_id": r[1], "remind_at": r[2], "sent": bool(r[3]), "title": r[4]}
        for r in rows
    ]

def _fetch_due_reminders(now_iso: str) -> List[Dict[str, Any]]:
    """Internal: fetch reminders due at or before now and not yet sent."""
    with get_db() as con:
        cur = con.cursor()
        rows = cur.execute(
            "SELECT r.id, r.task_id, r.remind_at, t.title "
            "FROM reminders r JOIN tasks t ON r.task_id=t.id "
            "WHERE r.sent=0 AND r.remind_at <= ? ORDER BY r.remind_at, r.id",
            (now_iso,),
        ).fetchall()
    return [{"id": r[0], "task_id": r[1], "remind_at": r[2], "title": r[3]} for r in rows]

def _mark_reminders_sent(ids: List[int]) -> None:
    if not ids:
        return
    with get_db() as con:
        cur = con.cursor()
        cur.executemany("UPDATE reminders SET sent=1 WHERE id=?", [(i,) for i in ids])

# ----------------------- Reliability helpers ---------------------------- #

def _sanitize_title(title: Optional[str]) -> str:
    if not title:
        return "untitled task"
    t = " ".join(str(title).strip().split())
    return t[:200] or "untitled task"

def _normalize_iso_utc(s: str) -> datetime:
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=TZ)
    return dt.astimezone(TZ).replace(microsecond=0)

def _validate_due_iso(due: Optional[str]) -> Tuple[Optional[str], Optional[str]]:
    if not due:
        return None, None
    try:
        dt = _normalize_iso_utc(due)
        if dt < datetime.now(TZ):
            return dt.isoformat(), "due_is_past"
        return dt.isoformat(), None
    except Exception:
        return None, "due_parse_failed"

def _validate_task_id(task_id: Any) -> int:
    try:
        tid = int(task_id)
        if tid <= 0:
            raise ValueError
        return tid
    except Exception:
        raise ValueError("invalid_task_id")

# ---------- Agent-safe wrappers ---------------------------------------- #

def agent_add_task(title: str, due: Optional[str] = None) -> Dict[str, Any]:
    clean_title = _sanitize_title(title)
    norm_due, warn = _validate_due_iso(due)
    res = add_task(clean_title, norm_due)
    if warn:
        res["warning"] = warn
    return res

def agent_update_task(task_id: Any, title: Optional[str] = None, due: Optional[str] = None) -> Dict[str, Any]:
    tid = _validate_task_id(task_id)
    clean_title = _sanitize_title(title) if title is not None else None
    norm_due, warn = _validate_due_iso(due) if due is not None else (None, None)
    res = update_task(tid, title=clean_title, due=norm_due)
    if warn:
        res["warning"] = warn
    return res

def agent_set_reminder(task_id: Any, remind_at: str) -> Dict[str, Any]:
    tid = _validate_task_id(task_id)
    iso, warn = _validate_due_iso(remind_at)
    if iso is None and warn == "due_parse_failed":
        return {"error": "invalid_datetime"}
    res = set_reminder(tid, iso or remind_at)
    if warn:
        res["warning"] = warn
    return res

def agent_cancel_reminder(reminder_id: Any) -> Dict[str, Any]:
    try:
        rid = int(reminder_id)
        if rid <= 0:
            raise ValueError
    except Exception:
        return {"deleted": 0}
    return cancel_reminder(rid)

# ----------------------- Filters & date helpers ------------------------- #

def _utc_now() -> datetime:
    return datetime.now(TZ).replace(microsecond=0)

def _week_bounds_utc(now: Optional[datetime] = None) -> Tuple[datetime, datetime]:
    """
    Next-7-days window **in local time**, converted to UTC for DB comparisons.
    """
    now = now or _utc_now()
    now_local = now.astimezone(LOCAL_TZ)
    start_local = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
    end_local = start_local + timedelta(days=7)
    return start_local.astimezone(TZ).replace(microsecond=0), end_local.astimezone(TZ).replace(microsecond=0)

def _today_bounds_utc(now: Optional[datetime] = None) -> Tuple[datetime, datetime]:
    """
    Local calendar day [00:00, 24:00) converted to UTC.
    """
    now = now or _utc_now()
    now_local = now.astimezone(LOCAL_TZ)
    start_local = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
    end_local = start_local + timedelta(days=1)
    return start_local.astimezone(TZ).replace(microsecond=0), end_local.astimezone(TZ).replace(microsecond=0)


def list_tasks_filtered(scope: str = "open") -> List[Dict[str, Any]]:
    now = _utc_now()
    with get_db() as con:
        cur = con.cursor()
        base = "SELECT id, title, due, done, created_at FROM tasks"
        where, params = [], []

        if scope == "open":
            where.append("done = 0")
        elif scope == "done":
            where.append("done = 1")
        elif scope == "all":
            pass
        elif scope == "today":
            start, end = _today_bounds_utc(now)
            where.append("due IS NOT NULL AND due >= ? AND due < ?")
            params.extend([start.isoformat(), end.isoformat()])
        elif scope == "this_week":
            start, end = _week_bounds_utc(now)
            where.append("due IS NOT NULL AND due >= ? AND due < ?")
            params.extend([start.isoformat(), end.isoformat()])
        elif scope == "overdue":
            where.append("due IS NOT NULL AND done = 0 AND due < ?")
            params.append(now.isoformat())
        else:
            where.append("done = 0")

        where_clause = (" WHERE " + " AND ".join(where)) if where else ""
        order = " ORDER BY done, due IS NULL, due, id"
        rows = cur.execute(base + where_clause + order, params).fetchall()

    return [
        {"id": r[0], "title": r[1], "due": r[2], "done": bool(r[3]), "created_at": r[4]}
        for r in rows
    ]

# ----------------------- Natural date parsing tool ---------------------- #

WEEKDAYS = {
    'monday': 0, 'tuesday': 1, 'wednesday': 2, 'thursday': 3,
    'friday': 4, 'saturday': 5, 'sunday': 6
}

def _parse_time_part(t: str) -> Tuple[int, int]:
    t = t.strip().lower()
    m = re.match(r"^(\d{1,2})(?::(\d{2}))?\s*(am|pm)?$", t)
    if m:
        hh = int(m.group(1)); mm = int(m.group(2) or 0); ampm = m.group(3)
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

def parse_when(text: str, now: Optional[datetime] = None, local_tz: timezone = TZ) -> Dict[str, Any]:
    if not now:
        now = datetime.now(tz=local_tz)
    s = text.strip().lower()

    m = re.search(r"in\s+(\d+)\s*(minute|minutes|min|hour|hours|day|days|week|weeks)", s)
    if m:
        qty = int(m.group(1)); unit = m.group(2)
        delta = {
            'minute': timedelta(minutes=qty), 'minutes': timedelta(minutes=qty), 'min': timedelta(minutes=qty),
            'hour': timedelta(hours=qty), 'hours': timedelta(hours=qty),
            'day': timedelta(days=qty), 'days': timedelta(days=qty),
            'week': timedelta(weeks=qty), 'weeks': timedelta(weeks=qty)
        }[unit]
        dt = now + delta
        return {'input': text, 'iso_utc': dt.astimezone(TZ).replace(microsecond=0).isoformat(),
                'pretty': dt.strftime('%a, %b %d at %H:%M %Z')}

    if s.startswith('today') or s.startswith('tomorrow') or any(s.startswith(w) for w in WEEKDAYS):
        if s.startswith('today'):
            base = now; rest = s.replace('today', '', 1).strip()
        elif s.startswith('tomorrow'):
            base = now + timedelta(days=1); rest = s.replace('tomorrow', '', 1).strip()
        else:
            for w, idx in WEEKDAYS.items():
                if s.startswith(w):
                    base = _next_weekday(now, idx); rest = s.replace(w, '', 1).strip()
                    break
        hh, mm = (9, 0)
        if rest:
            try: hh, mm = _parse_time_part(rest)
            except Exception: pass
        dt_local = base.replace(hour=hh, minute=mm, second=0, microsecond=0)
        return {'input': text, 'iso_utc': dt_local.astimezone(TZ).replace(microsecond=0).isoformat(),
                'pretty': dt_local.strftime('%a, %b %d at %H:%M %Z')}

    m = re.match(r"next\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\s+(.*)$", s)
    if m:
        wd = WEEKDAYS[m.group(1)]; hh, mm = _parse_time_part(m.group(2))
        dt_local = _next_weekday(now, wd).replace(hour=hh, minute=mm, second=0, microsecond=0)
        return {'input': text, 'iso_utc': dt_local.astimezone(TZ).replace(microsecond=0).isoformat(),
                'pretty': dt_local.strftime('%a, %b %d at %H:%M %Z')}

    m = re.match(r"(\d{4})-(\d{2})-(\d{2})(?:\s+(\d{1,2})(?::(\d{2}))?)?", s)
    if m:
        year, month, day = map(int, m.group(1, 2, 3))
        hh = int(m.group(4) or 9); mm = int(m.group(5) or 0)
        dt_local = datetime(year, month, day, hh, mm, tzinfo=local_tz)
        return {'input': text, 'iso_utc': dt_local.astimezone(TZ).replace(microsecond=0).isoformat(),
                'pretty': dt_local.strftime('%a, %b %d at %H:%M %Z')}

    m = re.match(r"(\d{1,2})/(\d{1,2})(?:\s+(\d{1,2}(?::\d{2})?\s*(?:am|pm)?))?", s)
    if m:
        month, day = map(int, m.group(1, 2))
        year = now.year if (month, day) >= (now.month, now.day) else now.year + 1
        time_part = m.group(3); hh, mm = (9, 0)
        if time_part:
            hh, mm = _parse_time_part(time_part)
        dt_local = datetime(year, month, day, hh, mm, tzinfo=local_tz)
        return {'input': text, 'iso_utc': dt_local.astimezone(TZ).replace(microsecond=0).isoformat(),
                'pretty': dt_local.strftime('%a, %b %d at %H:%M %Z')}

    try:
        hh, mm = _parse_time_part(s)
        dt_local = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
        if dt_local < now:
            dt_local += timedelta(days=1)
        return {'input': text, 'iso_utc': dt_local.astimezone(TZ).replace(microsecond=0).isoformat(),
                'pretty': dt_local.strftime('%a, %b %d at %H:%M %Z')}
    except Exception:
        pass

    raise ValueError("Could not parse date/time phrase")

# --------------------------- OpenAI orchestration ------------------------ #

SYSTEM_PROMPT = (
    "You are a concise To-Do assistant.\n"
    "- When the user asks to add a task, call add_task with a short title and, if present, a parsed ISO UTC due using parse_when.\n"
    "- If the user includes a natural date/time phrase, first call parse_when, then pass its iso_utc to add_task.\n"
    "- For \"list\" requests, call list_tasks.\n"
    "- If the user asks for specific scopes (today/this week/overdue/done/open), use list_tasks_filtered with the right scope.\n"
    "- For \"complete\" requests, call complete_task with the numeric id.\n"
    "- For \"update\" requests, call parse_when when needed, then call update_task with title and/or due (ISO UTC) and the id.\n"
    "- For reminders: to schedule use set_reminder (parse natural text via parse_when first if needed), to cancel use cancel_reminder, and to view use list_reminders.\n"
    "- If a tool returns a 'warning' like 'due_is_past' or 'due_parse_failed', state it briefly in your reply.\n"
    "- Prefer tool calls over free-text answers and keep language crisp.\n"
)

def build_tools_schema() -> List[Dict[str, Any]]:
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
            "name": "list_tasks_filtered",
            "description": "List tasks by scope: one of {all, open, done, today, this_week, overdue}.",
            "parameters": {
                "type": "object",
                "properties": {
                    "scope": {
                        "type": "string",
                        "enum": ["all", "open", "done", "today", "this_week", "overdue"],
                        "default": "open"
                    }
                }
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
            "name": "update_task",
            "description": "Update a task's title and/or due (due should be ISO 8601 UTC; call parse_when first if needed).",
            "parameters": {
                "type": "object",
                "properties": {
                    "task_id": {"type": "integer"},
                    "title": {"type": ["string", "null"]},
                    "due": {"type": ["string", "null"], "description": "ISO 8601 UTC datetime string or null"},
                },
                "required": ["task_id"],
                "additionalProperties": False,
            },
        },
        {
            "type": "function",
            "name": "delete_task",
            "description": "Delete a task by id.",
            "parameters": {
                "type": "object",
                "properties": {"task_id": {"type": "integer"}},
                "required": ["task_id"],
            },
        },
        {
            "type": "function",
            "name": "set_reminder",
            "description": "Schedule a reminder for a task (remind_at must be ISO 8601 UTC; call parse_when first if natural language).",
            "parameters": {
                "type": "object",
                "properties": {
                    "task_id": {"type": "integer"},
                    "remind_at": {"type": "string", "description": "ISO 8601 UTC datetime"},
                },
                "required": ["task_id", "remind_at"],
            },
        },
        {
            "type": "function",
            "name": "cancel_reminder",
            "description": "Cancel a reminder by id.",
            "parameters": {
                "type": "object",
                "properties": {"reminder_id": {"type": "integer"}},
                "required": ["reminder_id"],
            },
        },
        {
            "type": "function",
            "name": "list_reminders",
            "description": "List reminders (only pending by default).",
            "parameters": {
                "type": "object",
                "properties": {"only_pending": {"type": "boolean", "default": True}},
                "required": [],
            },
        },
        {
            "type": "function",
            "name": "parse_when",
            "description": "Parse a natural-language date/time phrase to ISO UTC.",
            "parameters": {"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]},
        },
    ]

TOOL_MAP = {
    "add_task": lambda **kw: agent_add_task(**kw),
    "list_tasks": lambda **kw: list_tasks(**kw) if kw else list_tasks(),
    "list_tasks_filtered": lambda **kw: list_tasks_filtered(**kw) if kw else list_tasks_filtered(),
    "complete_task": lambda **kw: complete_task(_validate_task_id(kw["task_id"])),
    "update_task": lambda **kw: agent_update_task(**kw),
    "delete_task": lambda **kw: delete_task(_validate_task_id(kw["task_id"])),
    "set_reminder": lambda **kw: agent_set_reminder(**kw),
    "cancel_reminder": lambda **kw: agent_cancel_reminder(**kw),
    "list_reminders": lambda **kw: list_reminders(**kw) if kw else list_reminders(),
    "parse_when": lambda **kw: parse_when(kw["text"], local_tz=LOCAL_TZ),
}

# --------------------------- Pretty Printers ----------------------------- #

def pretty_print_tasks(tasks: List[Dict[str, Any]]) -> str:
    if not tasks:
        return "No tasks found."
    now = _utc_now()
    lines = []
    for t in tasks:
        status = f"{GREEN}✅{RESET}" if t.get("done") else "⬜"
        due = t.get("due")
        extra = ""
        if due:
            try:
                due_dt = datetime.fromisoformat(due)
                if due_dt.tzinfo is None:
                    due_dt = due_dt.replace(tzinfo=TZ)
                if t.get("done"):
                    extra = f" — due {_fmt_local(due)} (local)"
                else:
                    if due_dt < now:
                        extra = f" — {RED}overdue{RESET} ({(now - due_dt).days}d) • {_fmt_local(due)}"
                    else:
                        delta = due_dt - now
                        days = delta.days
                        hours = delta.seconds // 3600
                        if days > 0:
                            extra = f" — due in {days}d {hours}h • {_fmt_local(due)}"
                        elif hours > 0:
                            extra = f" — due in {hours}h • {_fmt_local(due)}"
                        else:
                            mins = max(1, (delta.seconds % 3600) // 60)
                            extra = f" — due in {mins}m • {_fmt_local(due)}"
            except Exception:
                extra = f" — due {due}"
        lines.append(f"{status} {t['id']}. {t['title']}{extra}")
    return "\n".join(lines)

def pretty_print_reminders(reminders: List[Dict[str, Any]]) -> str:
    if not reminders:
        return "No reminders."
    lines = []
    for r in reminders:
        sent = "✅" if r.get("sent") else "⏰"
        lines.append(f"{sent} {r['id']}. task #{r['task_id']} — at {r['remind_at']} — {r.get('title','')}")
    return "\n".join(lines)

def print_help() -> None:
    print(
        "\nCommands:\n"
        "  add <title> [when...]                     add task (e.g., 'add buy milk tomorrow 5pm')\n"
        "  list | list today | list this week | list overdue | list done | list open\n"
        "  ls [-a|--all|-t|--today|-w|--week|-o|--overdue|-d|--done|-p|--open]\n"
        "  complete task <id>                        mark complete\n"
        "  update task <id> title <new title>\n"
        "  update task <id> due <when...>\n"
        "  delete task <id> [--yes]                  confirm delete unless --yes\n"
        "  set reminder for task <id> at <when...>\n"
        "  list reminders | cancel reminder <id> | snooze reminder <id> by <N> minutes\n"
        "  plan <goal>                               break a high-level goal into subtasks\n"
        "  reflect                                   show recent reflections\n"
        "  mode                                      show whether you are ONLINE (Agent/GPT) or OFFLINE (CLI)\n"
        f"\nDisplay timezone: {LOCAL_TZ_NAME} (set LOCAL_TZ env to change)\n"
        "Scopes:\n"
        "  today      = today (local day)\n"
        "  this week  = next 7 days (rolling)\n"
        "  overdue    = due date passed and not done\n"
    )



# --------------------------- Background Scheduler ------------------------ #

class ReminderScheduler(threading.Thread):
    def __init__(self, stop_event: threading.Event, poll_seconds: int = SCHED_POLL):
        super().__init__(daemon=True)
        self.stop_event = stop_event
        self.poll_seconds = max(5, poll_seconds)

    def run(self) -> None:
        log.info("Reminder scheduler started (poll=%ss)", self.poll_seconds)
        while not self.stop_event.is_set():
            try:
                now_iso = _utc_now().isoformat()
                due = _fetch_due_reminders(now_iso)
                if due:
                    ids = [d["id"] for d in due]
                    _mark_reminders_sent(ids)
                    for d in due:
                        print(f"\n🔔 REMINDER: Task #{d['task_id']} — {d['title']} (at {d['remind_at']})\n")
                for _ in range(self.poll_seconds):
                    if self.stop_event.is_set():
                        break
                    time.sleep(1)
            except Exception as e:
                log.exception("Scheduler error: %s", e)
                time.sleep(self.poll_seconds)
        log.info("Reminder scheduler stopped")

# --------------------------- CLI Helpers -------------------------------- #

def _warn_no_api_key():
    if not os.environ.get("OPENAI_API_KEY"):
        log.warning("OPENAI_API_KEY is not set; agent requests will fail. CLI fallback still works.")


def _local_heuristic_fallback(user_text: str) -> Optional[str]:
    """
    Lightweight non-LLM fallback. Supports:
      - add <title> [when...]
      - list / list today / list this week / list overdue / list done / list open
      - ls [-a|--all|-t|--today|-w|--week|-o|--overdue|-d|--done|-p|--open]
      - complete task <id>
      - delete task <id> [--yes]
      - update task <id> title <new title>
      - update task <id> due <when...>
      - set reminder for task <id> at <when...>
      - cancel reminder <id>
      - list reminders
      - snooze reminder <id> by <N> minutes
      - help / ? / h
    """
    s = user_text.strip().lower()

    # plan <goal>
    if s.startswith("plan "):
        goal = user_text[5:].strip()
        if not goal:
            return "What should I plan?"
        tasks = planner_plan(goal)
        out = []
        for t in tasks:
            agent_add_task(t)
            out.append(f" - {t}")
        return "Planned tasks:\n" + "\n".join(out)

    # reflect (view memory)
    if s in {"reflect", "show reflections", "history reflect", "reflection"}:
        reflections = get_reflections()
        if not reflections:
            return "No reflections yet."
        return "Recent reflections:\n" + "\n".join(f"• {r}" for r in reflections)

    # help
    if s in {"help", "?", "h"}:
        print_help()
        return ""
    if s in {"mode", "status"}:
        m = _agent_mode()
        return f"Current mode: {m} — " + ("Agent/GPT enabled" if m == "ONLINE" else "CLI fallback")

    # lists
    if s in {"list", "list tasks", "list my tasks"}:
        return pretty_print_tasks(list_tasks())
    if s in {"list today", "list todays tasks", "list today tasks"}:
        return pretty_print_tasks(list_tasks_filtered("today"))
    if s in {"list this week", "list week", "list this week tasks"}:
        return pretty_print_tasks(list_tasks_filtered("this_week"))
    if s in {"list overdue", "overdue"}:
        return pretty_print_tasks(list_tasks_filtered("overdue"))
    if s in {"list done", "list completed"}:
        return pretty_print_tasks(list_tasks_filtered("done"))
    if s in {"list open", "list pending"}:
        return pretty_print_tasks(list_tasks_filtered("open"))

    # ls aliases
    if s == "ls":
        return pretty_print_tasks(list_tasks_filtered("open"))
    if s in {"ls -a", "ls --all"}:
        return pretty_print_tasks(list_tasks_filtered("all"))
    if s in {"ls -t", "ls --today"}:
        return pretty_print_tasks(list_tasks_filtered("today"))
    if s in {"ls -w", "ls --week"}:
        return pretty_print_tasks(list_tasks_filtered("this_week"))
    if s in {"ls -o", "ls --overdue"}:
        return pretty_print_tasks(list_tasks_filtered("overdue"))
    if s in {"ls -d", "ls --done"}:
        return pretty_print_tasks(list_tasks_filtered("done"))
    if s in {"ls -p", "ls --open"}:
        return pretty_print_tasks(list_tasks_filtered("open"))

    # complete task N
    m = re.match(r"(?:complete|finish|done)\s+task\s+(\d+)", s)
    if m:
        tid = _validate_task_id(m.group(1))
        complete_task(tid)
        from reflection import add_reflection
        add_reflection(f"Completed task {tid}", source="task")
        return "Task completed ✅"

    # delete task N [--yes]
    m = re.match(r"(?:delete|remove)\s+task\s+(\d+)(?:\s+(--yes))?", s)
    if m:
        tid = _validate_task_id(m.group(1))
        force = bool(m.group(2))
        if not force:
            return f"Confirm delete task {tid}? Re-run: delete task {tid} --yes"
        delete_task(tid)
        return "Task deleted 🗑️"

    # update task N title ...
    m = re.match(r"update\s+task\s+(\d+)\s+title\s+(.+)$", s, re.IGNORECASE)
    if m:
        tid = _validate_task_id(m.group(1))
        new_title = user_text[m.start(2):].strip()
        agent_update_task(tid, title=new_title)
        return "Task updated ✏️"

    # update task N due <when...>
    m = re.match(r"update\s+task\s+(\d+)\s+due\s+(.+)$", s, re.IGNORECASE)
    if m:
        tid = _validate_task_id(m.group(1))
        when_text = user_text[m.start(2):].strip()
        try:
            r = parse_when(when_text, local_tz=LOCAL_TZ)
            agent_update_task(tid, due=r["iso_utc"])
            return "Task updated ✏️"
        except Exception:
            return "Couldn't parse that due date."

    # set reminder for task N at <when...>
    m = re.match(r"set\s+reminder\s+for\s+task\s+(\d+)\s+at\s+(.+)$", s, re.IGNORECASE)
    if m:
        tid = _validate_task_id(m.group(1))
        when_text = user_text[m.start(2):].strip()
        try:
            r = parse_when(when_text, local_tz=LOCAL_TZ)
            agent_set_reminder(tid, r["iso_utc"])
            return "Reminder set ⏰"
        except Exception:
            return "Couldn't parse that reminder time."

    # cancel reminder N
    m = re.match(r"(?:cancel|delete|remove)\s+reminder\s+(\d+)", s, re.IGNORECASE)
    if m:
        rid = int(m.group(1))
        cancel_reminder(rid)
        return "Reminder canceled ❌"

    # snooze reminder N by M minutes
    m = re.match(r"snooze\s+reminder\s+(\d+)\s+by\s+(\d+)\s+minutes?", s, re.IGNORECASE)
    if m:
        rid = int(m.group(1)); mins = int(m.group(2))
        with get_db() as con:
            cur = con.cursor()
            row = cur.execute("SELECT remind_at FROM reminders WHERE id=? AND sent=0", (rid,)).fetchone()
            if not row:
                return "No pending reminder with that id."
            base = datetime.fromisoformat(row[0])
            if base.tzinfo is None:
                base = base.replace(tzinfo=TZ)
            else:
                base = base.astimezone(TZ)
            new_iso = (base + timedelta(minutes=mins)).isoformat()
            cur.execute("UPDATE reminders SET remind_at=? WHERE id=?", (new_iso, rid))
        return f"Reminder snoozed by {mins} minutes 😴"

    # add ...
    if s.startswith("add "):
        raw = user_text[4:].strip()
        when_pat = re.compile(
            r"("
            r"(?:today|tomorrow)(?:\s+\d{1,2}(?::\d{2})?\s*(?:am|pm)?)?"
            r"|next\s+(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)\s+\d{1,2}(?::\d{2})?\s*(?:am|pm)?"
            r"|(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)\s+\d{1,2}(?::\d{2})?\s*(?:am|pm)?"
            r"|\d{4}-\d{2}-\d{2}(?:\s+\d{1,2}(?::\d{2})?)?"
            r"|\d{1,2}/\d{1,2}(?:\s+\d{1,2}(?::\d{2})?\s*(?:am|pm)?)?"
            r"|in\s+\d+\s+(?:minutes?|minute|min|hours?|hour|days?|day|weeks?|week)"
            r"|\d{1,2}(?::\d{2})?\s*(?:am|pm)"
            r")\s*$",
            re.IGNORECASE,
        )
        when_str = None
        m2 = when_pat.search(raw)
        if m2:
            when_str = m2.group(1).strip()
            title = raw[: m2.start()].strip(" ,.-") or raw
        else:
            title = raw

        if when_str:
            try:
                r = parse_when(when_str, local_tz=LOCAL_TZ)
                agent_add_task(title=title, due=r["iso_utc"])
                return "Task added ✅"
            except Exception:
                pass

        agent_add_task(title=title)
        return "Task added ✅"

    return None

# --------------------------- Main Loop ---------------------------------- #

def run_cli() -> None:
    # tests first?
    if len(sys.argv) > 1 and sys.argv[1].lower() == "test":
        run_tests()
        return

    if not OPENAI_AVAILABLE:
        log.warning("`openai` package not installed. Agent path disabled; CLI fallback available.")
    else:
        _warn_no_api_key()

    init_db()

    # start scheduler
    stop_event = threading.Event()
    scheduler = ReminderScheduler(stop_event, poll_seconds=SCHED_POLL)
    scheduler.start()

    mode = _agent_mode()
    print(f"[MODE: {mode} — {'Agent/GPT enabled' if mode == 'ONLINE' else 'CLI fallback'}]")

    try:
        print(
            "To-Do Agent ready. Try:\n"
            "- help\n"
            "- add buy milk tomorrow 5pm\n"
            "- ls -t  |  ls -w  |  ls -o  |  ls -d  |  ls -a\n"
            "- set reminder for task 1 in 1 minute\n"
            "- update task 1 title buy oat milk\n"
            "- update task 1 due Friday 6pm\n"
            "- complete task 1\n"
            "- delete task 1  (add --yes to confirm)\n"
            "Type 'exit' to quit.\n"
        )

        msgs = [{"role": "system", "content": SYSTEM_PROMPT}] if OPENAI_AVAILABLE else []
        client = OpenAI() if OPENAI_AVAILABLE else None

        while True:
            try:
                user = input("YOU: ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                break
            if not user:
                continue
            if user.lower() in {"quit", "exit"}:
                break

            # --- NEW: show help instantly, even in agent mode ---
            if user.strip().lower() in {"help", "?", "h"}:
                print_help()
                print()
                continue
            # -----------------------------------------------------
            # intercept "mode" / "status" before GPT
            if user.lower() in {"mode", "status"}:
                m = _agent_mode()
                print(f"\nASSISTANT:\nCurrent mode: {m} — " + ("Agent/GPT enabled" if m == "ONLINE" else "CLI fallback") + "\n")
                continue

            # intercept "plan" before GPT
            if user.lower().startswith("plan "):
                goal = user[5:].strip()
                tasks = planner_plan(goal)
                out = []
                for t in tasks:
                    agent_add_task(t)  # uses your existing DB-safe wrapper
                    out.append(f" - {t}")
                print("\nASSISTANT:\nPlanned tasks:\n" + "\n".join(out) + "\n")
                continue

            # intercept "reflect" before GPT
            if user.lower() in {"reflect", "reflection", "show reflections"}:
                reflections = get_reflections()
                if not reflections:
                    print("\nASSISTANT:\nNo reflections yet.\n")
                else:
                    txt = "\n".join(f"• {r}" for r in reflections)
                    print(f"\nASSISTANT:\nRecent reflections:\n{txt}\n")
                continue

            # First, try agent path if available
            if OPENAI_AVAILABLE and os.environ.get("OPENAI_API_KEY"):
                msgs.append({"role": "user", "content": user})
                try:
                    resp = client.responses.create(
                        model=MODEL,
                        input=msgs,
                        tools=build_tools_schema(),
                    )
                except Exception as e:
                    log.error("Initial call failed: %s", e)
                    fb = _local_heuristic_fallback(user)
                    if fb is not None:
                        print("\nASSISTANT:\n" + fb + "\n")
                    continue

                tool_outputs: List[Dict[str, Any]] = []
                assistant_msgs: List[Dict[str, Any]] = []

                # --- NEW: SDK-shape-agnostic parsing of resp.output ---
                def _get_attr(obj, name, default=None):
                    return getattr(obj, name, obj.get(name, default) if isinstance(obj, dict) else default)

                def _as_dict(model_obj):
                    if hasattr(model_obj, "model_dump"):
                        return model_obj.model_dump()
                    return model_obj

                for item in (resp.output or []):
                    if _get_attr(item, "type") == "message":
                        msg = _get_attr(item, "message", item)
                        role = _get_attr(msg, "role")
                        content = _get_attr(msg, "content", [])
                        tool_calls = _get_attr(msg, "tool_calls") or []

                        content_dicts = [_as_dict(c) for c in (content or [])]
                        tc_dicts = [_as_dict(tc) for tc in (tool_calls or [])]

                        m = {"role": role, "content": content_dicts}
                        if tc_dicts:
                            m["tool_calls"] = tc_dicts
                        assistant_msgs.append(m)

                        for tc in (tool_calls or []):
                            tc_d = _as_dict(tc)
                            tc_id = _get_attr(tc_d, "id")
                            fn = _get_attr(tc_d, "function", {})
                            name = _get_attr(fn, "name")
                            args_json = _get_attr(fn, "arguments", "{}") or "{}"
                            try:
                                args = json.loads(args_json)
                            except Exception:
                                args = {}
                            try:
                                result = TOOL_MAP[name](**args)
                                tool_outputs.append({
                                    "role": "tool",
                                    "tool_call_id": tc_id,
                                    "name": name,
                                    "content": json.dumps(result),
                                })
                            except Exception as e:
                                tool_outputs.append({
                                    "role": "tool",
                                    "tool_call_id": tc_id,
                                    "name": name,
                                    "content": json.dumps({"error": str(e)}),
                                })
                # ------------------------------------------------------

                if tool_outputs:
                    msgs.extend(assistant_msgs)
                    msgs.extend(tool_outputs)

                    try:
                        follow = client.responses.create(
                            model=MODEL,
                            input=msgs,
                            tools=build_tools_schema(),
                        )
                        final_text = follow.output_text or ""
                    except Exception as e:
                        final_text = ""
                        log.error("Follow-up call failed: %s", e)

                    if not final_text.strip():
                        try:
                            last_calls = [t for t in tool_outputs]

                            def ok(name: str) -> bool:
                                return any(t.get("name") == name and not json.loads(t.get("content","{}")).get("error") for t in last_calls)

                            def warn_from(name: str) -> Optional[str]:
                                for t in reversed(last_calls):
                                    if t.get("name") == name:
                                        try:
                                            w = json.loads(t.get("content","{}")).get("warning")
                                            if w == "due_is_past": return " (note: due is in the past)"
                                            if w == "due_parse_failed": return " (note: couldn't parse; saved without due)"
                                        except Exception: pass
                                return None

                            if ok("add_task"):
                                final_text = f"Task added ✅{warn_from('add_task') or ''}"
                            elif ok("complete_task"):
                                # NEW: reflection on model-driven completion
                                try:
                                    from reflection import add_reflection
                                    # Pull the most recent complete_task payload (to get the id if available)
                                    completed_id = None
                                    for t in reversed(last_calls):
                                        if t.get("name") == "complete_task":
                                            payload = json.loads(t.get("content", "{}"))
                                            if isinstance(payload, dict):
                                                completed_id = payload.get("id") or payload.get("task_id")
                                            break
                                    if completed_id:
                                        add_reflection(f"Completed task {completed_id}", source="task")
                                    else:
                                        add_reflection("Completed a task", source="task")
                                except Exception:
                                    pass
                                final_text = "Task completed ✅"
                            elif ok("update_task"):
                                final_text = f"Task updated ✏️{warn_from('update_task') or ''}"
                            elif ok("delete_task"):
                                final_text = "Task deleted 🗑️"
                            elif ok("set_reminder"):
                                final_text = f"Reminder set ⏰{warn_from('set_reminder') or ''}"
                            elif ok("cancel_reminder"):
                                final_text = "Reminder canceled ❌"
                            elif any(t.get("name") == "list_tasks" for t in last_calls):
                                for t in reversed(last_calls):
                                    if t.get("name") == "list_tasks":
                                        payload = json.loads(t.get("content","null"))
                                        if isinstance(payload, list):
                                            print("\nASSISTANT:\n" + pretty_print_tasks(payload) + "\n")
                                            final_text = ""
                                            break
                            elif any(t.get("name") == "list_tasks_filtered" for t in last_calls):
                                for t in reversed(last_calls):
                                    if t.get("name") == "list_tasks_filtered":
                                        payload = json.loads(t.get("content","null"))
                                        if isinstance(payload, list):
                                            print("\nASSISTANT:\n" + pretty_print_tasks(payload) + "\n")
                                            final_text = ""
                                            break
                            elif any(t.get("name") == "list_reminders" for t in last_calls):
                                for t in reversed(last_calls):
                                    if t.get("name") == "list_reminders":
                                        payload = json.loads(t.get("content","null"))
                                        if isinstance(payload, list):
                                            print("\nASSISTANT:\n" + pretty_print_reminders(payload) + "\n")
                                            final_text = ""
                                            break
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
                        fb = _local_heuristic_fallback(user)
                        if fb is not None:
                            print("\nASSISTANT:\n" + fb + "\n")
                        else:
                            log.warning("Model returned no content. Consider a different model.")
            else:
                # CLI fallback path only
                fb = _local_heuristic_fallback(user)
                if fb is not None:
                    print("\nASSISTANT:\n" + fb + "\n")
                else:
                    print("\nASSISTANT:\n" + "(no action)" + "\n")
    finally:
        # stop scheduler
        stop_event.set()
        scheduler.join(timeout=5)

# ------------------------------- Tests ---------------------------------- #

def _assert_eq(label: str, a, b) -> None:
    if a != b:
        raise AssertionError(f"{label}: expected {b!r}, got {a!r}")

def run_tests() -> None:
    print("Running tests...\n")
    # fresh DB
    try:
        os.remove(DB_PATH)
    except FileNotFoundError:
        pass
    init_db()

    base = datetime(2025, 10, 18, 12, 0, tzinfo=TZ)

    # _parse_time_part
    _assert_eq("time 5pm", _parse_time_part("5pm"), (17, 0))
    _assert_eq("time 5:30pm", _parse_time_part("5:30pm"), (17, 30))
    _assert_eq("time 09:15", _parse_time_part("09:15"), (9, 15))
    _assert_eq("time 0915", _parse_time_part("0915"), (9, 15))

    # Relative phrases
    r = parse_when("in 2 hours", now=base, local_tz=TZ)
    _assert_eq("in 2 hours", r["iso_utc"], (base + timedelta(hours=2)).replace(microsecond=0).isoformat())

    r = parse_when("in 3 days", now=base, local_tz=TZ)
    _assert_eq("in 3 days", r["iso_utc"], (base + timedelta(days=3)).replace(microsecond=0).isoformat())

    # Today / tomorrow
    r = parse_when("today 5pm", now=base, local_tz=TZ)
    _assert_eq("today 5pm", r["iso_utc"], base.replace(hour=17, minute=0, second=0, microsecond=0).isoformat())

    r = parse_when("tomorrow 09:30", now=base, local_tz=TZ)
    _assert_eq("tomorrow 09:30", r["iso_utc"], (base + timedelta(days=1)).replace(hour=9, minute=30, second=0, microsecond=0).isoformat())

    # Next weekday (next Monday from Sat Oct 18, 2025 -> Mon Oct 20, 2025)
    r = parse_when("next monday 8am", now=base, local_tz=TZ)
    _assert_eq("next monday 8am", r["iso_utc"], datetime(2025, 10, 20, 8, 0, tzinfo=TZ).isoformat())

    # Absolute formats
    r = parse_when("2025-10-20 14:00", now=base, local_tz=TZ)
    _assert_eq("YYYY-MM-DD HH:MM", r["iso_utc"], datetime(2025, 10, 20, 14, 0, tzinfo=TZ).isoformat())

    r = parse_when("10/21 4pm", now=base, local_tz=TZ)
    _assert_eq("MM/DD 4pm", r["iso_utc"], datetime(2025, 10, 21, 16, 0, tzinfo=TZ).isoformat())

    r = parse_when("5pm", now=base, local_tz=TZ)
    _assert_eq("time only today", r["iso_utc"], base.replace(hour=17, minute=0, second=0, microsecond=0).isoformat())

    # Filters + tasks
    t1 = agent_add_task("buy milk", datetime(2025,10,18,15,0,tzinfo=TZ).isoformat())
    t2 = agent_add_task("file taxes", datetime(2025,10,21,9,0,tzinfo=TZ).isoformat())
    complete_task(t1["id"])
    assert any(x["id"] == t1["id"] for x in list_tasks_filtered("done"))
    assert any(x["id"] == t2["id"] for x in list_tasks_filtered("this_week"))

    # Reminders DB logic (no thread)
    r1 = agent_set_reminder(t2["id"], datetime(2025,10,18,12,5,tzinfo=TZ).isoformat())
    assert r1.get("id")
    all_r = list_reminders(only_pending=False)
    assert any(rr["id"] == r1["id"] for rr in all_r)

    print("All tests passed.\n")

if __name__ == "__main__":
    run_cli()

