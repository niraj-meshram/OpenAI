import os, sqlite3, json, re
from typing import Dict, Any, List, Optional
from openai import OpenAI

# ====== NEW: date parsing ======
import pytz
import dateparser
from dateparser.search import search_dates
from datetime import datetime

# ====== Config ======
# Use your local timezone; change if needed.
LOCAL_TZ_NAME = os.getenv("AGENT_TIMEZONE", "America/Denver")
LOCAL_TZ = pytz.timezone(LOCAL_TZ_NAME)

MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")  # change if needed
DB_PATH = "todos.db"

client = OpenAI()   # reads OPENAI_API_KEY

# ====== Helpers ======
def _parse_args(a):
    """Responses API sometimes returns tool args as JSON string; sometimes a dict."""
    if a is None:
        return {}
    if isinstance(a, str):
        try:
            return json.loads(a)
        except json.JSONDecodeError:
            return {"value": a}
    return a  # already a dict

def _extract_title(args: Dict[str, Any], user_message: str) -> str:
    """Be robust to different arg keys; fall back to the user message."""
    title = (
        args.get("title")
        or args.get("task")
        or args.get("text")
        or args.get("name")
        or args.get("value")  # from string fallback
    )
    if title:
        return str(title).strip()
    cleaned = user_message.strip()
    for prefix in ("add ", "create ", "new task ", "please add ", "add task "):
        if cleaned.lower().startswith(prefix):
            cleaned = cleaned[len(prefix):]
            break
    return cleaned or "untitled task"

def _extract_task_id(args: Dict[str, Any], user_message: str) -> Optional[int]:
    """Accept task_id/id or infer from text like 'complete task 3'."""
    task_id = args.get("task_id") or args.get("id")
    if task_id is not None:
        try:
            return int(task_id)
        except (TypeError, ValueError):
            pass
    m = re.search(r"\btask\s+(\d+)\b", user_message.lower())
    if m:
        return int(m.group(1))
    return None

def _humanize_iso(iso_str: str) -> str:
    """Turn ISO string into a friendly local time, e.g. 'Tue, Oct 21 5:00 PM'."""
    dt = datetime.fromisoformat(iso_str)
    if dt.tzinfo is None:
        dt = LOCAL_TZ.localize(dt)
    local_dt = dt.astimezone(LOCAL_TZ)
    return local_dt.strftime("%a, %b %d %I:%M %p")

def _parse_natural_due(due_text: Optional[str]) -> Optional[str]:
    """
    Parse natural language like 'tomorrow 5pm' into ISO8601 with timezone.
    Returns ISO string or None if parsing fails.
    """
    if not due_text:
        return None
    # Put RELATIVE_BASE into settings (works across dateparser versions)
    now_local = datetime.now(LOCAL_TZ)
    settings = {
        "TIMEZONE": LOCAL_TZ_NAME,
        "RETURN_AS_TIMEZONE_AWARE": True,
        "PREFER_DATES_FROM": "future",  # 'this Friday' -> future Friday
        "RELATIVE_BASE": now_local,
    }
    dt = dateparser.parse(due_text, settings=settings, languages=None)
    if not dt:
        return None
    if dt.tzinfo is None:
        dt = LOCAL_TZ.localize(dt)
    return dt.isoformat()

def _split_title_and_due_from_title(title: str) -> (str, Optional[str]):
    """
    If the model didn't provide 'due', try to find a natural-language date/time
    inside the title, e.g. 'buy milk tomorrow 5pm' -> ('buy milk', 'tomorrow 5pm').
    """
    if not title:
        return title, None

    # Older dateparser builds don't accept RELATIVE_BASE for search_dates; omit it.
    found = search_dates(
        title,
        settings={
            "TIMEZONE": LOCAL_TZ_NAME,
            "RETURN_AS_TIMEZONE_AWARE": True,
            "PREFER_DATES_FROM": "future",
        },
    )
    if not found:
        return title, None

    # pick the last match (often at the end, most specific)
    matched_text, _ = found[-1]

    # remove matched date text from title (case-insensitive)
    t_lower = title.lower()
    m_lower = matched_text.lower()
    idx = t_lower.rfind(m_lower)
    if idx != -1:
        new_title = (title[:idx] + title[idx + len(matched_text):]).strip(" ,.-")
    else:
        new_title = title

    if not new_title:
        new_title = title

    return new_title, matched_text

def _format_list(tasks: List[Dict[str, Any]]) -> str:
    if not tasks:
        return "No open tasks. 🎉"
    lines = []
    for t in tasks:
        parts = [f"#{t['id']} — {t['title']}"]
        # Prefer due_at (parsed datetime) if present; fall back to due text
        if t.get("due_at"):
            try:
                when = _humanize_iso(t["due_at"])
                parts.append(f"(due: {when})")
            except Exception:
                if t.get("due"):
                    parts.append(f"(due: {t['due']})")
        elif t.get("due"):
            parts.append(f"(due: {t['due']})")
        if t.get("done"):
            parts.append("[done]")
        lines.append(" ".join(parts))
    return "\n".join(lines)

# ====== SQLite ======
def init_db():
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    # Base table (Level 1)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS tasks(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          title TEXT NOT NULL,
          due TEXT,
          done INTEGER DEFAULT 0,
          created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    # Level 2 migration: add due_at if missing
    cur.execute("PRAGMA table_info(tasks)")
    cols = [row[1] for row in cur.fetchall()]
    if "due_at" not in cols:
        cur.execute("ALTER TABLE tasks ADD COLUMN due_at TEXT")
    con.commit()
    con.close()

def add_task(title: str, due_text: Optional[str] = None) -> Dict[str, Any]:
    """
    Level 2: parse natural language due into due_at (ISO8601).
    Keep original due_text in 'due' for user transparency.
    """
    due_at_iso = _parse_natural_due(due_text)
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute("INSERT INTO tasks(title, due, due_at) VALUES (?, ?, ?)", (title, due_text, due_at_iso))
    con.commit()
    tid = cur.lastrowid
    con.close()
    return {"id": tid, "title": title, "due": due_text, "due_at": due_at_iso, "done": False}

def list_tasks(show_done: bool = False) -> List[Dict[str, Any]]:
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    # Order: incomplete first, then earliest due_at, then newest id
    q = """
      SELECT id,title,due,done,due_at
      FROM tasks
      {where_clause}
      ORDER BY done,
               CASE WHEN due_at IS NULL THEN 1 ELSE 0 END,
               due_at ASC,
               id DESC
    """
    where_clause = "" if show_done else "WHERE done=0"
    rows = cur.execute(q.format(where_clause=where_clause)).fetchall()
    con.close()
    return [{"id": r[0], "title": r[1], "due": r[2], "done": bool(r[3]), "due_at": r[4]} for r in rows]

def complete_task(task_id: int) -> Dict[str, Any]:
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute("UPDATE tasks SET done=1 WHERE id=?", (task_id,))
    con.commit()
    changed = cur.rowcount
    con.close()
    return {"updated": changed}

# ====== Tools ======
TOOLS = [
  {
    "type": "function",
    "name": "add_task",
    "function": {
      "description": "Add a new task with an optional due date (natural text OK, e.g., 'tomorrow 5pm').",
      "parameters": {
        "type": "object",
        "properties": {
          "title": {"type": "string"},
          "due": {"type": "string"}
        },
        "required": ["title"]
      }
    }
  },
  {
    "type": "function",
    "name": "list_tasks",
    "function": {
      "description": "List tasks. Defaults to only incomplete ones.",
      "parameters": {
        "type": "object",
        "properties": {
          "show_done": {"type": "boolean", "default": False}
        }
      }
    }
  },
  {
    "type": "function",
    "name": "complete_task",
    "function": {
      "description": "Mark a task complete by id.",
      "parameters": {
        "type": "object",
        "properties": {"task_id": {"type": "integer"}},
        "required": ["task_id"]
      }
    }
  }
]

SYSTEM_INSTRUCTIONS = f"""
You are a helpful To-Do Agent.
- Understand natural-language requests about tasks.
- Decide which tool to call (add_task, list_tasks, complete_task).
- After a tool runs, summarize the result briefly for the user.
- When a due date is mentioned, pass the natural text as "due".
- The application will try to parse that natural text into a real datetime in timezone {LOCAL_TZ_NAME}.
- When listing tasks, include ids so the user can complete one.
- When calling add_task, ALWAYS include both "title" and "due" (use null for due if none).
"""

# ====== Agent Runner ======
def _local_summarize(tool_outputs: List[Dict[str, Any]]) -> str:
    if not tool_outputs:
        return "(no actions taken)"
    last = tool_outputs[-1]["output"]
    if isinstance(last, dict) and {"id", "title"}.issubset(last.keys()):
        # add_task result
        if last.get("due_at"):
            try:
                when = _humanize_iso(last["due_at"])
                return f"Added task #{last['id']}: {last['title']} (due: {when})."
            except Exception:
                pass
        if last.get("due"):
            return f"Added task #{last['id']}: {last['title']} (due: {last['due']})."
        return f"Added task #{last['id']}: {last['title']}."
    if isinstance(last, dict) and "updated" in last:
        return "Marked the task complete." if last["updated"] else "I couldn't find that task id."
    if isinstance(last, list):
        return _format_list(last)
    return json.dumps(last, ensure_ascii=False)

def _has_submit_tool_outputs() -> bool:
    return hasattr(client.responses, "submit_tool_outputs")

def run_agent(user_message: str):
    # 1) Initial call: let the model decide which tool(s) to call
    try:
        r = client.responses.create(
            model=MODEL,
            input=[
                {"role": "system", "content": SYSTEM_INSTRUCTIONS},
                {"role": "user", "content": user_message}
            ],
            tools=TOOLS
        )
    except Exception as e:
        print("\nASSISTANT:\n", f"API error during initial call: {e}")
        return

    # 2) Execute local tools if the model requested them
    tool_outputs = []
    try:
        for item in getattr(r, "output", []):
            if getattr(item, "type", None) == "function_call":
                name = getattr(item, "name", None)
                args = _parse_args(getattr(item, "arguments", None))

                if name == "add_task":
                    title = _extract_title(args, user_message)
                    due_text = args.get("due")

                    # Level-2 robustness: if model didn't pass 'due', try to extract it from title
                    if not due_text:
                        title, possible_due = _split_title_and_due_from_title(title)
                        if possible_due:
                            due_text = possible_due

                    res = add_task(title, due_text)

                elif name == "list_tasks":
                    res = list_tasks(bool(args.get("show_done", False)))

                elif name == "complete_task":
                    task_id = _extract_task_id(args, user_message)
                    if task_id is None:
                        res = {"error": "missing task_id"}
                    else:
                        res = complete_task(int(task_id))
                else:
                    res = {"error": f"unknown tool {name}"}

                tool_outputs.append({"call_id": item.call_id, "output": res})
    except Exception as e:
        print("\nASSISTANT:\n", f"Local tool execution error: {e}")
        return

    # 3) Try to continue with tool outputs via SDK (new) or fall back to local summary (old)
    if tool_outputs:
        if _has_submit_tool_outputs():
            try:
                r = client.responses.submit_tool_outputs(
                    response_id=r.id,
                    tool_outputs=tool_outputs
                )
                print("\nASSISTANT:\n", getattr(r, "output_text", "").strip() or "(no text returned)")
                return
            except Exception as e:
                print("\nASSISTANT:\n", f"(SDK continuation failed; showing local result) {e}\n" + _local_summarize(tool_outputs))
                return
        else:
            print("\nASSISTANT:\n", _local_summarize(tool_outputs))
            return

    # If no tools were called, just print the model's text
    print("\nASSISTANT:\n", getattr(r, "output_text", "").strip() or "(no text returned)")

# ====== Main ======
if __name__ == "__main__":
    init_db()
    print("To-Do Agent (Level 2) ready. Try:")
    print("- add buy milk tomorrow 5pm")
    print("- add dentist appointment next Monday 8am")
    print("- list my tasks")
    print("- complete task 1")
    while True:
        try:
            msg = input("\nYOU: ")
            if msg.strip().lower() in {"quit", "exit"}:
                break
            run_agent(msg)
        except KeyboardInterrupt:
            break
