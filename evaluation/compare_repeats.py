import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
from src.repeat_detection import detect_repeat_contacts


clean = pd.read_parquet("data/processed/tickets_clean.parquet")
pilot = pd.read_parquet("data/ai/pilot_tickets.parquet")
ext = pd.read_parquet("data/ai/pilot_extractions.parquet")
audit_df = pd.read_csv("evaluation/repeat_audit.csv")

# 1. Pilot-only repeat detection (when engine is run only on the 200 pilot tickets)
res_pilot_only = detect_repeat_contacts(pilot, ext)
pilot_only_dict = dict(zip(res_pilot_only["ticket_id"], res_pilot_only["repeat_candidate"]))

# 2. Full-history repeat detection (when engine has access to full CRM customer history)
raw_to_issue = {
    "Delivery & Shipping": "DELIVERY",
    "Billing & Payments": "BILLING",
    "Returns & Refunds": "RETURNS",
    "Connectivity": "PRODUCT",
    "Charging & Battery": "PRODUCT",
    "Audio Quality": "PRODUCT",
    "Warranty & Repair": "WARRANTY",
    "App & Firmware": "APP",
    "Product Enquiry": "OTHER",
    "Account & Login": "OTHER",
    "Other": "OTHER",
}
clean_with_issues = clean.copy()
clean_with_issues["issue_code"] = clean_with_issues["category"].map(raw_to_issue).fillna("UNKNOWN")
pilot_ext_map = dict(zip(ext["ticket_id"], ext["issue_code"]))
clean_with_issues["issue_code"] = clean_with_issues["ticket_id"].map(pilot_ext_map).fillna(clean_with_issues["issue_code"])

res_full = detect_repeat_contacts(clean_with_issues)
full_dict = dict(zip(res_full["ticket_id"], res_full["repeat_candidate"]))

# Merge with audit_df
audit_df["pred_pilot_only"] = audit_df["ticket_id"].map(pilot_only_dict)
audit_df["pred_full_history"] = audit_df["ticket_id"].map(full_dict)
audit_df["gold_is_repeat"] = audit_df["manual_repeat_classification"] == "genuine_policy_repeat"

# Compute metrics for full history
tp = ((audit_df["pred_full_history"] == True) & (audit_df["gold_is_repeat"] == True)).sum()
fp = ((audit_df["pred_full_history"] == True) & (audit_df["gold_is_repeat"] == False)).sum()
fn = ((audit_df["pred_full_history"] == False) & (audit_df["gold_is_repeat"] == True)).sum()
tn = ((audit_df["pred_full_history"] == False) & (audit_df["gold_is_repeat"] == False)).sum()

prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
rec = tp / (tp + fn) if (tp + fn) > 0 else 0.0

print(f"Repeat Audit Results on 32 Repeat-Claim Tickets (Full CRM History):")
print(f"  TP: {tp} | FP: {fp} | FN: {fn} | TN: {tn}")
print(f"  Precision: {prec:.4f} ({tp}/{tp+fp})")
print(f"  Recall:    {rec:.4f} ({tp}/{tp+fn})")

# Also show pilot-only comparison
tp_po = ((audit_df["pred_pilot_only"] == True) & (audit_df["gold_is_repeat"] == True)).sum()
fp_po = ((audit_df["pred_pilot_only"] == True) & (audit_df["gold_is_repeat"] == False)).sum()
fn_po = ((audit_df["pred_pilot_only"] == False) & (audit_df["gold_is_repeat"] == True)).sum()
tn_po = ((audit_df["pred_pilot_only"] == False) & (audit_df["gold_is_repeat"] == False)).sum()
print(f"\nPilot-Only Comparison (Isolated 200 tickets):")
print(f"  TP: {tp_po} | FP: {fp_po} | FN: {fn_po} | TN: {tn_po}")
print(f"  Note: In pilot-only, 16 genuine repeats missed because prior ticket was outside the 200-ticket sample.")
