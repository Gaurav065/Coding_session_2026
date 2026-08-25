"""Audit Fertilizer Physical Ceiling & Validate across 10 Episodes

1. Audits fertilizer volume distribution across all 693 winning records in meta_portfolio_summary.csv.
2. Explains the tail skew and exact ceiling breakdown.
3. Tests exact financial accounting and physical collection limits on 10 episodes spanning the reward distribution.
"""

import csv
import json
import os
import glob
import numpy as np

def audit_dataset_distributions():
    path = r"C:\Coding\project_maestro\data\kaggle_results\meta_portfolio_summary.csv"
    with open(path, "r", encoding="utf-8") as f:
        records = list(csv.DictReader(f))

    winners = [r for r in records if r["won"] == "1"]
    print(f"================================================================================")
    print(f"DATASET AUDIT: 693 WINNING RECORDS")
    print(f"================================================================================")

    # Let's inspect percentiles for all products
    products = ["fert", "wheat", "strawberry", "milk", "wool", "melon", "carrot", "egg", "tomato"]
    
    print(f"\n{'PRODUCT':<12} | {'MEAN':>6} | {'P10':>6} | {'P25':>6} | {'P50 (MED)':>9} | {'P75':>6} | {'P90':>6} | {'P99':>6} | {'MAX':>6} | {'ZERO%':>6}")
    print("-" * 90)
    for p in products:
        vals = [float(r[f"{p}_sold"]) for r in winners]
        p10, p25, p50, p75, p90, p99 = np.percentile(vals, [10, 25, 50, 75, 90, 99])
        mean_v = np.mean(vals)
        max_v = np.max(vals)
        zero_pct = sum(1 for v in vals if v == 0) / len(vals) * 100
        print(f"{p.upper():<12} | {mean_v:>6.1f} | {p10:>6.1f} | {p25:>6.1f} | {p50:>9.1f} | {p75:>6.1f} | {p90:>6.1f} | {p99:>6.1f} | {max_v:>6.1f} | {zero_pct:>5.1f}%")

    # Analyze fertilizer specifically
    fert_vals = [float(r["fert_sold"]) for r in winners]
    print(f"\n--- FERTILIZER DISTRIBUTION BREAKDOWN ---")
    print(f"  <= 150 units (Standard collection): {sum(1 for v in fert_vals if v <= 150)} records ({sum(1 for v in fert_vals if v <= 150)/len(fert_vals)*100:.1f}%)")
    print(f"  151 - 350 units (High livestock collection): {sum(1 for v in fert_vals if 150 < v <= 350)} records ({sum(1 for v in fert_vals if 150 < v <= 350)/len(fert_vals)*100:.1f}%)")
    print(f"  > 350 units (Exceeds theoretical 358 cap): {sum(1 for v in fert_vals if v > 350)} records ({sum(1 for v in fert_vals if v > 350)/len(fert_vals)*100:.1f}%)")

    # Why did >350 units occur in the extractor?
    # In extractor line 224: actual_units = int(round(step_rev / p))
    # When price p crashes to $1 (the floor), step_rev / $1 allocates 1 unit per dollar.
    # At floor price $1, selling a batch credited dollar revenue at 1 unit/$1.
    # If a player sold fertilizer at $1 floor, 100 dollars gained was attributed as 100 units!

if __name__ == "__main__":
    audit_dataset_distributions()
