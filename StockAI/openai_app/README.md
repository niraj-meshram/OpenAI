# OpenAI App MCP Client

This config lets the OpenAI desktop app connect to your StockAI MCP server via stdio.

## Files
- `openai_app/mcp.json`:1 — declares the `stockai` MCP server.

## Use in OpenAI App
- Open the app’s MCP settings and add a new server using:
  - Command: `python`
  - Args: `-m stockai_mcp.server`
  - Transport: `stdio`
  - Env: leave empty (or set proxies if needed)
- Alternatively, merge the JSON in `openai_app/mcp.json`:1 into your app MCP config if the app supports importing a JSON config.

## Verify
- Start a new chat and ask something that requires the tool, e.g.:
  - “What’s the current price of AAPL? Use the StockAI tool.”
  - “Fetch MSFT historical prices from 2025-01-01 to 2025-02-01.”
- The app should auto-discover the MCP tools and call them.

## Troubleshooting
- Ensure dependencies are installed in the same Python that the app launches: `pip install -r requirements.txt`.
- On Windows, if multiple Python installations exist, consider an absolute `command` path (e.g., `C:\\Python312\\python.exe`).
- If corporate proxy blocks Yahoo, set `HTTP_PROXY`/`HTTPS_PROXY` in the MCP server `env` section.

