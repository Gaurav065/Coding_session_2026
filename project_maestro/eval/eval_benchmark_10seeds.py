"""Empirical Evaluation of Spatial Dispatcher Agent Across 10 Match Seeds - Project Maestro"""

import numpy as np
import pandas as pd
from kaggle_environments import make
from project_maestro.agent.dispatcher_agent import make_spatial_dispatcher_agent

def evaluate_seeds():
    seeds = [10, 42, 100, 2024, 777, 999, 1234, 5555, 8888, 9999]
    agent = make_spatial_dispatcher_agent()
    
    results = []
    print("=== EMPIRICAL 10-SEED EVALUATION OF SPATIAL DISPATCHER (10C/4S/0G) IN REAL ENGINE ===")
    print(f"{'Seed':<8} | {'Reward':<14} | {'Active Shops':<45}")
    print("-" * 75)

    for seed in seeds:
        env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": seed}, debug=False)
        env.run([agent, "pass"])
        rew = float(env.steps[-1][0].get("reward", 0) or 0)
        shops = env.steps[-1][0]["observation"]["town"]["unlocked_shops"]
        shops_str = ", ".join(shops[:4]) + ("..." if len(shops) > 4 else "")
        print(f"{seed:<8} | ${rew:,.1f}     | {shops_str:<45}")
        results.append({"seed": seed, "reward": rew, "shops": ", ".join(shops)})

    df = pd.DataFrame(results)
    mean_rew = df["reward"].mean()
    median_rew = df["reward"].median()
    min_rew = df["reward"].min()
    max_rew = df["reward"].max()
    std_rew = df["reward"].std()

    print("-" * 75)
    print(f"Summary over N={len(seeds)} Seeds:")
    print(f"  Mean Reward   : ${mean_rew:,.1f}")
    print(f"  Median Reward : ${median_rew:,.1f}")
    print(f"  Std Dev       : ${std_rew:,.1f}")
    print(f"  Min Reward    : ${min_rew:,.1f}")
    print(f"  Max Reward    : ${max_rew:,.1f}")

    out_csv = r"C:\Coding\project_maestro\results\dispatcher_10seed_benchmark.csv"
    df.to_csv(out_csv, index=False)
    print(f"\nWrote benchmark results to {out_csv}")

if __name__ == "__main__":
    evaluate_seeds()
