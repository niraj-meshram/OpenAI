from __future__ import annotations

import asyncio
import os
import json
from typing import Any, Dict, List
from urllib.parse import urlparse, parse_qs

from .yahoo import fetch_history, fetch_profile, fetch_quote as fetch_quote_yahoo
from .alpha import fetch_quote as fetch_quote_alpha
from .stooq import fetch_quote as fetch_quote_stooq


try:
    # Preferred import path in current SDKs
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    from mcp.types import Tool, TextContent, Resource, ResourceTemplate
except Exception:  # pragma: no cover - fallback for older/newer SDKs
    from mcp.server import Server  # type: ignore
    from mcp.transport.stdio import stdio_server  # type: ignore
    from mcp.types import Tool, TextContent, Resource, ResourceTemplate  # type: ignore


server = Server("stockai")


def _tool_defs() -> List[Dict[str, Any]]:
    return [
        {
            "name": "get_stock_price",
            "description": "Fetches current stock quote. Defaults to Alpha Vantage with Stooq fallback.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "symbol": {"type": "string"},
                    "currency": {"type": "string", "default": "USD"},
                    "provider": {"type": "string", "enum": ["alpha", "stooq", "yahoo"]},
                },
                "required": ["symbol"],
            },
        },
        {
            "name": "get_historical_prices",
            "description": "Fetch OHLCV time series for a symbol between dates.",
            "inputSchema": {
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
        {
            "name": "get_company_profile",
            "description": "Fetch basic company profile information.",
            "inputSchema": {
                "type": "object",
                "properties": {"symbol": {"type": "string"}},
                "required": ["symbol"],
            },
        },
    ]


@server.list_tools()
async def list_tools() -> List[Tool]:  # type: ignore[override]
    # The SDK will coerce dicts -> Tool models
    return _tool_defs()  # type: ignore[return-value]


@server.call_tool()
async def call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:  # type: ignore[override]
    try:
        if name == "get_stock_price":
            symbol = str(arguments["symbol"]).strip()
            currency = str(arguments.get("currency", "USD"))
            provider = arguments.get("provider")
            # basic ticker validation
            if not symbol or len(symbol) > 10 or not symbol.replace("-", "").replace(".", "").isalnum():
                return [TextContent(type="text", text=json.dumps({"error": f"Invalid ticker '{symbol}'"}))]  # type: ignore[arg-type]
            payload = _price_with_fallback(symbol, currency, provider)
            return [TextContent(type="text", text=json.dumps(payload))]  # type: ignore[arg-type]

        if name == "get_historical_prices":
            symbol = str(arguments["symbol"]).strip()
            start_date = str(arguments["start_date"]).strip()
            end_date = str(arguments["end_date"]).strip()
            interval = str(arguments.get("interval", "1d")).strip()
            payload = fetch_history(symbol, start_date, end_date, interval)
            return [TextContent(type="text", text=json.dumps(payload))]  # type: ignore[arg-type]

        if name == "get_company_profile":
            symbol = str(arguments["symbol"]).strip()
            payload = fetch_profile(symbol)
            return [TextContent(type="text", text=json.dumps(payload))]  # type: ignore[arg-type]

        return [TextContent(type="text", text=f"Unknown tool: {name}")]  # type: ignore[arg-type]
    except KeyError as e:
        return [TextContent(type="text", text=f"Missing argument: {e}")]  # type: ignore[arg-type]
    except Exception as e:  # defensive: surface errors to client
        return [TextContent(type="text", text=f"Error: {e}")]  # type: ignore[arg-type]


@server.list_resources()
async def list_resources() -> List[Resource]:  # type: ignore[override]
    # No static resources; all are via templates
    return []


@server.list_resource_templates()
async def list_resource_templates() -> List[ResourceTemplate]:  # type: ignore[override]
    return [
        ResourceTemplate(
            uriTemplate="stock://{symbol}",
            name="Stock Snapshot",
            description="Current quote for a symbol",
        ),
        ResourceTemplate(
            uriTemplate="stock-history://{symbol}?start={start}&end={end}&interval={interval}",
            name="Historical Prices",
            description="OHLCV time series for a symbol",
        ),
    ]


@server.read_resource()
async def read_resource(uri: str):  # type: ignore[override]
    parsed = urlparse(uri)
    scheme = parsed.scheme
    symbol = (parsed.netloc or parsed.path).strip("/")

    if not symbol:
        return [TextContent(type="text", text="Missing symbol in URI")]  # type: ignore[arg-type]

    if scheme == "stock":
        payload = _price_with_fallback(symbol, "USD", None)
        return [TextContent(type="text", text=json.dumps(payload))]  # type: ignore[arg-type]

    if scheme == "stock-history":
        qs = parse_qs(parsed.query)
        start = (qs.get("start", [""])[0] or "").strip()
        end = (qs.get("end", [""])[0] or "").strip()
        interval = (qs.get("interval", ["1d"])[0] or "1d").strip()
        if not start or not end:
            return [TextContent(type="text", text="start and end query params are required")]  # type: ignore[arg-type]
        payload = fetch_history(symbol, start, end, interval)
        return [TextContent(type="text", text=json.dumps(payload))]  # type: ignore[arg-type]

    return [TextContent(type="text", text=f"Unsupported resource scheme: {scheme}")]  # type: ignore[arg-type]


def _price_with_fallback(symbol: str, currency: str, provider: str | None) -> Dict[str, Any]:
    prov = (provider or os.getenv("STOCKAI_PROVIDER") or "alpha").lower()
    enable_yahoo_fb = str(os.getenv("STOCKAI_ENABLE_YAHOO_FALLBACK") or "0").lower() in {"1", "true", "yes", "on"}

    def ensure_provider(p: Dict[str, Any], name: str) -> Dict[str, Any]:
        if isinstance(p, dict) and "provider" not in p:
            p["provider"] = name
        return p

    try_order: List[str]
    if prov == "yahoo":
        try_order = ["yahoo"]
    elif prov == "stooq":
        try_order = ["stooq"]
    else:
        try_order = ["alpha", "stooq"]
        if enable_yahoo_fb:
            try_order.append("yahoo")

    last: Dict[str, Any] | None = None
    for p in try_order:
        if p == "alpha":
            if not os.getenv("ALPHAVANTAGE_API_KEY"):
                continue
            res = ensure_provider(fetch_quote_alpha(symbol, currency), "alpha_vantage")
        elif p == "stooq":
            res = ensure_provider(fetch_quote_stooq(symbol, currency), "stooq")
        else:
            res = ensure_provider(fetch_quote_yahoo(symbol, currency), "yahoo")

        last = res
        if isinstance(res, dict) and res.get("price") is not None:
            return res

    return last or {"symbol": symbol.upper(), "price": None, "currency": currency, "as_of": None}


async def amain() -> None:
    async with stdio_server() as (rx, tx):
        # Newer MCP SDKs require initialization_options
        try:
            await server.run(rx, tx, initialization_options={})
        except TypeError:
            # Backward compatibility with older signatures
            await server.run(rx, tx)


def main() -> None:
    asyncio.run(amain())


if __name__ == "__main__":
    main()
