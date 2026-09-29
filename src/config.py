"""
src/config.py — Policy constants and file paths.

ALL business-rule numbers come from this file.
No magic numbers in any other module.
Source: support-policy.pdf v3.2
"""

from __future__ import annotations
from datetime import timedelta
from pathlib import Path

# ── Paths ──────────────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent
DATA_RAW = ROOT / "data" / "raw"
DATA_PROCESSED = ROOT / "data" / "processed"
DATA_AI = ROOT / "data" / "ai"
OUTPUTS = ROOT / "outputs"

# UUID-prefixed filenames (actual names on disk)
RAW_FILES = {
    "tickets":   DATA_RAW / "cded5ec7-cd54-40e6-ba66-7b3e581319c7-tickets.csv",
    "agents":    DATA_RAW / "1bb95ea8-f7cb-44b6-b5d2-2fb20c9a4e47-agents.csv",
    "orders":    DATA_RAW / "e5c326e5-4764-4ab0-87fd-75abb8f287ae-orders.csv",
    "customers": DATA_RAW / "52fbee44-8a34-4fda-875a-b68ed16c17f2-customers.csv",
    "products":  DATA_RAW / "8e1b3214-16f2-4456-a618-cd1a4e8bddef-products.csv",
    "policy":    DATA_RAW / "e7923975-d5e7-450e-bdf7-19c75e616668-support-policy.pdf",
}

# ── Timestamp ─────────────────────────────────────────────────────────────────
# Legacy resolved_at is stored in UTC (event log). All other timestamps are IST.
# policy §9: "resolution timestamps for migrated tickets reconstructed from legacy event log (UTC)"
IST_OFFSET = timedelta(hours=5, minutes=30)

# Migration cutoff: tickets before this date may exist in both systems
MIGRATION_DATE = "2025-09-14"

# ── SLA targets (minutes) — policy §4 ────────────────────────────────────────
SLA_TARGETS_MIN: dict[str, int] = {
    "chat":   15,
    "email":  480,   # 8 hours
    "voice":  120,   # 2 hours
    "social": 240,   # 4 hours
}

# ── Costs — policy §7 ─────────────────────────────────────────────────────────
CHANNEL_CONTACT_COST: dict[str, int] = {
    "chat":   210,
    "email":  260,
    "voice":  520,
    "social": 240,
}
BLENDED_CONTACT_COST = 290        # official planning standard (Priya's email)
SLA_BREACH_CREDIT = 350           # Rs per breach — policy §4
TRANSFER_COST = 305               # Rs per transfer — policy §7
AGENT_HOUR_COST = 165             # Rs per agent-hour — policy §7

# ── Repeat contact — policy §6 ────────────────────────────────────────────────
REPEAT_WINDOW_DAYS = 30
RIGHT_CENSOR_DATE = "2026-05-31"  # exclude tickets resolved after this from repeat denominator

# ── CSAT — policy §6 ─────────────────────────────────────────────────────────
CSAT_VALID_MIN = 1
CSAT_VALID_MAX = 5
CSAT_LEGACY_NO_RESPONSE = 0       # legacy_fd encodes no-response as 0

# ── Auto-close — policy §8 ────────────────────────────────────────────────────
AUTO_CLOSE_STATUS = "closed"      # status value for auto-closed tickets

# ── Source systems ────────────────────────────────────────────────────────────
SOURCE_HELPDESK = "helpdesk"
SOURCE_LEGACY = "legacy_fd"

# ── Schema expectations ───────────────────────────────────────────────────────
REQUIRED_COLUMNS = {
    "tickets": [
        "ticket_id", "created_at", "first_response_at", "resolved_at",
        "status", "channel", "customer_id", "order_id", "product_sku",
        "category", "priority", "assigned_team", "agent_id", "transfers",
        "csat_score", "refund_amount_inr", "refund_reason_code",
        "replacement_issued", "customer_message", "agent_notes", "source_system",
    ],
    "agents":    ["agent_id", "name", "site", "team", "shift", "tier", "from_date", "to_date"],
    "orders":    ["order_id", "customer_id", "sku", "order_date", "channel", "qty",
                  "order_value_inr", "lot_code"],
    "customers": ["customer_id", "name", "city", "state", "signup_date", "care_plus"],
    "products":  ["sku", "product_name", "family", "launch_date", "unit_cost_inr",
                  "retail_price_inr", "warranty_months"],
}

# ── Valid categorical values (for validation) ─────────────────────────────────
VALID_CHANNELS = {"chat", "email", "voice", "social"}
VALID_STATUSES = {"resolved", "closed", "open", "pending"}
VALID_SOURCE_SYSTEMS = {SOURCE_HELPDESK, SOURCE_LEGACY}
VALID_PRIORITIES = {"Low", "Normal", "High"}

# ── Phase 3: AI Issue Extraction & Repeat Detection ───────────────────────────
PROMPTS_DIR = ROOT / "prompts"
PROMPT_ISSUE_EXTRACTION = PROMPTS_DIR / "issue_extraction.txt"

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_MODEL = "openai/gpt-4o-mini"

APPROVED_TAXONOMY = [
    "DELIVERY",
    "BILLING",
    "PRODUCT",
    "APP",
    "RETURNS",
    "WARRANTY",
    "OTHER",
    "UNKNOWN",
]

PILOT_SIZE = 200
PILOT_SEED = 42

PILOT_TICKETS_FILE = DATA_AI / "pilot_tickets.parquet"
PILOT_EXTRACTIONS_FILE = DATA_AI / "pilot_extractions.parquet"
EXTRACTION_CACHE_FILE = DATA_AI / "extraction_cache.parquet"

# ── Phase 4: Business Metrics & Repeat-Contact Economics ──────────────────────
REPEAT_CONTACT_TARGET = 0.05  # Working planning target (5.0%)

RAW_TO_OPERATIONAL_TAXONOMY: dict[str, str] = {
    "Delivery & Shipping": "DELIVERY",
    "Billing & Payments": "BILLING",
    "Returns & Refunds": "RETURNS",
    "Warranty & Repair": "WARRANTY",
    "App & Firmware": "APP",
    "Connectivity": "PRODUCT",
    "Charging & Battery": "PRODUCT",
    "Audio Quality": "PRODUCT",
    "Product Enquiry": "OTHER",
    "Account & Login": "OTHER",
    "Other": "OTHER",
}

# Phase 4 Parquet paths
BUSINESS_METRICS_PARQUET = DATA_PROCESSED / "business_metrics.parquet"
WEEKLY_METRICS_PARQUET = DATA_PROCESSED / "weekly_metrics.parquet"
ISSUE_METRICS_PARQUET = DATA_PROCESSED / "issue_metrics.parquet"
CHANNEL_ISSUE_METRICS_PARQUET = DATA_PROCESSED / "channel_issue_metrics.parquet"
PRODUCT_ISSUE_METRICS_PARQUET = DATA_PROCESSED / "product_issue_metrics.parquet"
TIER1_LEADERBOARD_PARQUET = DATA_PROCESSED / "tier1_leaderboard.parquet"
TIER1_WEEKLY_LEADERBOARD_PARQUET = DATA_PROCESSED / "tier1_weekly_leaderboard.parquet"
TIER2_OPERATIONS_PARQUET = DATA_PROCESSED / "tier2_operations.parquet"
TEAM_METRICS_PARQUET = DATA_PROCESSED / "team_metrics.parquet"
SLA_METRICS_PARQUET = DATA_PROCESSED / "sla_metrics.parquet"
CSAT_METRICS_PARQUET = DATA_PROCESSED / "csat_metrics.parquet"
REPEAT_ECONOMICS_PARQUET = DATA_PROCESSED / "repeat_economics.parquet"

# Phase 4 Report paths
PHASE4_BUSINESS_REPORT = OUTPUTS / "phase4_business_report.md"
PHASE4_QUALITY_REPORT = OUTPUTS / "phase4_quality_report.json"
PHASE4_REVIEW = OUTPUTS / "phase4_review.md"


