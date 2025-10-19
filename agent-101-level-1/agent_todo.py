import os, sqlite3, json, re
from typing import Dict, Any, List, Optional
from openai import OpenAI

# ====== Config ======
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

def _format_list(tasks: List[Dict[str, Any]]) -> str:
    if not tasks:
        return "No open tasks. 🎉"
    lines = []
    for t in tasks:
        parts = [f"#{t['id']} — {t['title']}"]
        if t.get("due"):
            parts.append(f"(due: {t['due']})")
        if t.get("done"):
            parts.append("[done]")
        lines.append(" ".join(parts))
    return "\n".join(lines)

def _local_summarize(tool_outputs: List[Dict[str, Any]]) -> str:
    """
    Fallback summary if SDK cannot submit tool outputs back to the model.
    We summarize the final tool result(s) locally, so the user still gets a clean answer.
    """
    if not tool_outputs:
        return "(no actions taken)"
    # Use the last output as the main thing to summarize
    last = tool_outputs[-1]["output"]
    if isinstance(last, dict) and {"id", "title"}.issubset(last.keys()):
        # add_task result
        due = f" (due: {last.get('due')})" if last.get("due") else ""
        return f"Added task #{last['id']}: {last['title']}{due}."
    if isinstance(last, dict) and "updated" in last:
        # complete_task result
        if last["updated"]:
            return "Marked the task complete."
        return "I couldn't find that task id."
    if isinstance(last, list):
        # list_tasks result
        return _format_list(last)
    # Generic fallback
    return json.dumps(last, ensure_ascii=False)

def _has_submit_tool_outputs() -> bool:
    # Older SDKs won't have this method
    return hasattr(client.responses, "submit_tool_outputs")

# ====== SQLite ======
def init_db():
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS tasks(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          title TEXT NOT NULL,
          due TEXT,
          done INTEGER DEFAULT 0,
          created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
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

def list_tasks(show_done: bool = False) -> List[Dict[str, Any]]:
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    q = "SELECT id,title,due,done FROM tasks"
    if not show_done:
        q += " WHERE done=0"
    q += " ORDER BY done, COALESCE(due,''), id DESC"
    rows = cur.execute(q).fetchall()
    con.close()
    return [{"id": r[0], "title": r[1], "due": r[2], "done": bool(r[3])} for r in rows]

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

SYSTEM_INSTRUCTIONS = """
You are a helpful To-Do Agent.
- Understand natural-language requests about tasks.
- Decide which tool to call (add_task, list_tasks, complete_task).
- After a tool runs, summarize the result briefly for the user.
- When a due date is mentioned, pass it through unchanged.
- When listing tasks, include ids so the user can complete one.
- When calling add_task, ALWAYS include both "title" and "due" (use null for due if none).
"""

# ====== Agent Runner ======
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
                    due = args.get("due")
                    res = add_task(title, due)
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
                # Even if this fails, still give a good local summary
                print("\nASSISTANT:\n", f"(SDK continuation failed; showing local result) {e}\n" + _local_summarize(tool_outputs))
                return
        else:
            # Old SDK path: provide local summary so user sees a clean answer
            print("\nASSISTANT:\n", _local_summarize(tool_outputs))
            return

    # If no tools were called, just print the model's text
    print("\nASSISTANT:\n", getattr(r, "output_text", "").strip() or "(no text returned)")

# ====== Main ======
if __name__ == "__main__":
    init_db()
    print("To-Do Agent ready. Try:")
    print("- add buy milk tomorrow 5pm")
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
