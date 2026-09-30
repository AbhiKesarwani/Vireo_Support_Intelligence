# Vireo Audio Support Intelligence — Submission Documentation
## Assignment Deliverables & Submission Summary

> **Document Status Notice:**  
> A template file named `submission-form.md` was **not provided** in the original assignment data pack.  
> As verified in `Readme.txt` (line 41: *"No other documentation is available"*) and confirmed via filesystem audit of both `c:/Users/abhin/Downloads/Banao/` and `vireo_support_intelligence/`, no formal form was supplied.  
> This document serves as the official completed submission record, answering all requirements, stakeholder questions from `Email-Thread.txt`, and core technical benchmarks.

---

### 1. Candidate & Project Information
- **Project Name:** Vireo Audio Support Intelligence System
- **Candidate Implementation:** Automated CX & Support Operations Intelligence Pipeline & Executive Dashboard
- **Target Audience:** Priya Raman (Head of CX), Arjun Mehta (Finance Controller), Neha Kulkarni (Support Operations Manager)
- **Coverage Window:** 18 Months (1 January 2025 – 30 June 2026)
- **Core Engineering Principle:** `CODE CALCULATES. AI INTERPRETS. HUMANS DECIDE.`

---

### 2. Stakeholder Answers (Email-Thread.txt Alignment)

#### Q1 (Priya Raman): "Weekly digest + a leaderboard by tickets closed. Keep it simple, I don't need a platform."
- **Delivered Solution:** 
  1. Streamlit application (`app.py`) providing an instantaneous, zero-latency executive digest and frontline volume leaderboard.
  2. One-page executive brief (`memo/one_page_memo.md` and `memo/one_page_memo.pdf`) summarizing operational findings, root causes, and repeat economics.
  3. Pre-computed Parquet intelligence pipeline that eliminates database and live LLM overhead.

#### Q2 (Arjun Mehta, Finance): "What does it save? Our cost per contact is roughly Rs 180... If it takes contacts out of the queue I'm interested. Also I do not want a per-ticket model bill."
- **Financial Findings:**
  1. Blended contact cost is **₹290** per policy doc §7 (not ₹180), yielding **₹32,48,430** in total direct contact spend across 11,875 canonical tickets.
  2. Repeat contacts account for **1,573** incoming contacts costing **₹4,09,470** (12.6% of entire support budget).
  3. **Planning Scenario (5% Target):** Reducing repeat-generating tickets from 14.38% (1,505 tickets) to 5.00% (523 tickets) yields an avoidable demand reduction of **982** repeat tickets.
  4. **Modelled Scenario Savings:** **₹2,56,488.58** (channel-mix basis at ₹261.19/ticket) to **₹2,84,780.00** (policy blended ₹290 standard).
  5. **Zero Per-Ticket Model Bill:** AI extraction is performed offline via a cached pilot pipeline; the production dashboard runs 100% deterministically with **zero live LLM API calls**.

#### Q3 (Neha Kulkarni, Operations): "Don't rank my warranty team on ticket counts, their cases take days by design... Chat frontline grumbling about 'I already told your colleague this'."
- **Operational Adjustments:**
  1. **Strict Tier Separation:** Tier-1 frontline agents (38 agents) are ranked by ticket volume on the Tier-1 Leaderboard. Tier-2 Escalations & Warranty agents (6 agents) are strictly segregated into the Tier-2 Operations page, evaluated by case turnaround time (median 2.68 days) and backlog depth rather than volume.
  2. **Repeat Contact Grounding:** Validated that repeat contacts are real operational demand (14.38% repeat rate). 100% of repeat mentions in the customer text audit are grounded in actual prior issues.

---

### 3. Audited Headline Metrics Summary

| Metric Dimension | Validated Value | Technical Source / Invariant |
| :--- | :--- | :--- |
| **Raw Ingested Records** | **12,528** rows | `tickets.csv` raw source |
| **Canonical Reconciled Population** | **11,875** tickets | Migration deduplication (653 duplicates) |
| **Resolved Tickets** | **10,159** tickets | Final status = resolved |
| **Auto-Closed Tickets** | **1,107** tickets | Final status = closed (no customer reply) |
| **Open / Pending Tickets** | **609** tickets | Active operational backlog |
| **SLA Breach Count & Rate** | **1,051** breaches (**8.85%**) | Policy §2 SLA rules |
| **SLA Credit Risk Exposure** | **₹3,67,850** | Policy §2 penalty credits |
| **Total Direct Contact Spend** | **₹32,48,430** | Policy §7 channel rates |
| **Helpdesk Transfer Surcharges** | **₹2,64,740** (1,040 tkts) | Policy §7 (₹305 / transfer) |
| **Valid CSAT Responses** | **5,269** responses (**44.37%**) | Legacy 0s converted to null |
| **Overall Mean CSAT** | **3.3152** / 5.00 | Valid 1–5 response mean |
| **Repeat-Eligible Evaluated Cohort** | **10,463** tickets | Resolved $\le$ 31-May-2026 (>=30d window) |
| **Right-Censored Tickets** | **803** tickets | Resolved June 2026 |
| **Repeat-Generating Tickets** | **1,505** tickets (**14.38%**) | Policy §6 same-issue within 30 days |
| **First Contact Resolution (FCR)** | **85.62%** | $1.0 - 0.1438$ |
| **Total Incoming Repeat Contacts** | **1,573** tickets | All-time repeat intake |
| **Total Repeat Contact Spend** | **₹4,09,470** | Incoming repeat contact spend |
| **5% Target Avoidable Tickets** | **982** repeat tickets | $1,505 - 523$ |
| **5% Scenario Savings (Channel-Mix)** | **₹2,56,488.58** | $982 \times ₹261.19$ (SCENARIO ESTIMATE) |
| **5% Scenario Savings (Blended)** | **₹2,84,780.00** | $982 \times ₹290.00$ (SCENARIO ESTIMATE) |

---

### 4. Operational Taxonomy Reconciliation (100.00% Coverage)

| Issue Category | Canonical Tickets | Volume Share | Repeat Rate | Total Spend | Repeat Spend | Mean CSAT |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **PRODUCT** | 2,893 | 24.36% | 16.90% | ₹8,07,170 | ₹1,28,540 | 3.32 |
| **OTHER** | 2,572 | 21.66% | 9.72% | ₹7,07,440 | ₹63,160 | 3.39 |
| **DELIVERY** | 2,138 | 18.00% | 15.34% | ₹5,73,810 | ₹84,440 | 3.03 |
| **BILLING** | 1,627 | 13.70% | 12.78% | ₹4,43,020 | ₹52,430 | 3.44 |
| **RETURNS** | 1,204 | 10.14% | 13.04% | ₹3,35,930 | ₹42,750 | 3.35 |
| **APP** | 824 | 6.94% | 12.99% | ₹2,16,210 | ₹24,960 | 3.29 |
| **WARRANTY** | 617 | 5.20% | 14.59% | ₹1,64,850 | ₹13,190 | 3.51 |
| **UNKNOWN** | 0 | 0.00% | 0.00% | ₹0 | ₹0 | — |
| **TOTAL** | **11,875** | **100.00%** | **13.25%** | **₹32,48,430** | **₹4,09,470** | **3.32** |

---

### 5. Tools, Models, Costs & Implementation Details

#### Tools Used
- **Language & Runtime:** Python 3.14
- **Web Application & UI:** Streamlit (Vanilla CSS styling, responsive layout, zero external UI framework dependencies)
- **Data Processing & Analytics:** Pandas, NumPy, PyArrow (Parquet storage engine)
- **Visualization:** Plotly Graph Objects & Express
- **Testing & Verification:** Pytest, Pytest-Cov, PyMuPDF (PDF generation and structural verification)

#### Model & API Used
- **LLM Model:** `openai/gpt-4o-mini` (via OpenRouter API, `https://openrouter.ai/api/v1`)
- **Pipeline Architecture:** Offline pilot extraction (200-ticket pilot sample with deterministic prompt formatting and JSON mode extraction).
- **Runtime Model Dependency:** **Zero**. The interactive Streamlit dashboard runs 100% on deterministically processed Parquet artifacts with zero live LLM inference calls or latency.

#### What It Cost (API & Operational Spend)
- **Pilot Inference Spend:** ~$0.09 total across the 200-ticket extraction pilot and 50-ticket gold validation set (~120,000 prompt tokens + 24,000 completion tokens).
- **Production Dashboard Runtime Cost:** **₹0.00 / ticket**. Complete operational independence from continuous per-ticket API charges, satisfying Finance Controller's constraint.

#### Approaches Attempted & Discarded
1. **Unsupervised Semantic Clustering (Discarded):** Early text embeddings produced overlapping, non-actionable clusters (e.g. "poor sound" vs "audio distortion") that did not map cleanly to Vireo's 6 operational frontline teams. Discarded in favor of an audited 8-category taxonomy aligned to operating policy v3.2.
2. **Real-time Live LLM Dashboard Queries (Discarded):** Calling LLMs on user dashboard filter clicks introduced latency (2–4 seconds) and per-query costs. Discarded in favor of an offline batch intelligence pipeline saving pre-computed Parquet tables.
3. **Composite Agent Performance Scoring (Discarded):** Blending CSAT, volume, and SLA breach rate into a single index unfairly penalized high-volume agents and obscured root causes. Replaced with transparent, unweighted weekly operational metrics sorted primarily by `tickets_closed DESC`.
4. **Ranking Tier-2 Escalations by Volume (Discarded):** Tier-2 hardware warranty cases require multi-day physical bench testing. Ranking them against frontline ticket closures was rejected per Policy §8.

---

### 6. Core Business Goal
- **Numerical Objective:** Reduce the policy-defined repeat-generating-ticket rate from **14.38% to 5.00%** among the **10,463** tickets with a full 30-day observation window.
- **Volume Reduction:** Avoid **982** repeat-generating tickets (reducing repeat generators from 1,505 observed baseline to 523 target).
- **Modeled Financial Planning Opportunity:**
  - **₹2,84,780.00** at the policy's ₹290 blended contact cost standard.
  - **₹2,56,488.58** at the channel-weighted contact cost (₹261.19/ticket).
- **Status:** **SCENARIO ESTIMATE** for operational planning, not claimed realized savings.

---

### 7. Correctness & Evaluation Methodology
- **Human Gold Evaluation Set:** 50 canonical customer tickets manually annotated across all 8 taxonomy categories.
- **Classification Benchmark:**
  - Accuracy: **96.0%** (48/50 correct)
  - Macro F1-Score: **0.9749**
  - Macro Precision: **0.9821** | Macro Recall: **0.9702**
- **Evidence Grounding:** 100% of extracted quotes verified against original raw customer messages; 0 hallucinated quotes.
- **Repeat Claim Audit:** 100% grounded in explicit customer references to prior contacts.
- **Test Suite Verification:** **136 / 136 automated unit and regression tests passed** (`pytest tests/ -q`), covering data ingestion, IST timestamp normalization, canonical deduplication, SLA breaches, repeat detection, weekly aggregation, and weekly Tier-1 leaderboard reconciliation.

---

### 8. Major Technical & Operational Limitations
1. **Right-Censoring:** 803 tickets resolved in June 2026 cannot be evaluated for 30-day repeats until July 31, 2026, and are right-censored per policy.
2. **AI Sampling Scope:** Granular sub-issue qualitative analysis was piloted on a representative sample (50-ticket human gold set; 200-ticket extraction pilot); full-corpus metrics are deterministically mapped.
3. **Non-Causal Observational Data:** Historical ticket correlations show operational friction points but do not constitute controlled clinical proof without prospective A/B intervention testing.

---

### 9. Recording & Deliverable Status
- **Interactive Application:** `app.py` fully operational locally (`http://localhost:8501`).
- **One-Page Executive Memo:** Available at `memo/one_page_memo.md` and compiled 1-page PDF at `memo/one_page_memo.pdf`.
- **System Documentation:** Full architecture (`architecture.md`), design decisions (`decision.md`), and quickstart guide (`README.md`).
- **Walkthrough Video Recording (<= 3 minutes):**
  - Video URL: `https://drive.google.com/file/d/1PC4FCOPeRSY6Fp3ZnoRzOZZxbZgN2ZOG/view?usp=drive_link`
