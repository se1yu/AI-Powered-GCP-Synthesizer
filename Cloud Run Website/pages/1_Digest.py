"""Cloud Comms — Weekly Digest page.

A multipage Streamlit app page (native st.navigation pattern via the
pages/ directory) giving TAMs a scannable, chart-backed summary instead of
having to ask the chat for it every time.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from release_agent.sources import fetch_service_health, get_recent_summary
from release_agent.theme import GLOBAL_CSS
from release_agent.ui import render_appbar, render_incident_banner

st.set_page_config(page_title="Cloud Comms — Weekly Digest", page_icon="\U0001f4ca", layout="wide")
st.markdown(GLOBAL_CSS, unsafe_allow_html=True)


render_appbar(
    "Weekly Digest",
    "Release activity + live status across Google Cloud",
    icon="\U0001f4ca",
)


days_back = st.segmented_control(
    "Window", [7, 14, 30], default=7, format_func=lambda d: f"{d}d"
)
days_back = days_back or 7

summary = get_recent_summary(days_back=days_back)

col_metrics, col_status = st.columns([2, 1])

with col_metrics:
    if summary.get("status") != "success":
        st.error(f"Couldn't load the digest: {summary.get('message', 'unknown error')}")
    elif not summary.get("summary"):
        st.info("No release activity in this window.")
    else:
        rows = summary["summary"]
        total = sum(r["count"] for r in rows)
        products_touched = len({r["product"] for r in rows})

        m1, m2, m3 = st.columns(3)
        m1.metric("Total updates", total)
        m2.metric("Products touched", products_touched)
        m3.metric("Window", f"{days_back} days")

        df = pd.DataFrame(rows)
        st.markdown("#### By product")
        chart_df = df.groupby("product")["count"].sum().sort_values(ascending=False).head(15)
        st.bar_chart(chart_df)

        st.markdown("#### Breakdown")
        st.dataframe(
            df.rename(
                columns={
                    "product": "Product",
                    "type": "Type",
                    "count": "Count",
                    "latest": "Most recent",
                }
            ),
            use_container_width=True,
            hide_index=True,
        )

        csv_bytes = df.to_csv(index=False).encode("utf-8")
        st.download_button(
            "Export CSV",
            data=csv_bytes,
            file_name=f"cloudcomms_digest_{days_back}d.csv",
            mime="text/csv",
            icon="\U0001f4e5",
        )

with col_status:
    st.markdown("#### Live status")
    health = fetch_service_health(active_only=True)
    if health.get("status") == "error":
        st.warning("Status feed unavailable right now.")
    else:
        render_incident_banner(health.get("incidents", []))

st.divider()
st.page_link("app.py", label="Back to chat", icon="\U0001f4e1")
