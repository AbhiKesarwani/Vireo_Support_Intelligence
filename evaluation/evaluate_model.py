import pandas as pd
from typing import Dict, Any, List

gold = pd.read_csv("evaluation/phase3_gold_labels.csv")
ext = pd.read_parquet("data/ai/pilot_extractions.parquet")
merged = gold.merge(ext, on="ticket_id")

total = len(merged)
correct = (merged["gold_issue_code"] == merged["issue_code"]).sum()
accuracy = correct / total

classes = sorted(list(set(merged["gold_issue_code"]).union(set(merged["issue_code"]))))

# Build confusion matrix
cm = pd.DataFrame(0, index=classes, columns=classes)
for _, r in merged.iterrows():
    cm.loc[r["gold_issue_code"], r["issue_code"]] += 1

# Per-class precision, recall, F1
metrics = {}
f1_list = []
for c in classes:
    tp = cm.loc[c, c]
    fp = cm[c].sum() - tp
    fn = cm.loc[c].sum() - tp
    support = cm.loc[c].sum()
    
    prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    rec = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * prec * rec / (prec + rec) if (prec + rec) > 0 else 0.0
    
    metrics[c] = {
        "precision": prec,
        "recall": rec,
        "f1": f1,
        "support": support,
    }
    f1_list.append(f1)

macro_f1 = sum(f1_list) / len(f1_list)

print(f"Accuracy: {accuracy:.4f} ({correct}/{total})")
print(f"Macro-F1: {macro_f1:.4f}")
print("\nConfusion Matrix (Rows: Gold, Cols: Predicted):")
print(cm)

print("\nPer-class Metrics:")
for c in classes:
    m = metrics[c]
    print(f"  {c:12s} Precision: {m['precision']:.4f} | Recall: {m['recall']:.4f} | F1: {m['f1']:.4f} | Support: {m['support']}")

disagreements = merged[merged["gold_issue_code"] != merged["issue_code"]]
print(f"\nDisagreements: {len(disagreements)}")
for _, r in disagreements.iterrows():
    print(f"  [{r['ticket_id']}] Gold: {r['gold_issue_code']} | Pred: {r['issue_code']} | Notes: {r['review_notes']}")
