"""Head-to-Head Real Environment Evaluation Harness - Project Maestro (Phase 2 Gate Validation)

Executes head-to-head matches in the official kaggriculture environment via env.run()
for the top 3 solved portfolios against the Reference 10C/4S/0G build across both seats.

Top 3 Solved Portfolios Evaluated:
1. Yarn-Store Exploiter (Cluster 02): 16 Cows / 14 Sheep / 0 Goose + 8 Wheat plots + 4 Strawberries, crew 5/6/10.
2. Additive-Goose Resilient (Cluster 00/03): 8 Cows / 6 Sheep / 12 Geese + 7 Wheat plots + 4 Strawberries, crew 5/4/8.
3. High-Yield Balanced (Cluster 07/09): 16 Cows / 6 Sheep / 8 Geese + 8 Wheat plots + 4 Strawberries, crew 5/6/10.
"""

import os
import random
from typing import Tuple, Dict, Any, List
import numpy as np
import pandas as pd
from kaggle_environments import make

from project_maestro.agent.parameterized_agent import make_agent

def run_match(agent0_fn, agent1_fn, seed: int = 42) -> Tuple[float, float, int]:
    """Run a single 720-step match between two agents in kaggriculture."""
    random.seed(seed)
    np.random.seed(seed)
    env = make("kaggriculture", configuration={"episodeSteps": 720}, debug=False)
    env.run([agent0_fn, agent1_fn])
    
    p0_reward = float(env.steps[-1][0].get("reward", 0) or 0)
    p1_reward = float(env.steps[-1][1].get("reward", 0) or 0)
    winner = 0 if p0_reward > p1_reward else (1 if p1_reward > p0_reward else -1)
    return p0_reward, p1_reward, winner


def evaluate_solved_portfolio(
    name: str,
    solved_params: Dict[str, Any],
    n_seeds: int = 10,
    base_seed: int = 100,
) -> Dict[str, Any]:
    """Evaluate a solved portfolio against the reference baseline across both seats."""
    ref_params = {
        "target_cows": 10, "target_sheep": 4, "target_geese": 0,
        "wheat_plots": 8, "cash_crop": "STRAWBERRY", "cash_crop_plots": 4,
        "day0_crew": 5, "maint_crew": 5, "peak_crew": 9,
    }

    solved_rewards_seat0 = []
    ref_rewards_seat1 = []
    solved_wins_seat0 = 0

    solved_rewards_seat1 = []
    ref_rewards_seat0 = []
    solved_wins_seat1 = 0

    print(f"\n=== Evaluating '{name}' Head-to-Head against 10C/4S/0G Reference (N={n_seeds} matches per seat) ===")

    # Seat 0: Solved Agent is Player 0, Ref is Player 1
    for i in range(n_seeds):
        seed = base_seed + i
        s_agent = make_agent(**solved_params)
        r_agent = make_agent(**ref_params)
        s_rew, r_rew, w = run_match(s_agent, r_agent, seed=seed)
        solved_rewards_seat0.append(s_rew)
        ref_rewards_seat1.append(r_rew)
        if w == 0: solved_wins_seat0 += 1
        print(f"  [Seat 0 | Seed {seed}] Solved: ${s_rew:,.0f} vs Ref: ${r_rew:,.0f} | Winner: {'SOLVED' if w == 0 else ('REF' if w == 1 else 'TIE')}")

    # Seat 1: Ref is Player 0, Solved Agent is Player 1
    for i in range(n_seeds):
        seed = base_seed + 1000 + i
        r_agent = make_agent(**ref_params)
        s_agent = make_agent(**solved_params)
        r_rew, s_rew, w = run_match(r_agent, s_agent, seed=seed)
        ref_rewards_seat0.append(r_rew)
        solved_rewards_seat1.append(s_rew)
        if w == 1: solved_wins_seat1 += 1
        print(f"  [Seat 1 | Seed {seed}] Solved: ${s_rew:,.0f} vs Ref: ${r_rew:,.0f} | Winner: {'SOLVED' if w == 1 else ('REF' if w == 0 else 'TIE')}")

    all_solved = solved_rewards_seat0 + solved_rewards_seat1
    all_ref = ref_rewards_seat1 + ref_rewards_seat0
    total_matches = 2 * n_seeds
    total_wins = solved_wins_seat0 + solved_wins_seat1
    win_rate = (total_wins / total_matches) * 100.0
    mean_solved = np.mean(all_solved)
    mean_ref = np.mean(all_ref)
    mean_margin = mean_solved - mean_ref

    print(f"\nSummary for '{name}':")
    print(f"  Total Matches: {total_matches} (Seat 0: {n_seeds}, Seat 1: {n_seeds})")
    print(f"  Win Rate: {win_rate:.1f}% ({total_wins}/{total_matches} wins)")
    print(f"  Mean Solved Reward: ${mean_solved:,.1f}")
    print(f"  Mean Ref Reward:    ${mean_ref:,.1f}")
    print(f"  Net Margin:         +${mean_margin:,.1f} (+{(mean_margin / mean_ref) * 100:.1f}%)")

    return {
        "portfolio_name": name,
        "total_matches": total_matches,
        "win_rate": win_rate,
        "solved_mean": mean_solved,
        "ref_mean": mean_ref,
        "net_margin": mean_margin,
        "edge_pct": (mean_margin / mean_ref) * 100.0,
    }


def run_all_top3_evaluations():
    # 1. Yarn Store Exploiter
    yarn_params = {
        "target_cows": 16, "target_sheep": 14, "target_geese": 0,
        "wheat_plots": 8, "cash_crop": "STRAWBERRY", "cash_crop_plots": 4,
        "day0_crew": 5, "maint_crew": 6, "peak_crew": 10,
    }
    r1 = evaluate_solved_portfolio("1. Yarn-Store Exploiter (16C/14S/0G)", yarn_params, n_seeds=5, base_seed=101)

    # 2. Additive-Goose Resilient
    goose_params = {
        "target_cows": 8, "target_sheep": 6, "target_geese": 12,
        "wheat_plots": 7, "cash_crop": "STRAWBERRY", "cash_crop_plots": 4,
        "day0_crew": 5, "maint_crew": 5, "peak_crew": 9,
    }
    r2 = evaluate_solved_portfolio("2. Additive-Goose Resilient (8C/6S/12G)", goose_params, n_seeds=5, base_seed=201)

    # 3. High-Yield Balanced
    balanced_params = {
        "target_cows": 16, "target_sheep": 6, "target_geese": 8,
        "wheat_plots": 8, "cash_crop": "STRAWBERRY", "cash_crop_plots": 4,
        "day0_crew": 5, "maint_crew": 6, "peak_crew": 10,
    }
    r3 = evaluate_solved_portfolio("3. High-Yield Balanced (16C/6S/8G)", balanced_params, n_seeds=5, base_seed=301)

    # Output validation summary CSV
    out_df = pd.DataFrame([r1, r2, r3])
    out_path = r"C:\Coding\project_maestro\results\top3_empirical_validation.csv"
    out_df.to_csv(out_path, index=False)
    print(f"\nWrote validation results to {out_path}")


if __name__ == "__main__":
    from typing import Tuple, Dict, Any
    run_all_top3_evaluations()
