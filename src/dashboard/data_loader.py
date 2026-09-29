"""
src/dashboard/data_loader.py — Data loading layer for Streamlit dashboard.

Loads pre-computed, verified Parquet outputs.
CODE CALCULATES. AI INTERPRETS. HUMANS DECIDE.
Never recalculates or invents business metrics on the fly.
"""

from __future__ import annotations

import functools
import json
from pathlib import Path
from typing import Any, Dict
import pandas as pd
import streamlit as st

from src.config import (
    BUSINESS_METRICS_PARQUET,
    CHANNEL_ISSUE_METRICS_PARQUET,
    CSAT_METRICS_PARQUET,
    DATA_PROCESSED,
    ISSUE_METRICS_PARQUET,
    OUTPUTS,
    PHASE4_QUALITY_REPORT,
    PRODUCT_ISSUE_METRICS_PARQUET,
    REPEAT_ECONOMICS_PARQUET,
    SLA_METRICS_PARQUET,
    TEAM_METRICS_PARQUET,
    TIER1_LEADERBOARD_PARQUET,
    TIER1_WEEKLY_LEADERBOARD_PARQUET,
    TIER2_OPERATIONS_PARQUET,
    WEEKLY_METRICS_PARQUET,
)
from src.business_metrics import compute_business_kpis
from src.repeat_economics import calculate_repeat_economics


# Compatibility guard for Streamlit 1.64+ when loaded outside of streamlit run
if not hasattr(st, "_main"):
    try:
        st._main = type("DummyMain", (), {"_id": "main"})()
    except Exception:
        pass


@st.cache_data(show_spinner=False)
def load_business_metrics() -> pd.DataFrame:
    """Load canonical enriched ticket-level dataset (11,875 tickets)."""
    return pd.read_parquet(BUSINESS_METRICS_PARQUET)


@st.cache_data(show_spinner=False)
def load_weekly_metrics() -> pd.DataFrame:
    """Load weekly aggregations (79 weeks)."""
    return pd.read_parquet(WEEKLY_METRICS_PARQUET)


@st.cache_data(show_spinner=False)
def load_issue_metrics() -> pd.DataFrame:
    """Load operational issue summary table."""
    return pd.read_parquet(ISSUE_METRICS_PARQUET)


@st.cache_data(show_spinner=False)
def load_channel_issue_metrics() -> pd.DataFrame:
    """Load channel x issue cross-tabulation."""
    return pd.read_parquet(CHANNEL_ISSUE_METRICS_PARQUET)


@st.cache_data(show_spinner=False)
def load_product_issue_metrics() -> pd.DataFrame:
    """Load product x issue cross-tabulation."""
    return pd.read_parquet(PRODUCT_ISSUE_METRICS_PARQUET)


@st.cache_data(show_spinner=False)
def load_tier1_leaderboard() -> pd.DataFrame:
    """Load policy-compliant Tier 1 volume leaderboard (38 agents)."""
    return pd.read_parquet(TIER1_LEADERBOARD_PARQUET)


@st.cache_data(show_spinner=False)
def load_tier1_weekly_leaderboard() -> pd.DataFrame:
    """Load policy-compliant weekly Tier 1 volume leaderboard."""
    return pd.read_parquet(TIER1_WEEKLY_LEADERBOARD_PARQUET)


@st.cache_data(show_spinner=False)
def load_tier2_operations() -> pd.DataFrame:
    """Load Tier 2 operational visibility table (6 agents) with active open cases."""
    df = pd.read_parquet(TIER2_OPERATIONS_PARQUET).copy()
    bm_df = load_business_metrics()
    opens = bm_df[bm_df["status"].isin(["open", "pending"])].groupby("agent_id").size().to_dict()
    df["open_cases"] = df["agent_id"].map(opens).fillna(0).astype(int)
    return df


@st.cache_data(show_spinner=False)
def load_team_metrics() -> pd.DataFrame:
    """Load team-level performance metrics."""
    return pd.read_parquet(TEAM_METRICS_PARQUET)


@st.cache_data(show_spinner=False)
def load_sla_metrics() -> pd.DataFrame:
    """Load multi-dimensional SLA metrics."""
    return pd.read_parquet(SLA_METRICS_PARQUET)


@st.cache_data(show_spinner=False)
def load_csat_metrics() -> pd.DataFrame:
    """Load multi-dimensional CSAT metrics."""
    return pd.read_parquet(CSAT_METRICS_PARQUET)


@st.cache_data(show_spinner=False)
def load_repeat_economics_table() -> pd.DataFrame:
    """Load dimensional repeat economics summary table."""
    return pd.read_parquet(REPEAT_ECONOMICS_PARQUET)


@st.cache_data(show_spinner=False)
def load_repeat_summary() -> Dict[str, Any]:
    """Calculate repeat economics and scenario targets from canonical data."""
    df = load_business_metrics()
    return calculate_repeat_economics(df)


@st.cache_data(show_spinner=False)
def load_executive_kpis() -> Dict[str, Any]:
    """Get verified executive KPI scorecard values."""
    df = load_business_metrics()
    return compute_business_kpis(df)


@st.cache_data(show_spinner=False)
def load_quality_report() -> Dict[str, Any]:
    """Load the Phase 4 quality & reconciliation report JSON."""
    if PHASE4_QUALITY_REPORT.exists():
        with open(PHASE4_QUALITY_REPORT, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}
