"""Fast Parallel Benchmark for Shop-Adaptive Production — Project Maestro

Evaluates Candidate 3 (early revealed cow-cap gating) across the full archetype suite
using ProcessPoolExecutor for rapid, multi-core evaluation with 100% fidelity.
"""

import sys
import os
import time
import numpy as np
from scipy import stats
from typing import Tuple, List, Dict, Any, Optional
from concurrent.futures import ProcessPoolExecutor

sys.path.insert(0, r"C:\Coding")

from project_maestro.engine.fast_engine import FastGame
from project_maestro.agent.dispatcher_agent import make_spatial_dispatcher_agent

OFFICIAL_20 = [10, 20, 30, 42, 55, 77, 99, 100, 123, 200,
               250, 300, 333, 404, 500, 600, 700, 777, 888, 999]
DISJOINT_100 = list(range(10000, 10100))

# Worker task function (pickleable)
def _worker_match(task: Tuple[Dict[str, Any], Optional[Dict[str, Any]], str, int]) -> Tuple[float, float]:
    cand_params, opp_params, opp_kind, seed = task
    
    cand_agent = make_spatial_dispatcher_agent(params=cand_params, kw_early=10)
    
    if opp_kind == "dispatcher":
        opp_agent = make_spatial_dispatcher_agent(params=opp_params, kw_early=10)
    elif opp_kind == "pass":
        opp_agent = lambda obs: {"farmer": ["PASS"], "hands": [], "market": []}
    else:
        opp_agent = make_spatial_dispatcher_agent(params=opp_params, kw_early=10)
        
    game = FastGame(seed=seed)
    while not game.done:
        game.step_game(cand_agent(game.get_observation(0)), opp_agent(game.get_observation(1)))
        
    return float(game.farms[0].money), float(game.farms[1].money)


def run_parallel_h2h(cand_params: Dict[str, Any],
                     opp_params: Optional[Dict[str, Any]],
                     opp_kind: str,
                     label: str,
                     seeds: List[int],
                     max_workers: int = 8) -> Dict[str, Any]:
    # Build paired seat tasks
    tasks = []
    for s in seeds:
        # Seat 0: Cand is P0, Opp is P1
        tasks.append((cand_params, opp_params, opp_kind, s))
        # Seat 1: Opp is P0, Cand is P1 (handled by flipping params/kind in worker)
        # For symmetric handling, we construct Cand as P1 by passing Opp as agent0
        tasks.append((opp_params, cand_params, "dispatcher", s))
        
    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        results = list(executor.map(_worker_match, tasks))
        
    diffs = []
    prod_scores = []
    opp_scores = []
    wins = losses = ties = 0
    
    for i in range(0, len(results), 2):
        # Seat 0: (r_cand0, r_opp1)
        r_cand0, r_opp1 = results[i]
        d0 = r_cand0 - r_opp1
        diffs.append(d0); prod_scores.append(r_cand0); opp_scores.append(r_opp1)
        if d0 > 0: wins += 1
        elif d0 < 0: losses += 1
        else: ties += 1
        
        # Seat 1: (r_opp0, r_cand1)
        r_opp0, r_cand1 = results[i+1]
        d1 = r_cand1 - r_opp0
        diffs.append(d1); prod_scores.append(r_cand1); opp_scores.append(r_opp0)
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
    
    print(f"  {label:<34} | Prod: ${mean_p:>9,.2f} | Opp: ${mean_o:>9,.2f} | Delta: ${mean_diff:>+9,.2f} (t={t_stat:>+5.2f}, p={p_val:.4e}) | WR: {wr:>5.1f}% ({wins}W/{losses}L/{ties}T)", flush=True)
    return {
        "label": label, "prod_mean": mean_p, "opp_mean": mean_o,
        "delta": mean_diff, "se": se_diff, "t": t_stat, "p": p_val,
        "wr": wr, "W": wins, "L": losses, "T": ties
    }


def run_parallel_self_play(params: Dict[str, Any], seeds: List[int], max_workers: int = 8) -> Tuple[float, float, float, float]:
    tasks = [(params, params, "dispatcher", s) for s in seeds]
    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        results = list(executor.map(_worker_match, tasks))
    all_scores = [r[0] for r in results] + [r[1] for r in results]
    return float(np.mean(all_scores)), float(np.median(all_scores)), float(np.min(all_scores)), float(np.max(all_scores))


def main():
    workers = min(os.cpu_count() or 4, 8)
    print("=" * 115)
    print(f"FAST MULTI-PROCESS ARCHETYPE BENCHMARK (PARALLEL WORKERS: {workers})")
    print("Candidate: Adaptive Cow Cap (Day 10 zero-milk -> cap 4, Day 10 <=1 milk -> cap 6)")
    print("=" * 115)
    
    cand_params = {
        "cow_gate_day_early": 10,
        "cow_cap_zero": 4,
        "cow_gate_day_mid": 10,
        "cow_cap_low": 6
    }
    
    t0 = time.time()
    
    # 1. Self-Play Suites
    sp_20_mean, sp_20_med, sp_20_min, sp_20_max = run_parallel_self_play(cand_params, OFFICIAL_20, max_workers=workers)
    sp_100_mean, sp_100_med, sp_100_min, sp_100_max = run_parallel_self_play(cand_params, DISJOINT_100, max_workers=workers)
    
    print(f"Self-Play Official 20:  Mean ${sp_20_mean:>9,.2f} (Median: ${sp_20_med:>9,.2f}, Min: ${sp_20_min:>9,.2f}, Max: ${sp_20_max:>9,.2f}) | Baseline: $44,743.35, Delta: {sp_20_mean - 44743.35:>+,.2f}", flush=True)
    print(f"Self-Play Disjoint 100: Mean ${sp_100_mean:>9,.2f} (Median: ${sp_100_med:>9,.2f}, Min: ${sp_100_min:>9,.2f}, Max: ${sp_100_max:>9,.2f}) | Baseline: $49,613.06, Delta: {sp_100_mean - 49613.06:>+,.2f}", flush=True)
    print("-" * 115, flush=True)
    print("Head-to-Head Matches (100 Disjoint Seeds x 2 seats = 200 matches per archetype):", flush=True)
    print("-" * 115, flush=True)
    
    run_parallel_h2h(cand_params, {}, "dispatcher", "Dominant Meta (10C/4S/0G)", DISJOINT_100, max_workers=workers)
    run_parallel_h2h(cand_params, {"cow_cap_base": 6, "sheep_cap": 12, "goose_cap": 0}, "dispatcher", "Wool-Heavy (6C/12S/0G)", DISJOINT_100, max_workers=workers)
    run_parallel_h2h(cand_params, {"cow_cap_base": 6, "sheep_cap": 8, "goose_cap": 0}, "dispatcher", "Balanced Pasture (6C/8S/0G)", DISJOINT_100, max_workers=workers)
    run_parallel_h2h(cand_params, {"goose_cap": 4}, "dispatcher", "Old Baseline (Goose-4, 10C/4S/4G)", DISJOINT_100, max_workers=workers)
    run_parallel_h2h(cand_params, {}, "pass", "Pass Baseline", OFFICIAL_20, max_workers=workers)
    
    elapsed = time.time() - t0
    print("=" * 115, flush=True)
    print(f"Benchmark completed in {elapsed:.2f} seconds ({len(DISJOINT_100)*2*4 + len(OFFICIAL_20)*2 + 120} matches total)", flush=True)
    print("=" * 115, flush=True)


if __name__ == "__main__":
    main()
