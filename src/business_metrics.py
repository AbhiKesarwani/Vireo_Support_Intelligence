"""
src/business_metrics.py — Core business metrics computation and ticket-level KPI enrichment.

CODE CALCULATES. AI INTERPRETS.
Enforces all policy rules from support-policy.pdf v3.2 and decisions D-01 through D-14.
"""

from __future__ import annotations

from typing import Any, Dict, Optional
import pandas as pd
import numpy as np

from src.config import (
    BLENDED_CONTACT_COST,
    BUSINESS_METRICS_PARQUET,
    CHANNEL_CONTACT_COST,
    CSAT_VALID_MAX,
    CSAT_VALID_MIN,
    RIGHT_CENSOR_DATE,
    SLA_BREACH_CREDIT,
    TRANSFER_COST,
)


def compute_business_kpis(df: pd.DataFrame) -> Dict[str, Any]:
    """
    Calculate executive-level aggregate business KPIs from enriched ticket dataset.
    """
    total_tickets = len(df)
    total_contact_cost = float(df["channel_contact_cost"].sum())
    total_sla_credit = float(df["sla_credit_cost"].sum())
    total_transfer_cost = float(df["transfer_cost"].sum())
    total_ticket_cost = float(df["total_ticket_cost"].sum())

    sla_breaches = int(df["sla_breach"].sum())
    sla_breach_rate = round(sla_breaches / total_tickets, 4) if total_tickets > 0 else 0.0

    transfers_count = int((df["transfers_num"] > 0).sum())
    transfer_rate = round(transfers_count / total_tickets, 4) if total_tickets > 0 else 0.0

    team_mismatches = int(df["team_mismatch"].sum())
    team_mismatch_rate = round(team_mismatches / total_tickets, 4) if total_tickets > 0 else 0.0

    auto_closed = int(df["is_auto_closed"].sum())
    auto_close_rate = round(auto_closed / total_tickets, 4) if total_tickets > 0 else 0.0

    # CSAT
    valid_csat = df[df["csat_score_clean"].notna()]
    csat_responses = len(valid_csat)
    csat_response_rate = round(csat_responses / total_tickets, 4) if total_tickets > 0 else 0.0
    mean_csat = round(float(valid_csat["csat_score_clean"].mean()), 4) if csat_responses > 0 else 0.0

    # Repeat contact counts
    repeat_candidates = int(df["repeat_candidate"].sum()) if "repeat_candidate" in df.columns else 0
    repeat_contact_cost = float(df["repeat_contact_cost"].sum()) if "repeat_contact_cost" in df.columns else 0.0

    return {
        "total_tickets": total_tickets,
        "total_contact_cost": total_contact_cost,
        "total_sla_credit_exposure": total_sla_credit,
        "total_transfer_cost": total_transfer_cost,
        "total_ticket_cost": total_ticket_cost,
        "sla_breach_count": sla_breaches,
        "sla_breach_rate": sla_breach_rate,
        "transfers_ticket_count": transfers_count,
        "transfer_rate": transfer_rate,
        "team_mismatch_count": team_mismatches,
        "team_mismatch_rate": team_mismatch_rate,
        "auto_closed_count": auto_closed,
        "auto_closed_rate": auto_close_rate,
        "csat_responses": csat_responses,
        "csat_response_rate": csat_response_rate,
        "csat_mean": mean_csat,
        "repeat_candidates_count": repeat_candidates,
        "repeat_contact_cost": repeat_contact_cost,
    }


def build_business_metrics_dataset(
    tickets_with_repeats: pd.DataFrame,
) -> pd.DataFrame:
    """
    Produce the canonical business metrics ticket-level dataset.
    Ensures all financial, operational, and repeat dimensions are preserved.
    """
    df = tickets_with_repeats.copy()

    # Verify no negative values in cost or time columns
    cost_cols = ["channel_contact_cost", "sla_credit_cost", "transfer_cost", "total_ticket_cost", "repeat_contact_cost"]
    for col in cost_cols:
        if col in df.columns:
            neg_mask = df[col] < 0
            if neg_mask.any():
                raise ValueError(f"Found negative values in cost column {col}: {df.loc[neg_mask, col].tolist()}")

    time_cols = ["frt_minutes", "handle_time_minutes"]
    for col in time_cols:
        if col in df.columns:
            neg_mask = df[col] < 0
            if neg_mask.any():
                raise ValueError(f"Found negative values in time column {col}: {df.loc[neg_mask, col].tolist()}")

    return df
