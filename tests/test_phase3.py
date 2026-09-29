"""
tests/test_phase3.py — Phase 3 Test Suite.

Covers:
- T01 through T15 automated pipeline & contract tests
- Synthetic repeat-contact detection unit tests
"""

import json
import os
import re
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest
from dotenv import load_dotenv

from src.ai_pipeline import generate_stratified_pilot
from src.config import (
    APPROVED_TAXONOMY,
    DATA_AI,
    DATA_PROCESSED,
    OUTPUTS,
    PILOT_EXTRACTIONS_FILE,
    PILOT_SEED,
    PILOT_SIZE,
    PILOT_TICKETS_FILE,
    PROMPT_ISSUE_EXTRACTION,
    RIGHT_CENSOR_DATE,
    ROOT,
)
from src.issue_extractor import (
    IssueExtractor,
    IssueExtractionSchema,
    compute_prompt_version,
    parse_and_clean_json,
    verify_evidence_grounding,
)
from src.llm_client import LLMClient, LLMClientError
from src.repeat_detection import calculate_repeat_metrics, detect_repeat_contacts

load_dotenv(ROOT / ".env", override=False)


# ==============================================================================
# FIXTURES
# ==============================================================================

@pytest.fixture(scope="session")
def clean_tickets():
    path = DATA_PROCESSED / "tickets_clean.parquet"
    if not path.exists():
        pytest.skip("tickets_clean.parquet missing; run Phase 2 first")
    return pd.read_parquet(path)


@pytest.fixture(scope="session")
def pilot_tickets(clean_tickets):
    if PILOT_TICKETS_FILE.exists():
        return pd.read_parquet(PILOT_TICKETS_FILE)
    return generate_stratified_pilot(clean_tickets, target_n=PILOT_SIZE, seed=PILOT_SEED)


@pytest.fixture(scope="session")
def pilot_extractions():
    if not PILOT_EXTRACTIONS_FILE.exists():
        pytest.skip("pilot_extractions.parquet not yet generated")
    return pd.read_parquet(PILOT_EXTRACTIONS_FILE)


# ==============================================================================
# AUTOMATED TESTS T01 - T15
# ==============================================================================

def test_t01_pilot_unique_ticket_ids(pilot_tickets):
    """T01 — every pilot ticket has a unique ticket_id."""
    assert len(pilot_tickets) > 0
    assert pilot_tickets["ticket_id"].nunique() == len(pilot_tickets)


def test_t02_extractions_map_to_existing_tickets(clean_tickets, pilot_extractions):
    """T02 — every extraction maps to an existing ticket_id."""
    assert set(pilot_extractions["ticket_id"]).issubset(set(clean_tickets["ticket_id"]))


def test_t03_no_duplicate_extractions(pilot_extractions):
    """T03 — no duplicate extraction for the same ticket_id."""
    assert pilot_extractions["ticket_id"].nunique() == len(pilot_extractions)


def test_t04_required_json_fields_exist(pilot_extractions):
    """T04 — all required JSON fields exist."""
    required = ["issue_code", "sub_issue", "repeat_claim", "evidence_span", "confidence", "ambiguous"]
    for field in required:
        assert field in pilot_extractions.columns, f"Missing field: {field}"


def test_t05_confidence_numeric_and_in_range(pilot_extractions):
    """T05 — confidence is numeric and within [0,1]."""
    for val in pilot_extractions["confidence"]:
        assert isinstance(val, (int, float, np.floating, np.integer))
        assert 0.0 <= float(val) <= 1.0


def test_t06_issue_code_belongs_to_taxonomy(pilot_extractions):
    """T06 — issue_code belongs to the approved taxonomy."""
    for code in pilot_extractions["issue_code"]:
        assert code in APPROVED_TAXONOMY, f"Invalid issue code: {code}"


def test_t07_ambiguous_values_valid_booleans(pilot_extractions):
    """T07 — ambiguous values are valid booleans."""
    for val in pilot_extractions["ambiguous"]:
        assert isinstance(val, (bool, np.bool_))


def test_t08_repeat_claim_values_valid(pilot_extractions):
    """T08 — repeat_claim is true/false/null."""
    for val in pilot_extractions["repeat_claim"]:
        assert (val is True) or (val is False) or (val is None) or pd.isna(val)


def test_t09_evidence_spans_grounded(pilot_tickets, pilot_extractions):
    """T09 — evidence_span is actually present in the source customer_message/agent_notes when non-empty."""
    merged = pilot_tickets.merge(pilot_extractions, on="ticket_id")
    for _, row in merged.iterrows():
        span = str(row.get("evidence_span", "") or "").strip()
        if span:
            is_grounded = verify_evidence_grounding(
                span,
                str(row.get("customer_message", "")),
                str(row.get("agent_notes", "")),
            )
            assert is_grounded, f"Ungrounded span '{span}' for ticket {row['ticket_id']}"


def test_t10_no_api_key_in_artifacts():
    """T10 — no API key appears anywhere in generated artifacts/logs."""
    api_key = os.getenv("OPENROUTER_API_KEY")
    # Scan files in outputs/, data/ai/, prompts/, and tests/
    dirs_to_check = [OUTPUTS, DATA_AI, ROOT / "prompts"]
    files_to_check = []
    for d in dirs_to_check:
        if d.exists():
            files_to_check.extend([p for p in d.rglob("*") if p.is_file()])

    # Check .env.example
    env_example = ROOT / ".env.example"
    if env_example.exists():
        files_to_check.append(env_example)

    for file_path in files_to_check:
        if file_path.suffix in [".parquet", ".png"]:
            continue  # Binary
        content = file_path.read_text(encoding="utf-8", errors="ignore")
        if api_key and len(api_key) > 10:
            assert api_key not in content, f"API key exposed in {file_path}"
        # Ensure no openrouter key pattern
        assert not re.search(r"sk-or-v1-[a-f0-9]{30,}", content), f"Potential OpenRouter API key found in {file_path}"


def test_t11_cached_tickets_not_recalled(pilot_tickets, pilot_extractions):
    """T11 — cached tickets are not unnecessarily re-called."""
    # Create an extractor with mocked LLM client
    mock_llm = MagicMock()
    mock_llm.model = "openai/gpt-4o-mini"
    extractor = IssueExtractor(llm_client=mock_llm)

    sample_row = pilot_tickets.iloc[0].to_dict()
    ticket_id = str(sample_row["ticket_id"])

    # First ensure it's in the extractor's cache_df
    assert extractor.is_cached(ticket_id)

    # Call extraction
    result = extractor.extract_ticket(sample_row, use_cache=True)
    assert result["from_cache"] is True
    # Ensure LLM generate was NOT called
    assert mock_llm.generate.call_count == 0



def test_t12_malformed_responses_handled_explicitly(pilot_tickets):
    """T12 — malformed model responses are handled explicitly."""
    mock_llm = MagicMock()
    mock_llm.generate.return_value = {
        "raw_text": "Not a JSON: {broken,",
        "extracted_at": "2026-09-29T00:00:00Z",
        "model": "test-model",
    }
    extractor = IssueExtractor(llm_client=mock_llm)
    sample_row = pilot_tickets.iloc[0].to_dict()

    with pytest.raises(ValueError, match="Extraction failed"):
        extractor.extract_ticket(sample_row, use_cache=False, max_retries=1)


def test_t13_pipeline_resumes_after_failure(pilot_tickets, tmp_path):
    """T13 — pipeline can resume after a failed API request without repeating completed items."""
    cache_path = tmp_path / "test_cache.parquet"
    mock_llm = MagicMock()
    mock_llm.model = "test-model"

    # Row 1 succeeds, Row 2 fails
    call_count = 0
    def mock_generate(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return {
                "raw_text": json.dumps({
                    "issue_code": "DELIVERY",
                    "sub_issue": "delayed_delivery",
                    "repeat_claim": False,
                    "evidence_span": "",
                    "confidence": 0.9,
                    "ambiguous": False,
                    "reason": "delayed package",
                }),
                "extracted_at": "2026-09-29T00:00:00Z",
                "model": "test-model",
            }
        raise RuntimeError("Transient network failure")

    mock_llm.generate.side_effect = mock_generate
    extractor = IssueExtractor(llm_client=mock_llm, cache_file=cache_path)

    row1 = pilot_tickets.iloc[0].to_dict()
    row2 = pilot_tickets.iloc[1].to_dict()

    res1 = extractor.extract_ticket(row1, use_cache=True)
    assert res1["ticket_id"] == str(row1["ticket_id"])

    with pytest.raises(ValueError):
        extractor.extract_ticket(row2, use_cache=True, max_retries=1)

    # Resume: Row 1 should be loaded from cache, generate only called for Row 2
    mock_llm.generate.side_effect = None
    mock_llm.generate.return_value = {
        "raw_text": json.dumps({
            "issue_code": "BILLING",
            "sub_issue": "invoice_request",
            "repeat_claim": False,
            "evidence_span": "",
            "confidence": 0.9,
            "ambiguous": False,
            "reason": "invoice needed",
        }),
        "extracted_at": "2026-09-29T00:00:00Z",
        "model": "test-model",
    }
    prev_calls = mock_llm.generate.call_count

    res1_cached = extractor.extract_ticket(row1, use_cache=True)
    assert res1_cached["from_cache"] is True
    assert mock_llm.generate.call_count == prev_calls  # No new call for row1

    res2_resume = extractor.extract_ticket(row2, use_cache=True)
    assert res2_resume["ticket_id"] == str(row2["ticket_id"])


def test_t14_deterministic_seed_reproduces_pilot(clean_tickets):
    """T14 — deterministic seed reproduces the same pilot sample."""
    sample1 = generate_stratified_pilot(clean_tickets, target_n=50, seed=42)
    sample2 = generate_stratified_pilot(clean_tickets, target_n=50, seed=42)
    pd.testing.assert_frame_equal(sample1, sample2)


def test_t15_no_business_metric_in_llm_output(pilot_extractions):
    """T15 — no business metric is generated by the LLM output."""
    forbidden = ["sla_breach", "sla_target", "cost", "csat", "savings", "refund_amount", "credit"]
    for col in pilot_extractions.columns:
        for f in forbidden:
            assert f not in col.lower(), f"Forbidden business metric in LLM extractions: {col}"


# ==============================================================================
# SYNTHETIC REPEAT DETECTION TESTS
# ==============================================================================

def create_synthetic_tickets():
    t0 = datetime(2026, 1, 1, 10, 0, 0)
    return pd.DataFrame([
        {
            "ticket_id": "TK-101",
            "customer_id": "CUST-A",
            "created_at_ist": t0,
            "resolved_at_ist": t0 + timedelta(hours=2),
            "status": "resolved",
            "product_sku": "SKU-1",
            "is_duplicate": False,
            "repeat_eligible": True,
            "issue_code": "DELIVERY",
            "ambiguous": False,
        },
        {
            "ticket_id": "TK-102",
            "customer_id": "CUST-A",
            "created_at_ist": t0 + timedelta(days=10),
            "resolved_at_ist": t0 + timedelta(days=10, hours=2),
            "status": "resolved",
            "product_sku": "SKU-1",
            "is_duplicate": False,
            "repeat_eligible": True,
            "issue_code": "DELIVERY",
            "ambiguous": False,
        },
        {
            "ticket_id": "TK-103",
            "customer_id": "CUST-A",
            "created_at_ist": t0 + timedelta(days=45),
            "resolved_at_ist": t0 + timedelta(days=45, hours=2),
            "status": "resolved",
            "product_sku": "SKU-1",
            "is_duplicate": False,
            "repeat_eligible": True,
            "issue_code": "DELIVERY",
            "ambiguous": False,
        },
        {
            "ticket_id": "TK-104",
            "customer_id": "CUST-B",
            "created_at_ist": t0 + timedelta(days=12),
            "resolved_at_ist": t0 + timedelta(days=12, hours=2),
            "status": "resolved",
            "product_sku": "SKU-1",
            "is_duplicate": False,
            "repeat_eligible": True,
            "issue_code": "DELIVERY",
            "ambiguous": False,
        },
        {
            "ticket_id": "TK-105",
            "customer_id": "CUST-A",
            "created_at_ist": t0 + timedelta(days=15),
            "resolved_at_ist": t0 + timedelta(days=15, hours=2),
            "status": "resolved",
            "product_sku": "SKU-1",
            "is_duplicate": False,
            "repeat_eligible": True,
            "issue_code": "BILLING",
            "ambiguous": False,
        },
        {
            "ticket_id": "TK-106",
            "customer_id": "CUST-C",
            "created_at_ist": t0 + timedelta(days=1),
            "resolved_at_ist": pd.NaT,
            "status": "open",
            "product_sku": "SKU-2",
            "is_duplicate": False,
            "repeat_eligible": False,
            "issue_code": "PRODUCT",
            "ambiguous": False,
        },
        {
            "ticket_id": "TK-107",
            "customer_id": "CUST-C",
            "created_at_ist": t0 + timedelta(days=5),
            "resolved_at_ist": t0 + timedelta(days=5, hours=1),
            "status": "resolved",
            "product_sku": "SKU-2",
            "is_duplicate": False,
            "repeat_eligible": True,
            "issue_code": "PRODUCT",
            "ambiguous": False,
        },
        {
            "ticket_id": "TK-108",
            "customer_id": "CUST-D",
            "created_at_ist": t0 + timedelta(days=1),
            "resolved_at_ist": t0 + timedelta(days=1, hours=2),
            "status": "resolved",
            "product_sku": "SKU-3",
            "is_duplicate": False,
            "repeat_eligible": True,
            "issue_code": "UNKNOWN",
            "ambiguous": True,
        },
        {
            "ticket_id": "TK-109",
            "customer_id": "CUST-D",
            "created_at_ist": t0 + timedelta(days=3),
            "resolved_at_ist": t0 + timedelta(days=3, hours=1),
            "status": "resolved",
            "product_sku": "SKU-3",
            "is_duplicate": False,
            "repeat_eligible": True,
            "issue_code": "UNKNOWN",
            "ambiguous": True,
        },
        {
            "ticket_id": "TK-110",
            "customer_id": "CUST-E",
            "created_at_ist": datetime(2026, 6, 10, 10, 0, 0),
            "resolved_at_ist": datetime(2026, 6, 10, 12, 0, 0),
            "status": "resolved",
            "product_sku": "SKU-4",
            "is_duplicate": False,
            "repeat_eligible": False,
            "issue_code": "WARRANTY",
            "ambiguous": False,
        },
        {
            "ticket_id": "TK-111",
            "customer_id": "CUST-A",
            "created_at_ist": t0 + timedelta(days=5),
            "resolved_at_ist": t0 + timedelta(days=5, hours=2),
            "status": "resolved",
            "product_sku": "SKU-1",
            "is_duplicate": True,  # Discarded migration duplicate
            "repeat_eligible": False,
            "issue_code": "DELIVERY",
            "ambiguous": False,
        },
    ])


def test_repeat_same_customer_same_issue_within_30d():
    """same customer + same issue + within 30 days -> repeat."""
    df = create_synthetic_tickets()
    res = detect_repeat_contacts(df, repeat_window_days=30)
    tk102 = res[res["ticket_id"] == "TK-102"].iloc[0]
    assert bool(tk102["repeat_candidate"]) is True
    assert tk102["prior_ticket_id"] == "TK-101"
    assert tk102["days_since_prior_resolution"] < 30.0


def test_repeat_same_customer_same_issue_over_30d():
    """same customer + same issue + >30 days -> not repeat."""
    df = create_synthetic_tickets()
    res = detect_repeat_contacts(df, repeat_window_days=30)
    tk103 = res[res["ticket_id"] == "TK-103"].iloc[0]
    # TK-103 is 35 days after TK-102 resolution
    assert bool(tk103["repeat_candidate"]) is False


def test_repeat_different_customer():
    """different customer -> not repeat."""
    df = create_synthetic_tickets()
    res = detect_repeat_contacts(df, repeat_window_days=30)
    tk104 = res[res["ticket_id"] == "TK-104"].iloc[0]
    assert bool(tk104["repeat_candidate"]) is False


def test_repeat_different_issue():
    """different issue -> not repeat."""
    df = create_synthetic_tickets()
    res = detect_repeat_contacts(df, repeat_window_days=30)
    tk105 = res[res["ticket_id"] == "TK-105"].iloc[0]
    # CUST-A has prior tickets, but TK-105 is BILLING, priors are DELIVERY
    assert bool(tk105["repeat_candidate"]) is False


def test_repeat_no_prior_resolution():
    """no prior resolution -> not repeat."""
    df = create_synthetic_tickets()
    res = detect_repeat_contacts(df, repeat_window_days=30)
    tk107 = res[res["ticket_id"] == "TK-107"].iloc[0]
    # Prior ticket TK-106 was open (never resolved)
    assert bool(tk107["repeat_candidate"]) is False


def test_repeat_ambiguous_issue_excluded():
    """ambiguous issue -> excluded/flagged."""
    df = create_synthetic_tickets()
    res = detect_repeat_contacts(df, repeat_window_days=30)
    tk109 = res[res["ticket_id"] == "TK-109"].iloc[0]
    assert bool(tk109["repeat_candidate"]) is False
    assert tk109["repeat_reason"] == "ambiguous_or_unknown_issue"



def test_repeat_right_censored_excluded_from_denominator():
    """right-censored ticket -> excluded from denominator."""
    df = create_synthetic_tickets()
    res = detect_repeat_contacts(df, repeat_window_days=30)
    metrics = calculate_repeat_metrics(res, right_censor_date=RIGHT_CENSOR_DATE)
    assert metrics["right_censored_count"] >= 1
    # TK-110 resolved in June 2026, after 2026-05-31 cutoff
    assert metrics["right_censored_cutoff"] == RIGHT_CENSOR_DATE


def test_repeat_duplicate_migration_record_ignored():
    """duplicate migration record -> never creates a false repeat."""
    df = create_synthetic_tickets()
    res = detect_repeat_contacts(df, repeat_window_days=30)
    # TK-111 has is_duplicate=True
    tk102 = res[res["ticket_id"] == "TK-102"].iloc[0]
    assert tk102["prior_ticket_id"] != "TK-111"  # Skipped duplicate, matched TK-101
