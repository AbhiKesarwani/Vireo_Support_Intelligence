# Phase 3B — Model Classification Accuracy Report

> **Dataset:** 50 stratified pilot tickets from `data/ai/pilot_tickets.parquet`
> **Gold Standard:** Human-curated labels in `evaluation/phase3_gold_labels.csv`
> **Evaluator:** Exact comparison against LLM extractions (`pilot_extractions.parquet`)
> **Model Evaluated:** `openai/gpt-4o-mini` (Prompt `v1.0.0_3c43c3ce`)
> **Date:** 2026-09-29

---

## 1. Overall Performance Summary

The LLM issue classification model was evaluated against 50 independently reviewed and hand-labeled tickets.

| Metric | Measured Value | Standard / Interpretation |
|---|---|---|
| **Sample Size** | 50 tickets | Stratified across categories, channels, repeat claims |
| **Correct Predictions** | 48 / 50 | Exact match with human gold label |
| **Accuracy** | **96.00%** (0.9600) | Exceeds typical operational quality targets (>85%) |
| **Macro-F1 Score** | **97.49%** (0.9749) | Unweighted harmonic mean across all 7 represented classes |
| **Disagreements** | 2 tickets (4.0%) | Borderline boundary cases (documented below) |

---

## 2. Confusion Matrix

Rows represent **Ground Truth (Gold)**; Columns represent **LLM Predictions**.

| Gold \ Predicted | APP | BILLING | DELIVERY | OTHER | PRODUCT | RETURNS | WARRANTY | Total Gold |
|---|---|---|---|---|---|---|---|---|
| **APP** | **3** | 0 | 0 | 0 | 0 | 0 | 0 | 3 |
| **BILLING** | 0 | **9** | 0 | 0 | 0 | 0 | 0 | 9 |
| **DELIVERY** | 0 | 0 | **12** | 0 | 1 | 1 | 0 | 14 |
| **OTHER** | 0 | 0 | 0 | **3** | 0 | 0 | 0 | 3 |
| **PRODUCT** | 0 | 0 | 0 | 0 | **12** | 0 | 0 | 12 |
| **RETURNS** | 0 | 0 | 0 | 0 | 0 | **8** | 0 | 8 |
| **WARRANTY** | 0 | 0 | 0 | 0 | 0 | 0 | **1** | 1 |
| **Total Predicted** | 3 | 9 | 12 | 3 | 13 | 9 | 1 | **50** |

*Note: `UNKNOWN` was not predicted or labeled for any ticket in this 50-ticket gold set as all tickets had clear context.*

---

## 3. Per-Class Precision, Recall, and F1-Scores

| Issue Category | Gold Support | Predicted Count | Precision | Recall | F1-Score |
|---|---|---|---|---|---|
| **APP** | 3 | 3 | 1.0000 | 1.0000 | **1.0000** |
| **BILLING** | 9 | 9 | 1.0000 | 1.0000 | **1.0000** |
| **DELIVERY** | 14 | 12 | 1.0000 | 0.8571 | **0.9231** |
| **OTHER** | 3 | 3 | 1.0000 | 1.0000 | **1.0000** |
| **PRODUCT** | 12 | 13 | 0.9231 | 1.0000 | **0.9600** |
| **RETURNS** | 8 | 9 | 0.8889 | 1.0000 | **0.9412** |
| **WARRANTY** | 1 | 1 | 1.0000 | 1.0000 | **1.0000** |
| **Macro Average** | **50** | **50** | **0.9731** | **0.9796** | **0.9749** |

---

## 4. Analysis of Disagreements (Failure Modes)

Only 2 out of 50 tickets resulted in a disagreement between the human gold label and the LLM prediction. Both occur at legitimate operational boundaries:

### Disagreement 1: Ticket `TK-252194`
- **Customer Message:** `"box was crushed and the my nexa 2 watch is cracked"`
- **Agent Notes:** `"rplc raised, RMA shared w/ cx. Issue: unit rceeived damaged. Photos received, dammage confirmed."`
- **Gold Label:** `DELIVERY` (Sub: `damaged_in_transit`) — Courier mishandling damaged the parcel.
- **LLM Prediction:** `PRODUCT` (Sub: `hardware_defect` / physical damage) — Physical cracked watch screen.
- **Root Cause & Impact:** Boundary ambiguity between transit damage (`DELIVERY`) and physical device damage (`PRODUCT`). Both interpretations are justifiable from text.

### Disagreement 2: Ticket `TK-254841`
- **Customer Message:** `"Product: pulse 2 buds Order: VR908849 Purchased: 20 Jun Issue: my son ordered this without asking, please reverse Tried: tried cancel button, gryeed out Expected: resolution"`
- **Agent Notes:** `"Refunded Rs 3499. Issue: cancellation request. Checked shipent status. -TS"`
- **Gold Label:** `DELIVERY` (Sub: `order_cancellation`) — Order cancellation requested before dispatch.
- **LLM Prediction:** `RETURNS` (Sub: `refund_status` / reversal) — Customer explicitly asked to "reverse" and agent issued a refund.
- **Root Cause & Impact:** Boundary between pre-dispatch cancellation and post-order reversal. In business workflows, both route to fulfillment / billing.

---

## 5. Conclusion
With **96.0% accuracy** and a **Macro-F1 of 0.9749**, the LLM issue classification model demonstrates strong reliability. Zero false classifications occurred across `BILLING`, `APP`, `OTHER`, and `WARRANTY`. The only 2 disagreements represent nuanced edge cases between transit and hardware damage, and pre-dispatch cancellation vs return reversal.
