# Vireo Support Intelligence

An AI-assisted customer support analytics system for Vireo Audio (Jan 2025 – Jun 2026). It combines deterministic business analytics with LLM-assisted issue classification and evidence extraction to identify recurring customer issues, quantify repeat-contact economics, and deliver a policy-compliant operational dashboard.

**Core Principle:** `CODE CALCULATES. AI INTERPRETS. HUMANS DECIDE.`
*The LLM classifies issues in free text. All business KPIs and financial figures are computed deterministically by Python.*

---

## 1. Business Problem

Vireo Audio's customer support operation receives tickets across four channels (chat, email, voice, social). Management needed answers to:

1. **What issues are driving the highest repeat contact volume?** (recurring issue identification)
2. **What is the financial cost of repeat contacts?** (repeat-contact economics)
3. **Which frontline agents are handling the most volume?** (Tier-1 operational leaderboard)
4. **How are Tier-2 escalation specialists performing?** (Tier-2 operational visibility)
5. **Are SLA targets being met?** (SLA monitoring by channel)
6. **What does a weekly executive digest look like?** (structured business intelligence)

---

## 2. Business Goal

**Observed (from data):**
- 14.38% repeat-generating-ticket rate among 10,463 eligible tickets (1,505 tickets generated 1,573 incoming repeats)

**Planning Target:**
- Reduce repeat-generating rate to 5%

**Scenario (ESTIMATE — not realized savings):**
- At 5.0%, the target is 523 repeat-generating tickets
- Potential reduction: 982 repeat-generating tickets
- Channel-mix scenario savings: ₹2,56,489 (at ₹261.19/repeat-generating ticket)
- Blended policy scenario savings: ₹2,84,780 (at ₹290 planning standard)

*These are operational planning estimates for resource allocation, not guaranteed savings.*

---

## 3. Dataset

| Item | Value |
|---|---|
| Raw ticket rows | 12,528 |
| Migration duplicate pairs reconciled | 653 |
| Canonical tickets | **11,875** |
| Date range | Jan 2025 – Jun 2026 (79 weeks) |
| Channels | Chat, Email, Voice, Social |
| Source files | tickets, customers, orders, products, agents, support-policy.pdf, email thread |

---

## 4. Data Reconciliation

| Issue | Resolution |
|---|---|
| Migration duplicates | Keep `helpdesk` row; discard `legacy_fd` row per Policy §9 |
| Legacy timestamps | `resolved_at` offset corrected +05:30 (IST) for legacy rows only |
| CSAT zero encoding | Legacy `0` → `NaN` (non-response, excluded from averages per Policy §6) |
| Order join | Three-tier: direct `order_id` → date-bounded unique `customer+SKU` fallback → ambiguous |
| Right-censoring | 803 tickets resolved after May 31 2026 excluded from repeat denominator |
| Open/pending | 609 tickets excluded from repeat denominator and leaderboard resolution counts |

---

## 5. AI Layer

- **Model:** OpenRouter / `openai/gpt-4o-mini`
- **Input:** `customer_message` + `agent_notes` + raw `category` field
- **Output per ticket:** `issue_code`, `sub_issue`, `repeat_claim` (bool), `repeat_evidence` (quoted span), `confidence`, `ambiguous`
- **Caching:** All LLM outputs cached to `data/ai/extraction_cache.parquet` keyed by `ticket_id + prompt_hash`; subsequent runs incur zero API cost
- **Deterministic repeat detection:** The AI extracts `repeat_claim`; the actual repeat decision is made deterministically by the Python engine using Policy §6 (same customer + same issue + within 30 days of resolution)
- **The LLM does NOT calculate any business KPI, financial figure, or aggregate metric**

---

## 6. AI Evaluation

Evaluated on a 50-ticket stratified human gold set, independently labelled across all 7 issue categories:

| Metric | Value |
|---|---|
| Accuracy | **96.00%** (48/50 correct) |
| Macro-F1 | **0.9749** |
| Evidence — Exact substring match | **50/50 (100%)** |
| Hallucinated evidence | **0** |

Full 200-ticket pilot:
- 197 exact substring matches, 3 fuzzy, 0 hallucinated

Repeat claim audit (32 tickets with repeat language):
- TP 15 | FP 0 | FN 2 | TN 15
- Precision 100% | Recall 88.24%

*These metrics cover a 50–200 ticket evaluation sample, not the full 11,875 ticket corpus.*

---

## 7. Business Analytics

All metrics computed deterministically from `tickets_clean.parquet`:

| Metric | Value |
|---|---|
| Total contact spend | ₹32,48,430 |
| SLA breaches | 1,051 first-response breaches (8.85% of canonical tickets, generating ₹3,67,850 in credit exposure) |
| SLA credit risk | ₹3,67,850 |
| Transfer cost | ₹2,64,740 (1,040 tickets) |
| Mean CSAT | 3.3152 / 5.00 (5,269 responses, 44.37% rate) |
| Repeat spend | ₹4,09,470 |
| FCR rate | 85.62% |

Top issue by volume: PRODUCT (2,893 tickets, 16.9% repeat rate)
Top issue by repeat rate: PRODUCT (16.9%)
Highest cost issue: PRODUCT (₹1,28,540 repeat spend)

---

## 8. Dashboard

Start with: `streamlit run app.py` → opens at `http://localhost:8501`

| Page | Contents |
|---|---|
| 📊 Executive Digest | KPI scorecard, weekly volume trend, SLA overlay, strategic takeaways |
| 🔍 Issue Explorer | Issue taxonomy cross-tab (channel × issue, product × issue), repeat-rate overlay, interactive filters |
| 🔄 Repeat Contact Analysis | Population reconciliation, right-censoring transparency, 5% scenario simulator (slider), cost by channel and issue |
| 🏆 Tier-1 Agent Leaderboard | Frontline agent weekly closure rankings with week and team selectors; no composite score |
| 🛠️ Tier-2 Operations | Specialist case-depth view: turnaround days, open backlog, resolution quality |
| 🛡️ Quality & Methodology | Duplicate reconciliation audit, AI evaluation metrics, pipeline invariants |

---

## 9. Leaderboard Methodology

**No composite agent score is used.**

Frontline Tier-1 agents (38 agents across Chat, Email, Voice, Logistics, Billing, Returns) are presented on a **genuine weekly basis** ranked strictly by:
1. `tickets_closed DESC` (weekly volume)
2. `avg_csat DESC` (customer rating)
3. `sla_breach_rate ASC` (service quality)

Key principles:
- **Weekly closures:** Rankings reflect weekly tickets closed for each operating week, grouped strictly by ticket resolution/closure timestamp (`resolved_at_ist`), NOT creation timestamp.
- **Auto-closed separation:** Auto-closed tickets (`status == 'closed'`, 1,040 total across T1) are displayed separately from agent-resolved tickets (`status == 'resolved'`, 9,507 total across T1). Total Tier-1 closed = 10,547.
- **Strict Tier segregation:** Tier-2 specialists (6 agents handling Escalations & Warranty) are strictly segregated into the Tier-2 Operations page. They are evaluated on turnaround time (median 2.68 days) and backlog depth, never ranked against Tier-1 on weekly closure volume (Support Operating Policy §8).
- **All-time reference:** An optional expandable reference section provides 18-month cumulative closure figures without obscuring the weekly operational view.

---

## 10. Running Locally

```bash
# 1. Create and activate virtual environment
python -m venv venv
.\venv\Scripts\activate        # Windows
# source venv/bin/activate     # macOS/Linux

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure API key (required only to re-run AI pipeline)
copy .env.example .env
# Edit .env and set: OPENROUTER_API_KEY=your_key_here

# 4. (Optional) Re-run AI extraction pipeline
python -m src.intelligence_pipeline

# 5. Launch dashboard (uses pre-computed parquet outputs — no API key needed)
streamlit run app.py
```

**Required environment variable** (only for `intelligence_pipeline` re-run):
```
OPENROUTER_API_KEY=<your OpenRouter key>
OPENROUTER_MODEL=openai/gpt-4o-mini
```

---

## 11. Project Structure

```
vireo_support_intelligence/
├── app.py                      # Streamlit entry point
├── README.md
├── decision.md                 # All non-obvious design decisions
├── architecture.md             # Technical architecture reference
├── requirements.txt
├── .env.example                # Template — copy to .env, never commit .env
├── .gitignore
│
├── src/
│   ├── intelligence_pipeline.py  # Master pipeline runner
│   ├── load.py                   # Raw CSV ingestion
│   ├── clean.py                  # Deduplication, timestamps, CSAT
│   ├── joins.py                  # Customer/order/product/agent joins
│   ├── metrics.py                # SLA, FRT, costs, transfers
│   ├── issue_extractor.py        # LLM batch extraction
│   ├── llm_client.py             # OpenRouter client + retry
│   ├── repeat_detection.py       # Policy §6 repeat engine
│   ├── repeat_economics.py       # Cost aggregations
│   ├── business_metrics.py       # KPI rollups
│   ├── issue_analytics.py        # Issue/channel/product cross-tabs
│   ├── leaderboard.py            # Tier-1 / Tier-2 builder
│   ├── weekly_aggregation.py     # Weekly trend series
│   ├── ai_pipeline.py            # AI orchestration
│   ├── config.py                 # Paths and constants
│   └── dashboard/
│       ├── views.py              # One render function per page
│       ├── charts.py             # Plotly chart library
│       ├── data_loader.py        # Cached parquet readers
│       └── formatting.py         # INR / number formatters
│
├── data/
│   ├── raw/                      # Original source files (do not modify)
│   ├── processed/                # Deterministic pipeline outputs (parquet)
│   └── ai/                       # LLM extraction cache (parquet)
│
├── evaluation/
│   ├── phase3_gold_labels.csv    # 50-ticket human gold set
│   ├── repeat_audit.csv          # 32-ticket repeat claim audit
│   └── evaluate_model.py         # Evaluation scripts
│
├── outputs/
│   ├── phase3_accuracy_report.md   # AI classification evaluation
│   ├── phase3_evidence_report.md   # Evidence grounding audit
│   ├── phase3_repeat_audit.md      # Repeat claim audit
│   ├── phase4_business_report.md   # Business metrics narrative
│   ├── phase4_quality_report.json  # Reconciliation machine-readable audit
│   ├── phase6a_correctness_audit.md # Phase 6A correctness audit
│   ├── completed_submission_form.md # Submission form
│   └── figures/                    # EDA charts
│
├── memo/
│   ├── one_page_memo.md          # Executive CX brief (markdown)
│   └── one_page_memo.pdf         # Executive CX brief (PDF)
│
├── prompts/
│   └── issue_extraction.txt      # LLM prompt (versioned)
│
└── tests/
    ├── test_phase2.py                    # Data pipeline tests
    ├── test_phase3.py                    # AI extraction tests
    ├── test_phase3_eval.py               # Gold evaluation tests
    ├── test_phase4.py                    # Business metrics tests
    ├── test_phase5.py                    # Dashboard import/render tests
    ├── test_phase6a_filters.py           # Filter + scenario + chart tests
    └── test_phase6c_weekly_leaderboard.py # Weekly Tier-1 leaderboard tests
```

---

## 12. Security

- `.env` is **gitignored** and must never be committed or included in submission archives
- `.env.example` contains only placeholder variable names — no secrets
- The dashboard runs entirely offline against pre-computed parquet files; no API key is needed to view it
- No API keys, secrets, or tokens appear in source code, markdown, or outputs

---

## 13. Limitations

- **Historical roster:** `agents.csv` contains current assignments only; `to_date` is 100% null. All tickets attributed to agents' current team, not historical team.
- **Legacy transfer field inconsistency:** 268 legacy rows contain transfer values that policy says should only exist in the current helpdesk system. These are flagged in the audit but not adjusted.
- **AI evaluation sample:** The 50-ticket gold set and 200-ticket pilot are a rigorous sample — not a full-corpus evaluation. Production accuracy may vary.
- **Right-censoring:** 803 tickets cannot be observed for 30-day repeat windows. They are excluded from the repeat denominator but count in all volume and cost metrics.
- **Scenario savings:** The ₹2,84,780 figure is a planning model estimate assuming the same cost structure. It is NOT a forecast of realized savings.
- **No causal claim:** Reducing repeat-generating tickets does not automatically produce the full modelled savings; operational changes, root-cause resolution, and customer behaviour all affect outcomes.

---

## 14. Running Tests

```bash
pytest tests/ -q
```
Expected: **136 tests, 0 failures** (100% pass rate).

---

## 15. Submission Artifacts

| Artifact | Location |
|---|---|
| Interactive dashboard | `streamlit run app.py` |
| One-page executive memo | `memo/one_page_memo.pdf` / `memo/one_page_memo.md` |
| Completed submission form | `outputs/completed_submission_form.md` |
| AI evaluation evidence | `outputs/phase3_accuracy_report.md` |
| Business metrics report | `outputs/phase4_business_report.md` |
| Correctness audit | `outputs/phase6a_correctness_audit.md` |
| Final pre-submission audit | `outputs/final_pre_submission_audit.md` |
| Walkthrough recording (<=3 min) | **PENDING — recording not yet produced (to be recorded by user)** |
