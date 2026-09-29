# DECISIONS.md — Vireo Support Intelligence

> Every non-obvious design decision is documented here.
> Format: Question → Decision → Evidence → Risk if wrong.

---

## D-01 — Duplicate ticket handling

| Field | Value |
|---|---|
| **Question** | 12,528 raw rows but ~11,875 unique ticket IDs. How to handle duplicates? |
| **Decision** | For each duplicate pair, keep the `helpdesk` row; discard the `legacy_fd` row. |
| **Evidence** | Email thread (Sameer, 7 Sep): "the new helpdesk re-imported a chunk of it." Policy §9: migrated tickets may appear in both systems. Every pair = helpdesk + legacy_fd. |
| **Result** | 653 pairs reconciled → 11,875 canonical tickets. |

---

## D-02 — Legacy timestamp normalization

| Field | Value |
|---|---|
| **Question** | Legacy `resolved_at` comes from UTC event log. Helpdesk shows IST. Apply +5:30? |
| **Decision** | Yes. Apply IST_OFFSET (+5h30m) to `resolved_at` for all `source_system == legacy_fd` rows only. `created_at` and `first_response_at` are NOT adjusted. |
| **Evidence** | README.txt: "resolved_at reconstructed from the event log." Policy §9: "event log stores UTC." 618 pairs showed exactly -5:30 delta; zero negative durations after correction. |

---

## D-03 — CSAT missing value encoding

| Field | Value |
|---|---|
| **Question** | Legacy rows use 0 for no CSAT response. Helpdesk uses blank. How to unify? |
| **Decision** | Set `csat_score = NaN` where raw value is 0 or blank. Only 1–5 are valid responses. |
| **Evidence** | README.txt: "Legacy rows use 0 for no response." Policy §6: "blank score must be excluded from averages, not treated as zero." |

---

## D-04 — Cost per contact

| Field | Value |
|---|---|
| **Question** | Finance says ₹180; Priya's policy doc says ₹290 blended. Which to use? |
| **Decision** | Use channel-specific costs for all calculations (chat ₹210, email ₹260, voice ₹520, social ₹240 per Policy §7). Reference ₹290 only as the blended planning standard for scenario savings. The ₹180 discrepancy is documented in the memo. |
| **Evidence** | Policy §7 specifies channel costs. Email (Priya, 9 Sep): "₹290 blended per the policy doc." |

---

## D-05 — Agent leaderboard scope

| Field | Value |
|---|---|
| **Question** | Should all 44 agents be ranked together? |
| **Decision** | No. Tier-1 frontline agents (38) get a **weekly volume leaderboard** segmented by team (Priya's request: "leaderboard of agents by tickets closed per week"). Tier-2 specialists (6) get a separate operations section (case depth, median resolution days, CSAT). **No cross-tier ranking. No composite score.** |
| **Evidence** | Policy §8: "Tier 2 agents must not be compared with Tier 1 on volume metrics." Email (Neha Kulkarni): "please don't rank my warranty team on ticket counts." |
| **Why no composite score** | A composite score (e.g. volume + CSAT + SLA as weighted sum) introduces arbitrary weights that are not policy-backed. Transparent individual metrics allow managers to make contextual judgments. |

---

## D-06 — Auto-closed tickets in leaderboard

| Field | Value |
|---|---|
| **Question** | Auto-closed tickets count as closed — include in leaderboard? |
| **Decision** | Yes, show total closures. Always show `agent_resolved` and `auto_closed` as separate columns so managers can distinguish human resolution from system closure. |
| **Evidence** | Policy §8: "auto-closed tickets count as completed attendance." |

---

## D-07 — Order join strategy

| Field | Value |
|---|---|
| **Question** | Many tickets lack `order_id`. How to join orders? |
| **Decision** | Three-tier: (1) direct `order_id` match; (2) date-bounded unique fallback = `customer_id + product_sku` WHERE `order_date <= ticket_created_at` AND exactly one result; (3) ambiguous = multiple orders match — record as `join_confidence=ambiguous`, do not force. |
| **Evidence** | README.txt: "customer_id + product_sku is the fallback join." Date-bounding prevents future-order contamination. Unbounded join produces 751 ambiguous; date-bounded reduces to ~462. |

---

## D-08 — Repeat-contact definition

| Field | Value |
|---|---|
| **Question** | What counts as a repeat contact? |
| **Decision** | Policy §6: same `customer_id` + same `issue_code` (from AI classifier) + within 30 days of prior `resolved_at`. The raw `category` field is not used (too coarse; re-tagged by agents inconsistently). |
| **Evidence** | Policy §6: "A customer contacting again about the same issue within 30 days of resolution is a repeat contact." |

---

## D-09 — Right-censoring for repeat analysis

| Field | Value |
|---|---|
| **Question** | Tickets resolved in final 30 days cannot yet generate repeats. Include in denominator? |
| **Decision** | Exclude tickets resolved after May 31, 2026 from the repeat rate denominator. These 803 tickets are included in all volume, cost, and leaderboard metrics. |
| **Evidence** | Dataset ends June 30, 2026. A ticket resolved June 15 cannot have a 30-day repeat window within the dataset. |

---

## D-10 — Technology stack

| Field | Value |
|---|---|
| **Decision** | Python + Pandas + Streamlit + Plotly + OpenAI API via OpenRouter. No database. No LangChain. No FAISS. No fine-tuning. No RAG. |
| **Rationale** | Assignment specifies a 5-hour scope. These additions add complexity without proportional analytical value for this dataset size. |

---

## D-11 — AI output caching

| Field | Value |
|---|---|
| **Decision** | Cache all LLM extractions to `data/ai/extraction_cache.parquet` after first run. Re-use on subsequent runs. Cache key: `ticket_id + prompt_hash`. |
| **Evidence** | Finance email: "I do not want a per-ticket model bill that shows up as a surprise." This eliminates all repeat API costs after first pipeline run. |

---

## D-12 — Policy exception language

| Field | Value |
|---|---|
| **Decision** | Label anomalies (refund + replacement on same ticket, refund > order value, goodwill > ₹500) as "potential policy exception — requires review." The AI never labels anything as fraud — that requires human verification. |

---

## D-13 — Historical roster limitation

| Field | Value |
|---|---|
| **Finding** | `agents.csv` has 44 rows (44 unique agent IDs), `to_date` is 100% null. Current-state only; no historical assignment history. |
| **Consequence** | All tickets attributed to agents' current team assignment. Historical team attribution is unavailable. This limitation is noted in the memo and README. |

---

## D-14 — Known source contradictions (documented, not silently resolved)

| Item | Contradiction | Handling |
|---|---|---|
| Contact cost | Finance says ₹180; Policy says ₹290 blended | Use Policy §7 channel rates; note both in memo |
| Transfer field | Policy says transfers only in current helpdesk; 268 legacy rows have values | Flag as legacy anomaly; do not adjust |
| Leaderboard scope | Priya wants leaderboard; Neha says exclude warranty team | Implement Policy §8 separation; explain in memo and UI |

---

*Last updated: Phase 6B finalization — 2026-09-29*
