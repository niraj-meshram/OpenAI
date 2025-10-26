# file: session_state.py
from agents import Agent, Runner

agent = Agent(
    name="Concierge",
    instructions="Remember prior cities in this session unless user says 'new city'."
)

session = "user-123-session-1"
print(Runner.run(agent, "I'm in SLC today.", session_id=session).output_text)
print(Runner.run(agent, "What about tomorrow?", session_id=session).output_text)
