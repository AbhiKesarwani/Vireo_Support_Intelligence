"""
src/repeat_economics.py — Deterministic repeat-contact economics and savings scenario modeling.

Policy §6 & Decision D-08:
A repeat contact is a contact from the same customer regarding the same issue
within 30 days of prior resolution.

CODE CALCULATES. AI INTERPRETS.
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Tuple
import pandas as pd
import numpy as np

from src.config import (
    BLENDED_CONTACT_COST,
    CHANNEL_CONTACT_COST,
    RAW_TO_OPERATIONAL_TAXONOMY,
    REPEAT_CONTACT_TARGET,
    REPEAT_ECONOMICS_PARQUET,
    REPEAT_WINDOW_DAYS,
    RIGHT_CENSOR_DATE,
)
from src.repeat_detection import detect_repeat_contacts


def enrich_tickets_with_issues(
    clean_df: pd.DataFrame,
    ext_df: Optional[pd.DataFrame] = None,
) -> pd.DataFrame:
    """
    Enrich canonical tickets with operational issue_code.
    Uses AI extractions where available (e.g. pilot), otherwise maps
    the 11 intake categories to the 8 operational categories.
    """
    df = clean_df.copy()
    if "issue_code" not in df.columns or df["issue_code"].isna().all():
        df["issue_code"] = df["category"].map(RAW_TO_OPERATIONAL_TAXONOMY).fillna("UNKNOWN")

    if ext_df is not None and not ext_df.empty:
        ext_map = dict(zip(ext_df["ticket_id"], ext_df["issue_code"]))
        df["issue_code"] = df["ticket_id"].map(ext_map).fillna(df["issue_code"])

    return df


def build_tickets_with_repeats(
    clean_df: pd.DataFrame,
    ext_df: Optional[pd.DataFrame] = None,
) -> pd.DataFrame:
    """
    Run full-history deterministic repeat contact detection and attach repeat contact costs.
    """
    df = enrich_tickets_with_issues(clean_df, ext_df)
    with_repeats = detect_repeat_contacts(df, repeat_window_days=REPEAT_WINDOW_DAYS)

    # Cost of repeat ticket: channel_contact_cost of the repeat ticket itself
    with_repeats["repeat_contact_cost"] = np.where(
        with_repeats["repeat_candidate"],
        with_repeats["channel_contact_cost"].fillna(0.0),
        0.0,
    )

    return with_repeats


def calculate_repeat_economics(
    tickets_with_repeats: pd.DataFrame,
    right_censor_date: str = RIGHT_CENSOR_DATE,
    target_rate: float = REPEAT_CONTACT_TARGET,
) -> Dict[str, Any]:
    """
    Compute comprehensive repeat economics, right-censoring metrics,
    and target savings scenarios.
    """
    df = tickets_with_repeats.copy()
    total_tickets = len(df)
    total_contact_cost = float(df["channel_contact_cost"].sum())

    # Incoming repeat contacts
    repeats_mask = df["repeat_candidate"].fillna(False)
    total_repeat_contacts = int(repeats_mask.sum())
    total_repeat_cost = float(df.loc[repeats_mask, "repeat_contact_cost"].sum())
    avg_repeat_cost = (
        round(total_repeat_cost / total_repeat_contacts, 2)
        if total_repeat_contacts > 0
        else 0.0
    )
    incoming_repeat_rate = (
        round(total_repeat_contacts / total_tickets, 4) if total_tickets > 0 else 0.0
    )

    # Right-censored denominator: resolved on or before right_censor_date
    censor_dt = pd.to_datetime(right_censor_date)
    resolved_ts = pd.to_datetime(df["resolved_at_ist"], errors="coerce")

    # Repeat eligible = resolved and resolved <= censor_dt
    eligible_mask = resolved_ts.notna() & (resolved_ts <= censor_dt)
    repeat_eligible_count = int(eligible_mask.sum())

    # Right-censored = resolved and resolved > censor_dt
    right_censored_mask = resolved_ts.notna() & (resolved_ts > censor_dt)
    right_censored_count = int(right_censored_mask.sum())

    # Unresolved = resolved_at is NaT
    unresolved_count = int(resolved_ts.isna().sum())

    # Numerator for repeat rate: how many tickets in repeat_eligible generated a repeat within 30d?
    repeated_prior_ids = set(df.loc[repeats_mask, "prior_ticket_id"].dropna().unique())
    tickets_generating_repeats = int(
        df.loc[eligible_mask, "ticket_id"].isin(repeated_prior_ids).sum()
    )
    resolved_repeat_rate = (
        round(tickets_generating_repeats / repeat_eligible_count, 4)
        if repeat_eligible_count > 0
        else 0.0
    )
    fcr_rate = round(1.0 - resolved_repeat_rate, 4)

    # Unit Reconciliation & Derivation:
    # 1. Repeat contacts caused specifically by tickets in the repeat_eligible cohort
    eligible_ticket_ids = set(df.loc[eligible_mask, "ticket_id"])
    repeats_from_eligible = df.loc[repeats_mask & df["prior_ticket_id"].isin(eligible_ticket_ids)]
    repeat_contacts_from_eligible = len(repeats_from_eligible)
    repeat_cost_from_eligible = float(repeats_from_eligible["repeat_contact_cost"].sum())

    # Multiplier: average incoming repeat contacts per repeat-generating ticket
    repeat_contact_multiplier = (
        round(repeat_contacts_from_eligible / tickets_generating_repeats, 5)
        if tickets_generating_repeats > 0
        else 1.0
    )

    # Average cost per repeat-generating ticket (exact unit match for tickets_generating_repeats)
    cost_per_repeat_ticket = (
        round(repeat_cost_from_eligible / tickets_generating_repeats, 2)
        if tickets_generating_repeats > 0
        else 0.0
    )

    # Average cost per repeat contact within eligible cohort
    avg_cohort_repeat_cost = (
        round(repeat_cost_from_eligible / repeat_contacts_from_eligible, 2)
        if repeat_contacts_from_eligible > 0
        else 0.0
    )

    # Savings scenario model (planning target)
    target_repeat_count = int(round(target_rate * repeat_eligible_count))
    avoidable_reduced_count = max(0, tickets_generating_repeats - target_repeat_count)

    # Consistent Savings Calculations:
    # Method A: Channel-mix cost per repeat-generating ticket (or eliminated repeat contacts * cohort avg contact cost)
    savings_channel_mix = round(avoidable_reduced_count * cost_per_repeat_ticket, 2)
    # Method B: Policy planning standard (Rs 290) per ticket reduced
    savings_blended = round(avoidable_reduced_count * BLENDED_CONTACT_COST, 2)

    return {
        "total_tickets": total_tickets,
        "total_contact_cost": total_contact_cost,
        "incoming_repeat_contacts": total_repeat_contacts,
        "incoming_repeat_rate": incoming_repeat_rate,
        "total_repeat_cost": total_repeat_cost,
        "average_repeat_cost": avg_repeat_cost,
        "repeat_cost_share_pct": round(total_repeat_cost / total_contact_cost * 100, 2) if total_contact_cost > 0 else 0.0,
        "right_censored_cutoff": right_censor_date,
        "repeat_eligible_tickets": repeat_eligible_count,
        "right_censored_tickets": right_censored_count,
        "unresolved_tickets": unresolved_count,
        "tickets_generating_repeats": tickets_generating_repeats,
        "policy_repeat_rate": resolved_repeat_rate,
        "fcr_rate": fcr_rate,
        "planning_target_rate": target_rate,
        "target_repeat_tickets": target_repeat_count,
        "avoidable_repeats_to_reduce": avoidable_reduced_count,
        "repeat_contacts_from_eligible": repeat_contacts_from_eligible,
        "repeat_cost_from_eligible": repeat_cost_from_eligible,
        "repeat_contact_multiplier": repeat_contact_multiplier,
        "cost_per_repeat_generating_ticket": cost_per_repeat_ticket,
        "avg_cohort_repeat_cost": avg_cohort_repeat_cost,
        "estimated_savings_channel_mix": savings_channel_mix,
        "estimated_savings_blended": savings_blended,
    }


def build_repeat_economics_table(tickets_with_repeats: pd.DataFrame) -> pd.DataFrame:
    """
    Build a multi-dimensional summary table of repeat contacts and costs
    by channel, issue_code, and product family.
    """
    df = tickets_with_repeats.copy()
    rows = []

    # By Channel
    for ch, grp in df.groupby("channel"):
        reps = grp[grp["repeat_candidate"] == True]
        rows.append({
            "dimension": "channel",
            "segment": ch,
            "total_tickets": len(grp),
            "repeat_contacts": len(reps),
            "repeat_rate": round(len(reps) / len(grp), 4) if len(grp) > 0 else 0.0,
            "repeat_cost": float(reps["repeat_contact_cost"].sum()),
            "avg_cost_per_repeat": round(float(reps["repeat_contact_cost"].sum()) / len(reps), 2) if len(reps) > 0 else 0.0,
        })

    # By Issue Code
    for iss, grp in df.groupby("issue_code"):
        reps = grp[grp["repeat_candidate"] == True]
        rows.append({
            "dimension": "issue_code",
            "segment": iss,
            "total_tickets": len(grp),
            "repeat_contacts": len(reps),
            "repeat_rate": round(len(reps) / len(grp), 4) if len(grp) > 0 else 0.0,
            "repeat_cost": float(reps["repeat_contact_cost"].sum()),
            "avg_cost_per_repeat": round(float(reps["repeat_contact_cost"].sum()) / len(reps), 2) if len(reps) > 0 else 0.0,
        })

    # By Product Family
    for fam, grp in df.groupby("prod_family"):
        if pd.isna(fam):
            fam = "Unknown"
        reps = grp[grp["repeat_candidate"] == True]
        rows.append({
            "dimension": "product_family",
            "segment": str(fam),
            "total_tickets": len(grp),
            "repeat_contacts": len(reps),
            "repeat_rate": round(len(reps) / len(grp), 4) if len(grp) > 0 else 0.0,
            "repeat_cost": float(reps["repeat_contact_cost"].sum()),
            "avg_cost_per_repeat": round(float(reps["repeat_contact_cost"].sum()) / len(reps), 2) if len(reps) > 0 else 0.0,
        })

    return pd.DataFrame(rows)
