"""Test and Calibrate Simulation Against Real Kaggle Outcomes - Project Maestro"""

import pandas as pd
from project_maestro.engine.simulator import CalibratedFarmSimulation

def run_calibration_test():
    clusters_path = r"C:\Coding\project_maestro\results\demand_profile_outcomes.csv"
    df = pd.read_csv(clusters_path)

    print("=== CALIBRATING SIMULATOR ACROSS ALL 15 CLUSTERS ===")
    print(f"{'Cluster':<12} | {'Real Meta Avg':<14} | {'Ref Sim Score':<14} | {'Error %':<10} | {'Status'}")
    print("-" * 65)

    sim_scores = []
    real_scores = []

    for _, row in df.iterrows():
        cid = row["cluster_id"]
        real_avg = float(row["avg_player_reward"])
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

        # Reference Build (10 Cows / 4 Sheep / 0 Goose)
        sim = CalibratedFarmSimulation(
            target_cows=10, target_sheep=4, target_geese=0,
            wheat_plots=4, unlock_ne_day=6, unlock_sw_day=10, unlock_se_day=-1,
            day0_crew=5, maint_crew=5, peak_crew=9,
            demand_pressure=pressure,
            opp_cows=10, opp_sheep=4, opp_geese=0
        )
        res = sim.run()
        score = res["final_reward"]
        err_pct = ((score - real_avg) / real_avg) * 100.0
        status = "CALIBRATED" if abs(err_pct) <= 20.0 else "OUTLIER"

        sim_scores.append(score)
        real_scores.append(real_avg)

        print(f"{cid:<12} | ${real_avg:,.1f}     | ${score:,.1f}     | {err_pct:+6.1f}%    | {status}")

    mean_sim = sum(sim_scores) / len(sim_scores)
    mean_real = sum(real_scores) / len(real_scores)
    overall_err = ((mean_sim - mean_real) / mean_real) * 100.0

    print("-" * 65)
    print(f"Overall Mean : ${mean_real:,.1f}     | ${mean_sim:,.1f}     | {overall_err:+6.1f}%    | OVERALL")

if __name__ == "__main__":
    run_calibration_test()
