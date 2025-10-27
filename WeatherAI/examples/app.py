# app.py
import argparse
import asyncio
from agents import Runner
from weather_agent import weather_agent

async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("query", nargs="+")
    args = ap.parse_args()
    user_text = " ".join(args.query)

    result = await Runner.run(weather_agent, user_text)
    print(result.final_output)

if __name__ == "__main__":
    asyncio.run(main())
