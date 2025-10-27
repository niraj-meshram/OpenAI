from __future__ import annotations

from agents import Agent, function_tool
from typing import Dict, Any, Optional
from weather_ai.tools.api import fetch_forecast, fetch_six_month_trend


@function_tool
def get_forecast(city: str, when: Optional[str] = "today") -> Dict[str, Any]:
    """Return simple one-day summary (t_max_c, t_min_c, weathercode)."""
    return fetch_forecast(city, when)


@function_tool
def get_six_month_trend(city: str) -> Dict[str, Any]:
    """Return past/next 6 months monthly averages (in °C baseline)."""
    return fetch_six_month_trend(city)


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

