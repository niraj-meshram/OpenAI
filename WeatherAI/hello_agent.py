# file: hello_agent.py
import asyncio
from agents import Agent, Runner

greeter = Agent(
    name="Greeter",
    instructions="Be warm and brief. If user gives a name, greet them by it."
)

async def main():
    out = await Runner.run(greeter, "Hi, I'm Niraj")
    print(out.final_output)  # ← use final_output (string when no output_type)

if __name__ == "__main__":
    asyncio.run(main())
