"""
tests/test_phase5.py — Verification and regression tests for Phase 5 deliverables.

Covers:
1. Streamlit app & module imports
2. Dashboard data loaders integrity & schema
3. Operational issue reconciliation (exact 11,875 match, no old 6245)
4. Repeat economics unit consistency & scenario savings
5. Tier-1 vs Tier-2 operational separation
6. Memo existence & numerical fidelity
7. Security hygiene (.env gitignored, placeholders only)
"""

import json
from pathlib import Path
import pandas as pd
import pytest


def test_app_and_dashboard_modules_import():
    """Verify that app and dashboard modules import cleanly without exceptions."""
    import app
    from src.dashboard import charts, data_loader, formatting, views
    assert app is not None
    assert charts is not None
    assert data_loader is not None
    assert formatting is not None
    assert views is not None


def test_dashboard_data_loaders():
    """Verify that all dashboard data loaders return valid data structures."""
    from src.dashboard.data_loader import (
        load_business_metrics,
        load_channel_issue_metrics,
        load_csat_metrics,
        load_executive_kpis,
        load_issue_metrics,
        load_product_issue_metrics,
        load_quality_report,
        load_repeat_economics_table,
        load_repeat_summary,
        load_sla_metrics,
        load_team_metrics,
        load_tier1_leaderboard,
        load_tier2_operations,
        load_weekly_metrics,
    )

    bm = load_business_metrics()
    assert len(bm) == 11875

    wm = load_weekly_metrics()
    assert len(wm) == 79
    assert wm["tickets_created"].sum() == 11875

    iss = load_issue_metrics()
    assert len(iss) == 8
    assert iss["ticket_count"].sum() == 11875

    ch_iss = load_channel_issue_metrics()
    assert ch_iss["ticket_count"].sum() == 11875

    prod_iss = load_product_issue_metrics()
    assert prod_iss["ticket_count"].sum() == 11875

    kpis = load_executive_kpis()
    assert kpis["total_tickets"] == 11875
    assert kpis["sla_breach_count"] == 1051
    assert kpis["csat_responses"] == 5269
    assert kpis["total_contact_cost"] == 3248430.0

    repeats = load_repeat_summary()
    assert repeats["repeat_eligible_tickets"] == 10463
    assert repeats["tickets_generating_repeats"] == 1505
    assert repeats["right_censored_tickets"] == 803
    assert repeats["unresolved_tickets"] == 609
    assert repeats["incoming_repeat_contacts"] == 1573


def test_issue_taxonomy_reconciliation_and_no_old_values():
    """Verify that issue counts match the corrected values and the old 6245 bug is gone."""
    from src.dashboard.data_loader import load_issue_metrics

    iss = load_issue_metrics().set_index("issue_code")["ticket_count"].to_dict()

    expected = {
        "PRODUCT": 2893,
        "OTHER": 2572,
        "DELIVERY": 2138,
        "BILLING": 1627,
        "RETURNS": 1204,
        "APP": 824,
        "WARRANTY": 617,
        "UNKNOWN": 0,
    }
    assert iss == expected
    assert sum(iss.values()) == 11875
    assert iss["PRODUCT"] != 6245


def test_repeat_economics_unit_consistency():
    """Verify exact unit consistency and savings calculation for repeat economics."""
    from src.dashboard.data_loader import load_repeat_summary

    rep = load_repeat_summary()

    # Eligible population
    assert rep["repeat_eligible_tickets"] == 10463
    assert rep["right_censored_tickets"] == 803
    assert rep["unresolved_tickets"] == 609
    assert rep["repeat_eligible_tickets"] + rep["right_censored_tickets"] + rep["unresolved_tickets"] == 11875

    # Repeat rate numerator vs denominator
    assert rep["tickets_generating_repeats"] == 1505
    expected_rate = round(1505 / 10463, 4)
    assert rep["policy_repeat_rate"] == expected_rate
    assert rep["fcr_rate"] == round(1.0 - expected_rate, 4)

    # 5% Target Scenario
    target_tickets = int(round(0.05 * 10463))
    assert target_tickets == 523
    assert rep["avoidable_repeats_to_reduce"] == 1505 - 523  # 982

    # Savings basis
    cost_per_repeat_tkt = rep["cost_per_repeat_generating_ticket"]
    assert cost_per_repeat_tkt == 261.19
    assert rep["estimated_savings_channel_mix"] == round(982 * 261.19, 2)
    assert rep["estimated_savings_blended"] == round(982 * 290.0, 2)


def test_tier1_tier2_strict_separation():
    """Verify that Tier 1 and Tier 2 agents are completely separated."""
    from src.dashboard.data_loader import load_tier1_leaderboard, load_tier2_operations

    t1 = load_tier1_leaderboard()
    t2 = load_tier2_operations()

    assert len(t1) == 38
    assert len(t2) == 6

    t1_ids = set(t1["agent_id"])
    t2_ids = set(t2["agent_id"])
    assert len(t1_ids.intersection(t2_ids)) == 0

    # Verify Tier 2 includes open_cases
    assert "open_cases" in t2.columns
    assert t2["open_cases"].sum() > 0


def test_memo_files_exist_and_consistent():
    """Verify that one_page_memo.md and one_page_memo.pdf exist and contain key metrics."""
    memo_md = Path("memo/one_page_memo.md")
    memo_pdf = Path("memo/one_page_memo.pdf")

    assert memo_md.exists(), "memo/one_page_memo.md must exist"
    assert memo_pdf.exists(), "memo/one_page_memo.pdf must exist"

    content = memo_md.read_text(encoding="utf-8")
    for key_metric in ["11,875", "10,159", "1,107", "609", "1,051", "8.85%", "3,248,430", "10,463", "1,505", "14.38%", "2,893", "2,572", "2,138", "SCENARIO ESTIMATE"]:
        assert key_metric in content, f"Missing key metric {key_metric} in memo"


def test_submission_documentation_exists():
    """Verify completed submission documentation exists and records the absence of template."""
    sub_doc = Path("outputs/completed_submission_form.md")
    assert sub_doc.exists(), "outputs/completed_submission_form.md must exist"
    content = sub_doc.read_text(encoding="utf-8")
    assert "submission-form.md" in content
    assert "11,875" in content


def test_security_hygiene():
    """Verify that .env is gitignored and .env.example contains only placeholders."""
    gitignore = Path(".gitignore").read_text(encoding="utf-8")
    assert ".env" in gitignore

    env_ex = Path(".env.example").read_text(encoding="utf-8")
    assert "OPENROUTER_API_KEY=" in env_ex or "OPENAI_API_KEY=" in env_ex
    # Must not contain actual secret key
    assert "sk-or-v1-" not in env_ex
    assert "sk-proj-" not in env_ex
