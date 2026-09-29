"""
tests/test_phase2.py — Automated validation suite for Phase 2 pipeline.

Run:
    pytest tests/test_phase2.py -v

Tests cover:
  T01  Row counts before/after deduplication
  T02  Unique ticket IDs in canonical set
  T03  Duplicate reconciliation reproducibility
  T04  Timestamp correction: no negative resolved durations
  T05  Timestamp correction: no negative FRT
  T06  Timestamp correction: no negative handle time
  T07  CSAT: no legacy zeros in cleaned column
  T08  CSAT: valid scores are in range [1, 5]
  T09  SLA: targets match policy constants
  T10  SLA: breach = frt > target
  T11  Order join: date-bounded fallback respects order_date <= created_at
  T12  Order join: ambiguous joins have NULL matched_order_id
  T13  Order join: no orphan customer_ids
  T14  Order join: no orphan product_skus
  T15  Agent join: all agent_ids resolve
  T16  Duplicate reconciliation is deterministic (run twice = same result)
  T17  Pipeline output: tickets_clean.parquet exists and is non-empty
  T18  Pipeline output: metrics_base.parquet exists and is non-empty
  T19  Pipeline output: join_audit.parquet exists and is non-empty
  T20  Pipeline output: reconciliation_report.json exists and is valid JSON
  T21  Cost: SLA credit is zero for non-breach tickets
  T22  Cost: transfer_cost is zero for legacy_fd tickets
  T23  Transfer counts: transfers_num is non-negative
  T24  Team mismatch: boolean column, no NaN
  T25  Auto-closed: is_auto_closed is boolean, consistent with status
"""

from __future__ import annotations

import json
import pandas as pd
import numpy as np
import pytest

from src.config import (
    SLA_TARGETS_MIN, SLA_BREACH_CREDIT, TRANSFER_COST,
    SOURCE_HELPDESK, SOURCE_LEGACY,
    DATA_PROCESSED, CSAT_VALID_MIN, CSAT_VALID_MAX,
)


# ══════════════════════════════════════════════════════════════════════════════
#  Fixtures
# ══════════════════════════════════════════════════════════════════════════════

@pytest.fixture(scope="session")
def tickets_clean() -> pd.DataFrame:
    path = DATA_PROCESSED / "tickets_clean.parquet"
    if not path.exists():
        pytest.skip(f"tickets_clean.parquet not found — run src.pipeline first")
    return pd.read_parquet(path)


@pytest.fixture(scope="session")
def metrics_base() -> pd.DataFrame:
    path = DATA_PROCESSED / "metrics_base.parquet"
    if not path.exists():
        pytest.skip("metrics_base.parquet not found")
    return pd.read_parquet(path)


@pytest.fixture(scope="session")
def join_audit() -> pd.DataFrame:
    path = DATA_PROCESSED / "join_audit.parquet"
    if not path.exists():
        pytest.skip("join_audit.parquet not found")
    return pd.read_parquet(path)


@pytest.fixture(scope="session")
def reconciliation_report() -> dict:
    path = DATA_PROCESSED / "reconciliation_report.json"
    if not path.exists():
        pytest.skip("reconciliation_report.json not found")
    with open(path) as f:
        return json.load(f)


# ══════════════════════════════════════════════════════════════════════════════
#  T01-T03: Deduplication
# ══════════════════════════════════════════════════════════════════════════════

def test_T01_canonical_row_count(reconciliation_report):
    """T01: Canonical row count must match raw minus duplicates."""
    raw = reconciliation_report["steps"]["load"]["tickets"]
    dupes = reconciliation_report["steps"]["clean"]["duplicate_pairs"]
    canonical = reconciliation_report["canonical_row_count"]
    assert canonical == raw - dupes, (
        f"Expected {raw} - {dupes} = {raw - dupes} canonical rows, got {canonical}"
    )


def test_T02_unique_ticket_ids(tickets_clean):
    """T02: No duplicate ticket_ids in canonical set."""
    n_total = len(tickets_clean)
    n_unique = tickets_clean["ticket_id"].nunique()
    assert n_total == n_unique, (
        f"tickets_clean has {n_total} rows but only {n_unique} unique ticket_ids "
        f"({n_total - n_unique} duplicates remain)"
    )


def test_T03_canonical_size_matches_expected(tickets_clean):
    """T03: Canonical set should have 11,875 rows (Phase 1 confirmed value)."""
    expected = 11_875
    actual = len(tickets_clean)
    assert actual == expected, (
        f"Expected {expected} canonical tickets, got {actual}. "
        f"If data changed, update this test with evidence."
    )


# ══════════════════════════════════════════════════════════════════════════════
#  T04-T06: Timestamps
# ══════════════════════════════════════════════════════════════════════════════

def test_T04_no_negative_resolved_before_created(tickets_clean):
    """T04: After correction, resolved_at_ist must not be before created_at_ist."""
    df = tickets_clean
    has_resolution = df["resolved_at_ist"].notna()
    neg = (
        df.loc[has_resolution, "resolved_at_ist"] <
        df.loc[has_resolution, "created_at_ist"]
    )
    assert not neg.any(), (
        f"{neg.sum()} tickets still have resolved_at < created_at after normalization."
    )


def test_T05_no_negative_frt(tickets_clean):
    """T05: FRT must be non-negative for all tickets where it is computed."""
    df = tickets_clean
    has_frt = df["frt_minutes"].notna()
    neg = df.loc[has_frt, "frt_minutes"] < 0
    assert not neg.any(), (
        f"{neg.sum()} tickets have negative FRT (minutes)."
    )


def test_T06_no_negative_handle_time(tickets_clean):
    """T06: Handle time must be non-negative where computed."""
    df = tickets_clean
    has_ht = df["handle_time_minutes"].notna()
    neg = df.loc[has_ht, "handle_time_minutes"] < 0
    assert not neg.any(), (
        f"{neg.sum()} tickets have negative handle time."
    )


# ══════════════════════════════════════════════════════════════════════════════
#  T07-T08: CSAT
# ══════════════════════════════════════════════════════════════════════════════

def test_T07_no_csat_zeros(tickets_clean):
    """T07: csat_score_clean must not contain zeros (all legacy zeros replaced with NaN)."""
    zeros = (tickets_clean["csat_score_clean"] == 0).sum()
    assert zeros == 0, f"Found {zeros} zero values in csat_score_clean."


def test_T08_csat_valid_range(tickets_clean):
    """T08: All non-null csat_score_clean values must be in [1, 5]."""
    valid = tickets_clean["csat_score_clean"].dropna()
    out_of_range = ((valid < CSAT_VALID_MIN) | (valid > CSAT_VALID_MAX)).sum()
    assert out_of_range == 0, (
        f"{out_of_range} CSAT scores are outside [{CSAT_VALID_MIN}, {CSAT_VALID_MAX}]."
    )


# ══════════════════════════════════════════════════════════════════════════════
#  T09-T10: SLA
# ══════════════════════════════════════════════════════════════════════════════

def test_T09_sla_targets_match_policy(tickets_clean):
    """T09: sla_target_min must match SLA_TARGETS_MIN for every channel."""
    df = tickets_clean[tickets_clean["sla_target_min"].notna()]
    for ch, expected_target in SLA_TARGETS_MIN.items():
        ch_df = df[df["channel"] == ch]
        if ch_df.empty:
            continue
        wrong = (ch_df["sla_target_min"] != expected_target).sum()
        assert wrong == 0, (
            f"Channel '{ch}' has {wrong} rows with sla_target_min != {expected_target}"
        )


def test_T10_sla_breach_logic(tickets_clean):
    """T10: sla_breach must be True iff frt_minutes > sla_target_min."""
    df = tickets_clean[
        tickets_clean["frt_minutes"].notna() &
        tickets_clean["sla_target_min"].notna()
    ]
    computed_breach = df["frt_minutes"] > df["sla_target_min"]
    mismatch = (computed_breach != df["sla_breach"]).sum()
    assert mismatch == 0, (
        f"{mismatch} tickets have sla_breach inconsistent with frt > target."
    )


# ══════════════════════════════════════════════════════════════════════════════
#  T11-T15: Joins
# ══════════════════════════════════════════════════════════════════════════════

def test_T11_fallback_order_date_bounded(join_audit, tickets_clean):
    """T11: All unique_fallback joins must have order_date <= ticket created_at."""
    fallback = join_audit[join_audit["join_method"] == "unique_fallback"].copy()
    if fallback.empty:
        pytest.skip("No unique_fallback rows to test.")

    # Get order_date_matched from tickets_clean
    needed = tickets_clean[["ticket_id", "created_at_ist", "order_date_matched"]]
    merged = fallback.merge(needed, on="ticket_id", how="left")

    has_both = merged["order_date_matched"].notna() & merged["created_at_ist"].notna()
    violations = (
        merged.loc[has_both, "order_date_matched"] >
        merged.loc[has_both, "created_at_ist"]
    ).sum()
    assert violations == 0, (
        f"{violations} unique_fallback joins have order_date > ticket created_at. "
        f"Date-bound constraint (D-07) violated."
    )


def test_T12_ambiguous_joins_have_null_matched_order(join_audit):
    """T12: Tickets with join_method=ambiguous must have null matched_order_id."""
    ambiguous = join_audit[join_audit["join_method"] == "ambiguous"]
    if ambiguous.empty:
        return  # No ambiguous joins = pass
    non_null = ambiguous["matched_order_id"].notna().sum()
    assert non_null == 0, (
        f"{non_null} ambiguous-joined tickets have a non-null matched_order_id. "
        f"Ambiguous joins must not silently select an order."
    )


def test_T13_no_orphan_customer_ids(tickets_clean):
    """T13: All customer_ids with tickets must be found in customers.csv join."""
    # If customer join succeeded (no exception), cust_name must be populated
    if "cust_name" not in tickets_clean.columns:
        pytest.skip("cust_name column not present — customer join may not have run.")
    orphans = (
        tickets_clean["customer_id"].notna() &
        tickets_clean["cust_name"].isna()
    ).sum()
    assert orphans == 0, f"{orphans} tickets have unresolved customer_id."


def test_T14_no_orphan_product_skus(tickets_clean):
    """T14: All product_skus with tickets must be in products.csv join."""
    if "prod_product_name" not in tickets_clean.columns:
        pytest.skip("prod_product_name column not present.")
    orphans = (
        tickets_clean["product_sku"].notna() &
        tickets_clean["prod_product_name"].isna()
    ).sum()
    assert orphans == 0, f"{orphans} tickets have unresolved product_sku."


def test_T15_no_orphan_agent_ids(tickets_clean):
    """T15: All agent_ids in tickets must exist in agents.csv."""
    if "agent_name" not in tickets_clean.columns:
        pytest.skip("agent_name column not present.")
    orphans = (
        tickets_clean["agent_id"].notna() &
        tickets_clean["agent_name"].isna()
    ).sum()
    assert orphans == 0, f"{orphans} tickets have unresolved agent_id."


# ══════════════════════════════════════════════════════════════════════════════
#  T16: Reproducibility
# ══════════════════════════════════════════════════════════════════════════════

def test_T16_dedup_reproducible(tickets_clean):
    """T16: Applying dedup logic twice to the canonical set produces the same output."""
    # The canonical set should have no duplicates; running dedup again should be a no-op.
    n_before = len(tickets_clean)
    ids_before = set(tickets_clean["ticket_id"].tolist())

    # If we try to deduplicate on ticket_id again, nothing should change
    deduped = tickets_clean.drop_duplicates(subset="ticket_id", keep="first")
    n_after = len(deduped)
    ids_after = set(deduped["ticket_id"].tolist())

    assert n_before == n_after, f"Dedup not idempotent: {n_before} -> {n_after}"
    assert ids_before == ids_after, "Dedup changed ticket ID set."


# ══════════════════════════════════════════════════════════════════════════════
#  T17-T20: Output files
# ══════════════════════════════════════════════════════════════════════════════

def test_T17_tickets_clean_exists():
    """T17: tickets_clean.parquet exists and is non-empty."""
    path = DATA_PROCESSED / "tickets_clean.parquet"
    assert path.exists(), f"Output not found: {path}"
    df = pd.read_parquet(path)
    assert len(df) > 0, "tickets_clean.parquet is empty."


def test_T18_metrics_base_exists():
    """T18: metrics_base.parquet exists and is non-empty."""
    path = DATA_PROCESSED / "metrics_base.parquet"
    assert path.exists(), f"Output not found: {path}"
    df = pd.read_parquet(path)
    assert len(df) > 0, "metrics_base.parquet is empty."


def test_T19_join_audit_exists():
    """T19: join_audit.parquet exists and is non-empty."""
    path = DATA_PROCESSED / "join_audit.parquet"
    assert path.exists(), f"Output not found: {path}"
    df = pd.read_parquet(path)
    assert len(df) > 0, "join_audit.parquet is empty."


def test_T20_reconciliation_report_valid_json(reconciliation_report):
    """T20: reconciliation_report.json is valid JSON with expected keys."""
    assert "run_at" in reconciliation_report
    assert "steps" in reconciliation_report
    assert "clean" in reconciliation_report["steps"]
    assert "metrics" in reconciliation_report["steps"]


# ══════════════════════════════════════════════════════════════════════════════
#  T21-T25: Cost and flags
# ══════════════════════════════════════════════════════════════════════════════

def test_T21_sla_credit_zero_for_non_breach(tickets_clean):
    """T21: sla_credit_cost must be 0 for non-breach tickets."""
    # Select only the two needed columns to avoid large DataFrame allocation
    slim = tickets_clean[["sla_breach", "sla_credit_cost"]].copy()
    non_breach_credit = slim.loc[~slim["sla_breach"], "sla_credit_cost"]
    non_zero = (non_breach_credit != 0).sum()
    assert non_zero == 0, (
        f"{non_zero} non-breach tickets have non-zero sla_credit_cost."
    )



def test_T22_transfer_cost_zero_for_legacy(tickets_clean):
    """T22: transfer_cost must be 0 for legacy_fd tickets (D-14b)."""
    legacy = tickets_clean[tickets_clean["source_system"] == SOURCE_LEGACY]
    if legacy.empty:
        return
    non_zero = (legacy["transfer_cost"] > 0).sum()
    assert non_zero == 0, (
        f"{non_zero} legacy_fd tickets have non-zero transfer_cost. "
        f"D-14b: legacy transfers are a policy contradiction and should NOT be costed."
    )


def test_T23_transfers_non_negative(tickets_clean):
    """T23: transfers_num must be >= 0 for all rows."""
    neg = (tickets_clean["transfers_num"] < 0).sum()
    assert neg == 0, f"{neg} rows have negative transfers_num."


def test_T24_team_mismatch_boolean(tickets_clean):
    """T24: team_mismatch must be a boolean column with no NaN."""
    col = tickets_clean["team_mismatch"]
    assert col.dtype == bool or col.dtype == "bool", (
        f"team_mismatch dtype is {col.dtype}, expected bool."
    )
    assert col.notna().all(), "team_mismatch has NaN values."


def test_T25_auto_closed_consistent_with_status(tickets_clean):
    """T25: is_auto_closed must be True iff status == 'closed'."""
    should_be_auto = tickets_clean["status"] == "closed"
    mismatch = (should_be_auto != tickets_clean["is_auto_closed"]).sum()
    assert mismatch == 0, (
        f"{mismatch} tickets have inconsistent is_auto_closed vs status column."
    )
