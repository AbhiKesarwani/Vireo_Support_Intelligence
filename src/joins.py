"""
src/joins.py — Order, customer, product, and agent joins.

Join strategy (D-07 — updated after Phase 1 EDA):
  1. Direct join:     ticket.order_id → orders.order_id
  2. Unique fallback: customer_id + product_sku WHERE order_date <= ticket_created_at
                      (date-bounded: can't reference an order that didn't exist yet)
                      Only if exactly ONE order matches.
  3. Ambiguous:       Multiple orders match after date bound → store as ambiguous, do NOT force.
  4. None:            No orders match at all → join_method=none

Audit columns stored per ticket:
  join_method           direct | unique_fallback | ambiguous | none
  join_confidence       high | medium | ambiguous | none
  matched_order_id      the order_id used (may be None for ambiguous/none)
  order_date_anomaly    True if direct-matched order_date > ticket_created_at
"""

from __future__ import annotations

import pandas as pd
import numpy as np


# ══════════════════════════════════════════════════════════════════════════════
#  A. Order join
# ══════════════════════════════════════════════════════════════════════════════

def join_orders(
    tickets: pd.DataFrame,
    orders: pd.DataFrame,
) -> pd.DataFrame:
    """
    Three-tier order join per D-07.

    Requires:
      tickets has columns: ticket_id, order_id, customer_id, product_sku, created_at_ist
      orders has columns: order_id, customer_id, sku, order_date, order_value_inr
    """
    tickets = tickets.copy()
    orders = orders.copy()

    # Parse order_date
    orders["order_date_dt"] = pd.to_datetime(orders["order_date"], errors="coerce")

    # Initialise join audit columns (object dtype to accept string order IDs)
    tickets["join_method"] = "none"
    tickets["join_confidence"] = "none"
    tickets["matched_order_id"] = pd.array([None] * len(tickets), dtype=object)
    tickets["order_date_anomaly"] = False
    tickets["order_value_inr"] = np.nan
    tickets["lot_code_matched"] = pd.array([None] * len(tickets), dtype=object)
    tickets["order_date_matched"] = pd.NaT
    tickets["order_qty"] = np.nan

    # ── Tier 1: direct order_id match ────────────────────────────────────────
    has_order_id = tickets["order_id"].notna() & (tickets["order_id"].astype(str).str.strip() != "")

    # Merge tickets that have an order_id with orders table
    direct_tickets = tickets.loc[has_order_id, ["ticket_id", "order_id", "created_at_ist"]].copy()
    direct_merged = direct_tickets.merge(
        orders[["order_id", "order_value_inr", "lot_code", "order_date_dt", "qty"]],
        on="order_id",
        how="left",
    ).set_index("ticket_id")

    # Update matched_order_id, etc. for direct tickets
    direct_tids = tickets.loc[has_order_id, "ticket_id"].values
    tickets.loc[has_order_id, "join_method"] = "direct"
    tickets.loc[has_order_id, "join_confidence"] = "high"

    # Use a temporary mapping frame to avoid dtype issues
    tickets_idx = tickets.set_index("ticket_id")
    for col_src, col_dst in [
        ("order_id", "matched_order_id"),
        ("order_value_inr", "order_value_inr"),
        ("lot_code", "lot_code_matched"),
        ("order_date_dt", "order_date_matched"),
        ("qty", "order_qty"),
    ]:
        if col_src in direct_merged.columns:
            tickets_idx.loc[direct_tids, col_dst] = direct_merged.loc[
                direct_merged.index.isin(direct_tids), col_src
            ].reindex(direct_tids).values
    tickets = tickets_idx.reset_index()

    # Anomaly: order_date > ticket_created_at (logically impossible)
    direct_mask2 = has_order_id & tickets["order_date_matched"].notna()
    anomaly_mask = (
        direct_mask2 &
        (tickets["order_date_matched"] > tickets["created_at_ist"])
    )
    tickets.loc[anomaly_mask, "order_date_anomaly"] = True

    # ── Tier 2 + 3: fallback for tickets WITHOUT order_id ─────────────────────
    no_order_id = (
        ~has_order_id &
        tickets["customer_id"].notna() &
        tickets["product_sku"].notna()
    )
    fallback_tickets = tickets[no_order_id].copy()

    if not fallback_tickets.empty:
        results = _fallback_join(fallback_tickets, orders)
        # Map results back using ticket_id as key
        results_idx = results.set_index("ticket_id")
        fallback_tids = fallback_tickets["ticket_id"].values
        tickets_idx2 = tickets.set_index("ticket_id")
        for col in ["join_method", "join_confidence", "matched_order_id",
                    "order_value_inr", "lot_code_matched", "order_date_matched", "order_qty"]:
            if col in results_idx.columns:
                tickets_idx2.loc[fallback_tids, col] = results_idx.loc[
                    results_idx.index.isin(fallback_tids), col
                ].reindex(fallback_tids).values
        tickets = tickets_idx2.reset_index()

    return tickets



def _fallback_join(fallback_tickets: pd.DataFrame, orders: pd.DataFrame) -> pd.DataFrame:
    """
    Date-bounded fallback join: customer_id + product_sku + order_date <= ticket_created_at.

    Vectorized: no iterrows loop.
    For each ticket, counts how many candidate orders match the date bound.
    Unique match (count=1) → join_method=unique_fallback.
    Multi match (count>1)  → join_method=ambiguous.
    No match (count=0)     → join_method=none.
    """
    result = fallback_tickets.copy()
    result["join_method"] = "none"
    result["join_confidence"] = "none"
    result["matched_order_id"] = pd.array([None] * len(fallback_tickets), dtype=object)
    result["order_value_inr"] = np.nan
    result["lot_code_matched"] = pd.array([None] * len(fallback_tickets), dtype=object)
    result["order_date_matched"] = pd.NaT
    result["order_qty"] = np.nan

    if result.empty:
        return result

    tickets_slim = result[["ticket_id", "customer_id", "product_sku", "created_at_ist"]].copy()
    orders_slim = orders[["order_id", "customer_id", "sku", "order_date_dt",
                           "order_value_inr", "lot_code", "qty"]].copy()

    # Step 1: join on customer_id + product_sku (undated cross-join)
    joined = tickets_slim.merge(
        orders_slim,
        left_on=["customer_id", "product_sku"],
        right_on=["customer_id", "sku"],
        how="left",
    )

    # Step 2: apply date bound — keep only rows where order_date_dt <= created_at_ist
    date_valid = (
        joined["order_date_dt"].notna() &
        (joined["order_date_dt"] <= joined["created_at_ist"])
    )

    # Count valid orders per ticket
    candidate_counts = (
        joined[date_valid]
        .groupby("ticket_id")["order_id"]
        .count()
        .reset_index()
        .rename(columns={"order_id": "n_candidates"})
    )

    # ── Single match: unique_fallback ──────────────────────────────────────────
    single_ids = candidate_counts.loc[candidate_counts["n_candidates"] == 1, "ticket_id"]
    if not single_ids.empty:
        single = joined[date_valid & joined["ticket_id"].isin(single_ids)].copy()
        # Merge the single match details back into result
        single_map = single.set_index("ticket_id")[
            ["order_id", "order_value_inr", "lot_code", "order_date_dt", "qty"]
        ]
        result_idx = result.set_index("ticket_id")
        result_idx.loc[single_ids, "join_method"] = "unique_fallback"
        result_idx.loc[single_ids, "join_confidence"] = "medium"
        result_idx.loc[single_ids, "matched_order_id"] = single_map.loc[single_ids, "order_id"].values
        result_idx.loc[single_ids, "order_value_inr"] = single_map.loc[single_ids, "order_value_inr"].values
        result_idx.loc[single_ids, "lot_code_matched"] = single_map.loc[single_ids, "lot_code"].values
        result_idx.loc[single_ids, "order_date_matched"] = single_map.loc[single_ids, "order_date_dt"].values
        result_idx.loc[single_ids, "order_qty"] = single_map.loc[single_ids, "qty"].values
        result = result_idx.reset_index()

    # ── Multiple matches: ambiguous ────────────────────────────────────────────
    ambiguous_ids = candidate_counts.loc[candidate_counts["n_candidates"] > 1, "ticket_id"]
    if not ambiguous_ids.empty:
        result_idx2 = result.set_index("ticket_id")
        result_idx2.loc[ambiguous_ids, "join_method"] = "ambiguous"
        result_idx2.loc[ambiguous_ids, "join_confidence"] = "ambiguous"
        # matched_order_id stays None (intentional — never force selection)
        result = result_idx2.reset_index()

    return result





# ══════════════════════════════════════════════════════════════════════════════
#  B. Customer join
# ══════════════════════════════════════════════════════════════════════════════

def join_customers(tickets: pd.DataFrame, customers: pd.DataFrame) -> pd.DataFrame:
    """Add customer metadata. Fail loud if any ticket customer_id is missing."""
    tickets = tickets.copy()
    customers = customers.copy().add_prefix("cust_")
    customers.rename(columns={"cust_customer_id": "customer_id"}, inplace=True)

    merged = tickets.merge(customers, on="customer_id", how="left")

    # Check for orphan customer_ids
    orphans = merged["cust_name"].isna() & merged["customer_id"].notna()
    n_orphans = int(orphans.sum())
    if n_orphans > 0:
        raise ValueError(
            f"{n_orphans} tickets have customer_id values not found in customers.csv. "
            f"Reference integrity violated."
        )

    return merged


# ══════════════════════════════════════════════════════════════════════════════
#  C. Product join
# ══════════════════════════════════════════════════════════════════════════════

def join_products(tickets: pd.DataFrame, products: pd.DataFrame) -> pd.DataFrame:
    """Add product metadata. Fail loud if any ticket SKU is unknown."""
    tickets = tickets.copy()
    products = products.copy().add_prefix("prod_")
    products.rename(columns={"prod_sku": "product_sku"}, inplace=True)

    merged = tickets.merge(products, on="product_sku", how="left")

    orphans = merged["prod_product_name"].isna() & merged["product_sku"].notna()
    n_orphans = int(orphans.sum())
    if n_orphans > 0:
        raise ValueError(
            f"{n_orphans} tickets have product_sku values not found in products.csv. "
            f"Unknown SKUs: {merged.loc[orphans, 'product_sku'].unique()}"
        )

    return merged


# ══════════════════════════════════════════════════════════════════════════════
#  D. Agent join (current-state roster only — D-13 confirmed)
# ══════════════════════════════════════════════════════════════════════════════

def join_agents(tickets: pd.DataFrame, agents: pd.DataFrame) -> pd.DataFrame:
    """
    Join agent roster to tickets on agent_id.
    D-13: agents.csv is current-state only (to_date 100% null).
    This means team/shift/tier reflects current assignment, not historical.
    We record this limitation in agent_roster_note column.
    """
    tickets = tickets.copy()
    agents = agents.copy()

    # Deduplicate agents — should already be unique per D-13 finding
    if agents["agent_id"].duplicated().any():
        # If multiple rows, take the one with latest from_date (most current)
        agents = agents.sort_values("from_date", ascending=False)
        agents = agents.drop_duplicates(subset="agent_id", keep="first")

    agent_cols = ["agent_id", "name", "site", "team", "shift", "tier"]
    agents_slim = agents[agent_cols].copy().add_prefix("agent_")
    agents_slim.rename(columns={"agent_agent_id": "agent_id"}, inplace=True)

    merged = tickets.merge(agents_slim, on="agent_id", how="left")

    # Note the limitation
    merged["agent_roster_note"] = "current_state_only"

    # Orphan check: tickets with agent_id that doesn't exist in roster
    orphans = merged["agent_name"].isna() & merged["agent_id"].notna()
    n_orphans = int(orphans.sum())
    if n_orphans > 0:
        raise ValueError(
            f"{n_orphans} tickets have agent_id values not found in agents.csv. "
            f"Agent IDs: {merged.loc[orphans, 'agent_id'].unique()}"
        )

    return merged


# ══════════════════════════════════════════════════════════════════════════════
#  E. Team mismatch detection
# ══════════════════════════════════════════════════════════════════════════════

def flag_team_mismatch(tickets: pd.DataFrame) -> pd.DataFrame:
    """
    Flag tickets where assigned_team != resolver agent's team.
    This is an operational signal, NOT a data error.

    Requires agent_team column from join_agents().
    """
    tickets = tickets.copy()
    tickets["team_mismatch"] = (
        tickets["assigned_team"].notna() &
        tickets["agent_team"].notna() &
        (tickets["assigned_team"] != tickets["agent_team"])
    )
    return tickets


# ══════════════════════════════════════════════════════════════════════════════
#  F. Build join audit parquet
# ══════════════════════════════════════════════════════════════════════════════

def build_join_audit(tickets: pd.DataFrame) -> pd.DataFrame:
    """Extract join audit columns for separate storage."""
    audit_cols = [
        "ticket_id", "customer_id", "product_sku", "order_id",
        "join_method", "join_confidence", "matched_order_id",
        "order_date_anomaly", "agent_id", "agent_team",
        "team_mismatch", "agent_roster_note",
    ]
    available = [c for c in audit_cols if c in tickets.columns]
    return tickets[available].copy()


# ══════════════════════════════════════════════════════════════════════════════
#  G. Join coverage summary
# ══════════════════════════════════════════════════════════════════════════════

def join_coverage_summary(tickets: pd.DataFrame) -> dict:
    """Return a summary dict of join coverage stats."""
    jm = tickets["join_method"].value_counts(dropna=False).to_dict()
    jc = tickets["join_confidence"].value_counts(dropna=False).to_dict()

    return {
        "join_method_counts": {str(k): int(v) for k, v in jm.items()},
        "join_confidence_counts": {str(k): int(v) for k, v in jc.items()},
        "order_date_anomaly_count": int(tickets.get("order_date_anomaly", pd.Series(False)).sum()),
        "team_mismatch_count": int(tickets.get("team_mismatch", pd.Series(False)).sum()),
        "team_mismatch_rate_pct": round(
            tickets.get("team_mismatch", pd.Series(False)).mean() * 100, 2
        ),
    }
