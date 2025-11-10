from __future__ import annotations

import datetime as dt
import os
from typing import Any, Dict, List

import requests


def _iso(ts: dt.datetime) -> str:
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=dt.timezone.utc)
    return ts.isoformat()


def fetch_quote(symbol: str, currency: str = "USD") -> Dict[str, Any]:
    sym = symbol.lower()
    symbols_to_try = [sym]
    if "." not in sym and not sym.endswith(".us"):
        symbols_to_try.append(f"{sym}.us")

    urls: List[str] = []
    for s in symbols_to_try:
        urls.extend([
            # Prefer JSON to avoid CSV parsing ambiguities
            f"https://stooq.com/q/l/?s={s}&i=d&o=json",
            f"http://stooq.com/q/l/?s={s}&i=d&o=json",
            f"https://stooq.com/q/l/?s={s}&i=d",
            f"http://stooq.com/q/l/?s={s}&i=d",
        ])

    # Honor proxies and optional cert bundle for HTTPS fallback
    proxies = {
        "http": os.getenv("HTTP_PROXY") or os.getenv("http_proxy"),
        "https": os.getenv("HTTPS_PROXY") or os.getenv("https_proxy"),
    }
    verify: Any = True
    ca_hint = os.getenv("REQUESTS_CA_BUNDLE") or os.getenv("SSL_CERT_FILE")
    if ca_hint:
        verify = ca_hint
    verify_env = os.getenv("YF_VERIFY")
    if verify_env is not None and str(verify_env).lower() in {"0", "false", "no"}:
        verify = False

    last_error: str | None = None
    for url in urls:
        try:
            r = requests.get(url, timeout=8, proxies=proxies, verify=verify)
            r.raise_for_status()
            ctype = (r.headers.get("Content-Type") or "").lower()
            if "json" in ctype or (r.text.strip().startswith("[") or r.text.strip().startswith("{")):
                try:
                    data = r.json()
                except Exception:
                    last_error = "invalid json"
                    continue
                arr = data if isinstance(data, list) else data.get("data") or []
                if not arr:
                    last_error = "empty json"
                    continue
                item = arr[0]
                price_s = item.get("close") or item.get("c")
                price = float(price_s) if price_s not in (None, "", "-") else None
                d_s = item.get("date") or item.get("d")
                t_s = item.get("time") or item.get("t")
                try:
                    if d_s and t_s:
                        as_of = dt.datetime.fromisoformat(f"{d_s}T{t_s}Z").replace(tzinfo=dt.timezone.utc)
                    elif d_s:
                        as_of = dt.datetime.fromisoformat(d_s).replace(tzinfo=dt.timezone.utc)
                    else:
                        as_of = dt.datetime.now(dt.timezone.utc)
                except Exception:
                    as_of = dt.datetime.now(dt.timezone.utc)
            else:
                # CSV fallback
                text = r.text.strip()
                if not text:
                    last_error = "empty response"
                    continue
                # Use first non-header, non-empty line
                line = next((ln for ln in text.splitlines() if ln and not ln.lower().startswith("symbol")), None)
                if not line:
                    last_error = "no data line"
                    continue
                # Split by comma or semicolon and strip quotes
                raw_parts = [p.strip().strip('"') for p in line.replace(";", ",").split(",")]
                # Heuristics: close should be the second-to-last numeric before volume
                price = None
                as_of = None
                # Try 8-column format first
                if len(raw_parts) >= 8:
                    try:
                        price = float(raw_parts[6])
                    except Exception:
                        price = None
                    try:
                        d_s, t_s = raw_parts[1], raw_parts[2]
                        as_of = dt.datetime.fromisoformat(f"{d_s}T{t_s}Z").replace(tzinfo=dt.timezone.utc)
                    except Exception:
                        as_of = dt.datetime.now(dt.timezone.utc)
                # Fallback: try last numeric before last field
                if price is None:
                    nums = []
                    for p in raw_parts[:-1]:
                        try:
                            nums.append(float(p))
                        except Exception:
                            nums.append(None)
                    for val in reversed(nums):
                        if isinstance(val, float):
                            price = val
                            break
                    as_of = as_of or dt.datetime.now(dt.timezone.utc)

            return {
                "symbol": symbol.upper(),
                "price": price,
                "currency": currency,
                "as_of": _iso(as_of or dt.datetime.now(dt.timezone.utc)),
                "provider": "stooq",
            }
        except Exception as e:
            last_error = str(e)
            continue

    return {
        "symbol": symbol.upper(),
        "price": None,
        "currency": currency,
        "as_of": _iso(dt.datetime.now(dt.timezone.utc)),
        "provider": "stooq",
        "error": last_error or "stooq: fetch failed",
    }
