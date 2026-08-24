"""Dynamic Reallocation Policy Sweep — Project Maestro (§2x)

Tests capital reallocation policies using the production agent's new params:
- sheep_realloc_cap: sheep cap when YARN_STORE active & milk_shop_count<=1 on day>=10
- melon_realloc_target: melon seed target when SALAD_BAR or FARMERS_MARKET present

All policies are tested via the verified fast_parallel_benchmark harness pattern
with symmetric seat packing. Canary validation runs first.
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


def _worker_match(task):
    p0_params, p0_kind, p1_params, p1_kind, seed = task
    a0 = _build_agent(p0_kind, p0_params)
    a1 = _build_agent(p1_kind, p1_params)
    game = FastGame(seed=seed)
    while not game.done:
        game.step_game(a0(game.get_observation(0)), a1(game.get_observation(1)))
    return float(game.farms[0].money), float(game.farms[1].money)


def run_self_play(params, seeds, max_workers=8):
    tasks = [(params, "dispatcher", params, "dispatcher", s) for s in seeds]
    with ProcessPoolExecutor(max_workers=max_workers) as ex:
        results = list(ex.map(_worker_match, tasks))
    all_scores = [r[0] for r in results] + [r[1] for r in results]
    return float(np.mean(all_scores)), float(np.median(all_scores)), float(np.min(all_scores)), float(np.max(all_scores))


def run_h2h(cand_params, opp_params, opp_kind, seeds, max_workers=8):
    tasks = []
    for s in seeds:
        tasks.append((cand_params, "dispatcher", opp_params, opp_kind, s))
        tasks.append((opp_params, opp_kind, cand_params, "dispatcher", s))
    with ProcessPoolExecutor(max_workers=max_workers) as ex:
        results = list(ex.map(_worker_match, tasks))
    diffs, prod_sc, opp_sc = [], [], []
    wins = losses = ties = 0
    for i in range(0, len(results), 2):
        r_c0, r_o1 = results[i]
        d0 = r_c0 - r_o1; diffs.append(d0); prod_sc.append(r_c0); opp_sc.append(r_o1)
        if d0 > 0: wins += 1
        elif d0 < 0: losses += 1
        else: ties += 1
        r_o0, r_c1 = results[i+1]
        d1 = r_c1 - r_o0; diffs.append(d1); prod_sc.append(r_c1); opp_sc.append(r_o0)
        if d1 > 0: wins += 1
        elif d1 < 0: losses += 1
        else: ties += 1
    n = len(diffs)
    mean_d = float(np.mean(diffs))
    se_d = float(np.std(diffs, ddof=1) / np.sqrt(n))
    t_stat = mean_d / se_d if se_d > 0 else 0.0
    p_val = 2 * (1 - stats.t.cdf(abs(t_stat), df=n - 1))
    wr = (wins / (wins + losses)) * 100.0 if (wins + losses) > 0 else 0.0
    return {
        "prod_mean": float(np.mean(prod_sc)), "opp_mean": float(np.mean(opp_sc)),
        "delta": mean_d, "se": se_d, "t": t_stat, "p": p_val,
        "wr": wr, "W": wins, "L": losses, "T": ties
    }


def eval_policy(label, cand_params, workers):
    print(f"\n{'='*100}", flush=True)
    print(f"  {label}", flush=True)
    print(f"  Params: {cand_params}", flush=True)
    print(f"{'='*100}", flush=True)

    # Self-Play
    sp20_mean, sp20_med, sp20_min, sp20_max = run_self_play(cand_params, OFFICIAL_20, max_workers=workers)
    sp100_mean, sp100_med, sp100_min, sp100_max = run_self_play(cand_params, DISJOINT_100, max_workers=workers)
    print(f"  Self-Play Official 20:  ${sp20_mean:>9,.2f} (Med: ${sp20_med:>9,.2f}, Min: ${sp20_min:>9,.2f}) | Delta vs $47,224.93: {sp20_mean - 47224.93:>+,.2f}", flush=True)
    print(f"  Self-Play Disjoint 100: ${sp100_mean:>9,.2f} (Med: ${sp100_med:>9,.2f}, Min: ${sp100_min:>9,.2f}) | Delta vs $52,058.16: {sp100_mean - 52058.16:>+,.2f}", flush=True)

    # H2H vs Dominant Meta (un-gated 10C/4S/0G)
    opp_dom = {"cow_gate_day_early": 99, "cow_gate_day_mid": 99}
    r_dm = run_h2h(cand_params, opp_dom, "dispatcher", DISJOINT_100, max_workers=workers)
    print(f"  vs Dominant Meta (10C/4S/0G): Prod ${r_dm['prod_mean']:>9,.2f} | Opp ${r_dm['opp_mean']:>9,.2f} | Delta ${r_dm['delta']:>+9,.2f} (t={r_dm['t']:>+5.2f}, p={r_dm['p']:.4e}) | WR: {r_dm['wr']:>5.1f}% ({r_dm['W']}W/{r_dm['L']}L/{r_dm['T']}T)", flush=True)

    # H2H vs Wool-Heavy
    opp_wh = {"cow_cap_base": 6, "sheep_cap": 12, "goose_cap": 0, "cow_gate_day_early": 99, "cow_gate_day_mid": 99}
    r_wh = run_h2h(cand_params, opp_wh, "dispatcher", DISJOINT_100, max_workers=workers)
    print(f"  vs Wool-Heavy (6C/12S/0G):    Prod ${r_wh['prod_mean']:>9,.2f} | Opp ${r_wh['opp_mean']:>9,.2f} | Delta ${r_wh['delta']:>+9,.2f} (t={r_wh['t']:>+5.2f}, p={r_wh['p']:.4e}) | WR: {r_wh['wr']:>5.1f}% ({r_wh['W']}W/{r_wh['L']}L/{r_wh['T']}T)", flush=True)

    return {"label": label, "sp20": sp20_mean, "sp100": sp100_mean, "dm": r_dm, "wh": r_wh}


def main():
    workers = min(os.cpu_count() or 4, 8)
    print("=" * 100)
    print(f"DYNAMIC REALLOCATION POLICY SWEEP — §2x ({workers} WORKERS)")
    print("Baseline (§2w): Official 20 = $47,224.93, Disjoint 100 = $52,058.16, DM WR = 64.3%")
    print("=" * 100)

    # Canary: Verify Identity Control still passes
    print("\n--- STANDING CANARY: Identity Control ---", flush=True)
    baseline_params = {}  # All defaults
    r_ident = run_h2h(baseline_params, baseline_params, "dispatcher", DISJOINT_100, max_workers=workers)
    if abs(r_ident["wr"] - 50.0) > 1e-4 or abs(r_ident["delta"]) > 1e-4:
        raise RuntimeError(f"CANARY FAILED! Identity WR={r_ident['wr']:.1f}%, Delta=${r_ident['delta']:.2f}")
    print(f"  [PASS] Identity Control: WR=50.0%, Delta=$0.00 ({r_ident['W']}W/{r_ident['L']}L/{r_ident['T']}T)", flush=True)

    t0 = time.time()

    # Policy 0: Baseline (current production, all realloc params at default = no change)
    eval_policy("Policy 0: BASELINE (no reallocation)", {}, workers)

    # Policy 1: Sheep realloc cap 6 (when YARN_STORE + low milk on Day 10+)
    eval_policy("Policy 1: Sheep Cap 6 on YARN_STORE + Low Milk",
                {"sheep_realloc_cap": 6, "sheep_realloc_day": 10}, workers)

    # Policy 2: Sheep realloc cap 8 (when YARN_STORE + low milk on Day 10+)
    eval_policy("Policy 2: Sheep Cap 8 on YARN_STORE + Low Milk",
                {"sheep_realloc_cap": 8, "sheep_realloc_day": 10}, workers)

    # Policy 3: Melon realloc target 10 (when SALAD_BAR/FARMERS_MARKET present)
    eval_policy("Policy 3: Melon Target 10 on Melon Shops",
                {"melon_realloc_target": 10}, workers)

    # Policy 4: Combined — Sheep 6 + Melon 10
    eval_policy("Policy 4: Combined Sheep 6 + Melon 10",
                {"sheep_realloc_cap": 6, "sheep_realloc_day": 10, "melon_realloc_target": 10}, workers)

    # Policy 5: Sheep realloc cap 6 + stricter melon (target 8)
    eval_policy("Policy 5: Combined Sheep 6 + Melon 8",
                {"sheep_realloc_cap": 6, "sheep_realloc_day": 10, "melon_realloc_target": 8}, workers)

    elapsed = time.time() - t0
    print(f"\n{'='*100}", flush=True)
    print(f"Sweep completed in {elapsed:.1f}s", flush=True)
    print(f"{'='*100}", flush=True)


if __name__ == "__main__":
    main()
