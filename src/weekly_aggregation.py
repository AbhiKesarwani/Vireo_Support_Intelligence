"""
src/weekly_aggregation.py — Deterministic weekly business metrics aggregation layer.

CODE CALCULATES. AI INTERPRETS.
Enforces per-week accounting with strict reconciliation to canonical population.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
import pandas as pd
import numpy as np

from src.config import WEEKLY_METRICS_PARQUET


def compute_weekly_metrics(df: pd.DataFrame) -> pd.DataFrame:
    """
    Generate weekly business dataset from canonical enriched tickets.
    Reconciles exactly to canonical population: sum(tickets_created) == len(df).
    """
    # Sort chronologically by week
    weeks = sorted(df["week"].unique())
    rows: List[Dict[str, Any]] = []

    for w in weeks:
        sub = df[df["week"] == w]
        w_start, w_end = w.split("/") if "/" in w else (w, w)

        created_cnt = len(sub)
        resolved_cnt = int((sub["status"] == "resolved").sum())
        closed_cnt = int((sub["status"] == "closed").sum())
        open_cnt = int(sub["status"].isin(["open", "pending"]).sum())

        breaches = int(sub["sla_breach"].sum())
        breach_rate = round(breaches / created_cnt, 4) if created_cnt > 0 else 0.0
        sla_credit = float(sub["sla_credit_cost"].sum())

        contact_cost = float(sub["channel_contact_cost"].sum())
        transfers_cnt = int((sub["transfers_num"] > 0).sum())
        trans_cost = float(sub["transfer_cost"].sum())

        team_mismatches = int(sub["team_mismatch"].sum())
        auto_closed = int(sub["is_auto_closed"].sum())

        valid_csat = sub[sub["csat_score_clean"].notna()]
        csat_cnt = len(valid_csat)
        avg_csat = round(float(valid_csat["csat_score_clean"].mean()), 4) if csat_cnt > 0 else None

        repeat_eligible_cnt = int(sub["repeat_eligible"].sum())
        repeats_cnt = int(sub["repeat_candidate"].sum())
        repeat_rate = round(repeats_cnt / created_cnt, 4) if created_cnt > 0 else 0.0
        repeat_cost = float(sub["repeat_contact_cost"].sum())

        # Top 3 issues in this week
        issue_counts = sub["issue_code"].value_counts()
        top1_name = str(issue_counts.index[0]) if len(issue_counts) > 0 else None
        top1_cnt = int(issue_counts.iloc[0]) if len(issue_counts) > 0 else 0

        top2_name = str(issue_counts.index[1]) if len(issue_counts) > 1 else None
        top2_cnt = int(issue_counts.iloc[1]) if len(issue_counts) > 1 else 0

        top3_name = str(issue_counts.index[2]) if len(issue_counts) > 2 else None
        top3_cnt = int(issue_counts.iloc[2]) if len(issue_counts) > 2 else 0

        rows.append({
            "week": w,
            "week_start": w_start,
            "week_end": w_end,
            "tickets_created": created_cnt,
            "tickets_resolved": resolved_cnt,
            "tickets_closed": closed_cnt,
            "open_tickets": open_cnt,
            "sla_breaches": breaches,
            "sla_breach_rate": breach_rate,
            "sla_credit_exposure": sla_credit,
            "total_contact_cost": contact_cost,
            "transfer_count": transfers_cnt,
            "transfer_cost": trans_cost,
            "team_mismatch_count": team_mismatches,
            "auto_closed_count": auto_closed,
            "csat_responses": csat_cnt,
            "avg_csat": avg_csat,
            "repeat_eligible_tickets": repeat_eligible_cnt,
            "repeat_contacts": repeats_cnt,
            "repeat_contact_rate": repeat_rate,
            "repeat_contact_cost": repeat_cost,
            "top_issue_1": top1_name,
            "top_issue_1_count": top1_cnt,
            "top_issue_2": top2_name,
            "top_issue_2_count": top2_cnt,
            "top_issue_3": top3_name,
            "top_issue_3_count": top3_cnt,
        })

    weekly_df = pd.DataFrame(rows)
    return weekly_df
