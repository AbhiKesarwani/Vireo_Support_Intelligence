"""
src/issue_analytics.py — Issue-level analytics, channel/product cross-tabs, SLA and CSAT reporting.

CODE CALCULATES. AI INTERPRETS.
Enforces validated 8-class operational taxonomy.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
import pandas as pd
import numpy as np

from src.config import (
    APPROVED_TAXONOMY,
    CHANNEL_ISSUE_METRICS_PARQUET,
    CSAT_METRICS_PARQUET,
    ISSUE_METRICS_PARQUET,
    PRODUCT_ISSUE_METRICS_PARQUET,
    SLA_METRICS_PARQUET,
)


def compute_issue_metrics(df: pd.DataFrame) -> pd.DataFrame:
    """
    Build overall issue-level summary table.
    Fields: issue_code, ticket_count, ticket_share, repeat_count, repeat_rate,
            repeat_cost, avg_csat, sla_breach_rate.

    Hard Invariant:
    Every canonical ticket contributes exactly once to the primary issue table:
    sum(issue_metrics['ticket_count']) == len(df).
    Taxonomy is mutually exclusive across the 8 approved classes:
    APP, BILLING, DELIVERY, OTHER, PRODUCT, RETURNS, WARRANTY, UNKNOWN.
    """
    total_tickets = len(df)
    rows = []

    # Map missing or unmapped issue_code to UNKNOWN
    df_eval = df.copy()
    if "issue_code" not in df_eval.columns:
        raise ValueError("DataFrame must contain 'issue_code' column.")

    df_eval["issue_code"] = df_eval["issue_code"].fillna("UNKNOWN")
    unrecognized = ~df_eval["issue_code"].isin(APPROVED_TAXONOMY)
    if unrecognized.any():
        df_eval.loc[unrecognized, "issue_code"] = "UNKNOWN"

    for code in APPROVED_TAXONOMY:
        sub = df_eval[df_eval["issue_code"] == code]
        count = len(sub)
        # Always include if count > 0, or if UNKNOWN (to explicitly document unclassified count)
        if count == 0 and code != "UNKNOWN":
            continue

        share = round(count / total_tickets, 4) if total_tickets > 0 else 0.0
        repeats = sub[sub["repeat_candidate"] == True]
        repeat_cnt = len(repeats)
        repeat_rate = round(repeat_cnt / count, 4) if count > 0 else 0.0
        repeat_cost = float(repeats["repeat_contact_cost"].sum())

        valid_csat = sub[sub["csat_score_clean"].notna()]
        avg_csat = round(float(valid_csat["csat_score_clean"].mean()), 4) if len(valid_csat) > 0 else None

        breaches = int(sub["sla_breach"].sum())
        breach_rate = round(breaches / count, 4) if count > 0 else 0.0

        rows.append({
            "issue_code": code,
            "ticket_count": count,
            "ticket_share": share,
            "repeat_count": repeat_cnt,
            "repeat_rate": repeat_rate,
            "repeat_cost": repeat_cost,
            "avg_csat": avg_csat,
            "sla_breach_rate": breach_rate,
        })

    # Sort by ticket_count DESC, then issue_code
    issue_df = pd.DataFrame(rows).sort_values(["ticket_count", "issue_code"], ascending=[False, True]).reset_index(drop=True)

    # Hard Invariants
    computed_total = int(issue_df["ticket_count"].sum())
    if computed_total != total_tickets:
        raise AssertionError(
            f"Hard Invariant Violation: sum(issue_metrics.ticket_count)={computed_total} != canonical population {total_tickets}"
        )
    if total_tickets > 0 and abs(issue_df["ticket_share"].sum() - 1.0) > 1e-4:
        raise AssertionError(
            f"Hard Invariant Violation: sum(ticket_share)={issue_df['ticket_share'].sum()} != 1.0"
        )

    return issue_df


def compute_channel_issue_metrics(df: pd.DataFrame) -> pd.DataFrame:
    """
    Build channel x issue cross-tabulation.
    Fields: channel, issue_code, ticket_count, repeat_count, repeat_rate, cost.
    """
    rows = []
    for (ch, iss), grp in df.groupby(["channel", "issue_code"]):
        count = len(grp)
        reps = grp[grp["repeat_candidate"] == True]
        rep_cnt = len(reps)
        rep_rate = round(rep_cnt / count, 4) if count > 0 else 0.0
        tot_cost = float(grp["channel_contact_cost"].sum())
        rep_cost = float(reps["repeat_contact_cost"].sum())

        rows.append({
            "channel": ch,
            "issue_code": iss,
            "ticket_count": count,
            "repeat_count": rep_cnt,
            "repeat_rate": rep_rate,
            "channel_cost": tot_cost,
            "repeat_cost": rep_cost,
        })

    res = pd.DataFrame(rows).sort_values(["channel", "ticket_count"], ascending=[True, False]).reset_index(drop=True)
    if res["ticket_count"].sum() != len(df):
        raise AssertionError(
            f"Hard Invariant Violation: sum(channel_issue_metrics.ticket_count)={res['ticket_count'].sum()} != {len(df)}"
        )
    return res


def compute_product_issue_metrics(df: pd.DataFrame) -> pd.DataFrame:
    """
    Build product x issue cross-tabulation using verified product linkages.
    Fields: product_sku, product_name, prod_family, issue_code, ticket_count,
            repeat_count, repeat_rate, cost.
    """
    rows = []
    # Filter to rows with valid product linkage
    valid_prod = df[df["product_sku"].notna()]

    for (sku, iss), grp in valid_prod.groupby(["product_sku", "issue_code"]):
        count = len(grp)
        reps = grp[grp["repeat_candidate"] == True]
        rep_cnt = len(reps)
        rep_rate = round(rep_cnt / count, 4) if count > 0 else 0.0
        prod_name = grp["prod_product_name"].iloc[0] if "prod_product_name" in grp.columns else sku
        family = grp["prod_family"].iloc[0] if "prod_family" in grp.columns else "Unknown"
        tot_cost = float(grp["channel_contact_cost"].sum())
        rep_cost = float(reps["repeat_contact_cost"].sum())

        rows.append({
            "product_sku": sku,
            "product_name": prod_name,
            "prod_family": family,
            "issue_code": iss,
            "ticket_count": count,
            "repeat_count": rep_cnt,
            "repeat_rate": rep_rate,
            "total_cost": tot_cost,
            "repeat_cost": rep_cost,
        })

    res = pd.DataFrame(rows).sort_values("ticket_count", ascending=False).reset_index(drop=True)
    if res["ticket_count"].sum() != len(valid_prod):
        raise AssertionError(
            f"Hard Invariant Violation: sum(product_issue_metrics.ticket_count)={res['ticket_count'].sum()} != {len(valid_prod)}"
        )
    return res


def compute_sla_metrics(df: pd.DataFrame) -> pd.DataFrame:
    """
    Generate SLA performance analytics across dimensions: overall, channel, issue, and week.
    """
    rows = []

    # 1. Overall
    tot = len(df)
    brk = int(df["sla_breach"].sum())
    rows.append({
        "dimension": "overall",
        "segment": "All Tickets",
        "tickets": tot,
        "sla_breaches": brk,
        "sla_breach_rate": round(brk / tot, 4) if tot > 0 else 0.0,
        "sla_credit_exposure": float(df["sla_credit_cost"].sum()),
    })

    # 2. By Channel
    for ch, grp in df.groupby("channel"):
        cnt = len(grp)
        b = int(grp["sla_breach"].sum())
        rows.append({
            "dimension": "channel",
            "segment": ch,
            "tickets": cnt,
            "sla_breaches": b,
            "sla_breach_rate": round(b / cnt, 4) if cnt > 0 else 0.0,
            "sla_credit_exposure": float(grp["sla_credit_cost"].sum()),
        })

    # 3. By Issue Code
    for iss, grp in df.groupby("issue_code"):
        cnt = len(grp)
        b = int(grp["sla_breach"].sum())
        rows.append({
            "dimension": "issue_code",
            "segment": iss,
            "tickets": cnt,
            "sla_breaches": b,
            "sla_breach_rate": round(b / cnt, 4) if cnt > 0 else 0.0,
            "sla_credit_exposure": float(grp["sla_credit_cost"].sum()),
        })

    return pd.DataFrame(rows)


def compute_csat_metrics(df: pd.DataFrame) -> pd.DataFrame:
    """
    Generate CSAT analytics across dimensions: channel, team, and issue.
    Excludes legacy 0 and missing values.
    """
    rows = []
    tot = len(df)

    # 1. By Channel
    for ch, grp in df.groupby("channel"):
        valid = grp[grp["csat_score_clean"].notna()]
        v_cnt = len(valid)
        rows.append({
            "dimension": "channel",
            "segment": ch,
            "total_tickets": len(grp),
            "csat_responses": v_cnt,
            "csat_response_rate": round(v_cnt / len(grp), 4) if len(grp) > 0 else 0.0,
            "avg_csat": round(float(valid["csat_score_clean"].mean()), 4) if v_cnt > 0 else None,
        })

    # 2. By Team
    for tm, grp in df.groupby("agent_team"):
        valid = grp[grp["csat_score_clean"].notna()]
        v_cnt = len(valid)
        rows.append({
            "dimension": "team",
            "segment": tm,
            "total_tickets": len(grp),
            "csat_responses": v_cnt,
            "csat_response_rate": round(v_cnt / len(grp), 4) if len(grp) > 0 else 0.0,
            "avg_csat": round(float(valid["csat_score_clean"].mean()), 4) if v_cnt > 0 else None,
        })

    # 3. By Issue Code
    for iss, grp in df.groupby("issue_code"):
        valid = grp[grp["csat_score_clean"].notna()]
        v_cnt = len(valid)
        rows.append({
            "dimension": "issue_code",
            "segment": iss,
            "total_tickets": len(grp),
            "csat_responses": v_cnt,
            "csat_response_rate": round(v_cnt / len(grp), 4) if len(grp) > 0 else 0.0,
            "avg_csat": round(float(valid["csat_score_clean"].mean()), 4) if v_cnt > 0 else None,
        })

    return pd.DataFrame(rows)
