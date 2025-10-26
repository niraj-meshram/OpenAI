# file: handoff_example.py
from agents import Agent, Runner, Handoff

smalltalk = Agent(
    name="SmallTalk",
    instructions="Friendly chit-chat. Keep replies under 2 sentences."
)

weather = Agent(
    name="Weather",
    instructions=(
        "If the user asks about weather, answer. "
        "If not weather-related, hand off to SmallTalk."
    ),
    tools=[get_forecast],  # reuse from previous file
    handoffs=[
        Handoff(
            to=smalltalk,
            description="Use for non-weather questions."
        )
    ],
)

if __name__ == "__main__":
    print(Runner.run(weather, "How's your day?").output_text)
