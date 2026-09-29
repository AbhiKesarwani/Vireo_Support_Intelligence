# Phase 4 — Business Intelligence & Support Demand Economics

> **Document Type:** Operational Business Intelligence & Demand Economics Report
> **Data Scope:** 11,875 Canonical Tickets (January 2025 – June 2026)
> **Principle:** CODE CALCULATES. AI INTERPRETS. HUMANS DECIDE.
> **Date:** 2026-09-29

---

## 1. Executive Business Scorecard

| Business Dimension | Measured Actual | Benchmark / Target | Variance / Interpretation |
|---|---|---|---|
| **Total Ticket Volume** | **11,875** | Canonical population | Reconciled 100% |
| **Total Contact Cost** | **₹32,48,430** | Planning budget | Channel-weighted (Avg ₹273.55) |
| **SLA Breach Rate** | **8.85%** (1,051) | Policy target <10% | Compliant overall; email highest (11.6%) |
| **SLA Credit Exposure** | **₹3,67,850** | ₹350 per breach | Contractual risk |
| **Helpdesk Transfer Cost** | **₹2,64,740** | 1,040 transfers | ₹305 per transfer |
| **Team Mismatches** | **12.19%** (1,448) | Transfer indicator | Initial assignment divergence |
| **Customer Satisfaction (CSAT)** | **3.3152** | Scale 1.0 – 5.0 | 44.37% response rate (5,269 valid) |
| **Auto-Closed Tickets** | **9.32%** (1,107) | Policy attendance | Separated from agent resolutions |
| **Policy Repeat Contact Rate** | **14.38%** (1,505 / 10,463) | Working Target: 5.0% | Right-censored at 2026-05-31 |
| **Total Repeat Contact Cost** | **₹4,09,470** | 1,573 incoming repeats | ₹260.31 average cost per repeat |
| **Estimated Savings Opportunity** | **₹2,56,488 – ₹2,84,780** | Reduce repeats to 5.0% | 982 avoidable repeat-generating tickets |

---

## 2. Avoidable Support Demand & Repeat-Contact Economics

Under Support Policy §6, a repeat contact occurs when a customer reaches out regarding the same issue within 30 days of prior resolution.

### A. Population & Right-Censoring Breakdown
- **Canonical Population:** 11,875 tickets
- **Repeat-Eligible Denominator:** **10,463 tickets** (resolved on or before `2026-05-31`, allowing a complete 30-day observation window).
- **Right-Censored Exclusions:** **803 tickets** resolved after May 31, 2026 (cannot yet be evaluated for 30-day repeats).
- **Unresolved Exclusions:** **609 tickets** (open/pending or missing resolution timestamp).
- **Tickets Generating Repeats:** **1,505 tickets** (14.38% repeat rate; First Contact Resolution = 85.62%).
- **Incoming Repeat Contacts:** **1,573 tickets** (13.25% of total volume; ₹4,09,470 total channel cost).

### B. Scenario Savings Modeling (Target = 5.0%)
*Note: This is an estimated savings opportunity for planning, NOT achieved savings.*

| Scenario Parameter | Value | Calculation Logic |
|---|---|---|
| **Current Repeat-Generating Tickets** | 1,505 | Observed actuals |
| **Current Repeat Rate** | 14.38% | 1,505 / 10,463 |
| **Working Planning Target** | **5.00%** | Planning hypothesis |
| **Target Repeat Tickets Allowed** | 523 | 5.0% × 10,463 eligible tickets |
| **Avoidable Repeat Tickets Reduced** | **982** | 1,505 current − 523 target |
| **Estimated Savings (Channel Mix)** | **₹2,56,488** | 982 tickets × ₹261.19 (cohort repeat ticket cost) |
| **Estimated Savings (Blended Rs 290)** | **₹2,84,780** | 982 tickets × ₹290 (official policy standard) |

---

## 3. Operational Issue Distribution & Drivers

| Operational Issue | Ticket Count | Share (%) | Repeats | Repeat Rate | Repeat Cost | Mean CSAT | SLA Breach Rate |
|---|---|---|---|---|---|---|---|
| `PRODUCT` | 2,893 | 24.36% | 490 | 16.94% | ₹128,540 | 3.24 | 9.09% |
| `OTHER` | 2,572 | 21.66% | 224 | 8.71% | ₹58,850 | 3.68 | 7.43% |
| `DELIVERY` | 2,138 | 18.00% | 327 | 15.29% | ₹84,440 | 3.03 | 8.56% |
| `BILLING` | 1,627 | 13.70% | 200 | 12.29% | ₹52,880 | 3.46 | 9.53% |
| `RETURNS` | 1,204 | 10.14% | 162 | 13.46% | ₹42,130 | 3.05 | 9.97% |
| `APP` | 824 | 6.94% | 99 | 12.01% | ₹24,260 | 3.46 | 9.59% |
| `WARRANTY` | 617 | 5.20% | 71 | 11.51% | ₹18,370 | 3.09 | 9.72% |
| `UNKNOWN` | 0 | 0.00% | 0 | 0.00% | ₹0 | N/A | 0.00% |

### Key Drivers:
1. **PRODUCT (Hardware, Audio, Connectivity):** Largest volume (2,893 tickets, 24.36%) and highest repeat rate (16.94%). Generates **₹1,28,540 in repeat costs** (31.39% of all repeat spend).
2. **OTHER (Account, Login, General Inquiries):** Second largest volume (2,572 tickets, 21.66%), driving **₹58,850 in repeat costs** (8.71% repeat rate).
3. **DELIVERY (Fulfillment, Transit Damage, Tracking):** Third largest volume (2,138 tickets, 18.00%), driving **₹84,440 in repeat costs** (15.29% repeat rate).
4. **BILLING (Payment Failures, GST Invoices):** 1,627 tickets (13.70%), driving **₹52,880 in repeat costs** (12.29% repeat rate).
5. **RETURNS (Return Desk, Exchanges):** 1,204 tickets (10.14%), driving **₹42,130 in repeat costs** (13.46% repeat rate).
6. **APP (Firmware, App Connectivity):** 824 tickets (6.94%), driving **₹24,260 in repeat costs** (12.01% repeat rate).
7. **WARRANTY (Warranty Claims, Repairs):** 617 tickets (5.20%), driving **₹18,370 in repeat costs** (11.51% repeat rate).
8. **UNKNOWN (Missing / Unclassified):** 0 tickets (0.00%) — zero unclassified tickets across the canonical population.

---

## 4. Policy-Compliant Tier 1 Volume Leaderboard (Top 10)

*Policy Constraint (§8): Tier 2 agents must NOT be ranked on volume. Sorted by `tickets_closed` DESC, then CSAT, SLA breach rate, and agent ID.*

| Rank | Agent ID | Agent Name | Team | Total Closed | Agent Resolved | Auto Closed | SLA Breach | Mean CSAT | Repeat Rate |
|---|---|---|---|---|---|---|---|---|---|
| 1 | `A3033` | Diya Singh | Billing | 704 | 633 | 71 | 7.0% | 3.45 | 11.7% |
| 2 | `A3037` | Vivaan Sethi | Returns Desk | 502 | 461 | 41 | 5.9% | 3.19 | 9.5% |
| 3 | `A3029` | Geeta Rathore | Logistics | 472 | 421 | 51 | 7.3% | 3.11 | 13.0% |
| 4 | `A3031` | Aishwarya Agarwal | Logistics | 451 | 409 | 42 | 6.6% | 3.19 | 12.7% |
| 5 | `A3028` | Tarun Pereira | Logistics | 393 | 354 | 39 | 8.3% | 2.93 | 17.3% |
| 6 | `A3019` | Kavya D'Souza | Email Frontline | 385 | 343 | 42 | 6.4% | 3.61 | 9.8% |
| 7 | `A3027` | Rajat Saxena | Logistics | 383 | 340 | 43 | 10.0% | 2.97 | 18.2% |
| 8 | `A3038` | Pooja Patil | Returns Desk | 374 | 349 | 25 | 12.3% | 3.02 | 14.8% |
| 9 | `A3021` | Pooja Dhillon | Email Frontline | 355 | 318 | 37 | 6.1% | 3.50 | 10.6% |
| 10 | `A3030` | Gurpreet Kulkarni | Logistics | 350 | 317 | 33 | 11.1% | 2.96 | 16.4% |

---

## 5. Tier 2 Operational Visibility (Escalations & Warranty)

*Operational visibility table for complex escalations. Not a volume competition.*

| Agent ID | Agent Name | Team | Cases Resolved | Median Res Days | Mean Res Days | SLA Breach Rate | Mean CSAT |
|---|---|---|---|---|---|---|---|
| `A3044` | Meera Joshi | Escalations & Warranty | 175 | 5.08d | 5.82d | 8.5% | 3.10 |
| `A3040` | Sai Sharma | Escalations & Warranty | 158 | 4.1d | 5.42d | 10.1% | 3.01 |
| `A3042` | Aishwarya Kaur | Escalations & Warranty | 112 | 3.37d | 5.34d | 10.3% | 3.13 |
| `A3041` | Deepak Mathew | Escalations & Warranty | 92 | 4.04d | 5.66d | 12.4% | 3.16 |
| `A3039` | Vivaan Kulkarni | Escalations & Warranty | 91 | 5.21d | 6.11d | 9.4% | 3.03 |
| `A3043` | Rahul Gupta | Escalations & Warranty | 91 | 5.1d | 5.75d | 12.2% | 3.04 |

---

## 6. Weekly Volume & Trend Summary
- **Total Calendar Weeks:** 79 weeks (2025-W01 to 2026-W27).
- **Peak Ticket Volume Week:** `2025-11-17/2025-11-23` (240 tickets).
- **Weekly Canonical Reconciliation:** Sum of weekly tickets created = **11,875** (Matches canonical 11,875 exactly).
