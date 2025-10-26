# file: guardrails.py
from agents import Agent, InputGuardrail, Runner

block_sensitive = InputGuardrail(
    name="NoMedFin",
    instructions=(
        "If the user asks for medical or financial advice, trip the guardrail."
    )
)

safe_agent = Agent(
    name="Safe Weather",
    instructions="Answer weather only. Be concise.",
    tools=[get_forecast],
    input_guardrails=[block_sensitive],
)

if __name__ == "__main__":
    print(Runner.run(safe_agent, "Best injection schedule for AMD?"))  # will trip
