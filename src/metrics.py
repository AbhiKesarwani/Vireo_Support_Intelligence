"""
src/metrics.py — Policy-based business metrics.

All numeric constants come from src/config.py.
No hardcoded values in this file.

Metrics computed:
  frt_minutes          first_response_at_ist - created_at_ist
  handle_time_minutes  resolved_at_ist - first_response_at_ist
  sla_target_min       from SLA_TARGETS_MIN[channel]
  sla_breach           frt_minutes > sla_target_min (policy §4)
  sla_credit_cost      sla_breach * SLA_BREACH_CREDIT
  channel_contact_cost CHANNEL_CONTACT_COST[channel]
  transfer_cost        transfers * TRANSFER_COST (only helpdesk; see D-14b)
  is_legacy_transfer   flag for legacy_fd transfers (policy contradiction)
  total_ticket_cost    contact + sla_credit + transfer
  repeat_eligible      True if resolved_at <= RIGHT_CENSOR_DATE (D-09)
"""

from __future__ import annotations

import pandas as pd
import numpy as np

from src.config import (
    SLA_TARGETS_MIN,
    CHANNEL_CONTACT_COST,
    SLA_BREACH_CREDIT,
    TRANSFER_COST,
    RIGHT_CENSOR_DATE,
    SOURCE_HELPDESK,
)


# ══════════════════════════════════════════════════════════════════════════════
#  A. First Response Time
# ══════════════════════════════════════════════════════════════════════════════

def calc_frt(df: pd.DataFrame) -> pd.DataFrame:
    """
    frt_minutes = first_response_at_ist - created_at_ist (in minutes).
    Negative values are invalid and flagged (should be zero after normalization).
    """
    df = df.copy()
    delta = df["first_response_at_ist"] - df["created_at_ist"]
    df["frt_minutes"] = delta.dt.total_seconds() / 60.0

    # Flag any remaining negatives (should not exist, but guard explicitly)
    neg_frt = df["frt_minutes"].notna() & (df["frt_minutes"] < 0)
    n_neg = int(neg_frt.sum())
    if n_neg > 0:
        raise ValueError(
            f"{n_neg} tickets have negative FRT after timestamp normalization. "
            f"This should be zero. Investigate tickets: "
            f"{df.loc[neg_frt, 'ticket_id'].head(5).tolist()}"
        )

    return df


# ══════════════════════════════════════════════════════════════════════════════
#  B. Handle Time
# ══════════════════════════════════════════════════════════════════════════════

def calc_handle_time(df: pd.DataFrame) -> pd.DataFrame:
    """
    handle_time_minutes = resolved_at_ist - first_response_at_ist (in minutes).
    Only populated for resolved/closed tickets.
    Negative values raise an error.
    """
    df = df.copy()
    has_resolution = df["resolved_at_ist"].notna()
    delta = df["resolved_at_ist"] - df["first_response_at_ist"]
    df["handle_time_minutes"] = np.where(has_resolution, delta.dt.total_seconds() / 60.0, np.nan)

    neg_ht = df["handle_time_minutes"].notna() & (df["handle_time_minutes"] < 0)
    n_neg = int(neg_ht.sum())
    if n_neg > 0:
        raise ValueError(
            f"{n_neg} tickets have negative handle time after timestamp normalization. "
            f"Tickets: {df.loc[neg_ht, 'ticket_id'].head(5).tolist()}"
        )

    return df


# ══════════════════════════════════════════════════════════════════════════════
#  C. SLA breach
# ══════════════════════════════════════════════════════════════════════════════

def calc_sla(df: pd.DataFrame) -> pd.DataFrame:
    """
    SLA targets from policy §4 (SLA_TARGETS_MIN).
    sla_breach = True if frt_minutes > sla_target_min AND frt is populated.
    sla_credit_cost = SLA_BREACH_CREDIT per breach.
    """
    df = df.copy()

    # Map SLA target per channel
    df["sla_target_min"] = df["channel"].map(SLA_TARGETS_MIN)

    unmapped_channels = df[df["sla_target_min"].isna() & df["channel"].notna()]["channel"].unique()
    if len(unmapped_channels) > 0:
        raise ValueError(
            f"SLA target not defined for channels: {unmapped_channels}. "
            f"Add to SLA_TARGETS_MIN in config.py."
        )

    # Breach: frt exists AND exceeds target
    frt_available = df["frt_minutes"].notna() & df["sla_target_min"].notna()
    df["sla_breach"] = False
    df.loc[frt_available, "sla_breach"] = (
        df.loc[frt_available, "frt_minutes"] > df.loc[frt_available, "sla_target_min"]
    )

    df["sla_credit_cost"] = np.where(df["sla_breach"], SLA_BREACH_CREDIT, 0)

    return df


# ══════════════════════════════════════════════════════════════════════════════
#  D. Contact cost
# ══════════════════════════════════════════════════════════════════════════════

def calc_contact_cost(df: pd.DataFrame) -> pd.DataFrame:
    """
    Channel-specific contact cost from policy §7 (CHANNEL_CONTACT_COST).
    Applied to all canonical tickets regardless of resolution status.
    """
    df = df.copy()
    df["channel_contact_cost"] = df["channel"].map(CHANNEL_CONTACT_COST)

    unmapped = df[df["channel_contact_cost"].isna() & df["channel"].notna()]["channel"].unique()
    if len(unmapped) > 0:
        raise ValueError(f"Contact cost not defined for channels: {unmapped}")

    return df


# ══════════════════════════════════════════════════════════════════════════════
#  E. Transfer cost  (D-14b: legacy transfers are a contradiction)
# ══════════════════════════════════════════════════════════════════════════════

def calc_transfer_cost(df: pd.DataFrame) -> pd.DataFrame:
    """
    Policy §8: transfers exist in helpdesk only.
    Legacy_fd rows contain non-zero transfers (332 rows) — policy contradiction D-14b.

    We calculate:
      transfers_num           parsed numeric transfers
      is_legacy_transfer      True for legacy_fd rows with transfers > 0
      transfer_cost           Rs 305 * transfers_num  (ONLY for helpdesk rows)
      transfer_cost_legacy    same but for legacy rows (flagged, not used in primary cost model)
    """
    df = df.copy()

    df["transfers_num"] = pd.to_numeric(df["transfers"], errors="coerce").fillna(0).astype(int)
    df["is_legacy_transfer"] = (
        (df["source_system"] == SOURCE_HELPDESK) == False  # noqa (legacy rows)
    ) & (df["transfers_num"] > 0)

    # Transfer cost: only for helpdesk rows (policy-consistent)
    helpdesk_mask = df["source_system"] == SOURCE_HELPDESK
    df["transfer_cost"] = np.where(
        helpdesk_mask,
        df["transfers_num"] * TRANSFER_COST,
        0
    )

    # Record legacy transfer cost separately (informational only)
    df["transfer_cost_legacy_flagged"] = np.where(
        df["is_legacy_transfer"],
        df["transfers_num"] * TRANSFER_COST,
        0
    )

    return df


# ══════════════════════════════════════════════════════════════════════════════
#  F. Total ticket cost
# ══════════════════════════════════════════════════════════════════════════════

def calc_total_cost(df: pd.DataFrame) -> pd.DataFrame:
    """
    total_ticket_cost = channel_contact_cost + sla_credit_cost + transfer_cost
    (transfer_cost only counts helpdesk transfers per D-14b)
    """
    df = df.copy()
    df["total_ticket_cost"] = (
        df["channel_contact_cost"].fillna(0) +
        df["sla_credit_cost"].fillna(0) +
        df["transfer_cost"].fillna(0)
    )
    return df


# ══════════════════════════════════════════════════════════════════════════════
#  G. Repeat eligibility  (D-09)
# ══════════════════════════════════════════════════════════════════════════════

def flag_repeat_eligible(df: pd.DataFrame) -> pd.DataFrame:
    """
    D-09: tickets resolved after RIGHT_CENSOR_DATE cannot yet have generated
    a repeat contact within the 30-day window before the dataset ends.
    Exclude from repeat rate denominator.
    """
    df = df.copy()
    censor_date = pd.Timestamp(RIGHT_CENSOR_DATE)

    df["repeat_eligible"] = (
        df["resolved_at_ist"].notna() &
        (df["resolved_at_ist"] <= censor_date)
    )

    return df


# ══════════════════════════════════════════════════════════════════════════════
#  H. Refund numeric
# ══════════════════════════════════════════════════════════════════════════════

def parse_refund(df: pd.DataFrame) -> pd.DataFrame:
    """Parse refund_amount_inr as numeric and flag replacement_issued."""
    df = df.copy()
    df["refund_amount_num"] = pd.to_numeric(df["refund_amount_inr"], errors="coerce")
    df["has_refund"] = df["refund_amount_num"].notna()
    df["has_replacement"] = df["replacement_issued"] == "Y"
    df["has_both"] = df["has_refund"] & df["has_replacement"]
    return df


# ══════════════════════════════════════════════════════════════════════════════
#  I. Master metrics function
# ══════════════════════════════════════════════════════════════════════════════

def compute_all_metrics(df: pd.DataFrame) -> pd.DataFrame:
    """
    Apply all metric calculations in correct dependency order.
    Requires normalized timestamps from clean.py.
    """
    df = calc_frt(df)
    df = calc_handle_time(df)
    df = calc_sla(df)
    df = calc_contact_cost(df)
    df = calc_transfer_cost(df)
    df = calc_total_cost(df)
    df = flag_repeat_eligible(df)
    df = parse_refund(df)
    return df


# ══════════════════════════════════════════════════════════════════════════════
#  J. Metrics summary
# ══════════════════════════════════════════════════════════════════════════════

def metrics_summary(df: pd.DataFrame) -> dict:
    """Return a summary of all key business metrics."""
    canonical = df[~df.get("is_duplicate", pd.Series(False, index=df.index))]

    n = len(canonical)
    sla_available = canonical["sla_breach"].notna().sum()
    n_breach = int(canonical["sla_breach"].sum())
    breach_rate = round(n_breach / sla_available * 100, 3) if sla_available > 0 else 0.0

    total_contact_cost = int(canonical["channel_contact_cost"].sum())
    total_sla_credit = int(canonical["sla_credit_cost"].sum())
    total_transfer_cost = int(canonical["transfer_cost"].sum())
    total_cost = int(canonical["total_ticket_cost"].sum())

    transfer_tickets = int((canonical["transfers_num"] > 0).sum())
    transfer_rate = round(transfer_tickets / n * 100, 2) if n > 0 else 0.0

    n_repeat_eligible = int(canonical["repeat_eligible"].sum())

    by_channel = {}
    for ch, grp in canonical.groupby("channel"):
        by_channel[ch] = {
            "tickets": int(len(grp)),
            "sla_breach_count": int(grp["sla_breach"].sum()),
            "sla_breach_rate_pct": round(grp["sla_breach"].mean() * 100, 2),
            "contact_cost_total": int(grp["channel_contact_cost"].sum()),
        }

    return {
        "canonical_tickets": n,
        "sla_breach_count": n_breach,
        "sla_breach_rate_pct": breach_rate,
        "sla_credit_exposure_inr": total_sla_credit,
        "total_contact_cost_inr": total_contact_cost,
        "total_transfer_cost_inr": total_transfer_cost,
        "total_cost_inr": total_cost,
        "transfer_ticket_count": transfer_tickets,
        "transfer_rate_pct": transfer_rate,
        "repeat_eligible_tickets": n_repeat_eligible,
        "csat_mean": round(float(canonical["csat_score_clean"].mean()), 4),
        "csat_response_rate_pct": round(canonical["csat_score_clean"].notna().mean() * 100, 2),
        "auto_closed_count": int(canonical["is_auto_closed"].sum()),
        "auto_closed_rate_pct": round(canonical["is_auto_closed"].mean() * 100, 2),
        "refund_ticket_count": int(canonical["has_refund"].sum()),
        "refund_total_inr": int(canonical["refund_amount_num"].sum()),
        "replacement_count": int(canonical["has_replacement"].sum()),
        "refund_and_replacement_count": int(canonical["has_both"].sum()),
        "by_channel": by_channel,
    }
