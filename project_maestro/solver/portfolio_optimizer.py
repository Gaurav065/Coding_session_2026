"""Calibrated Portfolio Search & Integer Optimizer - Project Maestro (Phase 2)

Solves optimal integer asset allocation (Cows, Sheep, Geese, Cash Crops, Land Unlocks, 
and Dynamic Crew Sizing) for each of the 15 demand pressure clusters using the
fully calibrated simulation engine.

References:
- kaggriculture.py:97 (LAND_PRICES = [1000, 2000, 4000])
- kaggriculture.py:99-101 (Fibonacci hire cost formula)
- kaggriculture.py:126-150 (MARKET_PARAMS, MARKET_I0, PRICE_FLOOR)
- kaggriculture.py:195-207 (_refresh_prices exact price computation)
- kaggriculture.py:505 (FEED)
- kaggriculture.py:518 (CARE pending_care_bonus)
- kaggriculture.py:526 (COLLECT_FERTILIZER)
- kaggriculture.py:596-597 (interleaved per-unit market order execution)
- kaggriculture.py:728-750 (_town_consume)
- kaggriculture.py:804-839 (pending_care_bonus yield multipliers)
- kaggriculture.py:843 (shedCapacity = 100)
"""

import math
from typing import Dict, List, Tuple, Optional, Any
import pandas as pd
import numpy as np

from project_maestro.engine.simulator import CalibratedFarmSimulation, daily_hire_cost
from project_maestro.oracle.price_model import (
    MARKET_I0, PRICE_FLOOR, CROPS, ANIMALS, MARKET_PARAMS, SHOPS_MAP,
    calculate_exact_animal_yield, get_price, calculate_realized_revenue,
    calculate_interleaved_revenue
)


def solve_cluster_portfolio_calibrated(
    cluster_id: str,
    demand_pressure: Dict[str, float],
    opp_cows: int = 10,
    opp_sheep: int = 4,
    opp_geese: int = 0,
) -> Dict[str, Any]:
    """Solve for the optimal portfolio configuration on a specific demand pressure cluster
    using the calibrated simulation engine."""
    
    best_config = None
    best_money = -1e9

    has_yarn = demand_pressure.get("WOOL", 1.0) >= 13.0
    has_pet_cafe = demand_pressure.get("CARROT", 1.0) >= 13.0
    has_bakery = demand_pressure.get("EGG", 1.0) >= 7.0
    has_dairy = demand_pressure.get("MILK", 1.0) >= 13.0

    # Search candidates:
    cow_options = [10, 12, 14, 16] if has_dairy else [8, 10, 12]
    sheep_options = [8, 12, 14] if has_yarn else [2, 4, 6]
    goose_options = [0, 4, 8, 12] # Additive goose search!

    cash_crop_opts = [None]
    if has_pet_cafe:
        cash_crop_opts.append(("CARROT", 4))
    if demand_pressure.get("STRAWBERRY", 1.0) >= 19.0:
        cash_crop_opts.append(("STRAWBERRY", 4))

    for c in cow_options:
        for s in sheep_options:
            for g in goose_options:
                total_anim = c + s + g
                if total_anim > 30: # board density limit
                    continue

                wheat_plots = math.ceil(total_anim / 4.0)

                for crop_info in cash_crop_opts:
                    crop_type, crop_plots = (crop_info if crop_info else (None, 0))
                    total_tiles = total_anim + wheat_plots + crop_plots

                    # Quadrant expansion timing
                    if total_tiles <= 25:
                        unlock_ne, unlock_sw, unlock_se = -1, -1, -1
                    elif total_tiles <= 50:
                        unlock_ne, unlock_sw, unlock_se = 6, -1, -1
                    elif total_tiles <= 75:
                        unlock_ne, unlock_sw, unlock_se = 6, 10, -1
                    else:
                        unlock_ne, unlock_sw, unlock_se = 6, 10, 14

                    day0_c = 5
                    maint_c = max(4, math.ceil(total_tiles / 8.0))
                    peak_c = min(12, maint_c + 4)

                    sim = CalibratedFarmSimulation(
                        target_cows=c,
                        target_sheep=s,
                        target_geese=g,
                        wheat_plots=wheat_plots,
                        cash_crop_type=crop_type,
                        cash_crop_plots=crop_plots,
                        unlock_ne_day=unlock_ne,
                        unlock_sw_day=unlock_sw,
                        unlock_se_day=unlock_se,
                        day0_crew=day0_c,
                        maint_crew=maint_c,
                        peak_crew=peak_c,
                        demand_pressure=demand_pressure,
                        opp_cows=opp_cows,
                        opp_sheep=opp_sheep,
                        opp_geese=opp_geese,
                    )

                    res = sim.run()
                    score = res["final_reward"]

                    if score > best_money:
                        best_money = score
                        # Day build completed (when all animals purchased)
                        cash_hist = res["cash_history"]
                        build_completed_day = 14 if total_tiles > 50 else (10 if total_tiles > 25 else 0)
                        
                        best_config = {
                            "cluster_id": cluster_id,
                            "cows": c,
                            "sheep": s,
                            "geese": g,
                            "wheat_plots": wheat_plots,
                            "cash_crop": crop_type or "None",
                            "cash_crop_plots": crop_plots,
                            "quads_unlocked": res["quads_unlocked"],
                            "day0_crew": day0_c,
                            "maint_crew": maint_c,
                            "peak_crew": peak_c,
                            "labor_cost": res["total_labor_cost"],
                            "capital_cost": (g * 300) + (c * 400) + (s * 500),
                            "build_complete_day": build_completed_day,
                            "solved_reward": score,
                        }

    # Evaluate Reference Baseline (10C / 4S / 0G) on this cluster
    ref_sim = CalibratedFarmSimulation(
        target_cows=10,
        target_sheep=4,
        target_geese=0,
        wheat_plots=4,
        cash_crop_type=None,
        cash_crop_plots=0,
        unlock_ne_day=6,
        unlock_sw_day=10,
        unlock_se_day=-1,
        day0_crew=5,
        maint_crew=5,
        peak_crew=9,
        demand_pressure=demand_pressure,
        opp_cows=opp_cows,
        opp_sheep=opp_sheep,
        opp_geese=opp_geese,
    )
    ref_res = ref_sim.run()
    best_config["reference_reward"] = ref_res["final_reward"]
    best_config["edge_dollars"] = round(best_config["solved_reward"] - ref_res["final_reward"], 1)
    best_config["edge_pct"] = round((best_config["edge_dollars"] / ref_res["final_reward"]) * 100.0, 1)

    return best_config


def run_all_clusters_solver_calibrated(clusters_csv_path: str, output_csv_path: str) -> List[Dict]:
    """Solve and emit the complete calibrated Phase 2 Coverage Table for all 15 clusters."""
    df = pd.read_csv(clusters_csv_path)

    results = []
    print(f"=== Solving Calibrated Optimal Portfolios for all {len(df)} Demand Clusters ===")
    for _, row in df.iterrows():
        cid = row["cluster_id"]
        pressure = {
            "WHEAT": float(row["avg_p_wheat"]),
            "CARROT": float(row["avg_p_carrot"]),
            "TOMATO": float(row["avg_p_tomato"]),
            "STRAWBERRY": float(row["avg_p_strawberry"]),
            "MELON": float(row["avg_p_melon"]),
            "EGG": float(row["avg_p_egg"]),
            "MILK": float(row["avg_p_milk"]),
            "WOOL": float(row["avg_p_wool"]),
            "FERTILIZER": float(row["avg_p_fert"]),
        }
        res = solve_cluster_portfolio_calibrated(cid, pressure)
        results.append(res)
        print(f"[{cid}] Solved: {res['cows']}C/{res['sheep']}S/{res['geese']}G + {res['wheat_plots']}W | Quads: {res['quads_unlocked']} | Reward: ${res['solved_reward']:,.0f} vs Ref ${res['reference_reward']:,.0f} (Edge: +${res['edge_dollars']:,.0f} / +{res['edge_pct']:.1f}%)")

    out_df = pd.DataFrame(results)
    out_df.to_csv(output_csv_path, index=False)
    print(f"\nWrote Calibrated Phase 2 Coverage Table to {output_csv_path}")
    return results


if __name__ == "__main__":
    clusters_path = r"C:\Coding\project_maestro\results\demand_profile_outcomes.csv"
    coverage_path = r"C:\Coding\project_maestro\results\phase2_coverage_table.csv"
    run_all_clusters_solver_calibrated(clusters_path, coverage_path)
