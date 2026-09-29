# Phase 3B — Repeat-Contact Audit Report

> **Audit Scope:** All 32 pilot tickets containing explicit customer or agent repeat-contact language (`repeat_claim == True`).
> **Audit Dataset:** `evaluation/repeat_audit.csv`
> **Reference Standard:** Support Policy §6 & Decision D-08 (Same customer + same issue within 30 days of resolution).
> **Date:** 2026-09-29

---

## 1. Executive Summary & Policy Distinction

A foundational principle of the Vireo support intelligence architecture is:
**CODE CALCULATES. AI INTERPRETS. HUMANS DECIDE.**

When a customer writes *"I emailed twice"* or *"calling again, nobody came for pickup"*, the LLM correctly interprets the textual claim (`repeat_claim: true`). However, **customer language does not automatically satisfy the business policy definition of a repeat contact.**

Under Support Policy §6:
> *"A repeat contact is defined as a contact from the same customer regarding the same issue within 30 days of prior resolution."*

Every one of the 32 tickets where repeat language occurred was audited against the customer's full CRM ticket history in `tickets_clean.parquet`.

---

## 2. Manual Audit Breakdown (32 Repeat-Claim Tickets)

| Manual Audit Category | Ticket Count | Share (%) | Business & Operational Reality |
|---|---|---|---|
| **Genuine Policy-Defined Repeat** | **17** | **53.1%** | Customer had a prior resolved ticket for the same product/issue within 30 days. |
| **No Prior Resolved Ticket** | **11** | **34.4%** | First ticket in helpdesk; customer rescheduled with courier partner / self-service portal, or contacted via social media / IVR without a prior CRM resolution. |
| **Outside 30-Day Window** | **4** | **12.5%** | Customer had a prior resolved ticket for the same issue, but elapsed time was >30 days (ranging from 32.2 days to 216.9 days). |
| **Different Issue** | 0 | 0.0% | In cases with prior tickets within 30d, all matched product/issue line. |
| **Ambiguous / Other** | 0 | 0.0% | All 32 cases had clear chronological and categorical history. |
| **Total Audited** | **32** | **100.0%** | Full audit completed in `evaluation/repeat_audit.csv`. |

### Key Insight
Nearly half (46.9%) of all tickets where customers used repeat language were **NOT policy-defined repeats**:
- **34.4% had no prior resolution in CRM:** The customer attempted self-service or called multiple times before their initial ticket was resolved.
- **12.5% exceeded the 30-day window:** While the customer experienced a recurrence of a previous issue, it fell outside the 30-day SLA window.

---

## 3. Deterministic Engine Performance Against Manual Audit

The deterministic repeat detection engine (`src/repeat_detection.py`) was evaluated on these 32 tickets against the manual gold classification.

### Performance on Full CRM History (11,875 tickets)
When the deterministic engine evaluates tickets with access to the customer's historical CRM records:

| Metric | Value | Formula / Count |
|---|---|---|
| **True Positives (TP)** | 15 | Correctly flagged genuine policy repeats |
| **False Positives (FP)** | **0** | Never flagged an invalid or out-of-window repeat |
| **False Negatives (FN)** | 2 | Missed due to legacy category label divergence on prior ticket |
| **True Negatives (TN)** | 15 | Correctly excluded no-prior and out-of-window claims |
| **Repeat Precision** | **100.0%** (1.0000) | $\text{TP} / (\text{TP} + \text{FP}) = 15 / 15$ |
| **Repeat Recall** | **88.24%** (0.8824) | $\text{TP} / (\text{TP} + \text{FN}) = 15 / 17$ |

### Performance on Isolated Pilot Sample (200 tickets)
When evaluated strictly within the boundaries of the isolated 200-ticket pilot:
- **TP:** 1
- **FP:** 0 (Precision: 100.0%)
- **FN:** 16 (Recall: 5.9%)
- **Why this occurs:** A 200-ticket pilot represents only ~1.7% of the total 11,875 tickets. In 16 of the 17 cases, the customer's prior ticket was situated in the remaining 98.3% of the dataset. This proves that **repeat contact detection requires querying the full customer history**, not just an isolated batch sample.

---

## 4. Audit Table of Representative Cases

| Ticket ID | Customer | Channel | Text Claim | Prior Ticket | Days Post-Res | Audit Classification | Engine Result |
|---|---|---|---|---|---|---|---|
| `TK-245395` | C104287 | voice | *"same complaint. order not delivered"* | `TK-244637` | 25.6d | **Genuine Policy Repeat** | Repeat Candidate (Match) |
| `TK-251343` | C102657 | chat | *"supposedly sorted by your team last time"* | `TK-251194` | 4.0d | **Genuine Policy Repeat** | Repeat Candidate (Match) |
| `TK-250134` | C101637 | voice | *"rescheduled pickup twice"* | None | N/A | **No Prior Resolution** | Non-Repeat (Correct) |
| `TK-243363` | C103743 | chat | *"raised this 2 weeks ago and told resolved"* | `TK-242788` | 32.2d | **Outside 30-Day Window** | Non-Repeat (Correct) |
| `TK-241306` | C102874 | chat | *"emailed twice... waiting for refund"* | None | N/A | **No Prior Resolution** | Non-Repeat (Correct) |
| `TK-246465` | C103325 | social | *"fourth time writing about the same thing"* | `TK-244976` | 18.2d | **Genuine Policy Repeat** | Repeat Candidate (Match) |

---

## 5. Audit Conclusion
1. **The LLM cannot and should not calculate repeat metrics directly.** The model's role is strictly interpreting text (`repeat_claim: true`), which has a 53.1% precision relative to policy repeats.
2. **The deterministic repeat engine achieves 100.0% precision.** It never produces a false positive repeat.
3. **Full history is essential:** For Phase 4 full-scale calculation, the repeat engine will evaluate all tickets across the full 11,875 canonical dataset with right-censoring at `2026-05-31`.
