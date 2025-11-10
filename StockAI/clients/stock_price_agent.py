import os
import sys
import json
import argparse
import time
import re
from typing import Any, Dict, Optional

from openai import OpenAI

# Ensure repository root is on sys.path when running directly
_HERE = os.path.dirname(__file__)
_ROOT = os.path.abspath(os.path.join(_HERE, ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from stockai_mcp.yahoo import fetch_quote as fetch_quote_yahoo
from stockai_mcp.stooq import fetch_quote as fetch_quote_stooq
from stockai_mcp.alpha import fetch_quote as fetch_quote_alpha


# Single tool the model can call
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_stock_price",
            "description": "Return the latest available price for a stock symbol.",
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {"type": "string", "description": "Ticker symbol, e.g., AAPL"},
                    "currency": {"type": "string", "default": "USD"},
                },
                "required": ["symbol"],
            },
        },
    }
]


def _select_provider() -> str:
    return os.getenv("STOCKAI_PROVIDER", "alpha").lower()


def _has_alpha_key() -> bool:
    return bool(os.getenv("ALPHAVANTAGE_API_KEY"))


_TICKER_RE = re.compile(r"^[A-Z][A-Z0-9\.\-]{0,9}$")
_TICKER_STOP = {"USD", "PRICE", "STOCK", "OF", "GET", "SHOW", "PLEASE", "TICKER"}


def _valid_ticker(symbol: str) -> bool:
    return bool(_TICKER_RE.match(symbol))


def _extract_ticker(text: str) -> Optional[str]:
    candidates = re.findall(r"\b[A-Z][A-Z0-9\.\-]{0,9}\b", text.upper())
    for tok in candidates:
        if tok in _TICKER_STOP:
            continue
        if _valid_ticker(tok):
            return tok
    return None


def _moderate(client: OpenAI, text: str) -> bool:
    try:
        m = client.moderations.create(model="omni-moderation-latest", input=text)
        return bool(m.results[0].flagged)
    except Exception:
        return False


def _classify_intent(client: OpenAI, text: str) -> str:
    sys_prompt = (
        "You are an intent classifier. Return one of: price, history, profile, other. "
        "If the user asks for current, latest or real-time stock value or quote, return 'price'."
    )
    msg = [
        {"role": "system", "content": sys_prompt},
        {"role": "user", "content": text},
    ]
    try:
        r = client.chat.completions.create(model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"), messages=msg, temperature=0)
        out = (r.choices[0].message.content or "price").strip().lower()
        return out if out in {"price", "history", "profile", "other"} else "price"
    except Exception:
        return "price"


def call_tool(name: str, args: Dict[str, Any]) -> Any:
    if name == "get_stock_price":
        symbol = str(args["symbol"]).strip().upper()
        currency = str(args.get("currency", "USD"))
        if not _valid_ticker(symbol):
            return {"error": f"Invalid ticker '{symbol}'. Use A-Z, digits, . or - (max 10)."}

        provider = _select_provider()

        def _try(func, *fargs, **fkwargs):
            last = None
            for i in range(3):
                try:
                    res = func(*fargs, **fkwargs)
                    if isinstance(res, dict) and res.get("price") is not None:
                        return res
                    last = res
                except Exception as e:
                    last = {"error": str(e)}
                if i < 2:
                    time.sleep(0.3 * (i + 1))
            return last or {"error": "provider failure"}

        if provider == "yahoo":
            return _try(fetch_quote_yahoo, symbol, currency)
        if provider == "stooq":
            return _try(fetch_quote_stooq, symbol, currency)

        # Default and preferred: Alpha (if key present) with Stooq fallback
        primary = None
        if _has_alpha_key():
            primary = _try(fetch_quote_alpha, symbol, currency)
            if isinstance(primary, dict) and primary.get("price") is not None:
                return primary
        fallback = _try(fetch_quote_stooq, symbol, currency)
        if isinstance(fallback, dict) and fallback.get("price") is not None:
            return fallback
        return primary if primary is not None else fallback
    raise ValueError(f"Unknown tool: {name}")


def answer(prompt: str, model: str | None = None) -> str:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("Set OPENAI_API_KEY environment variable")

    client = OpenAI()
    model = model or os.environ.get("OPENAI_MODEL", "gpt-4o-mini")

    # Strong instruction: always return price; ask for symbol if missing.
    system = (
        "You are a precise stock price agent. "
        "If the user provides a ticker symbol, call get_stock_price and respond with a concise answer like "
        "'AAPL — $183.40 USD as of 2025-11-09T16:00Z'. "
        "If no symbol is provided, ask them to specify the ticker."
    )

    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": prompt},
    ]

    # Guardrail: pre-moderation
    if _moderate(client, prompt):
        return "Sorry, I can't help with that request."

    # Intent classification
    intent = _classify_intent(client, prompt)
    if intent != "price":
        return "I currently support stock price queries. Try 'AAPL price'."

    # Try direct tool call if we can confidently extract a ticker
    ticker = _extract_ticker(prompt)
    if ticker:
        direct = call_tool("get_stock_price", {"symbol": ticker})
        if isinstance(direct, dict):
            sym = direct.get("symbol", ticker)
            ccy = direct.get("currency", "USD")
            as_of = direct.get("as_of", "")
            price_val = direct.get("price")
            if price_val is None:
                return f"{sym} — price unavailable as of {as_of}"
            try:
                price_f = float(price_val)
                price_str = f"{price_f:,.2f}"
            except Exception:
                price_str = str(price_val)
            text = f"{sym} — ${price_str} {ccy} as of {as_of}"
            if _moderate(client, text):
                return "Sorry, I can't share that result."
            return text
        # If not a dict or no price, fall through to LLM tool invocation

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
            # Either a question asking for the symbol, or final text
            return msg.content or ""

        # Record assistant tool call
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

        # Execute tool(s) and send results back
        for tc in tool_calls:
            name = tc.function.name
            try:
                args = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}
            try:
                result = call_tool(name, args)
                content = json.dumps(result)
            except Exception as e:
                content = json.dumps({"error": str(e)})

            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "name": name,
                "content": content,
            })

        # Short-circuit: format a concise answer directly from the tool result
        try:
            last = json.loads(content)
            if isinstance(last, dict):
                sym = last.get("symbol") or args.get("symbol")
                ccy = last.get("currency", "USD")
                as_of = last.get("as_of", "")
                price = last.get("price")
                if price is None:
                    return f"{sym} — price unavailable as of {as_of}"
                try:
                    price_f = float(price)
                    price_str = f"{price_f:,.2f}"
                except Exception:
                    price_str = str(price)
                text = f"{sym} — ${price_str} {ccy} as of {as_of}"
                if _moderate(client, text):
                    return "Sorry, I can't share that result."
                return text
        except Exception:
            pass


def main() -> None:
    parser = argparse.ArgumentParser(prog="stock_price_agent", description="OpenAI SDK agent for stock prices")
    parser.add_argument("prompt", nargs="*", help="Prompt to ask the agent (default: interactive mode)")
    parser.add_argument("--model", default=None, help="OpenAI model (default: env OPENAI_MODEL or gpt-4o-mini)")
    parser.add_argument("--debug", action="store_true", help="Enable diagnostics (sets STOCKAI_DEBUG=1)")
    parser.add_argument("--force-direct", action="store_true", help="Bypass yfinance and use direct Yahoo JSON endpoint (Yahoo provider only)")
    parser.add_argument("--insecure", action="store_true", help="Disable SSL verification for direct path (temporary; Yahoo provider only)")
    parser.add_argument("--provider", choices=["stooq", "yahoo", "alpha"], default=None, help="Data provider to use (default: alpha; falls back to stooq)")
    parser.add_argument("--apikey", default=None, help="Provider API key (Alpha Vantage)")
    args = parser.parse_args()

    if args.debug:
        os.environ["STOCKAI_DEBUG"] = "1"
    if args.force_direct:
        os.environ["STOCKAI_FORCE_DIRECT"] = "1"
    if args.insecure:
        os.environ["YF_VERIFY"] = "false"

    if args.provider:
        os.environ["STOCKAI_PROVIDER"] = args.provider
    if args.apikey:
        os.environ["ALPHAVANTAGE_API_KEY"] = args.apikey

    if args.prompt:
        prompt = " ".join(args.prompt)
        print(answer(prompt, model=args.model))
        return

    print("Stock Price Agent — ask for a ticker (Ctrl+C to exit)")
    while True:
        try:
            q = input("you> ").strip()
            if not q:
                continue
            print("assistant>", answer(q, model=args.model))
        except KeyboardInterrupt:
            print()
            break


if __name__ == "__main__":
    main()

