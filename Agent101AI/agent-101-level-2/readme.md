# ðŸ§  Agent-101 â€” Level 2: Natural-Language Due Dates (OpenAI Responses + SQLite)

Level 2 upgrades your Level 1 To-Do agent so it can understand due dates written in **natural language** (e.g., â€œtomorrow 5pmâ€, â€œnext Monday 8amâ€), parse them into a **real timestamp**, and sort tasks by the actual time.

## ðŸš€ Whatâ€™s new in Level 2

- âœ… **Natural-language date parsing** using `dateparser`
- âœ… New DB column **`due_at`** (ISO8601 datetime with timezone)
- âœ… Stores both:
  - `due` â†’ the original text you typed
  - `due_at` â†’ parsed machine-readable datetime
- âœ… Smarter listing: orders by `done`, then earliest `due_at`
- âœ… Robust extraction: if the model passes only a single string (e.g., â€œbuy milk tomorrow 5pmâ€), the agent **auto-extracts** the due phrase from the title

> TL;DR â€” The agent now *understands time*, not just text.

---

## ðŸ§© Architecture snapshot


- The **Responses API** still chooses which tool to call.
- Python functions act as â€œtoolsâ€.
- SQLite is the persistent memory.
- Level 2 adds **date parsing** before writing to DB.

---

## ðŸ“¦ Requirements

Inside this projectâ€™s own virtual environment:

```bash
pip install openai dateparser pytz

Timezone

setx AGENT_TIMEZONE "America/Denver"

ðŸ—„ï¸ Database schema (Level 2)

| column     | type    | description                        |
| ---------- | ------- | ---------------------------------- |
| id         | INTEGER | primary key                        |
| title      | TEXT    | task title                         |
| due        | TEXT    | original natural-language due text |
| due_at     | TEXT    | parsed ISO8601 datetime (TZ aware) |
| done       | INTEGER | 0/1                                |
| created_at | TEXT    | timestamp when task was created    |

â–¶ï¸ Run

python agent_todo.py

add buy milk tomorrow 5pm
add dentist appointment next Monday 8am
list my tasks
complete task 1


ASSISTANT:
Added task #12: buy milk (due: Tue, Oct 21 05:00 PM).

#12 â€” buy milk (due: Tue, Oct 21 05:00 PM)
#11 â€” dentist appointment (due: Mon, Oct 27 08:00 AM)


ðŸ”Ž Verify parsing in the DB (optional)

PRAGMA table_info(tasks);

SELECT id, title, due, due_at, done
FROM tasks
ORDER BY done,
         CASE WHEN due_at IS NULL THEN 1 ELSE 0 END,
         due_at ASC,
         id DESC;

