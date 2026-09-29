"""
tests/test_phase3_eval.py — Automated tests for Phase 3B Model Quality & Audit.
"""

import os
import re
from pathlib import Path

import pandas as pd
import pytest
from dotenv import load_dotenv

from src.config import DATA_AI, ROOT

load_dotenv(ROOT / ".env", override=False)

GOLD_PATH = ROOT / "evaluation" / "phase3_gold_labels.csv"
REPEAT_AUDIT_PATH = ROOT / "evaluation" / "repeat_audit.csv"
PILOT_TICKETS_PATH = DATA_AI / "pilot_tickets.parquet"
PILOT_EXTRACTIONS_PATH = DATA_AI / "pilot_extractions.parquet"


@pytest.fixture
def gold_df():
    assert GOLD_PATH.exists(), "evaluation/phase3_gold_labels.csv missing"
    return pd.read_csv(GOLD_PATH)


@pytest.fixture
def pilot_df():
    assert PILOT_TICKETS_PATH.exists(), "data/ai/pilot_tickets.parquet missing"
    return pd.read_parquet(PILOT_TICKETS_PATH)


@pytest.fixture
def ext_df():
    assert PILOT_EXTRACTIONS_PATH.exists(), "data/ai/pilot_extractions.parquet missing"
    return pd.read_parquet(PILOT_EXTRACTIONS_PATH)


@pytest.fixture
def repeat_audit_df():
    assert REPEAT_AUDIT_PATH.exists(), "evaluation/repeat_audit.csv missing"
    return pd.read_csv(REPEAT_AUDIT_PATH)


def test_gold_labels_no_duplicate_ticket_ids(gold_df):
    """Ensure gold labels contain no duplicate ticket IDs."""
    assert len(gold_df) == 50
    assert gold_df["ticket_id"].nunique() == len(gold_df)


def test_every_gold_ticket_exists_in_pilot_data(gold_df, pilot_df):
    """Every gold ticket exists in pilot data."""
    assert set(gold_df["ticket_id"]).issubset(set(pilot_df["ticket_id"]))


def test_no_prediction_used_as_gold_label(gold_df, ext_df):
    """Verify that predictions are not blindly copied as gold labels."""
    merged = gold_df.merge(ext_df, on="ticket_id")
    # All gold labels have distinct review notes
    assert (gold_df["review_notes"].str.strip().str.len() > 10).all()
    # At least some disagreements exist where human labeled differently
    disagreements = merged[merged["gold_issue_code"] != merged["issue_code"]]
    assert len(disagreements) >= 2


def test_confusion_matrix_totals_equal_sample_size(gold_df, ext_df):
    """Confusion matrix totals equal evaluation sample size."""
    merged = gold_df.merge(ext_df, on="ticket_id")
    classes = sorted(list(set(merged["gold_issue_code"]).union(set(merged["issue_code"]))))
    cm = pd.DataFrame(0, index=classes, columns=classes)
    for _, r in merged.iterrows():
        cm.loc[r["gold_issue_code"], r["issue_code"]] += 1
    assert cm.values.sum() == len(gold_df) == 50


def test_precision_recall_calculations_valid(gold_df, ext_df):
    """Precision/recall calculations are mathematically valid."""
    merged = gold_df.merge(ext_df, on="ticket_id")
    classes = sorted(list(set(merged["gold_issue_code"]).union(set(merged["issue_code"]))))
    cm = pd.DataFrame(0, index=classes, columns=classes)
    for _, r in merged.iterrows():
        cm.loc[r["gold_issue_code"], r["issue_code"]] += 1

    f1_list = []
    for c in classes:
        tp = cm.loc[c, c]
        fp = cm[c].sum() - tp
        fn = cm.loc[c].sum() - tp
        prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        rec = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = 2 * prec * rec / (prec + rec) if (prec + rec) > 0 else 0.0
        assert 0.0 <= prec <= 1.0
        assert 0.0 <= rec <= 1.0
        assert 0.0 <= f1 <= 1.0
        f1_list.append(f1)

    macro_f1 = sum(f1_list) / len(f1_list)
    accuracy = (merged["gold_issue_code"] == merged["issue_code"]).sum() / len(merged)
    assert macro_f1 >= 0.85
    assert accuracy >= 0.90


def test_evidence_categories_mutually_auditable(gold_df, ext_df, pilot_df):
    """Evidence categories are mutually auditable and exhaustively partition the sample."""
    merged = gold_df.merge(ext_df, on="ticket_id").merge(
        pilot_df[["ticket_id", "customer_message", "agent_notes"]], on="ticket_id"
    )
    categories = []
    for _, r in merged.iterrows():
        span = str(r["evidence_span"] or "").strip().strip("\"'")
        comb = f"{r['customer_message']} {r['agent_notes']}"
        if span.lower() in comb.lower():
            categories.append("exact_substring")
        elif re.sub(r"\s+", " ", span).lower() in re.sub(r"\s+", " ", comb).lower():
            categories.append("normalized_whitespace")
        else:
            categories.append("other")

    assert len(categories) == 50
    # On gold set, all 50 are exact verbatim substrings
    assert categories.count("exact_substring") == 50


def test_repeat_audit_preserves_policy_definition(repeat_audit_df):
    """Repeat audit preserves the policy definition (§6)."""
    assert len(repeat_audit_df) == 32
    # Verify policy constraints on genuine repeats
    genuine = repeat_audit_df[repeat_audit_df["manual_repeat_classification"] == "genuine_policy_repeat"]
    assert len(genuine) == 17
    for _, r in genuine.iterrows():
        assert pd.notna(r["days_since_prior_resolution"])
        assert float(r["days_since_prior_resolution"]) <= 30.0
        assert pd.notna(r["matched_prior_ticket_id"])

    # Outside window must have >30 days
    outside = repeat_audit_df[repeat_audit_df["manual_repeat_classification"] == "outside_30_day_window"]
    for _, r in outside.iterrows():
        assert float(r["days_since_prior_resolution"]) > 30.0


def test_no_api_key_in_evaluation_artifacts():
    """API key never appears in evaluation artifacts."""
    api_key = os.getenv("OPENROUTER_API_KEY")
    eval_dir = ROOT / "evaluation"
    for file_path in eval_dir.rglob("*"):
        if file_path.is_file() and file_path.suffix in [".csv", ".json", ".py", ".md", ".txt"]:
            content = file_path.read_text(encoding="utf-8", errors="ignore")
            if api_key and len(api_key) > 10:
                assert api_key not in content, f"API key exposed in {file_path}"
            assert not re.search(r"sk-or-v1-[a-f0-9]{30,}", content), f"API key pattern found in {file_path}"
