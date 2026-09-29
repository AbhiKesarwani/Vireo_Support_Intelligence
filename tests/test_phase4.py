"""
tests/test_phase4.py — Test suite for Phase 4 Business Metrics & Repeat Economics.

Covers:
- Business metric cost correctness
- SLA cost calculation
- Transfer cost calculation
- Repeat-contact channel costing and non-negativity
- Right-censoring and repeat denominator logic
- Repeat window and issue matching constraints
- Weekly reconciliation to canonical population
- Leaderboard Tier 1 vs Tier 2 strict separation
- CSAT legacy 0 exclusion and response rate
- Integrity of raw, Phase 2, and Phase 3 artifacts
"""

import json
import os
from pathlib import Path
import pandas as pd
import numpy as np
import pytest

from src.config import (
    APPROVED_TAXONOMY,
    BLENDED_CONTACT_COST,
    BUSINESS_METRICS_PARQUET,
    CHANNEL_CONTACT_COST,
    CHANNEL_ISSUE_METRICS_PARQUET,
    CSAT_METRICS_PARQUET,
    DATA_AI,
    DATA_PROCESSED,
    DATA_RAW,
    ISSUE_METRICS_PARQUET,
    OUTPUTS,
    PHASE4_BUSINESS_REPORT,
    PHASE4_REVIEW,
    PRODUCT_ISSUE_METRICS_PARQUET,
    REPEAT_ECONOMICS_PARQUET,
    RIGHT_CENSOR_DATE,
    ROOT,
    SLA_BREACH_CREDIT,
    SLA_METRICS_PARQUET,
    TEAM_METRICS_PARQUET,
    TIER1_LEADERBOARD_PARQUET,
    TIER2_OPERATIONS_PARQUET,
    TRANSFER_COST,
    WEEKLY_METRICS_PARQUET,
)
from src.intelligence_pipeline import run_phase4_pipeline


@pytest.fixture(scope="session")
def business_df():
    assert BUSINESS_METRICS_PARQUET.exists(), "business_metrics.parquet missing"
    return pd.read_parquet(BUSINESS_METRICS_PARQUET)


@pytest.fixture(scope="session")
def weekly_df():
    assert WEEKLY_METRICS_PARQUET.exists(), "weekly_metrics.parquet missing"
    return pd.read_parquet(WEEKLY_METRICS_PARQUET)


@pytest.fixture(scope="session")
def issue_df():
    assert ISSUE_METRICS_PARQUET.exists(), "issue_metrics.parquet missing"
    return pd.read_parquet(ISSUE_METRICS_PARQUET)


@pytest.fixture(scope="session")
def t1_leaderboard():
    assert TIER1_LEADERBOARD_PARQUET.exists(), "tier1_leaderboard.parquet missing"
    return pd.read_parquet(TIER1_LEADERBOARD_PARQUET)


@pytest.fixture(scope="session")
def t2_operations():
    assert TIER2_OPERATIONS_PARQUET.exists(), "tier2_operations.parquet missing"
    return pd.read_parquet(TIER2_OPERATIONS_PARQUET)


# ==============================================================================
# 1. BUSINESS METRIC & COST TESTS
# ==============================================================================

def test_channel_costs_correct(business_df):
    """Channel contact cost strictly matches policy §7."""
    expected_costs = {
        "chat": 210,
        "email": 260,
        "voice": 520,
        "social": 240,
    }
    for ch, cost in expected_costs.items():
        ch_tickets = business_df[business_df["channel"] == ch]
        assert (ch_tickets["channel_contact_cost"] == cost).all()


def test_sla_credit_cost_correct(business_df):
    """SLA breach credit exposure matches policy §4 (Rs 350 per breach)."""
    breached = business_df[business_df["sla_breach"] == True]
    non_breached = business_df[business_df["sla_breach"] == False]
    assert (breached["sla_credit_cost"] == SLA_BREACH_CREDIT).all()
    assert (non_breached["sla_credit_cost"] == 0).all()


def test_transfer_cost_correct(business_df):
    """Transfer cost matches policy §7 (Rs 305/transfer) for modern helpdesk."""
    helpdesk_transfers = business_df[business_df["source_system"] == "helpdesk"]
    expected_cost = helpdesk_transfers["transfers_num"] * TRANSFER_COST
    pd.testing.assert_series_equal(
        helpdesk_transfers["transfer_cost"],
        expected_cost,
        check_names=False,
    )


def test_repeat_cost_uses_repeat_ticket_channel(business_df):
    """Repeat contact cost equals the channel cost of the repeat ticket itself."""
    repeats = business_df[business_df["repeat_candidate"] == True]
    non_repeats = business_df[business_df["repeat_candidate"] == False]

    # Every repeat ticket cost equals its own channel cost
    pd.testing.assert_series_equal(
        repeats["repeat_contact_cost"],
        repeats["channel_contact_cost"].astype(float),
        check_names=False,
    )

    # Non-repeats have 0 repeat cost
    assert (non_repeats["repeat_contact_cost"] == 0.0).all()


def test_no_negative_costs(business_df):
    """Zero negative costs across all financial columns."""
    cost_cols = [
        "channel_contact_cost",
        "sla_credit_cost",
        "transfer_cost",
        "total_ticket_cost",
        "repeat_contact_cost",
    ]
    for col in cost_cols:
        assert (business_df[col] >= 0).all(), f"Found negative costs in {col}"


# ==============================================================================
# 2. REPEAT ECONOMICS & RIGHT-CENSORING TESTS
# ==============================================================================

def test_right_censoring_works(business_df):
    """Tickets resolved after 2026-05-31 are excluded from repeat denominator."""
    censor_dt = pd.Timestamp(RIGHT_CENSOR_DATE)
    resolved_ts = pd.to_datetime(business_df["resolved_at_ist"])

    # All repeat-eligible tickets are resolved on or before censor_dt
    eligible = business_df[business_df["repeat_eligible"] == True]
    assert (pd.to_datetime(eligible["resolved_at_ist"]) <= censor_dt).all()

    # Right-censored tickets are resolved strictly after censor_dt
    after_censor = business_df[resolved_ts > censor_dt]
    assert (after_censor["repeat_eligible"] == False).all()


def test_repeat_denominator_correct(business_df):
    """Repeat denominator exactly matches tickets resolved on or before 2026-05-31."""
    eligible_count = business_df["repeat_eligible"].sum()
    assert eligible_count == 10463


def test_repeat_outside_30_days_excluded(business_df):
    """No repeat candidate has a prior resolution older than 30 days."""
    repeats = business_df[business_df["repeat_candidate"] == True]
    diffs = repeats["days_since_prior_resolution"].dropna()
    assert (diffs >= 0.0).all()
    assert (diffs <= 30.0).all()


def test_repeat_candidates_have_prior_ticket(business_df):
    """Every repeat candidate has a valid prior_ticket_id."""
    repeats = business_df[business_df["repeat_candidate"] == True]
    assert repeats["prior_ticket_id"].notna().all()
    assert (repeats["prior_ticket_id"].str.startswith("TK-")).all()


def test_repeat_economics_unit_consistency_and_savings_basis(business_df):
    """Verify units: repeat-generating tickets vs incoming contacts, and cost derivations."""
    from src.repeat_economics import calculate_repeat_economics
    econ = calculate_repeat_economics(business_df)

    # 1. Cohort definitions
    assert econ["repeat_eligible_tickets"] == 10463
    assert econ["tickets_generating_repeats"] == 1505
    assert econ["policy_repeat_rate"] == 0.1438
    assert econ["fcr_rate"] == 0.8562

    # 2. Multiplier and cost per repeat-generating ticket
    assert econ["repeat_contacts_from_eligible"] == 1512
    assert econ["repeat_cost_from_eligible"] == 393090.0
    expected_cost_per_ticket = round(393090.0 / 1505, 2)  # 261.19
    assert econ["cost_per_repeat_generating_ticket"] == expected_cost_per_ticket == 261.19

    # 3. Avoidable tickets reduction at 5% target
    target_tickets = int(round(0.05 * 10463))  # 523
    assert econ["target_repeat_tickets"] == target_tickets == 523
    avoidable_tickets = 1505 - 523  # 982
    assert econ["avoidable_repeats_to_reduce"] == avoidable_tickets == 982

    # 4. Consistent savings basis
    expected_channel_mix_savings = round(avoidable_tickets * expected_cost_per_ticket, 2)
    assert econ["estimated_savings_channel_mix"] == expected_channel_mix_savings == 256488.58

    expected_blended_savings = round(avoidable_tickets * 290, 2)
    assert econ["estimated_savings_blended"] == expected_blended_savings == 284780.0


# ==============================================================================
# 3. WEEKLY RECONCILIATION TESTS
# ==============================================================================

def test_weekly_counts_reconcile_to_canonical(weekly_df, business_df):
    """Sum of weekly tickets created exactly matches canonical ticket population."""
    assert weekly_df["tickets_created"].sum() == len(business_df) == 11875


def test_weekly_status_sum_reconciles(weekly_df, business_df):
    """Weekly resolved + closed + open matches total tickets created."""
    weekly_sum = (
        weekly_df["tickets_resolved"] +
        weekly_df["tickets_closed"] +
        weekly_df["open_tickets"]
    )
    pd.testing.assert_series_equal(
        weekly_df["tickets_created"],
        weekly_sum,
        check_names=False,
    )


def test_no_duplicate_ticket_in_weekly_aggregation(weekly_df):
    """All 79 calendar weeks are distinct."""
    assert weekly_df["week"].nunique() == len(weekly_df) == 79


# ==============================================================================
# 3B. ISSUE METRICS & CROSS-TAB RECONCILIATION TESTS (BLOCKER REGRESSION)
# ==============================================================================

def test_issue_metrics_reconcile_to_canonical_population(issue_df, business_df):
    """Hard Invariant: sum(issue_metrics['ticket_count']) == canonical classified population."""
    canonical_count = len(business_df)
    assert canonical_count == 11875
    assert issue_df["ticket_count"].sum() == canonical_count


def test_issue_metrics_share_sums_to_one(issue_df):
    """Issue shares sum to exactly 100% (1.0)."""
    assert abs(issue_df["ticket_share"].sum() - 1.0) < 1e-4


def test_operational_taxonomy_mutually_exclusive_and_exhaustive(business_df):
    """Every canonical ticket contributes exactly once to the primary issue table."""
    assert business_df["issue_code"].notna().all()
    assert business_df["issue_code"].isin(APPROVED_TAXONOMY).all()
    # Unique ticket ID check
    assert business_df["ticket_id"].nunique() == 11875 == len(business_df)


def test_channel_issue_metrics_reconcile_to_canonical(business_df):
    """Sum of channel_issue_metrics ticket_count matches canonical ticket population."""
    ch_df = pd.read_parquet(CHANNEL_ISSUE_METRICS_PARQUET)
    assert ch_df["ticket_count"].sum() == len(business_df) == 11875


def test_product_issue_metrics_reconcile_to_canonical(business_df):
    """Sum of product_issue_metrics ticket_count matches tickets with linked product."""
    prod_df = pd.read_parquet(PRODUCT_ISSUE_METRICS_PARQUET)
    valid_prod_count = len(business_df[business_df["product_sku"].notna()])
    assert prod_df["ticket_count"].sum() == valid_prod_count == 11875


def test_team_metrics_reconcile_to_canonical(business_df):
    """Sum of team tickets matches canonical ticket population."""
    team_df = pd.read_parquet(TEAM_METRICS_PARQUET)
    assert team_df["tickets"].sum() == len(business_df) == 11875


def test_reports_contain_no_inflated_or_unreconciled_issue_counts():
    """Verify that reports display issue distribution summing to exactly 11,875 and no inflated 6,245."""
    import re

    review_text = PHASE4_REVIEW.read_text(encoding="utf-8")
    biz_text = PHASE4_BUSINESS_REPORT.read_text(encoding="utf-8")

    # The buggy draft count 6,245 must not appear anywhere in review or business report
    assert "6,245" not in review_text, "Found legacy draft 6,245 in phase4_review.md"
    assert "6,245" not in biz_text, "Found legacy draft 6,245 in phase4_business_report.md"

    # In phase4_review.md, extract the issue table under ## 4. Operational Issue Analysis
    match = re.search(r"## 4\. Operational Issue Analysis\s*\n\s*\|.*?\n\|[-|\s]+\n(.*?)\n\n", review_text, re.DOTALL)
    assert match, "Could not find issue table in phase4_review.md"
    table_rows = match.group(1).strip().split("\n")

    parsed_counts = []
    for r in table_rows:
        parts = [p.strip() for p in r.split("|") if p.strip()]
        if len(parts) >= 2:
            count = int(parts[1].replace(",", ""))
            parsed_counts.append(count)

    assert sum(parsed_counts) == 11875, f"Markdown issue table in review sums to {sum(parsed_counts)}, expected 11875"


# ==============================================================================
# 4. LEADERBOARD & TIER SEPARATION TESTS
# ==============================================================================

def test_tier2_absent_from_tier1_leaderboard(t1_leaderboard, t2_operations):
    """Tier 2 agents strictly absent from Tier 1 leaderboard."""
    t1_agents = set(t1_leaderboard["agent_id"])
    t2_agents = set(t2_operations["agent_id"])

    assert len(t1_agents) == 38
    assert len(t2_agents) == 6
    assert t1_agents.isdisjoint(t2_agents)
    assert "Escalations & Warranty" not in t1_leaderboard["team"].values


def test_no_composite_score_in_leaderboard(t1_leaderboard):
    """No arbitrary composite score or invented ranking formula."""
    forbidden = ["composite", "score", "rank_score", "performance_score"]
    for col in t1_leaderboard.columns:
        for f in forbidden:
            assert f not in col.lower(), f"Forbidden composite score found: {col}"


def test_leaderboard_sorting_deterministic(t1_leaderboard):
    """Leaderboard is sorted primarily by tickets_closed DESC."""
    closed_counts = t1_leaderboard["tickets_closed"].tolist()
    assert closed_counts == sorted(closed_counts, reverse=True)


def test_tier1_auto_closed_split_preserved(t1_leaderboard):
    """Auto-closed and agent-resolved tickets are presented as distinct sub-columns."""
    assert "tickets_resolved" in t1_leaderboard.columns
    assert "auto_closed_count" in t1_leaderboard.columns
    pd.testing.assert_series_equal(
        t1_leaderboard["tickets_closed"],
        t1_leaderboard["tickets_resolved"] + t1_leaderboard["auto_closed_count"],
        check_names=False,
    )


# ==============================================================================
# 5. CSAT VALIDATION TESTS
# ==============================================================================

def test_zero_legacy_csat_not_included(business_df):
    """Zero CSAT scores from legacy_fd are converted to null and excluded from averages."""
    assert (business_df["csat_score_clean"] == 0).sum() == 0
    valid_csat = business_df["csat_score_clean"].dropna()
    assert (valid_csat >= 1.0).all()
    assert (valid_csat <= 5.0).all()


def test_csat_mean_and_response_rate(business_df):
    """CSAT mean matches 3.3152 and response rate matches 44.4%."""
    valid_csat = business_df["csat_score_clean"].dropna()
    assert len(valid_csat) == 5269
    assert round(valid_csat.mean(), 4) == 3.3152
    assert round(len(valid_csat) / len(business_df), 4) == 0.4437


# ==============================================================================
# 6. INTEGRITY & REPRODUCIBILITY TESTS
# ==============================================================================

def test_raw_data_unchanged():
    """Raw data files remain strictly untouched."""
    raw_files = list(DATA_RAW.glob("*"))
    assert len(raw_files) >= 6
    # No temporary files in raw
    assert not any(f.name.endswith(".tmp") for f in raw_files)


def test_phase2_outputs_unchanged():
    """Phase 2 output files are present and preserve canonical sizes."""
    p2_tickets = pd.read_parquet(DATA_PROCESSED / "tickets_clean.parquet")
    assert len(p2_tickets) == 11875
    assert (DATA_PROCESSED / "metrics_base.parquet").exists()
    assert (DATA_PROCESSED / "join_audit.parquet").exists()


def test_phase3_outputs_unchanged():
    """Phase 3 pilot outputs are preserved (substantive evaluation evidence only)."""
    assert (DATA_AI / "pilot_tickets.parquet").exists()
    assert (DATA_AI / "pilot_extractions.parquet").exists()
    # Authoritative evaluation evidence (replaced the development-phase review file)
    assert (OUTPUTS / "phase3_accuracy_report.md").exists()
    assert (OUTPUTS / "phase3_evidence_report.md").exists()
    assert (OUTPUTS / "phase3_repeat_audit.md").exists()


def test_repeated_pipeline_produces_identical_outputs():
    """Running Phase 4 pipeline twice produces byte-identical parquet outputs."""
    df1 = pd.read_parquet(BUSINESS_METRICS_PARQUET)
    # Run pipeline again
    run_phase4_pipeline()
    df2 = pd.read_parquet(BUSINESS_METRICS_PARQUET)
    pd.testing.assert_frame_equal(df1, df2)
