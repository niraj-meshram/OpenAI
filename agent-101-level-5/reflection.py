import json
import os
from typing import Dict, List, Optional

MEMORY_PATH = "agent_memory.json"

def _load_memory() -> Dict:
    if not os.path.exists(MEMORY_PATH):
        return {"recent_reflections": [], "max_entries": 20}
    try:
        with open(MEMORY_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"recent_reflections": [], "max_entries": 20}

def _save_memory(data: Dict) -> None:
    with open(MEMORY_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

def add_reflection(text: str, source: Optional[str] = None) -> None:
    """
    Add a short reflection entry (1–2 sentences).
    source = e.g. 'planner', 'task', 'user', etc. (optional)
    """
    mem = _load_memory()
    reflections: List[str] = mem.get("recent_reflections", [])

    entry = text.strip()
    if source:
        entry = f"[{source}] {entry}"

    reflections.append(entry)
    # enforce ring-buffer cap
    max_entries = mem.get("max_entries", 20)
    if len(reflections) > max_entries:
        reflections = reflections[-max_entries:]

    mem["recent_reflections"] = reflections
    _save_memory(mem)

def get_reflections() -> List[str]:
    mem = _load_memory()
    return mem.get("recent_reflections", [])
