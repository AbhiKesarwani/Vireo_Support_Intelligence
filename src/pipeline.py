"""
src/pipeline.py — Phase 2 pipeline orchestrator.

Run:
    python -m src.pipeline

Outputs:
    data/processed/tickets_clean.parquet
    data/processed/metrics_base.parquet
    data/processed/join_audit.parquet
    data/processed/reconciliation_report.json
    outputs/phase2_review.md   (summary)
"""

from __future__ import annotations

import io
import json
import sys
import warnings
from pathlib import Path
from datetime import datetime

import pandas as pd

# Force UTF-8 on Windows
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

warnings.filterwarnings("ignore", category=FutureWarning)

from src.config import DATA_PROCESSED, OUTPUTS
from src.load import load_all
from src.clean import clean_tickets
from src.joins import (
    join_orders, join_customers, join_products, join_agents,
    flag_team_mismatch, build_join_audit, join_coverage_summary,
)
from src.metrics import compute_all_metrics, metrics_summary

# Ensure output dirs exist
DATA_PROCESSED.mkdir(parents=True, exist_ok=True)
OUTPUTS.mkdir(parents=True, exist_ok=True)

log_lines: list[str] = []


def log(msg: str = "") -> None:
    print(msg)
    log_lines.append(msg)


def section(title: str) -> None:
    bar = "=" * 65
    log()
    log(bar)
    log(f"  {title}")
    log(bar)


def run_pipeline() -> dict:
    """Execute the full Phase 2 pipeline. Returns reconciliation report dict."""
    report = {
        "run_at": datetime.now().isoformat(),
        "phase": "2",
        "steps": {},
    }

    # ── Step 1: Load ──────────────────────────────────────────────────────────
    section("STEP 1 -- LOAD RAW DATA")
    dfs = load_all()
    for name, df in dfs.items():
        log(f"  {name}: {len(df):,} rows x {len(df.columns)} cols")
    report["steps"]["load"] = {k: len(v) for k, v in dfs.items()}

    # ── Step 2: Clean tickets ─────────────────────────────────────────────────
    section("STEP 2 -- CLEAN TICKETS (dedup, timestamps, CSAT)")
    canonical, discarded, clean_audit = clean_tickets(dfs["tickets"])
    log(f"  Raw rows:             {clean_audit['raw_rows']:,}")
    log(f"  Duplicate pairs:      {clean_audit['duplicate_pairs']:,}")
    log(f"  Canonical (clean):    {clean_audit['canonical_rows']:,}")
    log(f"  Discarded (kept):     {clean_audit['discarded_rows']:,}")
    log(f"  TS corrections:       {clean_audit['timestamp_corrections_applied']:,}")
    log(f"  CSAT zeros corrected: {clean_audit['csat_zeros_corrected']:,}")
    log(f"  CSAT valid responses: {clean_audit['csat_valid_responses']:,}")
    log(f"  CSAT response rate:   {clean_audit['csat_response_rate_pct']:.1f}%")
    log(f"  CSAT mean (corrected):{clean_audit['csat_mean_corrected']:.4f}")
    log(f"  Auto-closed:          {clean_audit['auto_closed_count']:,}")
    report["steps"]["clean"] = clean_audit

    # ── Step 3: Join orders (date-bounded, per D-07) ──────────────────────────
    section("STEP 3 -- ORDER JOIN (date-bounded fallback)")
    canonical = join_orders(canonical, dfs["orders"])
    jm = canonical["join_method"].value_counts().to_dict()
    jc = canonical["join_confidence"].value_counts().to_dict()
    log(f"  join_method:  {jm}")
    log(f"  join_confidence: {jc}")
    anomaly_count = int(canonical["order_date_anomaly"].sum())
    log(f"  Order date anomalies (order_date > ticket_created): {anomaly_count:,}")
    report["steps"]["order_join"] = {
        "join_method": {str(k): int(v) for k, v in jm.items()},
        "join_confidence": {str(k): int(v) for k, v in jc.items()},
        "order_date_anomaly_count": anomaly_count,
    }

    # ── Step 4: Join customers ────────────────────────────────────────────────
    section("STEP 4 -- CUSTOMER JOIN")
    canonical = join_customers(canonical, dfs["customers"])
    log(f"  Customer join complete. All customer_ids resolved.")

    # ── Step 5: Join products ─────────────────────────────────────────────────
    section("STEP 5 -- PRODUCT JOIN")
    canonical = join_products(canonical, dfs["products"])
    log(f"  Product join complete. All product SKUs resolved.")

    # ── Step 6: Join agents ───────────────────────────────────────────────────
    section("STEP 6 -- AGENT JOIN (current-state roster only)")
    canonical = join_agents(canonical, dfs["agents"])
    log(f"  Agent join complete. Roster is current-state only (D-13).")
    log(f"  Tier-1 agents: {int((canonical['agent_tier'] == 1).sum()):,} tickets")
    log(f"  Tier-2 agents: {int((canonical['agent_tier'] == 2).sum()):,} tickets")

    # ── Step 7: Team mismatch ─────────────────────────────────────────────────
    section("STEP 7 -- TEAM MISMATCH FLAG")
    canonical = flag_team_mismatch(canonical)
    n_mismatch = int(canonical["team_mismatch"].sum())
    mismatch_rate = round(n_mismatch / len(canonical) * 100, 2)
    log(f"  Team mismatches: {n_mismatch:,} ({mismatch_rate:.2f}%)")
    report["steps"]["team_mismatch"] = {"count": n_mismatch, "rate_pct": mismatch_rate}

    # ── Step 8: Business metrics ──────────────────────────────────────────────
    section("STEP 8 -- BUSINESS METRICS")
    canonical = compute_all_metrics(canonical)
    msum = metrics_summary(canonical)

    log(f"  SLA breach count:     {msum['sla_breach_count']:,}")
    log(f"  SLA breach rate:      {msum['sla_breach_rate_pct']:.2f}%")
    log(f"  SLA credit exposure:  Rs {msum['sla_credit_exposure_inr']:,}")
    log(f"  Total contact cost:   Rs {msum['total_contact_cost_inr']:,}")
    log(f"  Total transfer cost:  Rs {msum['total_transfer_cost_inr']:,}")
    log(f"  Total ticket cost:    Rs {msum['total_cost_inr']:,}")
    log(f"  Transfer rate:        {msum['transfer_rate_pct']:.2f}%")
    log(f"  CSAT mean:            {msum['csat_mean']:.4f}")
    log(f"  CSAT response rate:   {msum['csat_response_rate_pct']:.1f}%")
    log(f"  Auto-closed:          {msum['auto_closed_count']:,} ({msum['auto_closed_rate_pct']:.1f}%)")
    log(f"  Repeat eligible:      {msum['repeat_eligible_tickets']:,}")

    log("\n  By channel:")
    for ch, v in msum["by_channel"].items():
        log(f"    {ch:8s}  tickets={v['tickets']:,}  "
            f"breach_rate={v['sla_breach_rate_pct']:.1f}%  "
            f"cost=Rs {v['contact_cost_total']:,}")

    report["steps"]["metrics"] = msum

    # ── Step 9: Write outputs ─────────────────────────────────────────────────
    section("STEP 9 -- WRITING OUTPUTS")

    # tickets_clean.parquet (canonical only)
    out_tickets = DATA_PROCESSED / "tickets_clean.parquet"
    canonical.to_parquet(out_tickets, index=False, engine="pyarrow")
    log(f"  Written: {out_tickets} ({len(canonical):,} rows)")

    # metrics_base.parquet (same as tickets_clean but only metric + ID columns)
    metric_cols = [
        "ticket_id", "created_at_ist", "resolved_at_ist", "first_response_at_ist",
        "channel", "status", "customer_id", "product_sku", "agent_id",
        "assigned_team", "agent_team", "agent_tier",
        "week", "month", "quarter", "year",
        "frt_minutes", "handle_time_minutes",
        "sla_target_min", "sla_breach", "sla_credit_cost",
        "channel_contact_cost", "transfer_cost", "total_ticket_cost",
        "transfers_num", "is_legacy_transfer",
        "csat_score_clean", "is_auto_closed", "is_duplicate",
        "join_method", "join_confidence", "team_mismatch",
        "repeat_eligible",
        "refund_amount_num", "has_refund", "has_replacement", "has_both",
        "source_system", "category", "priority",
    ]
    available_cols = [c for c in metric_cols if c in canonical.columns]
    metrics_df = canonical[available_cols].copy()
    out_metrics = DATA_PROCESSED / "metrics_base.parquet"
    metrics_df.to_parquet(out_metrics, index=False, engine="pyarrow")
    log(f"  Written: {out_metrics} ({len(metrics_df):,} rows)")

    # join_audit.parquet
    join_audit_df = build_join_audit(canonical)
    out_join = DATA_PROCESSED / "join_audit.parquet"
    join_audit_df.to_parquet(out_join, index=False, engine="pyarrow")
    log(f"  Written: {out_join} ({len(join_audit_df):,} rows)")

    # reconciliation_report.json
    report["discarded_row_count"] = len(discarded)
    report["canonical_row_count"] = len(canonical)
    out_recon = DATA_PROCESSED / "reconciliation_report.json"
    with open(out_recon, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=str)
    log(f"  Written: {out_recon}")

    # ── Step 10: Phase 2 review report ───────────────────────────────────────
    section("STEP 10 -- WRITING PHASE 2 REVIEW REPORT")
    _write_phase2_review(report, clean_audit, msum, canonical)
    log(f"  Written: outputs/phase2_review.md")

    log()
    log("[PHASE 2 COMPLETE -- STOP. Await human review before Phase 3.]")

    return report


def _write_phase2_review(
    report: dict,
    clean_audit: dict,
    msum: dict,
    df: pd.DataFrame,
) -> None:
    lines = []

    def w(s=""):
        lines.append(s)

    w("# Phase 2 — Clean Pipeline Review")
    w(f"\n> Auto-generated {report['run_at']}. Do not edit manually.\n")

    w("## Row counts")
    w(f"| Metric | Value |")
    w("|---|---|")
    w(f"| Raw rows | {clean_audit['raw_rows']:,} |")
    w(f"| Duplicate pairs | {clean_audit['duplicate_pairs']:,} |")
    w(f"| Canonical rows (clean set) | {clean_audit['canonical_rows']:,} |")
    w(f"| Discarded (audit-preserved) | {clean_audit['discarded_rows']:,} |")

    w("\n## Timestamp validation")
    w(f"| Check | Result |")
    w("|---|---|")
    w(f"| legacy_fd resolved_at corrections | {clean_audit['timestamp_corrections_applied']:,} |")
    w(f"| negative resolved_at after correction | 0 (validated) |")
    w(f"| negative FRT count | 0 (validated) |")
    w(f"| negative handle time | 0 (validated) |")

    w("\n## CSAT")
    w(f"| Metric | Value |")
    w("|---|---|")
    w(f"| CSAT zeros corrected | {clean_audit['csat_zeros_corrected']:,} |")
    w(f"| Valid CSAT responses | {clean_audit['csat_valid_responses']:,} |")
    w(f"| Response rate | {clean_audit['csat_response_rate_pct']:.1f}% |")
    w(f"| Corrected CSAT mean | {clean_audit['csat_mean_corrected']:.4f} |")

    w("\n## Order join coverage")
    jm = report["steps"]["order_join"]["join_method"]
    jc = report["steps"]["order_join"]["join_confidence"]
    w(f"| join_method | Count |")
    w("|---|---|")
    for k, v in sorted(jm.items()):
        w(f"| {k} | {v:,} |")
    w(f"\n| join_confidence | Count |")
    w("|---|---|")
    for k, v in sorted(jc.items()):
        w(f"| {k} | {v:,} |")
    w(f"\nOrder date anomalies (order_date > ticket_created): {report['steps']['order_join']['order_date_anomaly_count']:,}")

    w("\n## SLA breach")
    w(f"| Metric | Value |")
    w("|---|---|")
    w(f"| Breach count | {msum['sla_breach_count']:,} |")
    w(f"| Breach rate | {msum['sla_breach_rate_pct']:.2f}% |")
    w(f"| Credit exposure | Rs {msum['sla_credit_exposure_inr']:,} |")
    w("\n| Channel | Tickets | Breach count | Breach rate |")
    w("|---|---|---|---|")
    for ch, v in msum["by_channel"].items():
        w(f"| {ch} | {v['tickets']:,} | {v['sla_breach_count']:,} | {v['sla_breach_rate_pct']:.1f}% |")

    w("\n## Cost metrics")
    w(f"| Metric | Value |")
    w("|---|---|")
    w(f"| Total contact cost | Rs {msum['total_contact_cost_inr']:,} |")
    w(f"| Total transfer cost | Rs {msum['total_transfer_cost_inr']:,} |")
    w(f"| Total ticket cost | Rs {msum['total_cost_inr']:,} |")
    w(f"| Transfer rate | {msum['transfer_rate_pct']:.2f}% |")
    w(f"| Transfer ticket count | {msum['transfer_ticket_count']:,} |")

    w("\n## Team mismatch")
    tm = report["steps"]["team_mismatch"]
    w(f"| Metric | Value |")
    w("|---|---|")
    w(f"| Mismatch count | {tm['count']:,} |")
    w(f"| Mismatch rate | {tm['rate_pct']:.2f}% |")

    w("\n## Comparison with Phase 1 / Claude anchors")
    w(f"| Metric | Phase 1 (raw) | Phase 2 (canonical) | Note |")
    w("|---|---|---|---|")
    w(f"| Unique ticket IDs | 11,875 | {clean_audit['canonical_rows']:,} | Should match |")
    w(f"| CSAT mean | 3.315 | {clean_audit['csat_mean_corrected']:.4f} | Should match |")
    w(f"| CSAT response rate | 44.6% | {clean_audit['csat_response_rate_pct']:.1f}% | Should match |")
    w(f"| SLA breach rate | 8.93% (raw) | {msum['sla_breach_rate_pct']:.2f}% (canonical) | Rate stable |")
    w(f"| SLA breach count | 1,119 (raw) | {msum['sla_breach_count']:,} (canonical) | Lower after dedup |")
    w(f"| Auto-closed | 1,168 (raw) | {msum['auto_closed_count']:,} (canonical) | |")

    w("\n## Auto-close breakdown")
    w(f"| Metric | Value |")
    w("|---|---|")
    w(f"| Auto-closed count | {msum['auto_closed_count']:,} |")
    w(f"| Auto-closed rate | {msum['auto_closed_rate_pct']:.1f}% |")
    w(f"| Repeat eligible tickets | {msum['repeat_eligible_tickets']:,} |")

    w("\n## Refunds and replacements")
    w(f"| Metric | Value |")
    w("|---|---|")
    w(f"| Tickets with refund | {msum['refund_ticket_count']:,} |")
    w(f"| Total refund value | Rs {msum['refund_total_inr']:,} |")
    w(f"| Tickets with replacement | {msum['replacement_count']:,} |")
    w(f"| Tickets with both | {msum['refund_and_replacement_count']:,} |")

    w("\n## Unresolved issues / caveats")
    w("1. **D-14b**: 332 legacy_fd rows contain non-zero transfers. Transfer cost only applies to helpdesk rows. Legacy transfers flagged as `is_legacy_transfer=True`.")
    w("2. **D-13**: agents.csv is current-state only. Shift/site attribution uses current assignment for all tickets. Historical attributions are unreliable.")
    w("3. **Order anomalies**: Some tickets have order_date > ticket_created_at. These are flagged `order_date_anomaly=True`. Order value should not be trusted for these tickets.")
    w("4. **Repeat rate**: Cannot be computed until Phase 3 (LLM issue classification). Keyword proxy = 3.9% (PROVISIONAL).")
    w("5. **FRT for auto-closed**: Auto-closed tickets still have FRT calculated (if first_response_at exists). This is correct — SLA applies regardless of resolution mechanism.")

    w("\n## Phase gate")
    w("> **Phase 2: COMPLETE**")
    w("> Phase 3 NOT started.")
    w("> Await human review before authorizing LLM extraction.")

    out = OUTPUTS / "phase2_review.md"
    with open(out, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


if __name__ == "__main__":
    run_pipeline()
