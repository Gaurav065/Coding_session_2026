"""Shop-Archetype / Demand-Pressure Evaluation Harness - Project Maestro

Evaluates the Production Dispatcher Agent bucketed by town-shop demand archetypes
across the benchmark suite (Official 20 Seeds and 100 Disjoint Seeds).

Archetypes Analyzed:
1. Milk Regimes:
   - Milk-Rich (>= 3 Milk Shops: PIZZA_SHOP, ICE_CREAM_SHOP, SMOOTHIE_SHOP)
   - Milk-Moderate (2 Milk Shops)
   - Milk-Starved (<= 1 Milk Shop)
2. Strawberry Regimes:
   - Strawberry-Rich (>= 4 Strawberry Shops: SMOOTHIE_SHOP, ICE_CREAM_SHOP, FARMERS_MARKET, BRUNCH_SPOT)
   - Strawberry-Moderate (2-3 Strawberry Shops)
   - Strawberry-Starved (<= 1 Strawberry Shop)
3. Wool Regimes:
   - Wool-Active (>= 1 YARN_STORE instance)
   - Wool-Dead (0 YARN_STORE instances, 34.4% of draw space)
4. Aggregate Demand Diversity:
   - High-Diversity (>= 6 distinct shop types)
   - Concentrated-Glut (<= 3 distinct shop types)
5. Demand-Pressure Matrix & Gap Analysis against Top-Tier Meta targets ($88k mean, $127k cluster max).

References:
- kaggriculture.py:103-118 (SHOPS, MAX_SHOP_INSTANCES)
- kaggriculture.py:727 (_town_consume)
- kaggriculture.py:886 (_end_of_day shop unlocks)
"""

import sys
import os
import csv
import numpy as np
from collections import defaultdict
from typing import Dict, List, Tuple, Any

sys.path.insert(0, r"C:\Coding")

from project_maestro.engine.fast_engine import FastGame
from project_maestro.agent.dispatcher_agent import make_spatial_dispatcher_agent

OFFICIAL_20_SEEDS = [10, 20, 30, 42, 55, 77, 99, 100, 123, 200, 250, 300, 333, 404, 500, 600, 700, 777, 888, 999]
DISJOINT_100_SEEDS = list(range(10000, 10100))
ALL_EVAL_SEEDS = OFFICIAL_20_SEEDS + DISJOINT_100_SEEDS

MILK_SHOPS = {"PIZZA_SHOP", "ICE_CREAM_SHOP", "SMOOTHIE_SHOP"}
STRAWBERRY_SHOPS = {"SMOOTHIE_SHOP", "ICE_CREAM_SHOP", "FARMERS_MARKET", "BRUNCH_SPOT"}
WOOL_SHOPS = {"YARN_STORE"}
VEG_SHOPS = {"PET_CAFE", "BAKERY", "FARMERS_MARKET"}


def run_match_and_record(seed: int) -> Dict[str, Any]:
    """Run self-play match of production agent and record rewards and unlocked shops."""
    game = FastGame(seed=seed)
    p0 = make_spatial_dispatcher_agent(seed=seed)
    p1 = make_spatial_dispatcher_agent(seed=seed)

    while not game.done:
        act0 = p0(game.get_observation(0))
        act1 = p1(game.get_observation(1))
        game.step_game(act0, act1)

    r0 = float(game.farms[0].money)
    r1 = float(game.farms[1].money)
    avg_reward = (r0 + r1) / 2.0
    shops = list(game.unlocked_shops)

    milk_count = sum(1 for s in shops if s in MILK_SHOPS)
    straw_count = sum(1 for s in shops if s in STRAWBERRY_SHOPS)
    wool_count = sum(1 for s in shops if s in WOOL_SHOPS)
    distinct_count = len(set(shops))

    return {
        "seed": seed,
        "r0": r0,
        "r1": r1,
        "reward": avg_reward,
        "shops": shops,
        "milk_count": milk_count,
        "straw_count": straw_count,
        "wool_count": wool_count,
        "distinct_count": distinct_count,
    }


def classify_match(rec: Dict[str, Any]) -> List[Tuple[str, str]]:
    """Return list of (category, bucket_label) for a match."""
    tags = []

    # 1. Milk Regime
    m = rec["milk_count"]
    if m >= 3: tags.append(("Milk Regime", "Milk-Rich (>=3 shops)"))
    elif m == 2: tags.append(("Milk Regime", "Milk-Moderate (2 shops)"))
    else: tags.append(("Milk Regime", "Milk-Starved (<=1 shop)"))

    # 2. Strawberry Regime
    s = rec["straw_count"]
    if s >= 4: tags.append(("Strawberry Regime", "Strawberry-Rich (>=4 shops)"))
    elif s in (2, 3): tags.append(("Strawberry Regime", "Strawberry-Moderate (2-3 shops)"))
    else: tags.append(("Strawberry Regime", "Strawberry-Starved (<=1 shop)"))

    # 3. Wool Regime
    w = rec["wool_count"]
    if w >= 1: tags.append(("Wool Regime", "Wool-Active (>=1 Yarn Store)"))
    else: tags.append(("Wool Regime", "Wool-Dead (0 Yarn Store)"))

    # 4. Demand Diversity
    d = rec["distinct_count"]
    if d >= 6: tags.append(("Demand Diversity", "High Diversity (>=6 types)"))
    elif d in (4, 5): tags.append(("Demand Diversity", "Moderate Diversity (4-5 types)"))
    else: tags.append(("Demand Diversity", "Concentrated Glut (<=3 types)"))

    return tags


def summarize_bucket(rewards: List[float]) -> Dict[str, Any]:
    if not rewards:
        return {"n": 0, "mean": 0.0, "std": 0.0, "min": 0.0, "median": 0.0, "max": 0.0, "p25": 0.0, "p75": 0.0}
    arr = np.array(rewards)
    return {
        "n": len(rewards),
        "mean": float(np.mean(arr)),
        "std": float(np.std(arr, ddof=1)) if len(arr) > 1 else 0.0,
        "min": float(np.min(arr)),
        "median": float(np.median(arr)),
        "max": float(np.max(arr)),
        "p25": float(np.percentile(arr, 25)),
        "p75": float(np.percentile(arr, 75)),
    }


def main():
    print("=" * 105, flush=True)
    print("=== SHOP-ARCHETYPE / DEMAND-PRESSURE PERFORMANCE HARNESS ===", flush=True)
    print(f"=== Evaluating {len(ALL_EVAL_SEEDS)} Seeds ({len(OFFICIAL_20_SEEDS)} Official + {len(DISJOINT_100_SEEDS)} Disjoint) ===", flush=True)
    print("=" * 105, flush=True)

    records = []
    for idx, seed in enumerate(ALL_EVAL_SEEDS):
        rec = run_match_and_record(seed)
        records.append(rec)
        if (idx + 1) % 20 == 0:
            print(f"  Processed {idx + 1}/{len(ALL_EVAL_SEEDS)} matches...", flush=True)

    # Bucket rewards by archetype
    buckets = defaultdict(list)
    for rec in records:
        tags = classify_match(rec)
        for cat, bucket_name in tags:
            buckets[(cat, bucket_name)].append(rec["reward"])

    overall_stats = summarize_bucket([r["reward"] for r in records])

    print("\n" + "=" * 105, flush=True)
    print("=== PERFORMANCE BY DEMAND-PRESSURE ARCHETYPE ===", flush=True)
    print("=" * 105, flush=True)
    header = f"{'Category':<22} | {'Demand Archetype':<32} | {'N':<4} | {'Mean':<11} | {'Median':<11} | {'Min':<11} | {'Max':<11} | {'Gap to $88k'}"
    print(header, flush=True)
    print("-" * len(header), flush=True)

    summary_rows = []
    categories = ["Milk Regime", "Strawberry Regime", "Wool Regime", "Demand Diversity"]
    for cat in categories:
        cat_buckets = [(k[1], v) for k, v in buckets.items() if k[0] == cat]
        # Sort by mean descending
        cat_buckets.sort(key=lambda x: np.mean(x[1]) if x[1] else 0, reverse=True)
        for b_name, rew_list in cat_buckets:
            s = summarize_bucket(rew_list)
            gap = s["mean"] - 88109.0 # vs 10C/4S/0G top meta mean
            print(
                f"{cat:<22} | "
                f"{b_name:<32} | "
                f"{s['n']:<4} | "
                f"${s['mean']:>9,.2f} | "
                f"${s['median']:>9,.2f} | "
                f"${s['min']:>9,.2f} | "
                f"${s['max']:>9,.2f} | "
                f"${gap:>+10,.2f}",
                flush=True
            )
            summary_rows.append({
                "category": cat,
                "archetype": b_name,
                "n": s["n"],
                "mean": s["mean"],
                "median": s["median"],
                "min": s["min"],
                "max": s["max"],
                "gap_to_meta_mean": gap,
            })
        print("-" * len(header), flush=True)

    print(
        f"{'OVERALL':<22} | "
        f"{'All Evaluated Seeds':<32} | "
        f"{overall_stats['n']:<4} | "
        f"${overall_stats['mean']:>9,.2f} | "
        f"${overall_stats['median']:>9,.2f} | "
        f"${overall_stats['min']:>9,.2f} | "
        f"${overall_stats['max']:>9,.2f} | "
        f"${overall_stats['mean'] - 88109.0:>+10,.2f}",
        flush=True
    )
    print("=" * 105, flush=True)

    # Save summary CSV
    os.makedirs(r"C:\Coding\project_maestro\results", exist_ok=True)
    out_csv = r"C:\Coding\project_maestro\results\demand_archetype_performance.csv"
    with open(out_csv, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["category", "archetype", "n", "mean", "median", "min", "max", "gap_to_meta_mean"])
        writer.writeheader()
        writer.writerows(summary_rows)
    print(f"\nSaved demand archetype summary table to: {out_csv}", flush=True)


if __name__ == "__main__":
    main()
