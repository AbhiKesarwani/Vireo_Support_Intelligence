# ARCHITECTURE.md — Vireo Support Intelligence

## Design Principle

> **"Code calculates. AI interprets. Humans decide."**

Deterministic Python owns all numbers. The LLM processes only free text where structured rules cannot. Every AI output is cached and auditable. Business KPIs are never computed by or delegated to the LLM.

---

## System Layers

```
RAW DATA (8 files)
       │
       ▼
[LAYER 0 — VALIDATION]
  Schema check, file inventory, row counts
       │
       ▼
[LAYER 1 — RECONCILIATION]            src/load.py + src/clean.py
  Deduplication (helpdesk vs legacy_fd) — 653 pairs → 11,875 canonical
  Timestamp normalization (+5:30 on legacy resolved_at only)
  CSAT encoding (0/blank → NaN)
       │
       ▼
[LAYER 2 — ENRICHMENT]                src/joins.py
  Join customers, products, agents
  Order join: direct order_id → date-bounded SKU fallback → ambiguous
  join_method + join_confidence columns recorded for every ticket
       │
       ▼
[LAYER 3 — BUSINESS METRICS]         src/metrics.py
  FRT minutes, handle time minutes
  SLA target by channel, sla_breach boolean
  sla_credit_cost (₹350 per breach per Policy §7)
  channel_contact_cost (₹210/₹260/₹520/₹240)
  transfer_cost (₹305 per helpdesk transfer)
  is_auto_closed, week, month, quarter columns
  team_mismatch (assigned_team ≠ resolver team)
       │
       ▼
[LAYER 4 — AI EXTRACTION]            src/issue_extractor.py + src/llm_client.py
  [CACHED → data/ai/extraction_cache.parquet]
  Input: customer_message + agent_notes + category
  Output per ticket:
    issue_code, sub_issue
    repeat_claim (bool), repeat_evidence (verbatim span)
    confidence, ambiguous
  Batch size: 20 tickets per API call
  Retry: exponential backoff via tenacity
  Cache key: ticket_id + prompt_hash
       │
       ▼
[LAYER 5 — REPEAT DETECTION]         src/repeat_detection.py
  Group by customer_id + issue_code
  Window: within 30 days of prior resolved_at (Policy §6)
  Right-censoring: exclude denominator tickets resolved after May 31 2026
  Output: is_repeat, repeat_lag_days, prior_ticket_id
       │
       ▼
[LAYER 6 — BUSINESS AGGREGATION]     src/business_metrics.py
                                      src/repeat_economics.py
                                      src/issue_analytics.py
                                      src/leaderboard.py
                                      src/weekly_aggregation.py
  Weekly ticket volume + SLA + CSAT series
  Issue distribution + repeat rates + channel × issue cross-tab
  Repeat economics by channel and issue_code
  Tier-1 weekly leaderboard (frontline weekly closures, no composite score, tier1_weekly_leaderboard.parquet)
  Tier-2 operations (specialist case-depth, separate table)
  All outputs → data/processed/*.parquet
       │
       ▼
[LAYER 7 — DASHBOARD]                app.py + src/dashboard/
  6-page Streamlit app
  All data read from pre-computed parquet files
  Zero LLM calls at runtime
  Zero API cost to view dashboard
```

---

## Data Flow — Source Files to Outputs

```
tickets.csv ──────────────────────────────────────────────────────────┐
agents.csv  ──────────────────────────────────────────┐               │
customers.csv ──────────────────────────────────┐     │               │
products.csv ────────────────────────────────┐  │     │               │
orders.csv ─────────────────────────────┐    │  │     │               │
                                        │    │  │     │               │
                                        ▼    ▼  ▼     ▼               ▼
                                      [src/load.py]
                                            │
                                      [src/clean.py]
                                      dedup / timestamps / CSAT
                                            │
                                      [src/joins.py]
                                      order + customer + agent joins
                                            │
                                      [src/metrics.py]
                                      SLA / FRT / cost / transfers
                                            │
                                  data/processed/tickets_clean.parquet
                                            │
                               ┌────────────┼──────────────┐
                               ▼                           ▼
                    [src/issue_extractor.py]    [src/business_metrics.py]
                    LLM batch extraction         deterministic KPI rollups
                    (cached to parquet)                     │
                               │                           ▼
                    data/ai/extraction_cache.parquet   data/processed/
                               │                      business_metrics.parquet
                               ▼                      weekly_metrics.parquet
                    [src/repeat_detection.py]         sla_metrics.parquet
                    Policy §6 repeat engine           csat_metrics.parquet
                               │                      team_metrics.parquet
                               ▼                           │
                    [src/repeat_economics.py]               │
                    [src/issue_analytics.py]                │
                    [src/leaderboard.py]                    │
                               │                           │
                    data/processed/                         │
                    repeat_economics.parquet   ◄────────────┘
                    issue_metrics.parquet
                    channel_issue_metrics.parquet
                    product_issue_metrics.parquet
                    tier1_leaderboard.parquet
                    tier2_operations.parquet
                               │
                               ▼
                         [app.py / src/dashboard/]
                         6-page Streamlit dashboard
```

---

## Dashboard Pages

| Page | Key Contents |
|---|---|
| Executive Digest | KPI strip, weekly trend chart, strategic takeaways |
| Issue Explorer | Channel × Issue cross-tab, product × issue cross-tab, filters, repeat-rate overlay |
| Repeat Contact Analysis | Population reconciliation, right-censoring, 5% scenario simulator (interactive slider), cost charts |
| Tier-1 Agent Leaderboard | Frontline volume table with team filter; transparent individual metrics; NO composite score |
| Tier-2 Operations | Specialist case table: resolution days, open backlog, CSAT |
| Quality & Methodology | Dedup audit, AI evaluation metrics, pipeline invariants |

---

## AI / Deterministic Boundary

| Component | Type | Why |
|---|---|---|
| Deduplication | Deterministic | Rule-based: helpdesk > legacy_fd |
| Timestamp correction | Deterministic | UTC + 5:30 for legacy rows |
| SLA computation | Deterministic | Channel thresholds from Policy §7 |
| Cost calculation | Deterministic | Channel rates from Policy §7 |
| Repeat detection | Deterministic | Policy §6: customer + issue + 30 days |
| All aggregations / KPIs | Deterministic | Pandas groupby |
| Issue classification | AI (LLM) | Free text; no structured rules exist |
| Sub-issue extraction | AI (LLM) | Free text |
| Evidence span grounding | AI (LLM) | Free text quote extraction |
| Repeat claim signal | AI (LLM) | Customer language interpretation |

---

## Key Derived Columns (tickets_clean.parquet)

| Column | Source | Notes |
|---|---|---|
| `is_duplicate` | dedup logic | True if non-kept legacy duplicate |
| `frt_minutes` | `first_response_at - created_at` | |
| `handle_time_minutes` | `resolved_at - first_response_at` | |
| `sla_target_min` | channel + policy | Chat 15, Voice 120, Social 240, Email 480 |
| `sla_breach` | `frt_minutes > sla_target_min` | |
| `sla_credit_cost` | `sla_breach × 350` | |
| `channel_contact_cost` | channel lookup | ₹210/260/520/240 |
| `transfer_cost` | `transfers × 305` | Helpdesk transfers only |
| `is_auto_closed` | `status == 'closed'` | Policy §8 |
| `join_method` | direct / unique_fallback / ambiguous / none | |
| `join_confidence` | high / medium / ambiguous | |
| `team_mismatch` | `assigned_team ≠ resolver_team` | |
| `week` | ISO week from `created_at` | |

---

## AI Extraction Schema

```json
{
  "ticket_id": "TK-XXXXXX",
  "issue_code": "DELIVERY",
  "sub_issue": "marked_delivered_not_received",
  "repeat_claim": true,
  "repeat_evidence": "I already reported this last week",
  "confidence": 0.91,
  "ambiguous": false,
  "model": "openai/gpt-4o-mini",
  "prompt_hash": "3c43c3ce"
}
```

---

## Issue Taxonomy (7 active categories)

| Code | Typical Sub-issues |
|---|---|
| DELIVERY | delayed, tracking_missing, delivered_not_received, damaged, wrong_address |
| BILLING | payment_failed, duplicate_charge, invoice_error, refund_status, price_dispute |
| PRODUCT | audio_quality, connectivity, battery, charging, hardware_fault |
| APP | login_fail, firmware_update, sync_error, app_crash |
| RETURNS | return_pickup, refund_pending, replacement_request |
| WARRANTY | hardware_fault_claim, RMA_escalation, repair_status |
| OTHER | miscellaneous; does not fit taxonomy |
| UNKNOWN | ambiguous = true; classifier could not determine category |

*UNKNOWN = 0 tickets in final corpus (all 11,875 classified).*

---

## Policy Rules Encoded

| Rule | Value | Location |
|---|---|---|
| Chat SLA | 15 min | `src/metrics.py` |
| Voice SLA | 120 min | `src/metrics.py` |
| Social SLA | 240 min | `src/metrics.py` |
| Email SLA | 480 min | `src/metrics.py` |
| SLA breach credit | ₹350 | `src/metrics.py` |
| Contact cost — chat | ₹210 | `src/metrics.py` |
| Contact cost — email | ₹260 | `src/metrics.py` |
| Contact cost — voice | ₹520 | `src/metrics.py` |
| Contact cost — social | ₹240 | `src/metrics.py` |
| Blended planning cost | ₹290 | Reference only (memo + scenario) |
| Transfer cost | ₹305 | `src/metrics.py` |
| Auto-close window | 72 hours | `src/clean.py` |
| CSAT non-response | exclude from avg | `src/clean.py` |
| Repeat contact window | 30 days | `src/repeat_detection.py` |
| Tier-2 volume comparison | FORBIDDEN | `src/leaderboard.py` + UI |

---

## What Was Deliberately Not Built

| Excluded | Reason |
|---|---|
| Real-time ingestion | Not required; adds DevOps scope |
| LangChain / agent framework | Unnecessary abstraction for this scale |
| FAISS / semantic search | Nice-to-have; outside 5-hour scope |
| Fine-tuned model | No labelled training corpus; overkill |
| Forecasting / anomaly detection | Speculative; not requested |
| Composite agent score | Not justified by policy; misleading |
| Automated recommendations | Recommendations must remain human-reviewed |
| PostgreSQL / database | Parquet is sufficient for 12K row dataset |
| Agentic loops | Over-engineering |
| Sentiment-primary analytics | Sentiment is not the business question |
