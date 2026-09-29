import re
import difflib
import pandas as pd

gold = pd.read_csv("evaluation/phase3_gold_labels.csv")
ext = pd.read_parquet("data/ai/pilot_extractions.parquet")
pilot = pd.read_parquet("data/ai/pilot_tickets.parquet")

merged = gold.merge(ext, on="ticket_id").merge(pilot[["ticket_id", "customer_message", "agent_notes"]], on="ticket_id")

results = []

for idx, r in merged.iterrows():
    span = str(r["evidence_span"] or "").strip()
    c_msg = str(r["customer_message"] or "")
    a_notes = str(r["agent_notes"] or "")
    combined = f"{c_msg} {a_notes}"
    
    clean_span = span.strip("\"'")
    
    # 1. Exact substring
    is_exact = clean_span in combined or clean_span.lower() in combined.lower()
    
    # 2. Normalized whitespace
    span_norm = re.sub(r"\s+", " ", clean_span).lower()
    comb_norm = re.sub(r"\s+", " ", combined).lower()
    is_norm = (span_norm in comb_norm) and not is_exact
    
    # 3. Typo-tolerant / fuzzy
    is_fuzzy = False
    fuzzy_ratio = 0.0
    matched_window = ""
    if not is_exact and not is_norm and span_norm:
        w_span = span_norm.split()
        w_comb = comb_norm.split()
        w_len = len(w_span)
        best_ratio = 0.0
        best_window = ""
        for i in range(max(1, len(w_comb) - w_len + 1)):
            window = " ".join(w_comb[i : i + w_len])
            ratio = difflib.SequenceMatcher(None, span_norm, window).ratio()
            if ratio > best_ratio:
                best_ratio = ratio
                best_window = window
        fuzzy_ratio = best_ratio
        matched_window = best_window
        if best_ratio >= 0.85:
            is_fuzzy = True
            
    # Category assignment
    if is_exact:
        cat = "exact_substring"
    elif is_norm:
        cat = "normalized_whitespace"
    elif is_fuzzy:
        cat = "typo_tolerant_fuzzy"
    else:
        cat = "unsupported_hallucinated"
        
    results.append({
        "ticket_id": r["ticket_id"],
        "evidence_span": span,
        "category": cat,
        "fuzzy_ratio": round(fuzzy_ratio, 3) if fuzzy_ratio > 0 else None,
        "matched_window": matched_window if is_fuzzy or cat == "unsupported_hallucinated" else "",
    })

res_df = pd.DataFrame(results)
print("Evidence Grounding Breakdown on 50 Gold Tickets:")
print(res_df["category"].value_counts())
print("\nDetails on non-exact:")
print(res_df[res_df["category"] != "exact_substring"])
