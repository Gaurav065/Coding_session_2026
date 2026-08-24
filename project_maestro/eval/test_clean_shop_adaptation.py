"""Clean Shop-Adaptive Parameter Sweep — Project Maestro

Evaluates early downward cow-cap gating directly via make_spatial_dispatcher_agent params.
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


def run_match(a0, a1, seed: int) -> Tuple[float, float]:
    game = FastGame(seed=seed)
    while not game.done:
        act0 = a0(game.get_observation(0))
        act1 = a1(game.get_observation(1))
        game.step_game(act0, act1)
    return float(game.farms[0].money), float(game.farms[1].money)


def eval_agent_params(params: Dict[str, Any], label: str):
    print(f"\n{'='*70}")
    print(f"Evaluating: {label}")
    print(f"Params: {params}")
    print(f"{'='*70}")
    
    # 1. Official 20 Self-Play
    sp_20 = []
    for s in OFFICIAL_20:
        r0, r1 = run_match(make_spatial_dispatcher_agent(params=params),
                           make_spatial_dispatcher_agent(params=params), s)
        sp_20.append((r0 + r1) / 2.0)
    mean_20 = float(np.mean(sp_20))
    
    # 2. 100 Disjoint Self-Play
    sp_100 = []
    for s in DISJOINT_100:
        r0, r1 = run_match(make_spatial_dispatcher_agent(params=params),
                           make_spatial_dispatcher_agent(params=params), s)
        sp_100.append((r0 + r1) / 2.0)
    mean_100 = float(np.mean(sp_100))
    
    # 3. Head-to-Head vs Dominant Meta (10C/4S/0G) across 100 Disjoint Seeds (200 matches)
    diffs = []
    wins = losses = ties = 0
    for s in DISJOINT_100:
        # Seat 0
        r0, r1 = run_match(make_spatial_dispatcher_agent(params=params),
                           make_spatial_dispatcher_agent(kw_early=10), s)
        d0 = r0 - r1; diffs.append(d0)
        if d0 > 0: wins += 1
        elif d0 < 0: losses += 1
        else: ties += 1
        # Seat 1
        r_opp, r_cand = run_match(make_spatial_dispatcher_agent(kw_early=10),
                                  make_spatial_dispatcher_agent(params=params), s)
        d1 = r_cand - r_opp; diffs.append(d1)
        if d1 > 0: wins += 1
        elif d1 < 0: losses += 1
        else: ties += 1
        
    n = len(diffs)
    mean_diff = float(np.mean(diffs))
    se_diff = float(np.std(diffs, ddof=1) / np.sqrt(n))
    t_stat = mean_diff / se_diff if se_diff > 0 else 0.0
    p_val = 2 * (1 - stats.t.cdf(abs(t_stat), df=n - 1))
    wr = (wins / (wins + losses)) * 100.0 if (wins + losses) > 0 else 0.0
    
    print(f"  Official 20 Self-Play:  ${mean_20:>10,.2f}  (Base: $44,743.35, Delta: {mean_20 - 44743.35:>+,.2f})")
    print(f"  Disjoint 100 Self-Play: ${mean_100:>10,.2f}  (Base: $49,613.06, Delta: {mean_100 - 49613.06:>+,.2f})")
    print(f"  H2H vs Dominant Meta:   WR={wr:.1f}% ({wins}W/{losses}L/{ties}T), Net Delta=${mean_diff:>+,.2f} (t={t_stat:>+.2f}, p={p_val:.4f})")
    
    return {
        "label": label, "mean_20": mean_20, "mean_100": mean_100,
        "wr_h2h": wr, "delta_h2h": mean_diff, "t_h2h": t_stat, "p_h2h": p_val
    }


def main():
    # Test 0: Baseline (current default)
    eval_agent_params({}, "Baseline (Default)")

    # Test 1: Day 7 zero-milk -> cap 6, Day 10 <=1 milk -> cap 6
    eval_agent_params({"cow_gate_day_early": 7, "cow_cap_zero": 6, "cow_gate_day_mid": 10},
                      "Cand 1: Day 7 zero-milk -> cap 6, Day 10 <=1 milk -> cap 6")

    # Test 2: Day 7 zero-milk -> cap 4, Day 10 <=1 milk -> cap 6
    eval_agent_params({"cow_gate_day_early": 7, "cow_cap_zero": 4, "cow_gate_day_mid": 10},
                      "Cand 2: Day 7 zero-milk -> cap 4, Day 10 <=1 milk -> cap 6")

    # Test 3: Day 10 zero-milk -> cap 4, Day 10 <=1 milk -> cap 6
    eval_agent_params({"cow_gate_day_early": 10, "cow_cap_zero": 4, "cow_gate_day_mid": 10},
                      "Cand 3: Day 10 zero-milk -> cap 4, Day 10 <=1 milk -> cap 6")

    # Test 4: Day 10 zero-milk -> cap 6, Day 13 <=1 milk -> cap 6
    eval_agent_params({"cow_gate_day_early": 10, "cow_cap_zero": 6, "cow_gate_day_mid": 13},
                      "Cand 4: Day 10 zero-milk -> cap 6, Day 13 <=1 milk -> cap 6")


if __name__ == "__main__":
    main()
