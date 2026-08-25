"""Check basket revenue reconciliation against $91,603 reward"""

import csv
import numpy as np

def check_reconciliation():
    path = r"C:\Coding\project_maestro\data\kaggle_results\meta_portfolio_summary.csv"
    with open(path, "r", encoding="utf-8") as f:
        reader = list(csv.DictReader(f))
        
    winners = [r for r in reader if r["won"] == "1"]
    
    # Calculate base revenue per player
    base_revs = []
    actual_rewards = []
    
    prices = {
        "wheat": 25, "carrot": 35, "tomato": 60, "strawberry": 120,
        "melon": 250, "egg": 50, "milk": 160, "wool": 200, "fert": 100
    }
    
    for r in winners:
        actual_rewards.append(float(r["reward"]))
        tot_base = 0.0
        for p, pr in prices.items():
            tot_base += float(r[f"{p}_sold"]) * pr
        base_revs.append(tot_base)
        
    print(f"Mean Winner Reward:       ${np.mean(actual_rewards):,.2f}")
    print(f"Mean Winner Base Revenue: ${np.mean(base_revs):,.2f}")
    print(f"Median Winner Reward:     ${np.median(actual_rewards):,.2f}")
    print(f"Median Winner Base Revenue:${np.median(base_revs):,.2f}")

if __name__ == "__main__":
    check_reconciliation()
