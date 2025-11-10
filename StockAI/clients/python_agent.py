import os
import json
import sys
from typing import Any, Dict

from openai import OpenAI

# Ensure repository root is on sys.path when running directly
_HERE = os.path.dirname(__file__)
_ROOT = os.path.abspath(os.path.join(_HERE, ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from stockai_mcp.yahoo import fetch_quote, fetch_history, fetch_profile


TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_stock_price",
            "description": "Fetches current stock quote (last close/real-time when available).",
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {"type": "string"},
                    "currency": {"type": "string", "default": "USD"},
                },
                "required": ["symbol"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_historical_prices",
            "description": "Fetch OHLCV time series for a symbol between dates.",
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {"type": "string"},
                    "start_date": {"type": "string", "pattern": "^\\d{4}-\\d{2}-\\d{2}$"},
                    "end_date": {"type": "string", "pattern": "^\\d{4}-\\d{2}-\\d{2}$"},
                    "interval": {
                        "type": "string",
                        "enum": ["1d", "1wk", "1mo", "1h", "30m", "15m", "5m", "1m"],
                        "default": "1d",
                    },
                },
                "required": ["symbol", "start_date", "end_date"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_company_profile",
            "description": "Fetch basic company profile information.",
            "parameters": {
                "type": "object",
                "properties": {"symbol": {"type": "string"}},
                "required": ["symbol"],
            },
        },
    },
]


def dispatch_tool(name: str, args: Dict[str, Any]) -> Any:
    if name == "get_stock_price":
        return fetch_quote(args["symbol"], args.get("currency", "USD"))
    if name == "get_historical_prices":
        return fetch_history(
            args["symbol"], args["start_date"], args["end_date"], args.get("interval", "1d")
        )
    if name == "get_company_profile":
        return fetch_profile(args["symbol"])
    raise ValueError(f"Unknown tool: {name}")


def chat_once(prompt: str, model: str = None) -> str:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("Set OPENAI_API_KEY in your environment")

    client = OpenAI()
    model = model or os.environ.get("OPENAI_MODEL", "gpt-4o-mini")

    messages = [
        {"role": "system", "content": "You are a helpful financial assistant. Use tools when helpful."},
        {"role": "user", "content": prompt},
    ]

    while True:
        resp = client.chat.completions.create(
            model=model,
            messages=messages,
            tools=TOOLS,
            tool_choice="auto",
        )

        msg = resp.choices[0].message
        tool_calls = msg.tool_calls or []

        if not tool_calls:
            return msg.content or ""

        # Append the assistant's tool call message first
        messages.append({
            "role": "assistant",
            "content": msg.content or "",
            "tool_calls": [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                }
                for tc in tool_calls
            ],
        })

        # Execute each tool call and add tool results
        for tc in tool_calls:
            name = tc.function.name
            try:
                args = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}
            try:
                result = dispatch_tool(name, args)
                content = json.dumps(result)
            except Exception as e:
                content = json.dumps({"error": str(e)})

            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "name": name,
                "content": content,
            })


def main() -> None:
    if len(sys.argv) > 1:
        prompt = " ".join(sys.argv[1:])
        print(chat_once(prompt))
        return

    print("StockAI Agent — type your query, Ctrl+C to exit")
    while True:
        try:
            prompt = input("you> ").strip()
            if not prompt:
                continue
            answer = chat_once(prompt)
            print("assistant>", answer)
        except KeyboardInterrupt:
            print()  # newline
            break


if __name__ == "__main__":
    main()
