import os
from typing import List, Dict, Optional
from reflection import add_reflection

# Optional: GPT if available
try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ModuleNotFoundError:
    OPENAI_AVAILABLE = False


def _rule_based_decompose(goal: str) -> List[str]:
    """
    Offline fallback (tasklist mode): extract verbs/nouns into actionable tasks.
    Very lightweight heuristics so it "feels intelligent" even offline.
    """
    g = goal.lower()
    tasks = []

    # Example heuristics
    if "clean" in g or "house" in g or "home" in g:
        tasks.extend([
            "clean living room",
            "clean kitchen",
            "take out trash",
            "do laundry",
        ])
    if "grocery" in g or "shopping" in g or "buy" in g:
        tasks.extend([
            "make grocery list",
            "go grocery shopping",
            "put groceries away"
        ])
    if "study" in g or "learn" in g:
        tasks.extend([
            "review notes",
            "practice examples",
            "summarize learnings"
        ])
    if not tasks:
        # fallback generic breakdown
        tasks = [
            f"start: {goal}",
            f"work on: {goal}",
            f"finish: {goal}"
        ]
    return tasks


def _gpt_decompose(goal: str) -> Optional[List[str]]:
    """Smart multi-step decomposition using GPT (if online)."""
    if not OPENAI_AVAILABLE or not os.environ.get("OPENAI_API_KEY"):
        return None

    client = OpenAI()
    prompt = (
        "Break the following goal into 3-7 short actionable to-do subtasks, "
        "return them as a plain JSON list of strings. No explanation.\n"
        f"Goal: {goal}"
    )

    try:
        resp = client.responses.create(
            model=os.environ.get("AGENT_MODEL", "gpt-4o-mini"),
            input=prompt,
        )
        txt = resp.output_text.strip()
        # try json extraction
        import json
        arr = json.loads(txt)
        if isinstance(arr, list):
            return [str(x).strip() for x in arr if x]
        return None
    except Exception:
        return None


def plan(goal: str) -> List[str]:
    """
    Returns list of subtasks (strings).
    Hybrid mode: GPT if available, else local heuristic.
    """
    tasks = _gpt_decompose(goal) or _rule_based_decompose(goal)
    # create minimal reflection entry
    add_reflection(f"Planned {len(tasks)} tasks for goal: {goal}")
    return tasks
