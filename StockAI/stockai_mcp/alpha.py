from __future__ import annotations

import datetime as dt
import os
from typing import Any, Dict

import requests


def _iso(ts: dt.datetime) -> str:
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=dt.timezone.utc)
    return ts.isoformat()


def fetch_quote(symbol: str, currency: str = "USD") -> Dict[str, Any]:
    apikey = os.getenv("ALPHAVANTAGE_API_KEY")
    if not apikey:
        return {"symbol": symbol.upper(), "price": None, "currency": currency, "as_of": _iso(dt.datetime.now(dt.timezone.utc)), "provider": "alpha_vantage", "error": "Missing ALPHAVANTAGE_API_KEY"}

    params = {
        "function": "GLOBAL_QUOTE",
        "symbol": symbol,
        "apikey": apikey,
    }

    proxies = {
        "http": os.getenv("HTTP_PROXY") or os.getenv("http_proxy"),
        "https": os.getenv("HTTPS_PROXY") or os.getenv("https_proxy"),
    }
    verify: Any = True
    ca_hint = os.getenv("REQUESTS_CA_BUNDLE") or os.getenv("SSL_CERT_FILE")
    if ca_hint:
        verify = ca_hint
    if (os.getenv("YF_VERIFY") or "").lower() in {"0", "false", "no"}:
        verify = False

    url = "https://www.alphavantage.co/query"
    try:
        r = requests.get(url, params=params, timeout=10, proxies=proxies, verify=verify)
        r.raise_for_status()
        data = r.json()
        # Handle API throttling or errors
        if isinstance(data, dict) and (data.get("Note") or data.get("Error Message")):
            msg = data.get("Note") or data.get("Error Message")
            return {
                "symbol": symbol.upper(),
                "price": None,
                "currency": currency,
                "as_of": _iso(dt.datetime.now(dt.timezone.utc)),
                "provider": "alpha_vantage",
                "error": msg,
            }

        quote = data.get("Global Quote") or data.get("globalQuote") or {}
        price_s = quote.get("05. price") or quote.get("price")
        price = float(price_s.replace(",", "")) if price_s else None
        day = quote.get("07. latest trading day")
        as_of = None
        if day:
            try:
                as_of = dt.datetime.fromisoformat(day).replace(tzinfo=dt.timezone.utc)
            except Exception:
                as_of = dt.datetime.now(dt.timezone.utc)
        # Sanity: reject implausible prices which might actually be volume
        if price is not None and price > 100000:
            return {
                "symbol": symbol.upper(),
                "price": None,
                "currency": currency,
                "as_of": _iso(as_of or dt.datetime.now(dt.timezone.utc)),
                "provider": "alpha_vantage",
                "error": f"implausible price {price}",
            }
        return {
            "symbol": symbol.upper(),
            "price": price,
            "currency": currency,
            "as_of": _iso(as_of or dt.datetime.now(dt.timezone.utc)),
            "provider": "alpha_vantage",
        }
    except Exception as e:
        return {
            "symbol": symbol.upper(),
            "price": None,
            "currency": currency,
            "as_of": _iso(dt.datetime.now(dt.timezone.utc)),
            "provider": "alpha_vantage",
            "error": str(e),
        }
