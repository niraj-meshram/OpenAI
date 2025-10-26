# interactive_cli.py
import sys
from agents import Runner, SQLiteSession    # <-- add SQLiteSession
from weather_agent import weather_agent

BANNER = """Weather CLI
Type a city (e.g., "Phoenix" or "Phoenix tomorrow").
Say "trend", "past 6", or "next 6" to see 6-month history/outlook.
Commands: :q to quit, :h for help.
"""

HELP = """Examples:
  Phoenix
  Phoenix tomorrow
  Salt Lake City trend
  San Diego past 6 and next 6
Commands:
  :q        quit
  :h        help
"""

def main():
    print(BANNER)
    session = SQLiteSession("weather-cli-session")   # <-- create a session
    while True:
        try:
            line = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nbye!")
            break

        if not line:
            continue
        if line in (":q", ":quit", ":exit"):
            print("bye!")
            break
        if line in (":h", ":help"):
            print(HELP)
            continue

        low = line.lower()
        query = line
        if any(k in low for k in ["trend", "history", "past 6", "next 6"]):
            city = line
            for k in ["trend", "history", "past 6", "next 6", "and"]:
                city = city.replace(k, "").replace(k.title(), "")
            city = city.strip(",;: ").strip()
            if not city:
                city = line.strip()
            query = f"{city} 6 month weather history and outlook"
        elif "weather" not in low:
            query = f"weather in {line}"

        try:
            result = Runner.run_sync(weather_agent, query, session=session)  # <-- pass session
            print(result.final_output)
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)

if __name__ == "__main__":
    main()
