import argparse
from agents import Runner
from weather_ai.agents.weather_agent import weather_agent


def main():
    ap = argparse.ArgumentParser(description="WeatherAI CLI")
    ap.add_argument("query", nargs="+")
    args = ap.parse_args()
    user_text = " ".join(args.query)

    # Run synchronously for convenience
    result = Runner.run_sync(weather_agent, user_text)
    print(result.final_output)


if __name__ == "__main__":
    main()

