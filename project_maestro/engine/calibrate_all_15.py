"""Calibrate All 15 Clusters Against Real Empirical 10C/4S/0G Reference Baseline - Project Maestro"""

import pandas as pd
import numpy as np
from project_maestro.engine.simulator import CalibratedFarmSimulation

def run_full_calibration():
    meta_path = r"C:\Coding\project_maestro\results\meta_portfolio_summary.csv"
    clusters_path = r"C:\Coding\project_maestro\results\demand_profile_outcomes.csv"
    
    df_meta = pd.read_csv(meta_path)
    df_clusters = pd.read_csv(clusters_path)

    # Filter to real 10C/4S/0G trajectories
    ref_mask = (df_meta["cows"] == 10) & (df_meta["sheep"] == 4) & (df_meta["geese"] == 0)
    df_ref = df_meta[ref_mask]

    ref_stats = df_ref.groupby("cluster_id")["reward"].agg(["count", "mean", "median", "std"]).reset_index()
    ref_dict = {int(row["cluster_id"]): row for _, row in ref_stats.iterrows()}

    print("=== CALIBRATING SIMULATOR ACROSS ALL 15 CLUSTERS AGAINST 527 REAL 10C/4S/0G TRAJECTORIES ===")
    print(f"{'Cluster ID':<12} | {'N':<4} | {'Real Ref Mean':<14} | {'Real Ref Med':<14} | {'Sim Ref Reward':<14} | {'Error %':<10} | {'Status'}")
    print("-" * 90)

    sim_results = []
    abs_errors = []

    for _, row in df_clusters.iterrows():
        cid_str = row["cluster_id"]
        cid_num = int(cid_str.split("_")[1])

        ref_data = ref_dict.get(cid_num)
        if ref_data is None:
            continue

        n_samples = int(ref_data["count"])
        real_mean = float(ref_data["mean"])
        real_median = float(ref_data["median"])

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

        # Reference Build (10C/4S/0G) with standard 4 strawberry plots
        sim = CalibratedFarmSimulation(
            target_cows=10, target_sheep=4, target_geese=0,
            wheat_plots=8, cash_crop_type="STRAWBERRY", cash_crop_plots=4,
            unlock_ne_day=6, unlock_sw_day=10, unlock_se_day=-1,
            day0_crew=5, maint_crew=5, peak_crew=9,
            demand_pressure=pressure,
            opp_cows=10, opp_sheep=4, opp_geese=0
        )
        res = sim.run()
        score = res["final_reward"]

        err_pct = ((score - real_mean) / real_mean) * 100.0
        abs_err = abs(err_pct)
        abs_errors.append(abs_err)

        status = "PASSED (<15%)" if abs_err <= 15.0 else ("ACCEPTABLE (<25%)" if abs_err <= 25.0 else "FAIL")

        print(f"{cid_str:<12} | {n_samples:<4} | ${real_mean:,.1f}     | ${real_median:,.1f}     | ${score:,.1f}     | {err_pct:+6.1f}%    | {status}")
        sim_results.append({
            "cluster_id": cid_str,
            "n": n_samples,
            "real_mean": real_mean,
            "real_median": real_median,
            "sim_score": score,
            "error_pct": err_pct,
        })

    print("-" * 90)
    mean_real_all = np.mean([r["real_mean"] for r in sim_results])
    mean_sim_all = np.mean([r["sim_score"] for r in sim_results])
    overall_err = ((mean_sim_all - mean_real_all) / mean_real_all) * 100.0
    print(f"Overall (N={len(df_ref)})   | ${mean_real_all:,.1f}     | ${np.median([r['real_median'] for r in sim_results]):,.1f}     | ${mean_sim_all:,.1f}     | {overall_err:+6.1f}%    | MAX_ERR = {np.max(abs_errors):.1f}% | MEAN_ABS_ERR = {np.mean(abs_errors):.1f}%")

    return sim_results

if __name__ == "__main__":
    run_full_calibration()
