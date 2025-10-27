import os
import time
import asyncio
import json
import pandas as pd
import streamlit as st

from weather_ai.utils.units import c_to_f, make_trend_df, format_quick_weather_text
from weather_ai.tools.api import fetch_forecast, fetch_six_month_trend


def _ensure_key_from_windows_env() -> None:
    if os.name == "nt" and not os.getenv("OPENAI_API_KEY"):
        try:
            import winreg  # type: ignore
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Environment") as key:
                val, _ = winreg.QueryValueEx(key, "OPENAI_API_KEY")
                if val:
                    os.environ["OPENAI_API_KEY"] = val
        except Exception:
            pass


def weathercode_emoji_desc(code: int) -> tuple[str, str]:
    mapping = {
        0: ("☀️", "Clear sky"), 1: ("🌤️", "Mainly clear"), 2: ("⛅", "Partly cloudy"), 3: ("☁️", "Overcast"),
        45: ("🌫️", "Fog"), 48: ("🌫️", "Depositing rime fog"),
        51: ("🌦️", "Light drizzle"), 53: ("🌦️", "Drizzle"), 55: ("🌧️", "Dense drizzle"),
        56: ("🌦️", "Freezing drizzle"), 57: ("🌧️", "Dense freezing drizzle"),
        61: ("🌦️", "Light rain"), 63: ("🌧️", "Rain"), 65: ("🌧️", "Heavy rain"),
        66: ("🌧️", "Freezing rain"), 67: ("🌧️", "Heavy freezing rain"),
        71: ("🌨️", "Light snow"), 73: ("🌨️", "Snow"), 75: ("❄️", "Heavy snow"),
        77: ("❄️", "Snow grains"),
        80: ("🌦️", "Rain showers"), 81: ("🌧️", "Heavy showers"), 82: ("⛈️", "Violent showers"),
        85: ("🌨️", "Snow showers"), 86: ("❄️", "Heavy snow showers"),
        95: ("⛈️", "Thunderstorm"), 96: ("⛈️", "Thunderstorm with hail"), 99: ("⛈️", "Thunderstorm with heavy hail"),
    }
    return mapping.get(int(code), ("🌡️", "Weather"))


@st.cache_data(ttl=600, show_spinner=False)
def cached_forecast(city: str, when: str):
    return fetch_forecast(city, when)


@st.cache_data(ttl=1800, show_spinner=False)
def cached_trend(city: str):
    return fetch_six_month_trend(city)


def render() -> None:
    _ensure_key_from_windows_env()

    if os.name == "nt":
        try:
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        except Exception:
            pass

    st.set_page_config(page_title="Weather Agent", page_icon="⛅", layout="centered")

    if not os.getenv("OPENAI_API_KEY"):
        st.warning("Set OPENAI_API_KEY in your environment before starting Streamlit.")

    st.title("⛅ Weather Agent")
    st.caption("Ask for today's/tomorrow's weather, or 6-month history & outlook via climatology.")

    with st.sidebar:
        st.header("Options")
        default_city = st.text_input("Default city", value="Phoenix")
        units = st.radio("Units", ["°C", "°F"], index=0, horizontal=True)
        st.markdown("---")
        st.write("Examples")
        st.code("Phoenix\nPhoenix tomorrow\nSalt Lake City trend")

    tab1, tab2 = st.tabs(["Quick Weather", "6-Month Trend"])

    # ---------- TAB 1: Quick Weather ----------
    with tab1:
        ex_cols = st.columns(4)
        if ex_cols[0].button("Phoenix today"):
            st.session_state["city_now"] = "Phoenix"
            st.session_state["when_now"] = "today"
        if ex_cols[1].button("NYC tomorrow"):
            st.session_state["city_now"] = "New York"
            st.session_state["when_now"] = "tomorrow"
        if ex_cols[2].button("Denver today"):
            st.session_state["city_now"] = "Denver"
            st.session_state["when_now"] = "today"
        if ex_cols[3].button("SLC tomorrow"):
            st.session_state["city_now"] = "Salt Lake City"
            st.session_state["when_now"] = "tomorrow"

        if "city_now" not in st.session_state:
            st.session_state["city_now"] = default_city
        if "when_now" not in st.session_state:
            st.session_state["when_now"] = "today"

        city = st.text_input("City", key="city_now")
        when = st.radio("When", ["today", "tomorrow"], horizontal=True, key="when_now")
        if st.button("Get weather", type="primary"):
            if not city.strip():
                st.error("Please enter a city.")
            else:
                with st.spinner("Fetching weather…"):
                    try:
                        payload = cached_forecast(city, when)
                        emoji, desc = weathercode_emoji_desc(payload.get("weathercode", -1))
                        text = format_quick_weather_text(payload, units)
                        st.success(f"{emoji} {text} ({desc.lower()})")

                        col1, col2 = st.columns(2)
                        t_max_c = float(payload.get("t_max_c"))
                        t_min_c = float(payload.get("t_min_c"))
                        if units == "°F":
                            col1.metric("High", f"{c_to_f(t_max_c):.1f} °F")
                            col2.metric("Low", f"{c_to_f(t_min_c):.1f} °F")
                        else:
                            col1.metric("High", f"{t_max_c:.1f} °C")
                            col2.metric("Low", f"{t_min_c:.1f} °C")

                        hist = st.session_state.setdefault("history", [])
                        hist.insert(0, {"city": city, "when": when, "units": units})
                        st.session_state["history"] = hist[:6]
                    except Exception as e:
                        st.error(f"Error: {e}")

    # ---------- TAB 2: Past & Next 6-Month Trend ----------
    with tab2:
        city2 = st.text_input("City", value=default_city, key="city_trend")
        explain = st.checkbox("Explain method", value=True)
        if st.button("Get 6-month history & outlook", type="secondary"):
            if not city2.strip():
                st.error("Please enter a city.")
            else:
                with st.spinner("Computing monthly averages…"):
                    t0 = time.time()
                    try:
                        trend = cached_trend(city2)
                        t1 = time.time()
                    except Exception as e:
                        st.error(f"Error: {e}")
                        st.stop()

                past_df = make_trend_df(trend.get("past_6", trend.get("past_6_months", [])), units)
                next_df = make_trend_df(trend.get("next_6", trend.get("next_6_months", [])), units)

                st.subheader(f"{city2}: Past 6 months (monthly averages)")
                if not past_df.empty:
                    st.dataframe(past_df, use_container_width=True)
                    chart_df = past_df.rename(columns={
                        "High (°C)": "High",
                        "Low (°C)": "Low",
                        "High (°F)": "High",
                        "Low (°F)": "Low",
                    }).set_index("Month")
                    st.line_chart(chart_df)
                    st.download_button(
                        label="Download past 6 CSV",
                        data=past_df.to_csv(index=False),
                        file_name=f"{city2.replace(' ','_')}_past6.csv",
                        mime="text/csv",
                    )
                else:
                    st.write("No data.")

                st.subheader(f"{city2}: Next 6 months (seasonal baseline)")
                if not next_df.empty:
                    st.dataframe(next_df, use_container_width=True)
                    chart_df2 = next_df.rename(columns={
                        "High (°C)": "High",
                        "Low (°C)": "Low",
                        "High (°F)": "High",
                        "Low (°F)": "Low",
                    }).set_index("Month")
                    st.line_chart(chart_df2)
                    st.download_button(
                        label="Download next 6 CSV",
                        data=next_df.to_csv(index=False),
                        file_name=f"{city2.replace(' ','_')}_next6.csv",
                        mime="text/csv",
                    )
                else:
                    st.write("No data.")

                if explain:
                    st.caption(
                        "Outlook is a seasonal baseline (10-year monthly climatology at this location), "
                        "not a deterministic forecast."
                    )

                st.caption(f"Finished in {t1 - t0:0.1f}s")

    if st.session_state.get("history"):
        st.markdown("---")
        st.caption("Recent searches")
        hcols = st.columns(min(6, len(st.session_state["history"])))
        for i, item in enumerate(st.session_state["history"][:6]):
            label = f"{item['city']} {item['when']} ({item['units']})"
            if hcols[i].button(label):
                st.session_state["city_now"] = item["city"]
                st.session_state["when_now"] = item["when"]

