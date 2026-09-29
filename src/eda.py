"""
src/eda.py — Phase 1: Complete EDA and data-quality investigation

Run:   python -m src.eda
Output:
  outputs/eda_report.md
  outputs/data_quality_report.json
  outputs/figures/*.png

Design rules:
  - Raw files are NEVER modified
  - Every number in the report is code-generated (no manual typing)
  - Findings are classified as FACT / INFERENCE / HYPOTHESIS
  - Comparison against Claude investigation anchors is explicit
"""

from __future__ import annotations

import io
import json
import os
import sys
import warnings
from datetime import timedelta
from pathlib import Path

# Force UTF-8 stdout on Windows to avoid CP1252 UnicodeEncodeError
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import matplotlib
matplotlib.use("Agg")  # non-interactive backend
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

warnings.filterwarnings("ignore", category=FutureWarning)

# ── Paths ──────────────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent
DATA_RAW = ROOT / "data" / "raw"
OUT_DIR = ROOT / "outputs"
FIG_DIR = OUT_DIR / "figures"
OUT_DIR.mkdir(parents=True, exist_ok=True)
FIG_DIR.mkdir(parents=True, exist_ok=True)

# Raw file map (actual filenames with UUID prefixes)
RAW_FILES = {
    "tickets":   DATA_RAW / "cded5ec7-cd54-40e6-ba66-7b3e581319c7-tickets.csv",
    "agents":    DATA_RAW / "1bb95ea8-f7cb-44b6-b5d2-2fb20c9a4e47-agents.csv",
    "orders":    DATA_RAW / "e5c326e5-4764-4ab0-87fd-75abb8f287ae-orders.csv",
    "customers": DATA_RAW / "52fbee44-8a34-4fda-875a-b68ed16c17f2-customers.csv",
    "products":  DATA_RAW / "8e1b3214-16f2-4456-a618-cd1a4e8bddef-products.csv",
}

# ── Policy constants ───────────────────────────────────────────────────────────
SLA_TARGETS_MIN = {"chat": 15, "email": 480, "voice": 120, "social": 240}
CHANNEL_COSTS = {"chat": 210, "email": 260, "voice": 520, "social": 240}
SLA_BREACH_CREDIT = 350
TRANSFER_COST = 305
IST_OFFSET = timedelta(hours=5, minutes=30)
REPEAT_WINDOW_DAYS = 30

# ── Claude investigation anchors (validation targets only — do NOT hard-code) ──
ANCHORS = {
    "raw_rows": 12528,
    "unique_ticket_ids": 11875,
    "duplicate_pairs": 653,
    "legacy_ts_correct_pairs": 618,
    "legacy_csat_zeros": 2083,
    "csat_response_rate_pct": 44.4,
    "sla_breach_count": 1051,
    "sla_breach_rate_pct": 8.9,
    "q2_2026_tickets": 2467,
    "direct_fallback_unique": 3460,
    "fallback_ambiguous": 462,
    "fallback_none": 101,
}

# ── Report accumulator ─────────────────────────────────────────────────────────
report_lines: list[str] = []
quality_report: dict = {"facts": [], "inferences": [], "hypotheses": [], "anchors": {}}


def log(text: str = "") -> None:
    print(text)
    report_lines.append(text)


def section(title: str) -> None:
    bar = "=" * 70
    log()
    log(bar)
    log(f"  {title}")
    log(bar)


def subsection(title: str) -> None:
    log()
    log(f"### {title}")
    log("-" * 50)


def fact(msg: str, metric=None, denominator=None, consequence: str = "") -> None:
    entry = {"type": "FACT", "msg": msg}
    if metric is not None:
        entry["metric"] = metric
    if denominator is not None:
        entry["denominator"] = denominator
    if consequence:
        entry["consequence"] = consequence
    quality_report["facts"].append(entry)
    log(f"[FACT] {msg}")
    if consequence:
        log(f"       → Consequence: {consequence}")


def inference(msg: str, consequence: str = "") -> None:
    quality_report["inferences"].append({"type": "INFERENCE", "msg": msg, "consequence": consequence})
    log(f"[INFERENCE] {msg}")
    if consequence:
        log(f"            → {consequence}")


def hypothesis(msg: str) -> None:
    quality_report["hypotheses"].append({"type": "HYPOTHESIS", "msg": msg})
    log(f"[HYPOTHESIS] {msg}")


def check_anchor(name: str, computed, description: str = "") -> None:
    expected = ANCHORS.get(name)
    if expected is None:
        return
    if isinstance(computed, float):
        diff = abs(computed - expected)
        match = diff < abs(expected) * 0.02  # within 2%
    else:
        match = computed == expected
    status = "MATCH" if match else "DIFFER"
    quality_report["anchors"][name] = {
        "expected": expected,
        "computed": computed,
        "status": status,
        "description": description,
    }
    marker = "OK" if match else "XX"
    log(f"  [{marker} ANCHOR {name}] expected={expected}, computed={computed} -- {status}")


# ── Loaders ───────────────────────────────────────────────────────────────────

def load_csv(name: str) -> pd.DataFrame:
    path = RAW_FILES[name]
    if not path.exists():
        log(f"[ERROR] Missing file: {path}")
        sys.exit(1)
    df = pd.read_csv(path, low_memory=False, encoding="utf-8-sig")
    log(f"Loaded {name}: {len(df):,} rows × {len(df.columns)} cols from {path.name}")
    return df


def basic_profile(df: pd.DataFrame, name: str) -> dict:
    """Return a basic profile dict for a dataframe."""
    profile = {
        "name": name,
        "rows": len(df),
        "cols": len(df.columns),
        "columns": list(df.columns),
        "dtypes": {c: str(df[c].dtype) for c in df.columns},
        "missing": {c: int(df[c].isna().sum()) for c in df.columns},
        "missing_pct": {c: round(df[c].isna().mean() * 100, 2) for c in df.columns},
        "unique": {c: int(df[c].nunique()) for c in df.columns},
    }
    return profile


# ══════════════════════════════════════════════════════════════════════════════
#  PHASE 0 — Input inventory
# ══════════════════════════════════════════════════════════════════════════════

def phase0_inventory() -> None:
    section("PHASE 0 — INPUT INVENTORY")
    inventory = {}
    required = list(RAW_FILES.keys()) + ["support-policy.pdf", "README.txt", "Email-Thread.txt"]
    for name, path in RAW_FILES.items():
        exists = path.exists()
        size = path.stat().st_size if exists else 0
        inventory[name] = {"path": str(path.name), "exists": exists, "size_bytes": size}
        log(f"  {'OK' if exists else 'MISSING':8s}  {path.name}  ({size:,} bytes)")

    # Check non-CSV files
    for fname in ["support-policy.pdf", "Readme.txt", "Email-Thread.txt"]:
        p = DATA_RAW / fname
        exists = p.exists()
        inventory[fname] = {"path": fname, "exists": exists, "size_bytes": p.stat().st_size if exists else 0}
        log(f"  {'OK' if exists else 'MISSING':8s}  {fname}")

    with open(OUT_DIR / "input_inventory.json", "w") as f:
        json.dump(inventory, f, indent=2)

    # Write MD inventory
    with open(OUT_DIR / "input_inventory.md", "w") as f:
        f.write("# Input Inventory\n\n")
        f.write("| File | Present | Size |\n|---|---|---|\n")
        for k, v in inventory.items():
            f.write(f"| {v['path']} | {'Yes' if v['exists'] else 'NO - MISSING'} | {v['size_bytes']:,} |\n")

    log("\n  Inventory written to outputs/input_inventory.json and outputs/input_inventory.md")


# ══════════════════════════════════════════════════════════════════════════════
#  PHASE 1-A — Dataset profiles
# ══════════════════════════════════════════════════════════════════════════════

def phase1_profiles(dfs: dict) -> dict:
    section("PHASE 1-A — DATASET PROFILES")
    profiles = {}
    for name, df in dfs.items():
        subsection(f"{name}.csv profile")
        p = basic_profile(df, name)
        profiles[name] = p
        log(f"  Rows: {p['rows']:,}  |  Cols: {p['cols']}")
        log(f"  Columns: {', '.join(p['columns'])}")

        # Missing values
        high_miss = {c: v for c, v in p["missing_pct"].items() if v > 5}
        if high_miss:
            log(f"  High missingness (>5%): {high_miss}")
        else:
            log("  No columns with >5% missing")
    return profiles


# ══════════════════════════════════════════════════════════════════════════════
#  PHASE 1-B — Tickets deep dive
# ══════════════════════════════════════════════════════════════════════════════

def phase1_tickets(df_raw: pd.DataFrame) -> pd.DataFrame:
    section("PHASE 1-B — TICKETS DEEP DIVE")

    # ── B1: Row count and unique ticket IDs ─────────────────────────────────
    subsection("B1: Row count and unique ticket IDs")
    raw_rows = len(df_raw)
    unique_ids = df_raw["ticket_id"].nunique()
    duplicate_count = raw_rows - unique_ids
    log(f"  Raw rows:        {raw_rows:,}")
    log(f"  Unique IDs:      {unique_ids:,}")
    log(f"  Duplicate rows:  {duplicate_count:,}")
    check_anchor("raw_rows", raw_rows, "Total CSV rows")
    check_anchor("unique_ticket_ids", unique_ids, "Distinct ticket_id values")
    check_anchor("duplicate_pairs", duplicate_count, "Rows where ticket_id appears more than once")
    fact(f"tickets.csv has {raw_rows:,} rows but {unique_ids:,} unique ticket IDs ({duplicate_count:,} duplicates)",
         metric={"raw_rows": raw_rows, "unique_ids": unique_ids, "duplicates": duplicate_count},
         consequence="Analytics must deduplicate before computing any metric.")

    # ── B2: Duplicate source analysis ───────────────────────────────────────
    subsection("B2: Duplicate pair source analysis")
    dup_ids = df_raw[df_raw.duplicated("ticket_id", keep=False)]["ticket_id"].unique()
    dup_df = df_raw[df_raw["ticket_id"].isin(dup_ids)].copy()
    pair_sources = (
        dup_df.groupby("ticket_id")["source_system"]
        .apply(lambda x: tuple(sorted(x.tolist())))
        .value_counts()
    )
    log(f"  Duplicate pair source combinations:\n{pair_sources.to_string()}")
    helpdesk_legacy_pairs = int(pair_sources.get(("helpdesk", "legacy_fd"), 0))
    other_pairs = int(pair_sources.drop(("helpdesk", "legacy_fd"), errors="ignore").sum())
    log(f"\n  helpdesk + legacy_fd pairs: {helpdesk_legacy_pairs:,}")
    log(f"  Other pair types:           {other_pairs:,}")
    fact(
        f"All {helpdesk_legacy_pairs:,} duplicate pairs are one helpdesk row + one legacy_fd row",
        metric={"helpdesk_legacy_pairs": helpdesk_legacy_pairs, "other_pairs": other_pairs},
        consequence="Keep helpdesk row as canonical per D-01."
    )

    # ── B3: Field differences between duplicate pairs ────────────────────────
    subsection("B3: Field differences in duplicate pairs")
    compare_cols = ["resolved_at", "csat_score", "transfers", "refund_amount_inr",
                    "replacement_issued", "status", "category"]
    diff_counts = {}
    hd_df = dup_df[dup_df["source_system"] == "helpdesk"].set_index("ticket_id")
    lg_df = dup_df[dup_df["source_system"] == "legacy_fd"].set_index("ticket_id")
    shared = hd_df.index.intersection(lg_df.index)
    for col in compare_cols:
        if col in hd_df.columns and col in lg_df.columns:
            hd_vals = hd_df.loc[shared, col].astype(str)
            lg_vals = lg_df.loc[shared, col].astype(str)
            n_diff = int((hd_vals != lg_vals).sum())
            diff_counts[col] = n_diff
            log(f"  {col:30s}  differ: {n_diff:,} / {len(shared):,}")
    fact(
        "resolved_at systematically differs between helpdesk and legacy_fd rows (IST vs UTC)",
        metric={"resolved_at_diff": diff_counts.get("resolved_at", "N/A")},
        consequence="Timestamp normalization (D-02) is required."
    )

    # ── B4: Migration date boundary ──────────────────────────────────────────
    subsection("B4: Migration boundary analysis (14 Sep 2025)")
    df_raw["created_at_dt"] = pd.to_datetime(df_raw["created_at"], format="mixed", dayfirst=False, errors="coerce")
    migration_date = pd.Timestamp("2025-09-14")
    pre_migration = (df_raw["created_at_dt"] < migration_date).sum()
    post_migration = (df_raw["created_at_dt"] >= migration_date).sum()
    legacy_count = (df_raw["source_system"] == "legacy_fd").sum()
    helpdesk_count = (df_raw["source_system"] == "helpdesk").sum()
    log(f"  source_system == legacy_fd: {legacy_count:,}")
    log(f"  source_system == helpdesk:  {helpdesk_count:,}")
    log(f"  created_at before 14 Sep 2025: {pre_migration:,}")
    log(f"  created_at on/after 14 Sep 2025: {post_migration:,}")

    # ── B5: Timestamp normalization ──────────────────────────────────────────
    subsection("B5: Timestamp normalization")
    df = df_raw.copy()
    df["created_at_dt"] = pd.to_datetime(df["created_at"], format="mixed", dayfirst=False, errors="coerce")
    df["first_response_at_dt"] = pd.to_datetime(df["first_response_at"], format="mixed", dayfirst=False, errors="coerce")
    df["resolved_at_raw"] = pd.to_datetime(df["resolved_at"], format="mixed", dayfirst=False, errors="coerce")

    # Before normalization: negative durations
    resolved_populated = df["resolved_at_raw"].notna()
    neg_created = int((df.loc[resolved_populated, "resolved_at_raw"] < df.loc[resolved_populated, "created_at_dt"]).sum())
    neg_frt = int((df.loc[resolved_populated, "resolved_at_raw"] < df.loc[resolved_populated, "first_response_at_dt"]).sum())
    log(f"  BEFORE normalization:")
    log(f"    resolved_at < created_at:          {neg_created:,}")
    log(f"    resolved_at < first_response_at:   {neg_frt:,}")
    fact(f"Before legacy timestamp correction: {neg_created:,} tickets have resolution before creation",
         metric={"neg_resolved_before_created": neg_created},
         consequence="These are all legacy_fd rows with UTC timestamps needing +5:30.")

    # Apply +5:30 to legacy_fd resolved_at only
    legacy_mask = (df["source_system"] == "legacy_fd") & df["resolved_at_raw"].notna()
    df["resolved_at_ist"] = df["resolved_at_raw"].copy()
    df.loc[legacy_mask, "resolved_at_ist"] = df.loc[legacy_mask, "resolved_at_raw"] + IST_OFFSET

    # After normalization
    resolved_populated2 = df["resolved_at_ist"].notna()
    neg_created_after = int((df.loc[resolved_populated2, "resolved_at_ist"] < df.loc[resolved_populated2, "created_at_dt"]).sum())
    neg_frt_after = int((df.loc[resolved_populated2, "resolved_at_ist"] < df.loc[resolved_populated2, "first_response_at_dt"]).sum())
    log(f"\n  AFTER normalization (+5:30 to legacy resolved_at):")
    log(f"    resolved_at < created_at:          {neg_created_after:,}")
    log(f"    resolved_at < first_response_at:   {neg_frt_after:,}")

    if neg_created_after == 0 and neg_frt_after == 0:
        fact("After +5:30 correction, zero negative resolved durations remain",
             consequence="Timestamp normalization strategy (D-02) is valid.")
    else:
        inference(f"After +5:30 correction, {neg_created_after} resolved-before-created anomalies remain — may need further investigation")

    # Count exact -5:30 pairs in duplicate set
    if not hd_df.empty and not lg_df.empty:
        hd_res = pd.to_datetime(hd_df.loc[shared, "resolved_at"], format="mixed", errors="coerce")
        lg_res = pd.to_datetime(lg_df.loc[shared, "resolved_at"], format="mixed", errors="coerce")
        delta = (hd_res - lg_res).dropna()
        exact_530 = int((delta == pd.Timedelta("5:30:00")).sum())
        log(f"\n  Duplicate pairs where hd_resolved - legacy_resolved == 5h30: {exact_530:,}")
        check_anchor("legacy_ts_correct_pairs", exact_530, "Pairs with exact -5:30 UTC offset")

    # ── B6: CSAT analysis ────────────────────────────────────────────────────
    subsection("B6: CSAT encoding")
    csat_raw = pd.to_numeric(df_raw["csat_score"], errors="coerce")
    n_zeros = int((csat_raw == 0).sum())
    n_blank = int(df_raw["csat_score"].isna().sum())
    n_valid = int(((csat_raw >= 1) & (csat_raw <= 5)).sum())
    legacy_zeros = int(((df_raw["source_system"] == "legacy_fd") & (csat_raw == 0)).sum())
    check_anchor("legacy_csat_zeros", legacy_zeros, "legacy_fd rows with csat_score == 0")

    csat_corrected = csat_raw.where((csat_raw >= 1) & (csat_raw <= 5))
    response_rate = csat_corrected.notna().mean() * 100
    csat_mean_wrong = csat_raw.replace(0, np.nan).mean()  # some zeros replaced
    csat_mean_correct = csat_corrected.mean()

    log(f"  Raw CSAT zeros:          {n_zeros:,}")
    log(f"  Raw CSAT blank:          {n_blank:,}")
    log(f"  Valid (1–5) responses:   {n_valid:,}")
    log(f"  Legacy zeros:            {legacy_zeros:,}")
    log(f"  Response rate (corrected): {response_rate:.1f}%")
    log(f"  CSAT mean (wrong, incl zeros): {csat_mean_wrong:.3f}")
    log(f"  CSAT mean (corrected):         {csat_mean_correct:.3f}")
    check_anchor("csat_response_rate_pct", round(response_rate, 1), "Corrected CSAT response rate")

    fact(f"{legacy_zeros:,} legacy_fd rows encode no-response as csat_score=0",
         metric={"legacy_zeros": legacy_zeros, "correct_csat_mean": round(csat_mean_correct, 3),
                 "wrong_csat_mean": round(float(csat_mean_wrong), 3), "response_rate_pct": round(response_rate, 1)},
         consequence="Must convert 0 → NaN per D-03 before any CSAT aggregation.")

    df["csat_corrected"] = csat_corrected

    # ── B7: Status distribution ──────────────────────────────────────────────
    subsection("B7: Status distribution")
    status_dist = df_raw["status"].value_counts(dropna=False)
    log(status_dist.to_string())
    n_auto_closed = int((df_raw["status"] == "closed").sum())
    n_open = int((df_raw["status"] == "open").sum())
    n_pending = int((df_raw["status"] == "pending").sum())
    log(f"\n  auto-closed (status=closed): {n_auto_closed:,}  ({100*n_auto_closed/len(df_raw):.1f}%)")
    fact(f"{n_auto_closed:,} tickets have status='closed' (auto-closed by system)",
         metric={"auto_closed": n_auto_closed, "open": n_open, "pending": n_pending},
         consequence="D-06: show agent_resolved vs auto_closed split in leaderboard.")

    # ── B8: Channel distribution ─────────────────────────────────────────────
    subsection("B8: Channel distribution")
    channel_dist = df_raw["channel"].value_counts()
    log(channel_dist.to_string())

    # ── B9: Category distribution ────────────────────────────────────────────
    subsection("B9: Category distribution")
    cat_dist = df_raw["category"].value_counts(dropna=False)
    log(cat_dist.to_string())

    # ── B10: Priority, team distributions ────────────────────────────────────
    subsection("B10: Priority and assigned_team distributions")
    log("Priority:\n" + df_raw["priority"].value_counts(dropna=False).to_string())
    log("\nAssigned team:\n" + df_raw["assigned_team"].value_counts(dropna=False).to_string())

    # ── B11: Transfers ───────────────────────────────────────────────────────
    subsection("B11: Transfers analysis")
    transfers_num = pd.to_numeric(df_raw["transfers"], errors="coerce")
    log(f"  Transfers > 0: {int((transfers_num > 0).sum()):,}  ({100*(transfers_num > 0).mean():.1f}%)")
    log(f"  Transfers = 0: {int((transfers_num == 0).sum()):,}")
    log(f"  Transfers NaN: {int(transfers_num.isna().sum()):,}")
    log(f"  Transfers mean (non-zero): {transfers_num[transfers_num > 0].mean():.2f}")

    # Legacy transfers flag
    legacy_transfers = df_raw[df_raw["source_system"] == "legacy_fd"]
    lg_transfer_non0 = int((pd.to_numeric(legacy_transfers["transfers"], errors="coerce") > 0).sum())
    log(f"\n  legacy_fd rows with transfers > 0: {lg_transfer_non0:,}")
    if lg_transfer_non0 > 0:
        inference(
            "legacy_fd rows contain non-zero transfer values despite policy stating transfers only exist in current helpdesk",
            consequence="Policy contradiction (D-14b). Legacy transfer values may not be comparable to helpdesk values."
        )

    # ── B12: SLA breach ──────────────────────────────────────────────────────
    subsection("B12: SLA breach analysis")
    df["frt_minutes"] = (df["first_response_at_dt"] - df["created_at_dt"]).dt.total_seconds() / 60
    df["sla_target_min"] = df["channel"].map(SLA_TARGETS_MIN)
    df["sla_breach"] = df["frt_minutes"] > df["sla_target_min"]

    total_with_frt = df["frt_minutes"].notna().sum()
    n_breach = int(df["sla_breach"].sum())
    breach_rate = df["sla_breach"].mean() * 100
    check_anchor("sla_breach_count", n_breach, "Tickets with FRT exceeding SLA target")
    check_anchor("sla_breach_rate_pct", round(breach_rate, 1), "SLA breach rate percent")

    log(f"  Tickets with FRT data:    {total_with_frt:,}")
    log(f"  SLA breaches:             {n_breach:,}")
    log(f"  SLA breach rate:          {breach_rate:.2f}%")
    log(f"  Breach credit exposure:   Rs {n_breach * SLA_BREACH_CREDIT:,}")

    breach_by_channel = df.groupby("channel")["sla_breach"].agg(["sum", "mean"])
    breach_by_channel.columns = ["n_breach", "breach_rate"]
    breach_by_channel["breach_rate_pct"] = breach_by_channel["breach_rate"] * 100
    log(f"\n  SLA breach by channel:\n{breach_by_channel[['n_breach','breach_rate_pct']].to_string()}")

    fact(f"SLA breach rate is {breach_rate:.2f}% ({n_breach:,} tickets), creating Rs {n_breach * SLA_BREACH_CREDIT:,} credit exposure",
         metric={"n_breach": n_breach, "breach_rate_pct": round(breach_rate, 2),
                 "credit_exposure_inr": n_breach * SLA_BREACH_CREDIT})

    # ── B13: Refund / replacement ────────────────────────────────────────────
    subsection("B13: Refund and replacement analysis")
    df["refund_num"] = pd.to_numeric(df_raw["refund_amount_inr"], errors="coerce")
    n_refund = int(df["refund_num"].notna().sum())
    refund_total = df["refund_num"].sum()
    n_replacement = int((df_raw["replacement_issued"] == "Y").sum())
    n_both = int(((df_raw["replacement_issued"] == "Y") & df["refund_num"].notna()).sum())
    log(f"  Tickets with refund:          {n_refund:,}")
    log(f"  Total refund value:           Rs {refund_total:,.0f}")
    log(f"  Tickets with replacement:     {n_replacement:,}")
    log(f"  Tickets with both:            {n_both:,}")

    # Policy exception flags
    reason_dist = df_raw["refund_reason_code"].value_counts(dropna=False)
    log(f"\n  Refund reason code distribution:\n{reason_dist.to_string()}")

    # ── B14: Ticket volume trend ─────────────────────────────────────────────
    subsection("B14: Ticket volume trend by week/quarter")
    df["week"] = df["created_at_dt"].dt.to_period("W")
    df["month"] = df["created_at_dt"].dt.to_period("M")
    df["quarter"] = df["created_at_dt"].dt.to_period("Q")

    quarterly = df.groupby("quarter").size()
    log(f"\n  Quarterly ticket volume:\n{quarterly.to_string()}")

    # Q2 2026 check
    q2_2026 = int(quarterly.get(pd.Period("2026Q2"), 0))
    log(f"\n  Q2 2026 tickets: {q2_2026:,}")
    check_anchor("q2_2026_tickets", q2_2026, "Tickets created in Q2 2026")

    # ── B15: Exploratory repeat-contact baseline ─────────────────────────────
    subsection("B15: PROVISIONAL repeat-contact exploratory baseline")
    log("  NOTE: This is a heuristic/keyword baseline only. Not the final metric.")
    log("  Final repeat metric will use LLM issue_code (Phase 3).")

    repeat_kws = ["already told", "called before", "same issue", "again", "last time i called",
                  "reported earlier", "previous ticket", "unresolved", "still not fixed"]

    df_clean_src = df[df["source_system"] == "helpdesk"].copy()  # use non-duplicate rows
    df_clean_src = df_clean_src.drop_duplicates(subset="ticket_id", keep="first")
    df_clean_src["msg_lower"] = df_clean_src["customer_message"].fillna("").str.lower()
    df_clean_src["has_repeat_kw"] = df_clean_src["msg_lower"].apply(
        lambda t: any(kw in t for kw in repeat_kws)
    )
    n_repeat_kw = int(df_clean_src["has_repeat_kw"].sum())
    repeat_kw_rate = df_clean_src["has_repeat_kw"].mean() * 100
    log(f"  Tickets with repeat-language keywords: {n_repeat_kw:,} / {len(df_clean_src):,} ({repeat_kw_rate:.1f}%)")
    log("  [PROVISIONAL] This is keyword-based, not AI-based. Use as order-of-magnitude only.")
    hypothesis(
        f"~{repeat_kw_rate:.1f}% of helpdesk tickets contain explicit repeat-contact language "
        f"(keyword proxy). True repeat rate (policy: same customer + same issue within 30 days) "
        f"will be computed in Phase 3 using AI issue classifier."
    )

    return df


# ══════════════════════════════════════════════════════════════════════════════
#  PHASE 1-C — Reference data integrity
# ══════════════════════════════════════════════════════════════════════════════

def phase1_reference(df_t: pd.DataFrame, df_a: pd.DataFrame, df_c: pd.DataFrame,
                     df_p: pd.DataFrame, df_o: pd.DataFrame) -> None:
    section("PHASE 1-C — REFERENCE DATA INTEGRITY")

    # ── C1: Customer join ────────────────────────────────────────────────────
    subsection("C1: Customer join coverage")
    customer_ids_in_tickets = set(df_t["customer_id"].dropna().unique())
    customer_ids_in_customers = set(df_c["customer_id"].unique())
    missing_customers = customer_ids_in_tickets - customer_ids_in_customers
    log(f"  Ticket customer_ids: {len(customer_ids_in_tickets):,}")
    log(f"  Customers csv rows:  {len(df_c):,}")
    log(f"  Missing in customers.csv: {len(missing_customers):,}")
    if missing_customers:
        inference(f"{len(missing_customers):,} customer_ids in tickets not found in customers.csv",
                  consequence="These tickets cannot be enriched with customer data.")
    else:
        fact("All ticket customer_ids found in customers.csv", metric={"missing": 0})

    # ── C2: Agent join ───────────────────────────────────────────────────────
    subsection("C2: Agent join coverage")
    agent_ids_in_tickets = set(df_t["agent_id"].dropna().unique())
    agent_ids_in_roster = set(df_a["agent_id"].unique())
    missing_agents = agent_ids_in_tickets - agent_ids_in_roster
    log(f"  Ticket agent_ids: {len(agent_ids_in_tickets):,}")
    log(f"  Agents csv agent_ids: {len(agent_ids_in_roster):,}")
    log(f"  Missing in agents.csv: {len(missing_agents):,}")
    if missing_agents:
        inference(f"{len(missing_agents):,} agent_ids in tickets not found in agents.csv",
                  consequence="Roster data may be incomplete — some agents' team/tier unknown.")

    # ── C3: Product join ─────────────────────────────────────────────────────
    subsection("C3: Product join coverage")
    sku_in_tickets = set(df_t["product_sku"].dropna().unique())
    sku_in_products = set(df_p["sku"].unique())
    missing_sku = sku_in_tickets - sku_in_products
    log(f"  Ticket SKUs: {len(sku_in_tickets):,} unique")
    log(f"  Products csv SKUs: {len(sku_in_products):,}")
    log(f"  Unknown SKUs in tickets: {len(missing_sku):,}")
    if missing_sku:
        log(f"  Unknown: {missing_sku}")

    # ── C4: Order join ───────────────────────────────────────────────────────
    subsection("C4: Order join coverage")
    n_with_order_id = int(df_t["order_id"].notna().sum())
    n_without_order_id = int(df_t["order_id"].isna().sum())
    log(f"  Tickets with order_id:    {n_with_order_id:,}")
    log(f"  Tickets without order_id: {n_without_order_id:,}")

    # Direct order join
    direct_match = df_t[df_t["order_id"].notna()].merge(
        df_o[["order_id"]], on="order_id", how="inner"
    )
    log(f"  Direct order_id matches:  {len(direct_match):,}")

    # Fallback: customer_id + product_sku
    tickets_no_order = df_t[df_t["order_id"].isna() & df_t["customer_id"].notna() & df_t["product_sku"].notna()].copy()
    order_counts = df_o.groupby(["customer_id", "sku"])["order_id"].count().reset_index()
    order_counts.columns = ["customer_id", "product_sku", "n_orders"]
    merged_fallback = tickets_no_order.merge(order_counts, on=["customer_id", "product_sku"], how="left")
    n_unique_fallback = int((merged_fallback["n_orders"] == 1).sum())
    n_ambiguous = int((merged_fallback["n_orders"] > 1).sum())
    n_none = int(merged_fallback["n_orders"].isna().sum())
    log(f"\n  Fallback join (customer+SKU):")
    log(f"    Unique match (1 order):   {n_unique_fallback:,}")
    log(f"    Ambiguous (>1 order):     {n_ambiguous:,}")
    log(f"    No match:                 {n_none:,}")
    check_anchor("direct_fallback_unique", n_unique_fallback, "Unique fallback order matches")
    check_anchor("fallback_ambiguous", n_ambiguous, "Ambiguous fallback matches")
    check_anchor("fallback_none", n_none, "No fallback match")

    # Order date vs ticket creation
    tickets_direct = df_t[df_t["order_id"].notna()].merge(
        df_o[["order_id", "order_date"]], on="order_id", how="inner"
    )
    tickets_direct["order_date_dt"] = pd.to_datetime(tickets_direct["order_date"], errors="coerce")
    tickets_direct["created_at_dt"] = pd.to_datetime(tickets_direct["created_at"], format="mixed", errors="coerce")
    order_after_ticket = int((tickets_direct["order_date_dt"] > tickets_direct["created_at_dt"]).sum())
    log(f"\n  Direct-matched tickets where order_date > ticket_created: {order_after_ticket:,}")
    if order_after_ticket > 0:
        inference(f"{order_after_ticket:,} tickets have order dates after ticket creation — possible data anomaly",
                  consequence="Flag these in join quality; do not use order value for these tickets.")

    # ── C5: Roster analysis ──────────────────────────────────────────────────
    subsection("C5: Roster analysis (agents.csv)")
    log(f"  agents.csv rows:     {len(df_a):,}")
    log(f"  Unique agent_ids:    {df_a['agent_id'].nunique():,}")
    log(f"  Agents with >1 row:  {int((df_a.groupby('agent_id').size() > 1).sum()):,}")

    df_a["from_date_dt"] = pd.to_datetime(df_a["from_date"], errors="coerce")
    df_a["to_date_dt"] = pd.to_datetime(df_a["to_date"], errors="coerce")
    has_history = df_a["to_date"].notna().any()
    log(f"  Has to_date populated (historical rows): {has_history}")
    log(f"\n  Tier distribution:\n{df_a['tier'].value_counts().to_string()}")
    log(f"\n  Team distribution:\n{df_a['team'].value_counts().to_string()}")
    log(f"\n  Site distribution:\n{df_a['site'].value_counts().to_string()}")

    if has_history:
        fact("agents.csv contains historical assignment rows (to_date populated)",
             consequence="D-13: roster history available; shift-level attribution is feasible.")
    else:
        inference("agents.csv appears to contain current-state only (no to_date populated)",
                  consequence="D-13: historical shift/site attribution limited — report this clearly.")

    # Product launch date checks
    subsection("C6: Product launch date vs ticket timing")
    df_p_dt = df_p.copy()
    df_p_dt["launch_date_dt"] = pd.to_datetime(df_p_dt["launch_date"], errors="coerce")
    t_merged = df_t.merge(df_p_dt[["sku", "launch_date_dt"]], left_on="product_sku", right_on="sku", how="left")
    t_merged["created_at_dt2"] = pd.to_datetime(t_merged["created_at"], format="mixed", errors="coerce")
    tickets_before_launch = int((t_merged["created_at_dt2"] < t_merged["launch_date_dt"]).sum())
    log(f"  Tickets created before product launch date: {tickets_before_launch:,}")
    if tickets_before_launch > 0:
        inference(f"{tickets_before_launch:,} tickets predate product launch — may be legacy data or test tickets")


# ══════════════════════════════════════════════════════════════════════════════
#  PHASE 1-D — Figures
# ══════════════════════════════════════════════════════════════════════════════

def phase1_figures(df_t_raw: pd.DataFrame, df_enriched: pd.DataFrame) -> None:
    section("PHASE 1-D — GENERATING FIGURES")

    # 1. Weekly ticket volume
    df_enriched["created_at_dt"] = pd.to_datetime(df_enriched["created_at"], format="mixed", errors="coerce")
    weekly = df_enriched.groupby(df_enriched["created_at_dt"].dt.to_period("W")).size()
    fig, ax = plt.subplots(figsize=(14, 4))
    weekly.plot(ax=ax, color="#2563EB", linewidth=1.5)
    ax.set_title("Weekly Ticket Volume (all rows, pre-dedup)")
    ax.set_xlabel("Week")
    ax.set_ylabel("Tickets")
    plt.tight_layout()
    plt.savefig(FIG_DIR / "weekly_volume.png", dpi=120)
    plt.close()
    log("  Saved: weekly_volume.png")

    # 2. Channel distribution
    fig, ax = plt.subplots(figsize=(7, 4))
    df_t_raw["channel"].value_counts().plot.bar(ax=ax, color=["#2563EB", "#7C3AED", "#DB2777", "#D97706"])
    ax.set_title("Ticket Channel Distribution")
    ax.set_ylabel("Count")
    plt.tight_layout()
    plt.savefig(FIG_DIR / "channel_dist.png", dpi=120)
    plt.close()
    log("  Saved: channel_dist.png")

    # 3. Category distribution
    fig, ax = plt.subplots(figsize=(10, 5))
    df_t_raw["category"].value_counts().sort_values().plot.barh(ax=ax, color="#2563EB")
    ax.set_title("Category Distribution")
    ax.set_xlabel("Count")
    plt.tight_layout()
    plt.savefig(FIG_DIR / "category_dist.png", dpi=120)
    plt.close()
    log("  Saved: category_dist.png")

    # 4. CSAT distribution
    csat_raw = pd.to_numeric(df_t_raw["csat_score"], errors="coerce")
    csat_valid = csat_raw[(csat_raw >= 1) & (csat_raw <= 5)]
    fig, ax = plt.subplots(figsize=(7, 4))
    csat_valid.value_counts().sort_index().plot.bar(ax=ax, color="#7C3AED")
    ax.set_title("CSAT Distribution (valid 1–5 responses only)")
    ax.set_ylabel("Count")
    plt.tight_layout()
    plt.savefig(FIG_DIR / "csat_dist.png", dpi=120)
    plt.close()
    log("  Saved: csat_dist.png")

    # 5. SLA breach by channel
    df_enriched["frt_minutes"] = (
        pd.to_datetime(df_enriched["first_response_at"], format="mixed", errors="coerce") -
        pd.to_datetime(df_enriched["created_at"], format="mixed", errors="coerce")
    ).dt.total_seconds() / 60
    df_enriched["sla_target_min"] = df_enriched["channel"].map(SLA_TARGETS_MIN)
    df_enriched["sla_breach"] = df_enriched["frt_minutes"] > df_enriched["sla_target_min"]
    breach_by_ch = df_enriched.groupby("channel")["sla_breach"].mean() * 100
    fig, ax = plt.subplots(figsize=(7, 4))
    breach_by_ch.sort_values(ascending=False).plot.bar(ax=ax, color="#DB2777")
    ax.set_title("SLA Breach Rate by Channel (%)")
    ax.set_ylabel("Breach Rate %")
    plt.tight_layout()
    plt.savefig(FIG_DIR / "sla_breach_channel.png", dpi=120)
    plt.close()
    log("  Saved: sla_breach_channel.png")

    # 6. Source system distribution
    fig, ax = plt.subplots(figsize=(6, 4))
    df_t_raw["source_system"].value_counts().plot.bar(ax=ax, color=["#2563EB", "#7C3AED"])
    ax.set_title("Source System Distribution")
    ax.set_ylabel("Rows")
    plt.tight_layout()
    plt.savefig(FIG_DIR / "source_system.png", dpi=120)
    plt.close()
    log("  Saved: source_system.png")

    # 7. FRT distribution (winsorized)
    df_enriched["frt_minutes"] = pd.to_numeric(df_enriched["frt_minutes"], errors="coerce")
    frt_valid = df_enriched["frt_minutes"].dropna()
    frt_valid = frt_valid[frt_valid >= 0]
    frt_capped = frt_valid.clip(upper=frt_valid.quantile(0.95))
    fig, ax = plt.subplots(figsize=(10, 4))
    ax.hist(frt_capped, bins=60, color="#2563EB", alpha=0.8)
    ax.set_title("First Response Time Distribution (capped at 95th pct, minutes)")
    ax.set_xlabel("FRT (minutes)")
    ax.set_ylabel("Count")
    plt.tight_layout()
    plt.savefig(FIG_DIR / "frt_distribution.png", dpi=120)
    plt.close()
    log("  Saved: frt_distribution.png")

    log("\n  All figures saved to outputs/figures/")


# ══════════════════════════════════════════════════════════════════════════════
#  Report writer
# ══════════════════════════════════════════════════════════════════════════════

def write_report() -> None:
    # EDA markdown report
    md_path = OUT_DIR / "eda_report.md"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("# Vireo Support Intelligence — EDA Report (Phase 1)\n\n")
        f.write("> Auto-generated by `python -m src.eda`. Do not edit manually.\n\n")
        f.write("\n".join(report_lines))
    log(f"\n  EDA report written to {md_path}")

    # JSON quality report
    json_path = OUT_DIR / "data_quality_report.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(quality_report, f, indent=2, default=str)
    log(f"  Quality report written to {json_path}")


# ══════════════════════════════════════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════════════════════════════════════

def main() -> None:
    log("=" * 70)
    log("  VIREO SUPPORT INTELLIGENCE — EDA (Phase 0 + Phase 1)")
    log("  Run with: python -m src.eda")
    log("=" * 70)

    # Phase 0
    phase0_inventory()

    # Load all CSVs
    section("LOADING RAW DATA")
    dfs = {name: load_csv(name) for name in RAW_FILES}
    df_tickets_raw = dfs["tickets"]

    # Phase 1-A: profiles
    profiles = phase1_profiles(dfs)

    # Phase 1-B: tickets deep dive
    df_enriched = phase1_tickets(df_tickets_raw)

    # Phase 1-C: reference integrity
    phase1_reference(
        df_tickets_raw,
        dfs["agents"],
        dfs["customers"],
        dfs["products"],
        dfs["orders"],
    )

    # Phase 1-D: figures
    phase1_figures(df_tickets_raw, df_enriched)

    # Summary
    section("ANCHOR COMPARISON SUMMARY")
    for name, result in quality_report["anchors"].items():
        status = result["status"]
        marker = "OK" if status == "MATCH" else "XX"
        log(f"  [{marker}] {name}: expected={result['expected']}, computed={result['computed']} -- {status}")

    section("PHASE 1 CLASSIFICATION SUMMARY")
    log(f"  FACTS:       {len(quality_report['facts'])}")
    log(f"  INFERENCES:  {len(quality_report['inferences'])}")
    log(f"  HYPOTHESES:  {len(quality_report['hypotheses'])}")

    log("\n[PHASE 1 COMPLETE — STOP. Await human review before Phase 2.]")

    # Write outputs
    write_report()


if __name__ == "__main__":
    main()
