# weather_agent.py
import requests
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime, timedelta, timezone
from collections import defaultdict
from agents import Agent, function_tool

BASE_GEOCODE = "https://geocoding-api.open-meteo.com/v1/search"
BASE_ARCHIVE = "https://archive-api.open-meteo.com/v1/era5"

def _ymd(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d")

def _first_of_month(dt: datetime) -> datetime:
    return dt.replace(day=1)

def _last_of_month(dt: datetime) -> datetime:
    nxt = (dt.replace(day=28) + timedelta(days=4)).replace(day=1)
    return nxt - timedelta(days=1)

def _aggregate_monthly(daily: Dict[str, List[float]], dates: List[str]) -> Dict[str, Dict[str, float]]:
    """Return {YYYY-MM: {t_max_c, t_min_c}} using simple means."""
    by_month_max: Dict[str, List[float]] = defaultdict(list)
    by_month_min: Dict[str, List[float]] = defaultdict(list)
    for i, d in enumerate(dates):
        ym = d[:7]
        by_month_max[ym].append(daily["temperature_2m_max"][i])
        by_month_min[ym].append(daily["temperature_2m_min"][i])
    out: Dict[str, Dict[str, float]] = {}
    for ym in sorted(by_month_max.keys()):
        out[ym] = {
            "t_max_c": sum(by_month_max[ym]) / len(by_month_max[ym]),
            "t_min_c": sum(by_month_min[ym]) / len(by_month_min[ym]),
        }
    return out

def _geocode(city: str) -> Tuple[float, float, str]:
    g = requests.get(BASE_GEOCODE, params={"name": city, "count": 1}, timeout=20).json()
    if not g.get("results"):
        raise ValueError(f"Couldn't find {city}")
    r = g["results"][0]
    return r["latitude"], r["longitude"], r.get("timezone", "auto")

@function_tool
def get_forecast(city: str, when: Optional[str] = "today") -> Dict[str, Any]:
    """(Existing) Simple one-day/tomorrow summary."""
    lat, lon, tz = _geocode(city)
    w = requests.get(
        "https://api.open-meteo.com/v1/forecast",
        params={
            "latitude": lat,
            "longitude": lon,
            "daily": "temperature_2m_max,temperature_2m_min,weathercode",
            "timezone": tz,
        },
        timeout=20,
    ).json()
    d0 = w["daily"]
    idx = 1 if when == "tomorrow" and len(d0["time"]) > 1 else 0
    return {
        "city": city,
        "date": d0["time"][idx],
        "t_max_c": d0["temperature_2m_max"][idx],
        "t_min_c": d0["temperature_2m_min"][idx],
        "weathercode": d0["weathercode"][idx],
    }

@function_tool
def get_six_month_trend(city: str) -> Dict[str, Any]:
    """
    Return past 6 months (monthly avg highs/lows in °C) and a naive next 6 months
    outlook using 10-year monthly climatology at this location.
    """
    lat, lon, tz = _geocode(city)

    today = datetime.now(timezone.utc).astimezone()
    start_hist = _first_of_month((today.replace(day=1) - timedelta(days=1)).replace(day=1) - timedelta(days=5*31))
    # last completed month end:
    end_hist = _last_of_month(today.replace(day=1) - timedelta(days=1))

    # 1) Past 6 months daily highs/lows
    hist = requests.get(
        BASE_ARCHIVE,
        params={
            "latitude": lat, "longitude": lon,
            "start_date": _ymd(start_hist),
            "end_date": _ymd(end_hist),
            "daily": "temperature_2m_max,temperature_2m_min",
            "timezone": tz,
        },
        timeout=30,
    ).json()

    if "daily" not in hist:
        return {"error": f"No historical data for {city}"}

    monthly_hist = _aggregate_monthly(hist["daily"], hist["daily"]["time"])
    # keep only last 6 months
    last_6_keys = sorted([k for k in monthly_hist.keys()])[-6:]
    past_6 = [{ "month": k, **monthly_hist[k] } for k in last_6_keys]

    # 2) Next 6 months seasonal climatology (10y back averages of those months)
    outlook = []
    # months for next 6 starting next calendar month
    anchor = today.replace(day=1)
    next_month = (anchor + timedelta(days=32)).replace(day=1)
    months_ahead: List[datetime] = []
    m = next_month
    for _ in range(6):
        months_ahead.append(m)
        # move to next month
        m = (m + timedelta(days=32)).replace(day=1)

    for target in months_ahead:
        # pull the same calendar month over last 10 years
        accum_max: List[float] = []
        accum_min: List[float] = []
        for y in range(1, 11):
            year = target.year - y
            s = target.replace(year=year, day=1)
            e = _last_of_month(s)
            block = requests.get(
                BASE_ARCHIVE,
                params={
                    "latitude": lat, "longitude": lon,
                    "start_date": _ymd(s), "end_date": _ymd(e),
                    "daily": "temperature_2m_max,temperature_2m_min",
                    "timezone": tz,
                },
                timeout=30,
            ).json()
            if "daily" not in block:
                continue
            dd = block["daily"]
            # average for that historical month
            if dd["temperature_2m_max"]:
                accum_max.append(sum(dd["temperature_2m_max"]) / len(dd["temperature_2m_max"]))
                accum_min.append(sum(dd["temperature_2m_min"]) / len(dd["temperature_2m_min"]))
        if accum_max and accum_min:
            outlook.append({
                "month": target.strftime("%Y-%m"),
                "t_max_c": sum(accum_max)/len(accum_max),
                "t_min_c": sum(accum_min)/len(accum_min),
                "method": "10y monthly climatology (naive seasonal)",
            })
        else:
            outlook.append({
                "month": target.strftime("%Y-%m"),
                "error": "insufficient data for climatology"
            })

    return {
        "city": city,
        "past_6_months": past_6,
        "next_6_months": outlook,
        "notes": "Outlook is a seasonal baseline (not a deterministic forecast).",
    }

weather_agent = Agent(
    name="Weather Agent",
    instructions=(
        "You answer weather and trend questions.\n"
        "- For single-day questions, call get_forecast.\n"
        "- If the user asks for past or next 6 months (history/outlook/trend), call get_six_month_trend.\n"
        "When returning monthly values, show month (YYYY-MM) and average high/low in °C, and briefly explain that the next 6 months are a seasonal baseline from the last 10 years."
    ),
    tools=[get_forecast, get_six_month_trend],
)
