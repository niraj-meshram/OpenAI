# file: background.py
import time
from agents import Agent, Runner, background_task

@background_task
def refresh_cache():
    # pretend work
    time.sleep(1)
    return "refreshed"

agent = Agent(
    name="Weather with Background",
    instructions="After answering, schedule refresh_cache in background.",
    tools=[get_forecast],
    background_tasks=[refresh_cache],
)

if __name__ == "__main__":
    res = Runner.run(agent, "Weather in Denver today?")
    print(res.output_text)
