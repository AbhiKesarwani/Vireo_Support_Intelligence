"""
tests/test_phase6c_weekly_leaderboard.py — Verification of Phase 6C Weekly Tier-1 Leaderboard.

Tests:
1. Tier-1 weekly leaderboard parquet exists and contains required columns.
2. Tier-2 agents are strictly excluded.
3. Every week's closed ticket count reconciles to canonical Tier-1 closed tickets for that week.
4. Total sum across all weeks matches exactly 10,547 (canonical Tier-1 closed tickets).
5. Closed tickets = agent_resolved + auto_closed.
6. Weekly ranks are deterministic (1 to N per week).
7. Manual audit of a specific week and specific agent.
8. Dashboard data loader loads weekly leaderboard properly.
"""

import pandas as pd
import pytest
from src.config import (
    BUSINESS_METRICS_PARQUET,
    TIER1_LEADERBOARD_PARQUET,
    TIER1_WEEKLY_LEADERBOARD_PARQUET,
)
from src.dashboard.data_loader import load_tier1_weekly_leaderboard
from src.leaderboard import compute_tier1_weekly_leaderboard


@pytest.fixture(scope="module")
def business_df():
    return pd.read_parquet(BUSINESS_METRICS_PARQUET)


@pytest.fixture(scope="module")
def weekly_lb():
    return pd.read_parquet(TIER1_WEEKLY_LEADERBOARD_PARQUET)


def test_weekly_leaderboard_schema(weekly_lb):
    """Weekly leaderboard must have all required columns."""
    required = [
        "week", "agent_id", "agent_name", "team", "site", "shift",
        "tickets_closed", "tickets_resolved", "auto_closed_count",
        "sla_breaches", "sla_breach_rate", "csat_responses", "avg_csat",
        "repeat_contacts", "repeat_rate", "weekly_rank"
    ]
    for col in required:
        assert col in weekly_lb.columns, f"Missing column: {col}"
    assert len(weekly_lb) > 0
    assert weekly_lb["week"].nunique() >= 79


def test_tier2_strictly_excluded(weekly_lb, business_df):
    """Tier-2 agents (Escalations & Warranty) must NOT appear in weekly Tier-1 leaderboard."""
    t2_agents = set(business_df[business_df["agent_tier"] == 2]["agent_id"].unique())
    t1_weekly_agents = set(weekly_lb["agent_id"].unique())
    intersection = t2_agents.intersection(t1_weekly_agents)
    assert len(intersection) == 0, f"Found Tier-2 agents in Tier-1 weekly leaderboard: {intersection}"


def test_weekly_closed_reconciliation(weekly_lb, business_df):
    """
    Every week's sum of tickets_closed in weekly_lb must match the canonical Tier-1
    closed tickets for that resolution/closure week in business_metrics.
    """
    t1_df = business_df[business_df["agent_tier"] == 1].copy()
    t1_closed = t1_df[t1_df["status"].isin(["resolved", "closed"])].copy()

    # Check overall total across all weeks
    total_weekly_closed = weekly_lb["tickets_closed"].sum()
    canonical_total = len(t1_closed)
    assert total_weekly_closed == 10547, f"Expected 10,547 closed tickets, got {total_weekly_closed}"
    assert total_weekly_closed == canonical_total

    # Check per-week reconciliation using closure week (resolved_at_ist)
    t1_closed["closure_week"] = pd.to_datetime(t1_closed["resolved_at_ist"]).dt.to_period("W").astype(str)
    weekly_canonical = t1_closed.groupby("closure_week").size()
    weekly_lb_sums = weekly_lb.groupby("week")["tickets_closed"].sum()

    for w in weekly_canonical.index:
        expected = weekly_canonical[w]
        actual = weekly_lb_sums.get(w, 0)
        assert actual == expected, f"Week {w} mismatch: expected {expected}, got {actual}"


def test_tickets_closed_composition(weekly_lb):
    """tickets_closed must equal tickets_resolved + auto_closed_count for every row."""
    mismatches = weekly_lb[
        weekly_lb["tickets_closed"] != (weekly_lb["tickets_resolved"] + weekly_lb["auto_closed_count"])
    ]
    assert len(mismatches) == 0, f"Found {len(mismatches)} rows where closed != resolved + auto_closed"


def test_weekly_ranking_deterministic(weekly_lb):
    """Weekly ranks must start at 1 and be contiguous per week."""
    for week, grp in weekly_lb.groupby("week"):
        ranks = grp["weekly_rank"].tolist()
        expected = list(range(1, len(grp) + 1))
        assert ranks == expected, f"Ranks in week {week} not contiguous 1..N: {ranks[:5]}"

        # Check sort order: tickets_closed descending
        closed_counts = grp["tickets_closed"].tolist()
        assert closed_counts == sorted(closed_counts, reverse=True), f"Week {week} not sorted by tickets_closed DESC"


def test_manual_week_and_agent_audit(weekly_lb, business_df):
    """Audit one specific week and one specific agent manually against raw business metrics."""
    test_week = "2025-01-06/2025-01-12"
    week_lb_rows = weekly_lb[weekly_lb["week"] == test_week]

    t1_df = business_df[business_df["agent_tier"] == 1].copy()
    t1_closed = t1_df[t1_df["status"].isin(["resolved", "closed"])].copy()
    t1_closed["closure_week"] = pd.to_datetime(t1_closed["resolved_at_ist"]).dt.to_period("W").astype(str)
    week_closed_raw = t1_closed[t1_closed["closure_week"] == test_week]

    assert week_lb_rows["tickets_closed"].sum() == len(week_closed_raw)

    # Pick an agent in this week
    sample_agent = week_lb_rows.iloc[0]["agent_id"]
    agent_lb = week_lb_rows[week_lb_rows["agent_id"] == sample_agent].iloc[0]

    agent_raw = week_closed_raw[week_closed_raw["agent_id"] == sample_agent]
    agent_raw_res = (agent_raw["status"] == "resolved").sum()
    agent_raw_auto = agent_raw["is_auto_closed"].sum()

    assert agent_lb["tickets_resolved"] == agent_raw_res
    assert agent_lb["auto_closed_count"] == agent_raw_auto
    assert agent_lb["tickets_closed"] == agent_raw_res + agent_raw_auto


def test_data_loader_tier1_weekly():
    """load_tier1_weekly_leaderboard must return the cached DataFrame with expected columns."""
    df = load_tier1_weekly_leaderboard()
    assert isinstance(df, pd.DataFrame)
    assert len(df) > 0
    assert "weekly_rank" in df.columns
    assert "tickets_closed" in df.columns


def test_tier1_tier2_unresolved_decomposition(business_df):
    """
    Tier-1 closed + Tier-2 closed + unresolved (open/pending) must exactly equal 11,875.
    Policy §8 invariant verification.
    """
    t1_closed = business_df[(business_df["agent_tier"] == 1) & (business_df["status"].isin(["resolved", "closed"]))]
    t2_closed = business_df[(business_df["agent_tier"] == 2) & (business_df["status"].isin(["resolved", "closed"]))]
    unresolved = business_df[business_df["status"].isin(["open", "pending"])]

    assert len(t1_closed) == 10547, f"Expected 10,547 Tier-1 closed, got {len(t1_closed)}"
    assert len(t2_closed) == 719, f"Expected 719 Tier-2 closed, got {len(t2_closed)}"
    assert len(unresolved) == 609, f"Expected 609 unresolved tickets, got {len(unresolved)}"

    total_decomposed = len(t1_closed) + len(t2_closed) + len(unresolved)
    assert total_decomposed == len(business_df) == 11875

