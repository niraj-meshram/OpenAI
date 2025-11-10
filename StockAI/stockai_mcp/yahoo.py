from __future__ import annotations

import datetime as dt
import os
from typing import Any, Dict, List, Optional

import requests
import yfinance as yf
try:
    import certifi_win32  # type: ignore  # patches Requests to use Windows cert store
except Exception:
    certifi_win32 = None  # not required


def _iso(dtobj: dt.datetime) -> str:
    if dtobj.tzinfo is None:
        return dtobj.replace(tzinfo=dt.timezone.utc).isoformat()
    return dtobj.isoformat()


def _debug_enabled() -> bool:
    val = os.getenv("STOCKAI_DEBUG")
    if val is None:
        return False
    return str(val).strip().lower() in {"1", "true", "yes", "on"}


def _prepare_network_env() -> None:
    """Ensure env variables are set for curl-based yfinance backend."""
    ca_hint = os.getenv("YF_CA_BUNDLE") or os.getenv("REQUESTS_CA_BUNDLE") or os.getenv("SSL_CERT_FILE")
    if ca_hint and not os.getenv("CURL_CA_BUNDLE"):
        os.environ["CURL_CA_BUNDLE"] = ca_hint
    # Mirror proxies to lowercase env for libcurl if needed
    if os.getenv("HTTP_PROXY") and not os.getenv("http_proxy"):
        os.environ["http_proxy"] = os.environ["HTTP_PROXY"]
    if os.getenv("HTTPS_PROXY") and not os.getenv("https_proxy"):
        os.environ["https_proxy"] = os.environ["HTTPS_PROXY"]


def _make_session() -> requests.Session:
    s = requests.Session()
    # Honor corporate CA bundle for direct Requests fallback
    ca_hint = os.getenv("YF_CA_BUNDLE") or os.getenv("REQUESTS_CA_BUNDLE") or os.getenv("SSL_CERT_FILE")
    # Corporate CA bundle
    ca_bundle = ca_hint
    if ca_bundle:
        s.verify = ca_bundle
    else:
        verify_env = os.getenv("YF_VERIFY")
        if verify_env is not None and str(verify_env).lower() in {"0", "false", "no"}:
            s.verify = False  # last-resort workaround; insecure

    http_proxy = os.getenv("HTTP_PROXY") or os.getenv("http_proxy")
    https_proxy = os.getenv("HTTPS_PROXY") or os.getenv("https_proxy")
    if http_proxy or https_proxy:
        s.proxies.update({"http": http_proxy, "https": https_proxy})
    return s


def fetch_quote(symbol: str, currency: str = "USD") -> Dict[str, Any]:
    _prepare_network_env()
    # Optional: force direct Yahoo JSON endpoint, skipping yfinance (helps in restricted networks)
    force_direct_env = os.getenv("STOCKAI_FORCE_DIRECT") or os.getenv("YF_FORCE_DIRECT")
    force_direct = str(force_direct_env).strip().lower() in {"1", "true", "yes", "on"}
    if force_direct:
        try:
            direct = _direct_quote(symbol, _make_session())
            price = direct.get("price")
            as_of = direct.get("as_of")
            curr2 = direct.get("currency") or currency
            result = {
                "symbol": symbol.upper(),
                "price": price,
                "currency": curr2,
                "as_of": _iso(as_of or dt.datetime.now(dt.timezone.utc)),
            }
            if _debug_enabled():
                result["debug"] = {
                    "used": "direct (forced)",
                    "env": {
                        "REQUESTS_CA_BUNDLE": os.getenv("REQUESTS_CA_BUNDLE"),
                        "SSL_CERT_FILE": os.getenv("SSL_CERT_FILE"),
                        "CURL_CA_BUNDLE": os.getenv("CURL_CA_BUNDLE"),
                        "HTTP_PROXY": os.getenv("HTTP_PROXY") or os.getenv("http_proxy"),
                        "HTTPS_PROXY": os.getenv("HTTPS_PROXY") or os.getenv("https_proxy"),
                        "YF_VERIFY": os.getenv("YF_VERIFY"),
                    },
                }
            return result
        except Exception as e:
            # Continue to normal path if forced direct failed
            pass

    t = yf.Ticker(symbol)  # Do not pass Requests session; yfinance prefers curl_cffi

    price = None
    as_of = None
    error: str | None = None
    used: Optional[str] = None
    debug: Dict[str, Any] = {}

    if _debug_enabled():
        debug = {
            "env": {
                "REQUESTS_CA_BUNDLE": os.getenv("REQUESTS_CA_BUNDLE"),
                "SSL_CERT_FILE": os.getenv("SSL_CERT_FILE"),
                "CURL_CA_BUNDLE": os.getenv("CURL_CA_BUNDLE"),
                "HTTP_PROXY": os.getenv("HTTP_PROXY") or os.getenv("http_proxy"),
                "HTTPS_PROXY": os.getenv("HTTPS_PROXY") or os.getenv("https_proxy"),
                "YF_VERIFY": os.getenv("YF_VERIFY"),
            },
            "attempts": [],
            "note": "no session passed to yfinance",
        }

    # Try minute history for freshest price
    try:
        hist = t.history(period="1d", interval="1m")
        if not hist.empty:
            last_row = hist.tail(1)
            price = float(last_row["Close"].iloc[0])
            as_of = last_row.index[-1].to_pydatetime()
            used = "history:1m"
            if _debug_enabled():
                debug["attempts"].append({"path": "history:1m", "ok": True})
    except Exception as e:
        error = f"history: {e}"
        if _debug_enabled():
            debug["attempts"].append({"path": "history:1m", "ok": False, "error": str(e)})

    # Fallback to fast_info/info
    if price is None:
        try:
            info = getattr(t, "fast_info", None) or {}
            fast_last = getattr(info, "last_price", None) or getattr(info, "lastPrice", None)
            if fast_last is not None:
                price = float(fast_last)
                used = "fast_info"
                if _debug_enabled():
                    debug["attempts"].append({"path": "fast_info", "ok": True})
        except Exception as e:
            error = (error or "") + f"; fast_info: {e}"
            if _debug_enabled():
                debug["attempts"].append({"path": "fast_info", "ok": False, "error": str(e)})

    if price is None:
        try:
            info = t.info
            if info and info.get("regularMarketPrice") is not None:
                price = float(info.get("regularMarketPrice"))
                ts = info.get("regularMarketTime")
                if ts:
                    as_of = dt.datetime.fromtimestamp(ts, tz=dt.timezone.utc)
                used = "info"
                if _debug_enabled():
                    debug["attempts"].append({"path": "info", "ok": True})
        except Exception as e:
            error = (error or "") + f"; info: {e}"
            if _debug_enabled():
                debug["attempts"].append({"path": "info", "ok": False, "error": str(e)})

    # Final fallback: direct Yahoo quote endpoint via Requests
    if price is None:
        try:
            direct = _direct_quote(symbol, _make_session())
            price = direct.get("price")
            as_of = direct.get("as_of") or as_of
            curr2 = direct.get("currency")
            if curr2:
                currency = curr2
            used = "direct"
            if _debug_enabled():
                debug["attempts"].append({"path": "direct", "ok": True})
        except Exception as e:
            error = (error or "") + f"; direct: {e}"
            if _debug_enabled():
                debug["attempts"].append({"path": "direct", "ok": False, "error": str(e)})

    # Currency best-effort from fast_info
    try:
        info = getattr(t, "fast_info", None) or {}
        yf_ccy = getattr(info, "currency", None) or getattr(info, "curr", None) or None
        currency = yf_ccy or currency
    except Exception:
        pass

    result = {
        "symbol": symbol.upper(),
        "price": price,
        "currency": currency,
        "as_of": _iso(as_of or dt.datetime.now(dt.timezone.utc)),
    }
    if error and price is None:
        result["error"] = error
    if _debug_enabled():
        result["debug"] = {"used": used, **debug}
    return result


def _direct_quote(symbol: str, session: requests.Session) -> Dict[str, Any]:
    url = "https://query1.finance.yahoo.com/v7/finance/quote"
    r = session.get(url, params={"symbols": symbol}, timeout=10)
    r.raise_for_status()
    data = r.json()
    res = (data or {}).get("quoteResponse", {}).get("result", [])
    if not res:
        return {"price": None}
    item = res[0]
    price = item.get("regularMarketPrice")
    currency = item.get("currency")
    ts = item.get("regularMarketTime")
    as_of = dt.datetime.fromtimestamp(ts, tz=dt.timezone.utc) if ts else None
    return {"price": price, "currency": currency, "as_of": as_of}


def fetch_history(
    symbol: str,
    start_date: str,
    end_date: str,
    interval: str = "1d",
) -> Dict[str, Any]:
    _prepare_network_env()
    t = yf.Ticker(symbol)
    df = t.history(start=start_date, end=end_date, interval=interval)
    records: List[Dict[str, Any]] = []
    if not df.empty:
        for idx, row in df.iterrows():
            when = idx.to_pydatetime() if hasattr(idx, "to_pydatetime") else idx
            records.append(
                {
                    "timestamp": _iso(when if isinstance(when, dt.datetime) else dt.datetime.combine(when, dt.time.min, tzinfo=dt.timezone.utc)),
                    "open": float(row.get("Open", float("nan"))),
                    "high": float(row.get("High", float("nan"))),
                    "low": float(row.get("Low", float("nan"))),
                    "close": float(row.get("Close", float("nan"))),
                    "volume": int(row.get("Volume", 0)) if not (row.get("Volume") != row.get("Volume")) else None,  # handle NaN
                }
            )
    return {
        "symbol": symbol.upper(),
        "interval": interval,
        "start": start_date,
        "end": end_date,
        "prices": records,
    }


def fetch_profile(symbol: str) -> Dict[str, Any]:
    _prepare_network_env()
    t = yf.Ticker(symbol)
    info: Dict[str, Any] = {}
    try:
        info = t.info
    except Exception:
        info = {}

    profile = {
        "symbol": symbol.upper(),
        "name": info.get("longName") or info.get("shortName"),
        "sector": info.get("sector"),
        "industry": info.get("industry") or info.get("industryKey"),
        "employees": info.get("fullTimeEmployees"),
        "website": info.get("website"),
        "summary": info.get("longBusinessSummary"),
        "market_cap": info.get("marketCap"),
        "currency": info.get("currency"),
        "exchange": info.get("exchange"),
        "country": info.get("country"),
    }
    return profile
