# StockAI MCP Server (Python)

A Model Context Protocol (MCP) stdio server exposing stock tools backed by Yahoo Finance (`yfinance`).

## Tools
- `get_stock_price(symbol, currency="USD", provider?="alpha|stooq|yahoo")` — current quote snapshot. Defaults to Alpha Vantage with Stooq fallback.
- `get_historical_prices(symbol, start_date, end_date, interval="1d")` — OHLCV series.
- `get_company_profile(symbol)` — basic company fundamentals.

## Resources
- Template: `stock://{symbol}` — current quote as JSON text.
- Template: `stock-history://{symbol}?start={YYYY-MM-DD}&end={YYYY-MM-DD}&interval={1d|1wk|1mo|1h|30m|15m|5m|1m}` — historical prices.

## Setup

- Python 3.10+
- Install dependencies:

```
pip install -r requirements.txt
```

### Provider and API key

- Default provider: Alpha Vantage (near real-time). Set `ALPHAVANTAGE_API_KEY` in your environment.
- Fallback provider: Stooq (latest close, no key).
- Optional: set `STOCKAI_PROVIDER` to `alpha`, `stooq`, or `yahoo`.
- Optional: set `STOCKAI_ENABLE_YAHOO_FALLBACK=1` to allow Yahoo as a last resort.

## Run (stdio)

Launch the server so an MCP-capable client can connect via stdio:

```
python -m stockai_mcp.server
```

The process waits on stdio, advertising tools and resources to the client.

## Example MCP Client Config (pseudo)

Configure your agent to spawn this server as a stdio MCP server. Example shape:

```json
{
  "mcpServers": {
    "stockai": {
      "command": "python",
      "args": ["-m", "stockai_mcp.server"],
      "env": {}
    }
  }
}
```

## Notes
- Yahoo Finance data via `yfinance` may vary by market hours and availability.
- `get_stock_price` prefers minute-level history for recency and falls back to market price fields.
- Resource reads return JSON as text content; tool calls return JSON-encoded text as well.
