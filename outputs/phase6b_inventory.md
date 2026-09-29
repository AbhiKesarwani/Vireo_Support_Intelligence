# Phase 6B — Project Inventory

> Generated: 2026-09-29
> Scope: All files excluding venv/

## Classification Key
A = REQUIRED FOR SUBMISSION
B = REQUIRED RUNTIME
C = REQUIRED SOURCE DATA  
D = REQUIRED EVALUATION EVIDENCE
E = OPTIONAL DOCUMENTATION
F = DEVELOPMENT ARTIFACT (deleted)
G = REDUNDANT / OBSOLETE (deleted)

---

## Root Level

| File | Class | Notes |
|---|---|---|
| app.py | A + B | Streamlit entry point |
| README.md | A | Authoritative project documentation |
| decision.md | A | All non-obvious design decisions |
| architecture.md | A | Technical architecture reference |
| requirements.txt | A + B | Python dependencies |
| .env.example | A | Template (no secrets) |
| .gitignore | A | Repository hygiene |
| .env | LOCAL ONLY | Contains real API key — gitignored, exclude from submission archive |

## Deleted from Root (development artifacts)
| File | Reason |
|---|---|
| full_audit.py | One-off audit script; content superseded by phase6a_correctness_audit.md |
| scan_views.py | One-off scan script; superseded |
| check_charts.py | One-off chart verification script; superseded |
| .pytest_cache/ | Auto-generated; excluded |
| __pycache__/ | Auto-generated; excluded |

---

## src/

| File | Class | Notes |
|---|---|---|
| intelligence_pipeline.py | A + B | Master pipeline runner |
| load.py | B | Raw CSV ingestion |
| clean.py | B | Deduplication, timestamps, CSAT |
| joins.py | B | Customer/order/product/agent joins |
| metrics.py | B | SLA, FRT, cost, transfers |
| issue_extractor.py | B | LLM batch extraction |
| llm_client.py | B | OpenRouter client + retry |
| repeat_detection.py | B | Policy §6 repeat engine |
| repeat_economics.py | B | Cost aggregations |
| business_metrics.py | B | KPI rollups |
| issue_analytics.py | B | Issue/channel/product cross-tabs |
| leaderboard.py | B | Tier-1 / Tier-2 builder |
| weekly_aggregation.py | B | Weekly trend series |
| ai_pipeline.py | B | AI orchestration |
| config.py | B | Paths and constants |
| pipeline.py | B | Pipeline orchestration |
| eda.py | E | EDA report generator (not needed for submission) |
| dashboard/ | A + B | All 4 dashboard source files |

---

## data/raw/

| File | Class | Notes |
|---|---|---|
| tickets.csv | C | Primary source; 12,528 raw rows |
| customers.csv | C | Customer reference |
| orders.csv | C | Order reference |
| products.csv | C | Product reference |
| agents.csv | C | Agent reference |
| support-policy.pdf | C | Policy rules document |
| Email-Thread.txt | C | Stakeholder email context |
| Readme.txt | C | Dataset readme |

---

## data/processed/

| File | Class | Notes |
|---|---|---|
| tickets_clean.parquet | B + D | 11,875 canonical tickets |
| business_metrics.parquet | B | Canonical ticket rows with all metrics |
| weekly_metrics.parquet | B | 79-week trend series |
| issue_metrics.parquet | B | 8-category issue aggregations |
| channel_issue_metrics.parquet | B | Channel × issue cross-tab |
| product_issue_metrics.parquet | B | Product × issue cross-tab |
| sla_metrics.parquet | B | SLA by channel |
| csat_metrics.parquet | B | CSAT by dimension |
| team_metrics.parquet | B | Team-level aggregations |
| tier1_leaderboard.parquet | B | 38 Tier-1 agent records |
| tier2_operations.parquet | B | 6 Tier-2 specialist records |
| repeat_economics.parquet | B | Repeat cost by channel and issue_code |
| metrics_base.parquet | B | Pre-join metrics base |
| join_audit.parquet | D | Order join quality evidence |
| reconciliation_report.json | D | Population reconciliation machine-readable |

---

## data/ai/

| File | Class | Notes |
|---|---|---|
| extraction_cache.parquet | B | Full 11,875-ticket LLM extraction cache |
| pilot_tickets.parquet | D | 200-ticket pilot input |
| pilot_extractions.parquet | D | 200-ticket pilot LLM outputs |

---

## evaluation/

| File | Class | Notes |
|---|---|---|
| phase3_gold_labels.csv | D | 50-ticket human gold labels |
| repeat_audit.csv | D | 32-ticket repeat claim audit |
| evaluate_model.py | D | Evaluation script |
| audit_evidence.py | D | Evidence grounding audit script |
| audit_repeats_full.py | D | Full repeat audit script |
| build_gold_csv.py | D | Gold set construction script |
| compare_repeats.py | D | Repeat comparison script |

---

## outputs/

| File | Class | Notes |
|---|---|---|
| phase3_accuracy_report.md | D | AI classification evaluation (96% accuracy) |
| phase3_evidence_report.md | D | Evidence grounding audit (0 hallucinations) |
| phase3_repeat_audit.md | D | Repeat claim audit (TP=15, FP=0) |
| phase4_business_report.md | D | Business metrics narrative |
| phase4_quality_report.json | D | Reconciliation + transfer audit (machine-readable) |
| phase6a_correctness_audit.md | D | Phase 6A comprehensive correctness audit |
| completed_submission_form.md | A | Submission form |
| figures/*.png | E | EDA charts (7 PNG files) |

## Deleted from outputs/ (stale development artifacts)
| File | Reason |
|---|---|
| phase3_review.md | Development-phase internal review; superseded |
| phase4_review.md | Development-phase internal review; superseded |
| phase6_inventory.md | Superseded by this document |
| eda_report.md | Development artifact; information in README + figures |
| data_quality_report.json | Superseded by phase4_quality_report.json |

---

## memo/

| File | Class | Notes |
|---|---|---|
| one_page_memo.md | A | Executive CX brief (markdown) |
| one_page_memo.pdf | A | Executive CX brief (PDF) |
| build_pdf.py | E | PDF build script |

---

## prompts/

| File | Class | Notes |
|---|---|---|
| issue_extraction.txt | A + B | Versioned LLM prompt |

---

## tests/

| File | Class | Notes |
|---|---|---|
| test_phase2.py | B | Data pipeline tests |
| test_phase3.py | B | AI extraction tests |
| test_phase3_eval.py | B | Gold evaluation tests |
| test_phase4.py | B | Business metrics tests |
| test_phase5.py | B | Dashboard import/render tests |
| test_phase6a_filters.py | B | Filter + scenario + chart regression tests |

---

## Excluded from Submission Archive
- venv/
- .env
- __pycache__/ directories
- .pytest_cache/
