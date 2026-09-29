"""
src/leaderboard.py — Policy-compliant Tier 1 Leaderboard and Tier 2 Operational reporting.

Policy §8 & Decision D-05, D-06:
- Tier 2 agents must NOT be compared with Tier 1 on volume metrics.
- Tier 1 leaderboard only; segmented by team.
- No composite score; sort primarily by tickets_closed DESC.
- Auto-closed and agent-resolved shown distinctly.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
import pandas as pd
import numpy as np

from src.config import (
    TIER1_LEADERBOARD_PARQUET,
    TIER1_WEEKLY_LEADERBOARD_PARQUET,
    TIER2_OPERATIONS_PARQUET,
    TEAM_METRICS_PARQUET,
)


def compute_tier1_weekly_leaderboard(df: pd.DataFrame) -> pd.DataFrame:
    """
    Build policy-compliant weekly Tier 1 volume leaderboard.
    Strictly excludes Tier 2 agents.
    Per-week ranking by tickets_closed DESC, avg_csat DESC, sla_breach_rate ASC, agent_id ASC.
    """
    # Filter strictly to Tier 1 closed tickets (resolved or auto-closed)
    # Grouping is based on ticket's resolution/closure week, NOT creation week
    t1_df = df[df["agent_tier"] == 1].copy()
    closed_mask = (t1_df["status"] == "resolved") | (t1_df["is_auto_closed"])
    t1_closed = t1_df[closed_mask].copy()

    # Determine closure week from resolved_at_ist timestamp
    closure_dt = pd.to_datetime(t1_closed["resolved_at_ist"])
    t1_closed["closure_week"] = closure_dt.dt.to_period("W").astype(str)

    rows = []
    for (week, agent_id), grp in t1_closed.groupby(["closure_week", "agent_id"]):
        agent_name = grp["agent_name"].iloc[0] if "agent_name" in grp.columns else agent_id
        team = grp["agent_team"].iloc[0] if "agent_team" in grp.columns else "Unknown"
        site = grp["agent_site"].iloc[0] if "agent_site" in grp.columns else "Unknown"
        shift = grp["agent_shift"].iloc[0] if "agent_shift" in grp.columns else "Unknown"

        # Resolved by agent vs Auto-closed
        agent_resolved = int((grp["status"] == "resolved").sum())
        auto_closed = int(grp["is_auto_closed"].sum())
        total_closed = agent_resolved + auto_closed

        # SLA
        tot_tickets = len(grp)
        breaches = int(grp["sla_breach"].sum())
        breach_rate = round(breaches / tot_tickets, 4) if tot_tickets > 0 else 0.0

        # CSAT
        valid_csat = grp[grp["csat_score_clean"].notna()]
        csat_cnt = len(valid_csat)
        csat_resp_rate = round(csat_cnt / tot_tickets, 4) if tot_tickets > 0 else 0.0
        avg_csat = round(float(valid_csat["csat_score_clean"].mean()), 4) if csat_cnt > 0 else None

        # Transfers & Repeats
        transfers_cnt = int((grp["transfers_num"] > 0).sum()) if "transfers_num" in grp.columns else 0
        repeats_cnt = int(grp["repeat_candidate"].sum()) if "repeat_candidate" in grp.columns else 0
        repeat_rate = round(repeats_cnt / tot_tickets, 4) if tot_tickets > 0 else 0.0

        rows.append({
            "week": week,
            "agent_id": agent_id,
            "agent_name": agent_name,
            "team": team,
            "site": site,
            "shift": shift,
            "tickets_closed": total_closed,
            "tickets_resolved": agent_resolved,
            "auto_closed_count": auto_closed,
            "sla_breaches": breaches,
            "sla_breach_rate": breach_rate,
            "csat_responses": csat_cnt,
            "avg_csat": avg_csat,
            "csat_response_rate": csat_resp_rate,
            "transfer_count": transfers_cnt,
            "repeat_contacts": repeats_cnt,
            "repeat_rate": repeat_rate,
        })

    lb_df = pd.DataFrame(rows)

    # Sort deterministically within each week: tickets_closed DESC, avg_csat DESC, sla_breach_rate ASC, agent_id ASC
    lb_df["csat_sort_key"] = lb_df["avg_csat"].fillna(-1.0)
    lb_df = lb_df.sort_values(
        by=["week", "tickets_closed", "csat_sort_key", "sla_breach_rate", "agent_id"],
        ascending=[True, False, False, True, True],
    ).drop(columns=["csat_sort_key"]).reset_index(drop=True)

    # Compute weekly rank per week
    lb_df["weekly_rank"] = lb_df.groupby("week").cumcount() + 1

    return lb_df


def compute_tier1_leaderboard(df: pd.DataFrame) -> pd.DataFrame:
    """
    Build policy-compliant Tier 1 volume leaderboard.
    Strictly excludes Tier 2 agents.
    Deterministic sorting: tickets_closed DESC, avg_csat DESC, sla_breach_rate ASC, agent_id ASC.
    """
    # Filter strictly to Tier 1
    t1_df = df[df["agent_tier"] == 1].copy()

    rows = []
    for agent_id, grp in t1_df.groupby("agent_id"):
        agent_name = grp["agent_name"].iloc[0] if "agent_name" in grp.columns else agent_id
        team = grp["agent_team"].iloc[0] if "agent_team" in grp.columns else "Unknown"
        site = grp["agent_site"].iloc[0] if "agent_site" in grp.columns else "Unknown"
        shift = grp["agent_shift"].iloc[0] if "agent_shift" in grp.columns else "Unknown"

        # Resolved by agent vs Auto-closed
        agent_resolved = int((grp["status"] == "resolved").sum())
        auto_closed = int(grp["is_auto_closed"].sum())
        total_closed = agent_resolved + auto_closed  # Policy §8 / D-06

        # SLA
        tot_tickets = len(grp)
        breaches = int(grp["sla_breach"].sum())
        breach_rate = round(breaches / tot_tickets, 4) if tot_tickets > 0 else 0.0

        # CSAT (valid responses only)
        valid_csat = grp[grp["csat_score_clean"].notna()]
        csat_cnt = len(valid_csat)
        csat_resp_rate = round(csat_cnt / tot_tickets, 4) if tot_tickets > 0 else 0.0
        avg_csat = round(float(valid_csat["csat_score_clean"].mean()), 4) if csat_cnt > 0 else None

        # Transfers & Repeats
        transfers_cnt = int((grp["transfers_num"] > 0).sum())
        repeats_cnt = int(grp["repeat_candidate"].sum()) if "repeat_candidate" in grp.columns else 0
        repeat_rate = round(repeats_cnt / tot_tickets, 4) if tot_tickets > 0 else 0.0

        rows.append({
            "agent_id": agent_id,
            "agent_name": agent_name,
            "team": team,
            "site": site,
            "shift": shift,
            "tickets_closed": total_closed,
            "tickets_resolved": agent_resolved,
            "auto_closed_count": auto_closed,
            "sla_breach_rate": breach_rate,
            "avg_csat": avg_csat,
            "csat_response_rate": csat_resp_rate,
            "transfer_count": transfers_cnt,
            "repeat_contacts": repeats_cnt,
            "repeat_rate": repeat_rate,
        })

    lb_df = pd.DataFrame(rows)

    # Sort deterministically: tickets_closed DESC, avg_csat DESC (nulls last), sla_breach_rate ASC, agent_id ASC
    lb_df["csat_sort_key"] = lb_df["avg_csat"].fillna(-1.0)
    lb_df = lb_df.sort_values(
        by=["tickets_closed", "csat_sort_key", "sla_breach_rate", "agent_id"],
        ascending=[False, False, True, True],
    ).drop(columns=["csat_sort_key"]).reset_index(drop=True)

    return lb_df


def compute_tier2_operations(df: pd.DataFrame) -> pd.DataFrame:
    """
    Build operational reporting for Tier 2 (Escalations & Warranty).
    NOT a volume leaderboard — focuses on case resolution times, CSAT, and SLA.
    """
    t2_df = df[df["agent_tier"] == 2].copy()

    rows = []
    for agent_id, grp in t2_df.groupby("agent_id"):
        agent_name = grp["agent_name"].iloc[0] if "agent_name" in grp.columns else agent_id
        team = grp["agent_team"].iloc[0] if "agent_team" in grp.columns else "Escalations & Warranty"
        site = grp["agent_site"].iloc[0] if "agent_site" in grp.columns else "Unknown"
        shift = grp["agent_shift"].iloc[0] if "agent_shift" in grp.columns else "Unknown"

        resolved_cases = grp[grp["resolved_at_ist"].notna()].copy()
        cases_resolved = len(resolved_cases)

        # Resolution days
        if cases_resolved > 0:
            diff_days = (resolved_cases["resolved_at_ist"] - resolved_cases["created_at_ist"]).dt.total_seconds() / 86400.0
            median_res_days = round(float(diff_days.median()), 2)
            avg_res_days = round(float(diff_days.mean()), 2)
        else:
            median_res_days = None
            avg_res_days = None

        # CSAT
        valid_csat = grp[grp["csat_score_clean"].notna()]
        csat_cnt = len(valid_csat)
        avg_csat = round(float(valid_csat["csat_score_clean"].mean()), 4) if csat_cnt > 0 else None

        # SLA
        breaches = int(grp["sla_breach"].sum())
        breach_rate = round(breaches / len(grp), 4) if len(grp) > 0 else 0.0

        rows.append({
            "agent_id": agent_id,
            "agent_name": agent_name,
            "team": team,
            "site": site,
            "shift": shift,
            "cases_resolved": cases_resolved,
            "median_resolution_days": median_res_days,
            "avg_resolution_days": avg_res_days,
            "avg_csat": avg_csat,
            "csat_responses": csat_cnt,
            "sla_breaches": breaches,
            "sla_breach_rate": breach_rate,
        })

    t2_ops = pd.DataFrame(rows).sort_values("cases_resolved", ascending=False).reset_index(drop=True)
    return t2_ops


def compute_team_metrics(df: pd.DataFrame) -> pd.DataFrame:
    """
    Build team-level operational metrics including team mismatches and transfer indicators.
    """
    tot_tickets = len(df)
    rows = []

    for team, grp in df.groupby("agent_team"):
        cnt = len(grp)
        share = round(cnt / tot_tickets, 4) if tot_tickets > 0 else 0.0
        transfers_cnt = int((grp["transfers_num"] > 0).sum())
        mismatches = int(grp["team_mismatch"].sum())

        breaches = int(grp["sla_breach"].sum())
        breach_rate = round(breaches / cnt, 4) if cnt > 0 else 0.0

        valid_csat = grp[grp["csat_score_clean"].notna()]
        avg_csat = round(float(valid_csat["csat_score_clean"].mean()), 4) if len(valid_csat) > 0 else None

        repeats = grp[grp["repeat_candidate"] == True] if "repeat_candidate" in grp.columns else pd.DataFrame()
        rep_rate = round(len(repeats) / cnt, 4) if cnt > 0 else 0.0
        tot_cost = float(grp["total_ticket_cost"].sum())

        rows.append({
            "team": team,
            "tickets": cnt,
            "share": share,
            "transfers": transfers_cnt,
            "team_mismatches": mismatches,
            "sla_breach_rate": breach_rate,
            "avg_csat": avg_csat,
            "repeat_rate": rep_rate,
            "total_cost": tot_cost,
        })

    return pd.DataFrame(rows).sort_values("tickets", ascending=False).reset_index(drop=True)
