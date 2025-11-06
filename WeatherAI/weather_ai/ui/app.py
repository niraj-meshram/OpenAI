import os
import time
import asyncio
import streamlit as st
import streamlit.components.v1 as components
import plotly.graph_objects as go

from weather_ai.utils.units import c_to_f, make_trend_df, format_quick_weather_text
from weather_ai.tools.api import fetch_forecast, fetch_six_month_trend


def _ensure_key_from_secrets() -> None:
    if not os.getenv("OPENAI_API_KEY"):
        try:
            key = st.secrets.get("OPENAI_API_KEY", "")
            if key:
                os.environ["OPENAI_API_KEY"] = str(key)
        except Exception:
            pass


def _ensure_key_from_dotenv() -> None:
    if os.getenv("OPENAI_API_KEY"):
        return
    try:
        for candidate in (".env", ".streamlit/.env"):
            if os.path.exists(candidate):
                with open(candidate, "r", encoding="utf-8") as fh:
                    for line in fh:
                        line = line.strip()
                        if not line or line.startswith("#"):
                            continue
                        if line.startswith("OPENAI_API_KEY="):
                            val = line.split("=", 1)[1].strip().strip('"').strip("'")
                            if val:
                                os.environ["OPENAI_API_KEY"] = val
                            return
    except Exception:
        pass


def _get_mapbox_token() -> str | None:
    token = os.getenv("MAPBOX_TOKEN")
    if token:
        return token
    try:
        token = st.secrets.get("MAPBOX_TOKEN", "")
        if token:
            os.environ["MAPBOX_TOKEN"] = str(token)
            return str(token)
    except Exception:
        pass
    return None


def weathercode_emoji_desc(code: int) -> tuple[str, str]:
    mapping = {
        0: ("☀️", "Clear sky"),
        1: ("🌤️", "Mainly clear"),
        2: ("⛅", "Partly cloudy"),
        3: ("☁️", "Overcast"),
        45: ("🌫️", "Fog"),
        48: ("🌫️", "Depositing rime fog"),
        51: ("🌦️", "Light drizzle"),
        53: ("🌧️", "Drizzle"),
        55: ("🌧️", "Dense drizzle"),
        56: ("🌧️❄️", "Freezing drizzle"),
        57: ("🌧️❄️", "Dense freezing drizzle"),
        61: ("🌦️", "Light rain"),
        63: ("🌧️", "Rain"),
        65: ("🌧️", "Heavy rain"),
        66: ("🌧️❄️", "Freezing rain"),
        67: ("🌧️❄️", "Heavy freezing rain"),
        71: ("🌨️", "Light snow"),
        73: ("🌨️", "Snow"),
        75: ("❄️", "Heavy snow"),
        77: ("❄️", "Snow grains"),
        80: ("🌦️", "Rain showers"),
        81: ("🌧️", "Heavy showers"),
        82: ("⛈️", "Violent showers"),
        85: ("🌨️", "Snow showers"),
        86: ("❄️", "Heavy snow showers"),
        95: ("⛈️", "Thunderstorm"),
        96: ("⛈️", "Thunderstorm with hail"),
        99: ("⛈️", "Thunderstorm with heavy hail"),
    }
    return mapping.get(int(code), ("🌡️", "Weather"))


@st.cache_data(ttl=600, show_spinner=False)
def cached_forecast(city: str, when: str):
    return fetch_forecast(city, when)


@st.cache_data(ttl=1800, show_spinner=False)
def cached_trend(city: str):
    return fetch_six_month_trend(city)


def render() -> None:
    _ensure_key_from_secrets()
    _ensure_key_from_dotenv()

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
        show_emoji = st.checkbox("Show emoji", value=True)
        desc_place = st.radio("Description", ["inline", "caption"], index=0, horizontal=True)
        st.markdown("---")
        st.write("Examples")
        st.code("Phoenix\nPhoenix tomorrow\nSalt Lake City trend")

    tab1, tab2 = st.tabs(["Quick Weather", "6-Month Trend"])

    # ---------- TAB 1: Quick Weather ----------
    with tab1:
        ex_cols = st.columns(4)
        if ex_cols[0].button("Phoenix today", key="ex_phx_today"):
            st.session_state["city_now"] = "Phoenix"
            st.session_state["when_now"] = "today"
        if ex_cols[1].button("NYC tomorrow", key="ex_nyc_tomorrow"):
            st.session_state["city_now"] = "New York"
            st.session_state["when_now"] = "tomorrow"
        if ex_cols[2].button("Denver today", key="ex_denver_today"):
            st.session_state["city_now"] = "Denver"
            st.session_state["when_now"] = "today"
        if ex_cols[3].button("Tokyo tomorrow", key="ex_tokyo_tomorrow"):
            st.session_state["city_now"] = "Tokyo"
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
                        display = text
                        if show_emoji:
                            display = f"{emoji} {display}"
                        if desc_place == "inline":
                            display = f"{display} ({desc.lower()})"
                            st.success(display)
                        else:
                            st.success(display)
                            st.caption(desc.capitalize())

                        # Apply dynamic theme based on weather
                        try:
                            _apply_weather_theme(int(payload.get("weathercode", -1)))
                        except Exception:
                            pass

                        # Render globe: Mapbox GL if token available, else fallback Plotly globe
                        try:
                            lat = float(payload.get("lat"))
                            lon = float(payload.get("lon"))
                            token = _get_mapbox_token()
                            if token:
                                _render_globe_mapbox(token, lat, lon, city)
                            else:
                                globe_ph = st.empty()
                                for size in (4, 9, 14, 18):
                                    fig = _build_globe(lat, lon, city, size)
                                    globe_ph.plotly_chart(fig, use_container_width=True)
                                    time.sleep(0.08)
                        except Exception:
                            pass

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
                chart_df = past_df.rename(
                    columns={
                        "High (°C)": "High",
                        "Low (°C)": "Low",
                        "High (°F)": "High",
                        "Low (°F)": "Low",
                    }
                ).set_index("Month")
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
                chart_df2 = next_df.rename(
                    columns={
                        "High (°C)": "High",
                        "Low (°C)": "Low",
                        "High (°F)": "High",
                        "Low (°F)": "Low",
                    }
                ).set_index("Month")
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
                    "Outlook is a seasonal baseline (10-year monthly climatology at this location), not a deterministic forecast."
                )

            st.caption(f"Finished in {t1 - t0:0.1f}s")

    if st.session_state.get("history"):
        st.markdown("---")
        st.caption("Recent searches")
        hcols = st.columns(min(6, len(st.session_state["history"])))
        for i, item in enumerate(st.session_state["history"][:6]):
            label = f"{item['city']} {item['when']} ({item['units']})"
            if hcols[i].button(label, key=f"hist_btn_{i}_{label}"):
                st.session_state["city_now"] = item["city"]
                st.session_state["when_now"] = item["when"]


def _apply_weather_theme(code: int) -> None:
    theme = _theme_for_code(code)
    bg = theme["bg"]
    primary = theme["accent"]
    st.markdown(
        f"""
        <style>
        .stApp {{
            background: {bg} !important;
        }}
        :root {{
            --primary-color: {primary};
            --secondary-background-color: rgba(255,255,255,0.05);
        }}
        .stButton button {{
            background-color: {primary} !important;
            border-color: {primary} !important;
            color: #ffffff !important;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def _theme_for_code(code: int) -> dict:
    if code == 0:
        return {"bg": "linear-gradient(135deg,#87CEEB,#FFE082)", "accent": "#f39c12"}
    if code in (1, 2, 3):
        return {"bg": "linear-gradient(135deg,#cfd8dc,#90a4ae)", "accent": "#607d8b"}
    if code in (45, 48):
        return {"bg": "linear-gradient(135deg,#b0bec5,#eceff1)", "accent": "#78909c"}
    if code in (51, 53, 55, 56, 57, 61, 63, 65, 66, 67, 80, 81, 82):
        return {"bg": "linear-gradient(135deg,#0a2740,#27496d)", "accent": "#3498db"}
    if code in (71, 73, 75, 77, 85, 86):
        return {"bg": "linear-gradient(135deg,#e0f7fa,#80deea)", "accent": "#00acc1"}
    if code in (95, 96, 99):
        return {"bg": "linear-gradient(135deg,#2c3e50,#4b0082)", "accent": "#8e44ad"}
    return {"bg": "linear-gradient(135deg,#1f2937,#374151)", "accent": "#10b981"}


def _build_globe(lat: float, lon: float, label: str, size: int) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(
        go.Scattergeo(
            lon=[lon],
            lat=[lat],
            mode="markers+text",
            text=[label],
            textposition="bottom center",
            marker=dict(size=size, color="#e74c3c", line=dict(width=1, color="#ffffff")),
        )
    )
    fig.update_geos(
        projection_type="orthographic",
        projection_rotation=dict(lon=float(lon), lat=float(lat), roll=0),
        showland=True,
        landcolor="#eaeaea",
        showcountries=True,
        countrycolor="#a0a0a0",
        showocean=True,
        oceancolor="#0a2640",
        lataxis_showgrid=True,
        lonaxis_showgrid=True,
    )
    fig.update_layout(
        margin=dict(l=0, r=0, t=0, b=0),
        height=420,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )
    return fig


def _render_globe_mapbox(token: str, lat: float, lon: float, city: str) -> None:
    token_js = token.replace("\\", "\\\\").replace("'", "\\'")
    city_js = city.replace("\\", "\\\\").replace("'", "\\'")
    html = f"""
    <html>
    <head>
      <meta charset='utf-8' />
      <meta name='viewport' content='initial-scale=1,maximum-scale=1,user-scalable=no' />
      <link href='https://api.mapbox.com/mapbox-gl-js/v2.15.0/mapbox-gl.css' rel='stylesheet' />
      <script src='https://api.mapbox.com/mapbox-gl-js/v2.15.0/mapbox-gl.js'></script>
      <style>
        body, html, #map {{ height: 100%; margin: 0; padding: 0; background: transparent; }}
        .marker-label {{
          color: white; font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial;
          text-shadow: 0 1px 2px rgba(0,0,0,0.6); font-size: 13px; margin-top: 4px;
        }}
      </style>
    </head>
    <body>
      <div id='map'></div>
      <script>
        mapboxgl.accessToken = '{token_js}';
        const map = new mapboxgl.Map({{
          container: 'map',
          style: 'mapbox://styles/mapbox/satellite-v9',
          projection: 'globe',
          center: [0, 20],
          zoom: 1.2,
          pitch: 0,
          bearing: 0,
          attributionControl: false
        }});
        map.on('style.load', () => {{ map.setFog({{}}); }});

        let start;
        function rotate(ts) {{
          if (!start) start = ts;
          const elapsed = ts - start;
          const rotation = (elapsed / 50.0) % 360.0;
          map.setBearing(rotation);
          if (elapsed < 4000) {{
            requestAnimationFrame(rotate);
          }} else {{
            const city = [{lon}, {lat}];
            new mapboxgl.Marker({{ color: '#e74c3c' }}).setLngLat(city).addTo(map);
            new mapboxgl.Popup({{ closeButton: false, closeOnClick: false }})
              .setLngLat(city)
              .setHTML('<div class=\'marker-label\'>{city_js}</div>')
              .addTo(map);
            map.flyTo({{
              center: city,
              zoom: 5.2,
              pitch: 45,
              bearing: rotation,
              speed: 0.6,
              curve: 1.42,
              essential: true
            }});
          }}
        }}
        requestAnimationFrame(rotate);
      </script>
    </body>
    </html>
    """
    components.html(html, height=480)

