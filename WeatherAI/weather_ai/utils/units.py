from __future__ import annotations

import pandas as pd


def c_to_f(c: float) -> float:
    return c * 9 / 5 + 32


def format_quick_weather_text(payload: dict, units: str) -> str:
    city = payload.get("city", "")
    date = payload.get("date", "")
    t_max = payload.get("t_max_c")
    t_min = payload.get("t_min_c")
    if t_max is None or t_min is None:
        raise ValueError("Missing t_max_c/t_min_c in payload")
    if units == "°F":
        t_max = c_to_f(t_max)
        t_min = c_to_f(t_min)
        return f"{city} {date}: High {t_max:.1f} °F, Low {t_min:.1f} °F"
    return f"{city} {date}: High {t_max:.1f} °C, Low {t_min:.1f} °C"


def make_trend_df(items: list[dict], units_label: str) -> pd.DataFrame:
    if not items:
        return pd.DataFrame()
    df = pd.DataFrame(items)
    if units_label == "°F":
        if "t_max_c" in df.columns:
            df["t_max_f"] = df["t_max_c"].apply(c_to_f)
        if "t_min_c" in df.columns:
            df["t_min_f"] = df["t_min_c"].apply(c_to_f)
        keep = [c for c in ["month", "t_max_f", "t_min_f"] if c in df.columns]
        df = df[keep]
        rename = {"month": "Month", "t_max_f": "High (°F)", "t_min_f": "Low (°F)"}
    else:
        keep = [c for c in ["month", "t_max_c", "t_min_c"] if c in df.columns]
        df = df[keep]
        rename = {"month": "Month", "t_max_c": "High (°C)", "t_min_c": "Low (°C)"}
    df = df.rename(columns=rename)
    return df
