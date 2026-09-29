"""
src/clean.py — Deduplication, timestamp normalization, CSAT correction.

All decisions implemented here are traceable to decision.md:
  D-01: Duplicate handling (keep helpdesk, mark legacy_fd)
  D-02: Legacy resolved_at + 5:30 UTC→IST correction
  D-03: CSAT 0 / blank → NaN
  D-06: Auto-closed flag

Audit trail:
  Every row gets: is_duplicate, duplicate_group_id, source_system_kept, duplicate_reason
  Every timestamp correction is recorded: resolved_at_correction_applied
"""

from __future__ import annotations

import hashlib
import pandas as pd
import numpy as np
from typing import Tuple

from src.config import (
    IST_OFFSET,
    SOURCE_HELPDESK,
    SOURCE_LEGACY,
    CSAT_VALID_MIN,
    CSAT_VALID_MAX,
    CSAT_LEGACY_NO_RESPONSE,
    AUTO_CLOSE_STATUS,
)


# ══════════════════════════════════════════════════════════════════════════════
#  A. Timestamp parsing helpers
# ══════════════════════════════════════════════════════════════════════════════

def _parse_ts(series: pd.Series) -> pd.Series:
    """Parse a datetime column with mixed formats. Returns UTC-naive datetime."""
    return pd.to_datetime(series, format="mixed", dayfirst=False, errors="coerce")


def _to_ist(series: pd.Series) -> pd.Series:
    """Add IST offset to UTC timestamps."""
    return series + IST_OFFSET


# ══════════════════════════════════════════════════════════════════════════════
#  B. Deduplication  (D-01)
# ══════════════════════════════════════════════════════════════════════════════

def reconcile_duplicates(df: pd.DataFrame) -> pd.DataFrame:
    """
    Identify duplicate ticket IDs (migration artifacts).

    Strategy (D-01):
      - Every duplicate pair must be one helpdesk + one legacy_fd row.
      - Keep the helpdesk row as canonical.
      - Mark the legacy_fd row as is_duplicate=True.
      - If a pair is NOT (helpdesk, legacy_fd), raise an error — do not silently resolve.

    Returns the full DataFrame with added columns:
      duplicate_group_id     str | None
      is_duplicate           bool
      source_system_kept     str | None
      duplicate_reason       str | None
    """
    df = df.copy()

    # Initialize audit columns
    df["duplicate_group_id"] = None
    df["is_duplicate"] = False
    df["source_system_kept"] = None
    df["duplicate_reason"] = None

    # Find ticket IDs that appear more than once
    dup_mask = df.duplicated(subset="ticket_id", keep=False)
    dup_df = df[dup_mask].copy()

    if dup_df.empty:
        return df

    # Inspect each duplicate group
    unexpected_pairs = []

    for ticket_id, group in dup_df.groupby("ticket_id"):
        sources = set(group["source_system"].tolist())
        group_id = hashlib.md5(ticket_id.encode()).hexdigest()[:8]

        # Expected: exactly one helpdesk + one legacy_fd
        if sources == {SOURCE_HELPDESK, SOURCE_LEGACY} and len(group) == 2:
            hd_idx = group[group["source_system"] == SOURCE_HELPDESK].index[0]
            lg_idx = group[group["source_system"] == SOURCE_LEGACY].index[0]

            # Mark helpdesk row as canonical
            df.loc[hd_idx, "duplicate_group_id"] = group_id
            df.loc[hd_idx, "is_duplicate"] = False
            df.loc[hd_idx, "source_system_kept"] = SOURCE_HELPDESK
            df.loc[hd_idx, "duplicate_reason"] = "migration_reimport"

            # Mark legacy_fd row as duplicate (to be excluded)
            df.loc[lg_idx, "duplicate_group_id"] = group_id
            df.loc[lg_idx, "is_duplicate"] = True
            df.loc[lg_idx, "source_system_kept"] = SOURCE_HELPDESK
            df.loc[lg_idx, "duplicate_reason"] = "migration_reimport"

        else:
            # Unexpected pair: log but do NOT silently resolve
            unexpected_pairs.append({
                "ticket_id": ticket_id,
                "sources": sorted(sources),
                "count": len(group),
            })

    if unexpected_pairs:
        raise ValueError(
            f"Unexpected duplicate pairs found (not helpdesk+legacy_fd): {unexpected_pairs}\n"
            f"Manual investigation required. Do NOT proceed silently."
        )

    return df


def drop_duplicates_keep_canonical(df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Split into:
      - canonical: is_duplicate == False  (the clean working set)
      - discarded: is_duplicate == True   (preserved for audit)
    """
    canonical = df[~df["is_duplicate"]].copy().reset_index(drop=True)
    discarded = df[df["is_duplicate"]].copy().reset_index(drop=True)
    return canonical, discarded


# ══════════════════════════════════════════════════════════════════════════════
#  C. Timestamp normalization  (D-02)
# ══════════════════════════════════════════════════════════════════════════════

def normalize_timestamps(df: pd.DataFrame) -> pd.DataFrame:
    """
    Parse all timestamp columns and apply +5:30 correction to legacy resolved_at.

    Logic (D-02):
      - created_at, first_response_at: IST as displayed in helpdesk (no correction)
      - resolved_at:
          helpdesk rows: IST as displayed (no correction)
          legacy_fd rows: UTC from event log → add +5:30 → IST

    Adds columns:
      created_at_ist          datetime (no correction applied, just parsed)
      first_response_at_ist   datetime (no correction applied, just parsed)
      resolved_at_ist         datetime (corrected for legacy_fd)
      resolved_at_correction_applied  bool
    """
    df = df.copy()

    df["created_at_ist"] = _parse_ts(df["created_at"])
    df["first_response_at_ist"] = _parse_ts(df["first_response_at"])
    df["resolved_at_raw"] = _parse_ts(df["resolved_at"])

    # Start with raw (no correction)
    df["resolved_at_ist"] = df["resolved_at_raw"].copy()

    # Apply +5:30 to legacy_fd rows where resolved_at is populated
    legacy_mask = (df["source_system"] == SOURCE_LEGACY) & df["resolved_at_raw"].notna()
    df.loc[legacy_mask, "resolved_at_ist"] = _to_ist(df.loc[legacy_mask, "resolved_at_raw"])
    df["resolved_at_correction_applied"] = legacy_mask

    # Validation: after correction, no resolution should be before creation
    resolved_populated = df["resolved_at_ist"].notna()
    neg_before_creation = (
        df.loc[resolved_populated, "resolved_at_ist"] <
        df.loc[resolved_populated, "created_at_ist"]
    )
    n_neg = int(neg_before_creation.sum())
    if n_neg > 0:
        raise ValueError(
            f"After timestamp correction, {n_neg} tickets still have "
            f"resolved_at < created_at. This should be zero. "
            f"Investigate before proceeding."
        )

    # Drop intermediate column
    df.drop(columns=["resolved_at_raw"], inplace=True)

    return df


# ══════════════════════════════════════════════════════════════════════════════
#  D. CSAT correction  (D-03)
# ══════════════════════════════════════════════════════════════════════════════

def fix_csat(df: pd.DataFrame) -> pd.DataFrame:
    """
    Unify CSAT encoding:
      legacy_fd uses 0 for no response.
      helpdesk uses blank (NaN) for no response.
      Policy §6: exclude non-responses from averages.

    Adds column: csat_score_clean (NaN for non-response, 1-5 for valid)
    Preserves original: csat_score (untouched)
    """
    df = df.copy()

    raw = pd.to_numeric(df["csat_score"], errors="coerce")

    # Replace 0 (legacy no-response) and any out-of-range with NaN
    csat_clean = raw.where(
        (raw >= CSAT_VALID_MIN) & (raw <= CSAT_VALID_MAX),
        other=np.nan
    )

    df["csat_score_clean"] = csat_clean

    # Validation: no zeros should remain in csat_score_clean
    n_zeros_remaining = int((df["csat_score_clean"] == 0).sum())
    if n_zeros_remaining > 0:
        raise ValueError(f"CSAT fix left {n_zeros_remaining} zeros in csat_score_clean. Bug.")

    return df


# ══════════════════════════════════════════════════════════════════════════════
#  E. Auto-close flag  (D-06)
# ══════════════════════════════════════════════════════════════════════════════

def flag_auto_closed(df: pd.DataFrame) -> pd.DataFrame:
    """
    policy §8: tickets auto-closed after 72h without reply are status='closed'.
    These count as closed attendance but were not actively resolved by agent.

    Adds column: is_auto_closed (bool)
    """
    df = df.copy()
    df["is_auto_closed"] = df["status"] == AUTO_CLOSE_STATUS
    return df


# ══════════════════════════════════════════════════════════════════════════════
#  F. Time period columns
# ══════════════════════════════════════════════════════════════════════════════

def add_time_periods(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add week, month, quarter columns derived from created_at_ist.
    These are always based on IST-normalized creation timestamp.
    """
    df = df.copy()
    dt = df["created_at_ist"]
    df["week"] = dt.dt.to_period("W").astype(str)
    df["month"] = dt.dt.to_period("M").astype(str)
    df["quarter"] = dt.dt.to_period("Q").astype(str)
    df["year"] = dt.dt.year
    return df


# ══════════════════════════════════════════════════════════════════════════════
#  G. Master clean function
# ══════════════════════════════════════════════════════════════════════════════

def clean_tickets(df_raw: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """
    Full cleaning pipeline for tickets.csv.

    Returns:
      canonical_df    — cleaned, deduplicated tickets (11,875 expected)
      discarded_df    — duplicate rows kept for audit
      audit_summary   — dict of counts and validation results
    """
    # Step 1: Mark duplicates
    df = reconcile_duplicates(df_raw)

    # Step 2: Split canonical vs discarded
    canonical, discarded = drop_duplicates_keep_canonical(df)

    # Step 3: Normalize timestamps
    canonical = normalize_timestamps(canonical)

    # Step 4: Fix CSAT
    canonical = fix_csat(canonical)

    # Step 5: Auto-close flag
    canonical = flag_auto_closed(canonical)

    # Step 6: Time periods
    canonical = add_time_periods(canonical)

    # Build audit summary
    audit = {
        "raw_rows": len(df_raw),
        "duplicate_pairs": int(df["is_duplicate"].sum()),
        "canonical_rows": len(canonical),
        "discarded_rows": len(discarded),
        "timestamp_corrections_applied": int(canonical["resolved_at_correction_applied"].sum()),
        "csat_zeros_corrected": int(
            (pd.to_numeric(df_raw["csat_score"], errors="coerce") == CSAT_LEGACY_NO_RESPONSE).sum()
        ),
        "csat_valid_responses": int(canonical["csat_score_clean"].notna().sum()),
        "csat_response_rate_pct": round(canonical["csat_score_clean"].notna().mean() * 100, 2),
        "csat_mean_corrected": round(float(canonical["csat_score_clean"].mean()), 4),
        "auto_closed_count": int(canonical["is_auto_closed"].sum()),
        "neg_resolved_before_correction": None,  # checked inside normalize_timestamps
        "neg_resolved_after_correction": 0,       # validate_timestamps raises if non-zero
    }

    return canonical, discarded, audit
