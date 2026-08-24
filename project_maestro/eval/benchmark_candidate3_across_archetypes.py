"""Full Archetype Matrix & Benchmark for Early Cow-Cap Adaptation (Candidate 3)

Candidate 3 Parameters:
- cow_gate_day_early = 10, cow_cap_zero = 4 (Day 10: 0 milk shops -> cap at 4 cows)
- cow_gate_day_mid = 10, cow_cap_low = 6   (Day 10: <=1 milk shop -> cap at 6 cows)

Evaluates across:
1. Official 20 Seeds Self-Play
2. 100 Disjoint Seeds Self-Play (10000..10099)
3. Full 7-Archetype Matrix on 100 Disjoint Seeds (200 matches per archetype = 1,400 matches)
   - Dominant Meta (10C/4S/0G)
   - Wool-Heavy (6C/12S/0G)
   - Balanced Pasture (6C/8S/0G)
   - Unsteered Baseline (10C/4S/0G default)
   - Starter Baseline
   - Random Baseline
   - Pass Baseline
"""

import sys
import numpy as np
from scipy import stats
from typing import Tuple, List, Dict, Any

sys.path.insert(0, r"C:\Coding")

from project_maestro.engine.fast_engine import FastGame
from project_maestro.agent.dispatcher_agent import make_spatial_dispatcher_agent

OFFICIAL_20 = [10, 20, 30, 42, 55, 77, 99, 100, 123, 200,
               250, 300, 333, 404, 500, 600, 700, 777, 888, 999]
DISJOINT_100 = list(range(10000, 10100))

CAND3_PARAMS = {
    "cow_gate_day_early": 10,
    "cow_cap_zero": 4,
    "cow_gate_day_mid": 10,
    "cow_cap_low": 6
}


def run_match(a0, a1, seed: int) -> Tuple[float, float]:
    game = FastGame(seed=seed)
    while not game.done:
        act0 = a0(game.get_observation(0))
        act1 = a1(game.get_observation(1))
        game.step_game(act0, act1)
    return float(game.farms[0].money), float(game.farms[1].money)


def eval_h2h(cand_factory, opp_factory, label: str, seeds: List[int] = DISJOINT_100):
    diffs = []
    prod_scores = []
    opp_scores = []
    wins = losses = ties = 0
    for s in seeds:
        # Seat 0
        r0, r1 = run_match(cand_factory(), opp_factory(s), s)
        d0 = r0 - r1; diffs.append(d0); prod_scores.append(r0); opp_scores.append(r1)
        if d0 > 0: wins += 1
        elif d0 < 0: losses += 1
        else: ties += 1
        # Seat 1
        r_opp, r_cand = run_match(opp_factory(s), cand_factory(), s)
        d1 = r_cand - r_opp; diffs.append(d1); prod_scores.append(r_cand); opp_scores.append(r_opp)
        if d1 > 0: wins += 1
        elif d1 < 0: losses += 1
        else: ties += 1
        
    n = len(diffs)
    mean_diff = float(np.mean(diffs))
    se_diff = float(np.std(diffs, ddof=1) / np.sqrt(n))
    t_stat = mean_diff / se_diff if se_diff > 0 else 0.0
    p_val = 2 * (1 - stats.t.cdf(abs(t_stat), df=n - 1))
    wr = (wins / (wins + losses)) * 100.0 if (wins + losses) > 0 else 0.0
    mean_p = float(np.mean(prod_scores))
    mean_o = float(np.mean(opp_scores))
    
    print(f"  {label:<32} | Prod: ${mean_p:>9,.2f} | Opp: ${mean_o:>9,.2f} | Delta: ${mean_diff:>+9,.2f} (t={t_stat:>+5.2f}, p={p_val:.4f}) | WR: {wr:>5.1f}% ({wins}W/{losses}L/{ties}T)")
    return {
        "label": label, "prod_mean": mean_p, "opp_mean": mean_o,
        "delta": mean_diff, "se": se_diff, "t": t_stat, "p": p_val,
        "wr": wr, "W": wins, "L": losses, "T": ties
    }


def main():
    print("=" * 110)
    print("FULL ARCHETYPE EVALUATION FOR SHOP-ADAPTIVE CANDIDATE 3")
    print("Params:", CAND3_PARAMS)
    print("=" * 110)
    
    cand = lambda: make_spatial_dispatcher_agent(params=CAND3_PARAMS)
    
    # 1. Self-Play Baselines
    sp_20 = [ (run_match(cand(), cand(), s)[0] + run_match(cand(), cand(), s)[1])/2.0 for s in OFFICIAL_20 ]
    sp_100 = [ (run_match(cand(), cand(), s)[0] + run_match(cand(), cand(), s)[1])/2.0 for s in DISJOINT_100 ]
    
    print(f"Self-Play Official 20:  ${np.mean(sp_20):>10,.2f}  (Baseline: $44,743.35, Delta: {np.mean(sp_20) - 44743.35:>+,.2f})")
    print(f"Self-Play Disjoint 100: ${np.mean(sp_100):>10,.2f}  (Baseline: $49,613.06, Delta: {np.mean(sp_100) - 49613.06:>+,.2f})")
    print("-" * 110)
    print("Head-to-Head vs Ladder Archetypes (100 Disjoint Seeds x 2 seats = 200 matches each):")
    print("-" * 110)
    
    eval_h2h(cand, lambda s: make_spatial_dispatcher_agent(kw_early=10), "Dominant Meta (10C/4S/0G)")
    eval_h2h(cand, lambda s: make_spatial_dispatcher_agent(params={"cow_cap_base": 6, "sheep_cap": 12, "goose_cap": 0}, kw_early=10), "Wool-Heavy (6C/12S/0G)")
    eval_h2h(cand, lambda s: make_spatial_dispatcher_agent(params={"cow_cap_base": 6, "sheep_cap": 8, "goose_cap": 0}, kw_early=10), "Balanced Pasture (6C/8S/0G)")
    eval_h2h(cand, lambda s: make_spatial_dispatcher_agent(params={"goose_cap": 4}, kw_early=10), "Old Baseline (Goose-4, 10C/4S/4G)")
    eval_h2h(cand, lambda s: "starter", "Starter Baseline")
    eval_h2h(cand, lambda s: "random", "Random Baseline")
    eval_h2h(cand, lambda s: "pass", "Pass Baseline")
    print("=" * 110)


if __name__ == "__main__":
    main()
