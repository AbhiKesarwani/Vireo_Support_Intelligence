"""
app.py — Vireo Audio Support Intelligence Dashboard

Executive CX analytics, operational issue taxonomy, repeat-contact economics,
and agent operations reporting for Vireo Audio (Jan 2025 – Jun 2026).

Usage:
    streamlit run app.py

Principle: CODE CALCULATES. AI INTERPRETS. HUMANS DECIDE.
"""

from __future__ import annotations

import streamlit as st

from src.dashboard.formatting import inject_custom_css
from src.dashboard.views import (
    render_executive_digest,
    render_issue_explorer,
    render_quality_methodology,
    render_repeat_analysis,
    render_tier1_leaderboard,
    render_tier2_operations,
)

st.set_page_config(
    page_title="Vireo Support Intelligence",
    page_icon="🎧",
    layout="wide",
    initial_sidebar_state="expanded",
)

inject_custom_css()

# ── SIDEBAR ────────────────────────────────────────────────────────────────────
st.sidebar.markdown(
    """
    <div style="padding: 1rem 0 0.75rem 0; border-bottom: 1px solid rgba(255,255,255,0.1); margin-bottom: 0.75rem;">
        <div style="font-size: 1.1rem; font-weight: 800; color: #F8FAFC; letter-spacing: -0.01em;">🎧 Vireo Audio</div>
        <div style="font-size: 0.72rem; color: #64748B; text-transform: uppercase; letter-spacing: 0.08em; margin-top: 0.1rem;">
            Support Intelligence
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

page = st.sidebar.radio(
    "Navigate to",
    [
        "📊 Executive Digest",
        "🔍 Issue Explorer",
        "🔄 Repeat Contact Analysis",
        "🏆 Tier-1 Agent Leaderboard",
        "🛠️ Tier-2 Operations",
        "🛡️ Quality & Methodology",
    ],
    index=0,
    label_visibility="collapsed",
)

st.sidebar.markdown(
    """
    <div style="margin-top: 1.25rem; padding: 0.75rem 0.6rem; background: rgba(255,255,255,0.05);
                border-radius: 6px; border: 1px solid rgba(255,255,255,0.08);">
        <div style="font-size: 0.7rem; font-weight: 700; color: #94A3B8; text-transform: uppercase;
                    letter-spacing: 0.06em; margin-bottom: 0.5rem;">Audit Snapshot</div>
        <div style="font-size: 0.78rem; color: #CBD5E1; line-height: 1.75;">
            Canonical: <strong style="color:#F8FAFC;">11,875</strong> tickets<br>
            SLA Breaches: <strong style="color:#F87171;">1,051</strong> (8.85%)<br>
            CSAT: <strong style="color:#F8FAFC;">3.32</strong> / 5.00 (44.37%)<br>
            Repeat Spend: <strong style="color:#FBBF24;">₹4,09,470</strong><br>
            Repeat Rate: <strong style="color:#FBBF24;">14.38%</strong> (eligible)<br>
            Tests Passed: <strong style="color:#34D399;">135 / 135</strong>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

st.sidebar.markdown(
    """
    <div style="margin-top: 1.1rem; padding: 0.5rem 0.6rem; border-top: 1px solid rgba(255,255,255,0.08);">
        <div style="font-size: 0.68rem; color: #475569; line-height: 1.5; font-style: italic;">
            CODE CALCULATES.<br>AI INTERPRETS.<br>HUMANS DECIDE.
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# ── ROUTER ──────────────────────────────────────────────────────────────────────
try:
    if page == "📊 Executive Digest":
        render_executive_digest()
    elif page == "🔍 Issue Explorer":
        render_issue_explorer()
    elif page == "🔄 Repeat Contact Analysis":
        render_repeat_analysis()
    elif page == "🏆 Tier-1 Agent Leaderboard":
        render_tier1_leaderboard()
    elif page == "🛠️ Tier-2 Operations":
        render_tier2_operations()
    elif page == "🛡️ Quality & Methodology":
        render_quality_methodology()
except Exception as e:
    st.error(f"**Application Error:** {str(e)}")
    st.info(
        "Dashboard requires pre-computed pipeline outputs in `data/processed/`. "
        "Run `python -m src.intelligence_pipeline` to regenerate."
    )
