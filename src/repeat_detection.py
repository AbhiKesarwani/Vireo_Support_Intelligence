"""
src/repeat_detection.py — Deterministic repeat-contact detection engine.

Policy Definition (§6):
A customer contacting again about the same issue within 30 days of resolution is a repeat contact.

CODE CALCULATES. AI INTERPRETS. HUMANS DECIDE.
The LLM does NOT calculate repeat metrics; this deterministic engine computes them.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
import pandas as pd

from src.config import REPEAT_WINDOW_DAYS, RIGHT_CENSOR_DATE


def detect_repeat_contacts(
    tickets_df: pd.DataFrame,
    extractions_df: Optional[pd.DataFrame] = None,
    repeat_window_days: int = REPEAT_WINDOW_DAYS,
) -> pd.DataFrame:
    """
    Deterministically identify repeat contacts according to support policy §6.

    Inputs:
    - tickets_df: cleaned tickets dataframe with ticket_id, customer_id, created_at_ist,
                  resolved_at_ist, product_sku, status, is_duplicate.
    - extractions_df: dataframe with ticket_id, issue_code, ambiguous.
                      If already present in tickets_df, extractions_df is optional.
    - repeat_window_days: 30 days by policy.

    Outputs:
    A DataFrame with the same rows as input tickets, plus:
    - repeat_candidate: bool (True if this ticket is a repeat contact of a prior ticket)
    - repeat_reason: str (Audit explanation)
    - prior_ticket_id: Optional[str] (ID of prior resolved ticket)
    - days_since_prior_resolution: Optional[float]
    """
    df = tickets_df.copy()

    # Merge extractions if provided separately
    if extractions_df is not None and not extractions_df.empty:
        ext_cols = [c for c in ["issue_code", "sub_issue", "ambiguous", "repeat_claim"] if c in extractions_df.columns]
        if ext_cols:
            # Drop existing if present to avoid collisions
            df = df.drop(columns=[c for c in ext_cols if c in df.columns], errors="ignore")
            df = df.merge(
                extractions_df[["ticket_id"] + ext_cols].drop_duplicates("ticket_id"),
                on="ticket_id",
                how="left",
            )

    # Ensure required columns exist
    if "is_duplicate" not in df.columns:
        df["is_duplicate"] = False
    if "issue_code" not in df.columns:
        df["issue_code"] = "UNKNOWN"
    if "ambiguous" not in df.columns:
        df["ambiguous"] = False

    # Convert timestamps to datetime if strings
    for ts_col in ["created_at_ist", "resolved_at_ist"]:
        if ts_col in df.columns and not pd.api.types.is_datetime64_any_dtype(df[ts_col]):
            df[ts_col] = pd.to_datetime(df[ts_col], errors="coerce")

    # Exclude discarded duplicates from matching
    active_mask = ~df["is_duplicate"].fillna(False)

    # Output columns to populate
    repeat_candidate_col: List[bool] = [False] * len(df)
    repeat_reason_col: List[str] = [""] * len(df)
    prior_ticket_id_col: List[Optional[str]] = [None] * len(df)
    days_since_prior_col: List[Optional[float]] = [None] * len(df)

    # Group valid tickets by customer_id
    # We sort chronologically by created_at_ist, ticket_id
    active_indices = df[active_mask].sort_values(
        by=["created_at_ist", "ticket_id"], na_position="last"
    ).index

    # Group indices by customer_id
    customer_groups: Dict[str, List[int]] = {}
    for idx in active_indices:
        cust_id = df.at[idx, "customer_id"]
        if pd.isna(cust_id) or not str(cust_id).strip():
            continue
        customer_groups.setdefault(str(cust_id), []).append(idx)

    for cust_id, indices in customer_groups.items():
        # Iterate chronologically through this customer's tickets
        for i, curr_idx in enumerate(indices):
            curr_ticket_id = df.at[curr_idx, "ticket_id"]
            curr_issue = df.at[curr_idx, "issue_code"]
            curr_ambiguous = bool(df.at[curr_idx, "ambiguous"])
            curr_created = df.at[curr_idx, "created_at_ist"]
            curr_sku = df.at[curr_idx, "product_sku"]

            # Ambiguous or UNKNOWN issues cannot be reliably matched
            if curr_ambiguous or curr_issue == "UNKNOWN" or pd.isna(curr_issue):
                repeat_candidate_col[curr_idx] = False
                repeat_reason_col[curr_idx] = "ambiguous_or_unknown_issue"
                continue

            if pd.isna(curr_created):
                repeat_candidate_col[curr_idx] = False
                repeat_reason_col[curr_idx] = "missing_creation_timestamp"
                continue

            # Look back at earlier tickets from the same customer
            found_repeat = False
            # Check backwards from most recent prior ticket
            for prior_idx in reversed(indices[:i]):
                prior_ticket_id = df.at[prior_idx, "ticket_id"]
                prior_issue = df.at[prior_idx, "issue_code"]
                prior_ambiguous = bool(df.at[prior_idx, "ambiguous"])
                prior_resolved = df.at[prior_idx, "resolved_at_ist"]
                prior_sku = df.at[prior_idx, "product_sku"]

                # Prior ticket must not be ambiguous/unknown
                if prior_ambiguous or prior_issue == "UNKNOWN" or pd.isna(prior_issue):
                    continue

                # Prior ticket must have been resolved before current ticket was created
                if pd.isna(prior_resolved):
                    continue
                if prior_resolved > curr_created:
                    continue

                # Calculate days between prior resolution and current contact
                delta_seconds = (curr_created - prior_resolved).total_seconds()
                delta_days = delta_seconds / 86400.0

                if delta_days < 0:
                    continue

                if delta_days > float(repeat_window_days):
                    # Outside window
                    continue

                # Issue must match
                if curr_issue != prior_issue:
                    continue

                # Product compatibility check: if both SKUs known, they must match
                if pd.notna(curr_sku) and pd.notna(prior_sku) and str(curr_sku) != str(prior_sku):
                    continue

                # Match confirmed!
                found_repeat = True
                repeat_candidate_col[curr_idx] = True
                repeat_reason_col[curr_idx] = (
                    f"repeat_contact_within_{round(delta_days, 1)}_days_of_resolution"
                )
                prior_ticket_id_col[curr_idx] = str(prior_ticket_id)
                days_since_prior_col[curr_idx] = round(delta_days, 4)
                break

            if not found_repeat:
                repeat_candidate_col[curr_idx] = False
                repeat_reason_col[curr_idx] = "no_prior_matching_resolution_within_30d"

    # Set values in DataFrame
    df["repeat_candidate"] = repeat_candidate_col
    df["repeat_reason"] = repeat_reason_col
    df["prior_ticket_id"] = prior_ticket_id_col
    df["days_since_prior_resolution"] = days_since_prior_col

    return df


def calculate_repeat_metrics(
    tickets_with_repeats: pd.DataFrame,
    right_censor_date: str = RIGHT_CENSOR_DATE,
) -> Dict[str, Any]:
    """
    Calculate repeat contact metrics and First Contact Resolution (FCR)
    with proper right-censoring according to policy §6 and Decision D-09.
    """
    df = tickets_with_repeats.copy()

    # Active canonical tickets only
    if "is_duplicate" in df.columns:
        df = df[~df["is_duplicate"].fillna(False)]

    total_tickets = len(df)
    total_repeat_candidates = int(df["repeat_candidate"].sum())
    incoming_repeat_rate = (
        round(total_repeat_candidates / total_tickets, 4) if total_tickets > 0 else 0.0
    )

    # Right-censored denominator: resolved on or before right_censor_date
    if "resolved_at_ist" in df.columns:
        ts_resolved = pd.to_datetime(df["resolved_at_ist"], errors="coerce")
        censor_dt = pd.to_datetime(right_censor_date)

        resolved_mask = ts_resolved.notna()
        eligible_mask = resolved_mask & (ts_resolved <= censor_dt)
        right_censored_mask = resolved_mask & (ts_resolved > censor_dt)

        denominator = int(eligible_mask.sum())
        right_censored_count = int(right_censored_mask.sum())

        # How many tickets in denominator generated a repeat contact?
        # A ticket generated a repeat if its ticket_id appears in prior_ticket_id of a repeat candidate
        repeated_prior_ids = set(df[df["repeat_candidate"]]["prior_ticket_id"].dropna().unique())
        generated_repeat_count = int(
            df[eligible_mask]["ticket_id"].isin(repeated_prior_ids).sum()
        )
        fcr_count = denominator - generated_repeat_count
        repeat_rate = (
            round(generated_repeat_count / denominator, 4) if denominator > 0 else 0.0
        )
        fcr_rate = round(fcr_count / denominator, 4) if denominator > 0 else 0.0
    else:
        denominator = total_tickets
        right_censored_count = 0
        generated_repeat_count = total_repeat_candidates
        repeat_rate = incoming_repeat_rate
        fcr_rate = round(1.0 - repeat_rate, 4)

    return {
        "total_tickets": total_tickets,
        "total_repeat_candidates": total_repeat_candidates,
        "incoming_repeat_rate": incoming_repeat_rate,
        "right_censored_cutoff": right_censor_date,
        "repeat_eligible_denominator": denominator,
        "right_censored_count": right_censored_count,
        "tickets_generating_repeats": generated_repeat_count,
        "repeat_rate": repeat_rate,
        "fcr_rate": fcr_rate,
    }
