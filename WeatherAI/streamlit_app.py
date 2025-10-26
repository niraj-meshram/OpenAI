import os
import time
import pandas as pd
import streamlit as st
from agents import Runner
from weather_agent import weather_agent  # your Agent with tools
# add near the top
import asyncio
import os
# (Windows-only robustness)
if os.name == "nt":
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    except Exception:
        pass

# --- Config ---
st.set_page_config(page_title="Weather Agent", page_icon="⛅", layout="centered")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    st.warning("Set OPENAI_API_KEY in your environment (or Streamlit Cloud Secrets).")

st.title("⛅ Weather Agent")
st.caption("Ask for today's/tomorrow's weather, or 6-month history & outlook via climatology.")

with st.sidebar:
    st.header("Options")
    default_city = st.text_input("Default city", value="Phoenix")
    units = st.radio("Units", ["°C", "°F"], index=0, horizontal=True)
    st.markdown("---")
    st.write("Examples")
    st.code("Phoenix\nPhoenix tomorrow\nSalt Lake City trend")
    # or if you actually wanted to display backslashes literally:
    # st.code(r"Phoenix\ nPhoenix tomorrow\ nSalt Lake City trend")

tab1, tab2 = st.tabs(["Quick Weather", "6-Month Trend"])

def c_to_f(c):
    return c * 9/5 + 32

# ---------- TAB 1: Quick Weather ----------
with tab1:
    city = st.text_input("City", value=default_city, key="city_now")
    when = st.radio("When", ["today", "tomorrow"], horizontal=True)
    if st.button("Get weather", type="primary"):
        if not city.strip():
            st.error("Please enter a city.")
        else:
            query = f"weather in {city} {when}"
            with st.spinner("Asking agent…"):
                try:
                    res = asyncio.run(Runner.run(weather_agent, query))

                    st.success("Done")
                    st.write(res.final_output)
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
            # Normalize a trend-style query so the agent calls the right tool
            query = f"{city2} 6 month weather history and outlook"
            with st.spinner("Computing monthly averages (can take ~20–40s on first run)…"):
                t0 = time.time()
                try:
                    res = asyncio.run(Runner.run(weather_agent, query))
                    t1 = time.time()
                except Exception as e:
                    st.error(f"Error: {e}")
                    st.stop()

            # res.final_output is natural language; we’ll ask the agent to format as JSON next time
            # For now, we can re-query the agent to return JSON, or simpler:
            # Let’s ask again to return JSON we can tabulate.
            with st.spinner("Formatting results…"):
                try:
                    fmt = asyncio.run(
                        Runner.run(
                            weather_agent,
                            f"Return ONLY JSON with keys past_6 (list of {{month, t_max_c, t_min_c}}) "
                            f"and next_6 (list of {{month, t_max_c, t_min_c}}) for {city2}, "
                            "based on the last tool result you just computed."
                        )
                    )

                    data = fmt.final_output
                except Exception as e:
                    st.error(f"Formatting error: {e}")
                    st.write(res.final_output)
                    st.stop()

            # Try to parse JSON
            import json
            try:
                j = json.loads(data)
            except Exception:
                st.info("Couldn’t parse structured JSON reliably; showing raw answer instead.")
                st.write(res.final_output)
                st.stop()

            # Build tables
            def make_df(items, units_label):
                if not items:
                    return pd.DataFrame()
                df = pd.DataFrame(items)
                if units_label == "°F":
                    if "t_max_c" in df.columns:
                        df["t_max_f"] = df["t_max_c"].apply(c_to_f)
                    if "t_min_c" in df.columns:
                        df["t_min_f"] = df["t_min_c"].apply(c_to_f)
                # nicer column names
                rename = {
                    "month": "Month",
                    "t_max_c": "High (°C)",
                    "t_min_c": "Low (°C)",
                    "t_max_f": "High (°F)",
                    "t_min_f": "Low (°F)",
                }
                df = df.rename(columns=rename)
                return df

            past_df = make_df(j.get("past_6", []), units)
            next_df = make_df(j.get("next_6", []), units)

            st.subheader(f"{city2}: Past 6 months (monthly averages)")
            if not past_df.empty:
                st.dataframe(past_df, use_container_width=True)
            else:
                st.write("No data.")

            st.subheader(f"{city2}: Next 6 months (seasonal baseline)")
            if not next_df.empty:
                st.dataframe(next_df, use_container_width=True)
            else:
                st.write("No data.")

            if explain:
                st.caption(
                    "Outlook is a seasonal baseline (10-year monthly climatology at this location), "
                    "not a deterministic forecast."
                )

            st.caption(f"Finished in {t1 - t0:0.1f}s")
