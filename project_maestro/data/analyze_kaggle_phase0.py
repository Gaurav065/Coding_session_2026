"""Analyze Kaggle Phase 0 Results CSVs cleanly and report ground-truth targets."""

import csv
from collections import defaultdict
import numpy as np

def analyze_portfolio():
    path = r"C:\Coding\project_maestro\data\kaggle_results\meta_portfolio_summary.csv"
    with open(path, "r", encoding="utf-8") as f:
        reader = list(csv.DictReader(f))

    print(f"Total Player Entries: {len(reader)} across {len(set(r['episode_id'] for r in reader))} episodes")
    
    winners = [r for r in reader if r["won"] == "1"]
    print(f"Winning Player Records: {len(winners)}")
    
    rewards = [float(r["reward"]) for r in winners]
    print(f"Winner Reward: Mean = ${np.mean(rewards):,.2f} | Median = ${np.median(rewards):,.2f} | Min = ${np.min(rewards):,.2f} | Max = ${np.max(rewards):,.2f}")

    products = ["wheat", "carrot", "tomato", "strawberry", "melon", "milk", "wool", "egg", "fert"]
    print("\n--- GROUND-TRUTH WINNER VOLUMES SOLD (UNITS) ---")
    for p in products:
        col = f"{p}_sold"
        vals = [float(r[col]) for r in winners]
        print(f"  {p.upper():<12}: Mean = {np.mean(vals):>6.1f} | Median = {np.median(vals):>6.1f} | Min = {np.min(vals):>5.1f} | Max = {np.max(vals):>6.1f} | Zero % = {sum(1 for v in vals if v==0)/len(vals)*100:.1f}%")

    animals = ["cows", "sheep", "geese"]
    print("\n--- GROUND-TRUTH WINNER ANIMAL HOLDINGS ---")
    for a in animals:
        vals = [float(r[a]) for r in winners]
        print(f"  {a.upper():<12}: Mean = {np.mean(vals):>5.1f} | Median = {np.median(vals):>5.1f} | Min = {np.min(vals):>4.1f} | Max = {np.max(vals):>5.1f} | Zero % = {sum(1 for v in vals if v==0)/len(vals)*100:.1f}%")

    crops = ["wheat_seeds", "carrot_seeds", "tomato_seeds", "strawberry_seeds", "melon_seeds"]
    print("\n--- GROUND-TRUTH WINNER SEEDS PURCHASED ---")
    for c in crops:
        vals = [float(r[c]) for r in winners]
        print(f"  {c:<18}: Mean = {np.mean(vals):>6.1f} | Median = {np.median(vals):>6.1f} | Min = {np.min(vals):>5.1f} | Max = {np.max(vals):>6.1f} | Zero % = {sum(1 for v in vals if v==0)/len(vals)*100:.1f}%")

    hires = ["day0_hires", "total_hires"]
    print("\n--- GROUND-TRUTH WINNER LABOR HIRES ---")
    for h in hires:
        vals = [float(r[h]) for r in winners]
        print(f"  {h:<18}: Mean = {np.mean(vals):>6.1f} | Median = {np.median(vals):>6.1f} | Min = {np.min(vals):>5.1f} | Max = {np.max(vals):>6.1f}")

    quads = ["ne_unlock_day", "sw_unlock_day", "se_unlock_day"]
    print("\n--- GROUND-TRUTH WINNER QUADRANT UNLOCK DAYS ---")
    for q in quads:
        vals = [float(r[q]) for r in winners if float(r[q]) >= 0]
        unlocked_pct = len(vals) / len(winners) * 100
        print(f"  {q:<18}: Unlocked Pct = {unlocked_pct:>5.1f}% | Mean Day = {np.mean(vals):>5.1f} | Median Day = {np.median(vals):>5.1f}")

if __name__ == "__main__":
    analyze_portfolio()
