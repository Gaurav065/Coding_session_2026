"""Fast Parallel Benchmark for Shop-Adaptive Production — Project Maestro

Evaluates Candidate 3 (early revealed cow-cap gating) across the full archetype suite
using ProcessPoolExecutor for rapid, multi-core evaluation with 100% fidelity.
Includes standing known-answer canaries (Pass Baseline and Identity Control).
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


def _build_agent(kind: str, params: Optional[Dict[str, Any]]):
    if kind == "dispatcher":
        return make_spatial_dispatcher_agent(params=params, kw_early=10)
    elif kind == "pass":
        return lambda obs: {"farmer": ["PASS"], "hands": [], "market": []}
    else:
        raise ValueError(f"Unknown agent kind: {kind}")


# Symmetric worker function (pickleable)
def _worker_match(task: Tuple[Optional[Dict[str, Any]], str, Optional[Dict[str, Any]], str, int]) -> Tuple[float, float]:
    p0_params, p0_kind, p1_params, p1_kind, seed = task
    
    a0 = _build_agent(p0_kind, p0_params)
    a1 = _build_agent(p1_kind, p1_params)
    
    game = FastGame(seed=seed)
    while not game.done:
        game.step_game(a0(game.get_observation(0)), a1(game.get_observation(1)))
        
    return float(game.farms[0].money), float(game.farms[1].money)


def run_parallel_h2h(cand_params: Dict[str, Any],
                     opp_params: Optional[Dict[str, Any]],
                     opp_kind: str,
                     label: str,
                     seeds: List[int],
                     max_workers: int = 8) -> Dict[str, Any]:
    # Build paired seat tasks:
    # Seat 0: Cand is P0, Opp is P1
    # Seat 1: Opp is P0, Cand is P1
    tasks = []
    for s in seeds:
        tasks.append((cand_params, "dispatcher", opp_params, opp_kind, s))
        tasks.append((opp_params, opp_kind, cand_params, "dispatcher", s))
        
    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        results = list(executor.map(_worker_match, tasks))
        
    diffs = []
    prod_scores = []
    opp_scores = []
    wins = losses = ties = 0
    
    for i in range(0, len(results), 2):
        # Seat 0: Cand is P0, Opp is P1
        r_cand0, r_opp1 = results[i]
        d0 = r_cand0 - r_opp1
        diffs.append(d0); prod_scores.append(r_cand0); opp_scores.append(r_opp1)
        if d0 > 0: wins += 1
        elif d0 < 0: losses += 1
        else: ties += 1
        
        # Seat 1: Opp is P0, Cand is P1
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
    tasks = [(params, "dispatcher", params, "dispatcher", s) for s in seeds]
    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        results = list(executor.map(_worker_match, tasks))
    all_scores = [r[0] for r in results] + [r[1] for r in results]
    return float(np.mean(all_scores)), float(np.median(all_scores)), float(np.min(all_scores)), float(np.max(all_scores))


def main():
    workers = min(os.cpu_count() or 4, 8)
    print("=" * 115)
    print(f"FAST MULTI-PROCESS ARCHETYPE BENCHMARK ({workers} WORKERS)")
    print("Candidate: Adaptive Cow Cap (Day 10 zero-milk -> cap 4, Day 10 <=1 milk -> cap 6)")
    print("=" * 115)
    
    cand_params = {
        "cow_gate_day_early": 10,
        "cow_cap_zero": 4,
        "cow_gate_day_mid": 10,
        "cow_cap_low": 6
    }
    
    # ── STANDING CANARIES ─────────────────────────────────────────────────────
    print("\n--- RUNNING STANDING CANARIES ---", flush=True)
    
    # Canary 1: Pass Baseline (Opponent must score exactly $3,000.00 and WR must be 100.0%)
    res_pass = run_parallel_h2h(cand_params, {}, "pass", "Canary 1: Pass Baseline", DISJOINT_100, max_workers=workers)
    if abs(res_pass["opp_mean"] - 3000.0) > 1e-4 or res_pass["wr"] != 100.0:
        raise RuntimeError(f"CANARY 1 FAILED! Pass baseline opponent mean is ${res_pass['opp_mean']:.2f} (expected $3,000.00) and WR is {res_pass['wr']:.1f}% (expected 100.0%)")
    print("  [PASS] Canary 1 (Pass Baseline): Opponent = $3,000.00, WR = 100.0% exactly.", flush=True)
    
    # Canary 2: Identity Control (Identical params must yield exactly 50.0% WR and Delta = $0.00)
    res_ident = run_parallel_h2h(cand_params, cand_params, "dispatcher", "Canary 2: Identity Control", DISJOINT_100, max_workers=workers)
    if abs(res_ident["wr"] - 50.0) > 1e-4 or abs(res_ident["delta"]) > 1e-4:
        raise RuntimeError(f"CANARY 2 FAILED! Identity control WR is {res_ident['wr']:.1f}% (expected 50.0%) and Delta is ${res_ident['delta']:.2f} (expected $0.00)")
    print("  [PASS] Canary 2 (Identity Control): WR = 50.0%, Delta = $0.00 exactly.", flush=True)
    
    # ── HEADLINE BENCHMARK SUITE ──────────────────────────────────────────────
    print("\n--- RUNNING HEADLINE ARCHETYPE BENCHMARK ---", flush=True)
    t0 = time.time()
    
    # 1. Self-Play Suites
    sp_20_mean, sp_20_med, sp_20_min, sp_20_max = run_parallel_self_play(cand_params, OFFICIAL_20, max_workers=workers)
    sp_100_mean, sp_100_med, sp_100_min, sp_100_max = run_parallel_self_play(cand_params, DISJOINT_100, max_workers=workers)
    
    print(f"Self-Play Official 20:  Mean ${sp_20_mean:>9,.2f} (Median: ${sp_20_med:>9,.2f}, Min: ${sp_20_min:>9,.2f}, Max: ${sp_20_max:>9,.2f}) | Baseline: $44,743.35, Delta: {sp_20_mean - 44743.35:>+,.2f}", flush=True)
    print(f"Self-Play Disjoint 100: Mean ${sp_100_mean:>9,.2f} (Median: ${sp_100_med:>9,.2f}, Min: ${sp_100_min:>9,.2f}, Max: ${sp_100_max:>9,.2f}) | Baseline: $49,613.06, Delta: {sp_100_mean - 49613.06:>+,.2f}", flush=True)
    print("-" * 115, flush=True)
    print("Head-to-Head Matches (100 Disjoint Seeds x 2 seats = 200 matches per archetype):", flush=True)
    print("-" * 115, flush=True)
    
    run_parallel_h2h(cand_params, {"cow_gate_day_early": 99, "cow_gate_day_mid": 99}, "dispatcher", "Dominant Meta (10C/4S/0G)", DISJOINT_100, max_workers=workers)
    run_parallel_h2h(cand_params, {"cow_cap_base": 6, "sheep_cap": 12, "goose_cap": 0, "cow_gate_day_early": 99, "cow_gate_day_mid": 99}, "dispatcher", "Wool-Heavy (6C/12S/0G)", DISJOINT_100, max_workers=workers)
    run_parallel_h2h(cand_params, {"cow_cap_base": 6, "sheep_cap": 8, "goose_cap": 0, "cow_gate_day_early": 99, "cow_gate_day_mid": 99}, "dispatcher", "Balanced Pasture (6C/8S/0G)", DISJOINT_100, max_workers=workers)
    run_parallel_h2h(cand_params, {"goose_cap": 4, "cow_gate_day_early": 99, "cow_gate_day_mid": 99}, "dispatcher", "Old Baseline (Goose-4, 10C/4S/4G)", DISJOINT_100, max_workers=workers)
    run_parallel_h2h(cand_params, {}, "pass", "Pass Baseline", DISJOINT_100, max_workers=workers)
    
    elapsed = time.time() - t0
    print("=" * 115, flush=True)
    print(f"Benchmark completed in {elapsed:.2f} seconds ({len(DISJOINT_100)*2*5 + 120} matches total)", flush=True)
    print("=" * 115, flush=True)


if __name__ == "__main__":
    main()
