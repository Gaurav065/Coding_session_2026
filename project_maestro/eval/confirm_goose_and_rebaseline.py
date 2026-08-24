"""Confirmation Run & Honest Re-baseline — Project Maestro

1. Confirmation Run:
   goose_cap=4 unsteered vs Dominant Meta (10C/4S/0G, goose_cap=0 unsteered)
   across 100 disjoint seeds (seeds 10000..10099) x 2 seats = 200 matches.
   Confirms the §2s 40-match finding (15% WR, p=0.018) at n=200 without steering confounds.

2. Honest Re-baseline of Production Agent:
   Default instantiation `make_spatial_dispatcher_agent()` with NO seed injected (kw_early=10 natural, goose_cap=0).
   Runs:
   - Official 20 Seeds Self-Play (env.run / FastGame)
   - 100 Disjoint Seeds Self-Play (seeds 10000..10099)
"""

import sys
import numpy as np
from scipy import stats
from typing import Tuple, List

sys.path.insert(0, r"C:\Coding")

from project_maestro.engine.fast_engine import FastGame
from project_maestro.agent.dispatcher_agent import (
    make_spatial_dispatcher_agent, MaestroFullPortfolioAgent
)

OFFICIAL_20_SEEDS = [10, 20, 30, 42, 55, 77, 99, 100, 123, 200,
                     250, 300, 333, 404, 500, 600, 700, 777, 888, 999]
DISJOINT_100_SEEDS = list(range(10000, 10100))


def run_fast_match(agent_0, agent_1, seed: int) -> Tuple[float, float]:
    game = FastGame(seed=seed)
    while not game.done:
        act0 = agent_0(game.get_observation(0))
        act1 = agent_1(game.get_observation(1))
        game.step_game(act0, act1)
    return float(game.farms[0].money), float(game.farms[1].money)


def run_confirmation_goose4_vs_dom_meta():
    print("=" * 80)
    print("1. CONFIRMATION RUN: goose_cap=4 unsteered vs Dominant Meta (10C/4S/0G, goose_cap=0)")
    print("   100 disjoint seeds x 2 seats = 200 matches via FastEngine")
    print("=" * 80)

    diffs = []
    prod_scores = []
    opp_scores = []
    wins = losses = ties = 0

    for seed in DISJOINT_100_SEEDS:
        # Seat 0: Us (goose_cap=4, kw_early=10) vs Opp (Dominant Meta: goose_cap=0, kw_early=10)
        p0 = make_spatial_dispatcher_agent(params={"goose_cap": 4}, kw_early=10)
        p1 = make_spatial_dispatcher_agent(params={"cow_cap_base": 10, "sheep_cap": 4, "goose_cap": 0}, kw_early=10)
        r0, r1 = run_fast_match(p0, p1, seed)
        d0 = r0 - r1
        diffs.append(d0)
        prod_scores.append(r0)
        opp_scores.append(r1)
        if d0 > 0: wins += 1
        elif d0 < 0: losses += 1
        else: ties += 1

        # Seat 1: Opp (Dominant Meta) vs Us (goose_cap=4, kw_early=10)
        p0_opp = make_spatial_dispatcher_agent(params={"cow_cap_base": 10, "sheep_cap": 4, "goose_cap": 0}, kw_early=10)
        p1_us = make_spatial_dispatcher_agent(params={"goose_cap": 4}, kw_early=10)
        r_opp, r_us = run_fast_match(p0_opp, p1_us, seed)
        d1 = r_us - r_opp
        diffs.append(d1)
        prod_scores.append(r_us)
        opp_scores.append(r_opp)
        if d1 > 0: wins += 1
        elif d1 < 0: losses += 1
        else: ties += 1

    n = len(diffs)
    mean_diff = float(np.mean(diffs))
    se = float(np.std(diffs, ddof=1) / np.sqrt(n))
    t_stat = mean_diff / se if se > 0 else 0.0
    p_val = 2 * (1 - stats.t.cdf(abs(t_stat), df=n - 1))
    mean_prod = float(np.mean(prod_scores))
    mean_opp = float(np.mean(opp_scores))
    wr_all = 100.0 * wins / n
    wr_notie = 100.0 * wins / (wins + losses) if (wins + losses) > 0 else 0.0

    print(f"  Production Mean (goose=4): ${mean_prod:>10,.2f}")
    print(f"  Opponent Mean (goose=0):   ${mean_opp:>10,.2f}")
    print(f"  Net Delta:                 ${mean_diff:>+10,.2f}  (SE: ${se:,.2f})")
    print(f"  t-stat / p-value:          t = {t_stat:>+.3f},  p = {p_val:.4e}")
    print(f"  W/L/T:                     {wins}W / {losses}L / {ties}T  (n={n})")
    print(f"  Win Rate (all):            {wr_all:.1f}%")
    print(f"  Win Rate (ex-ties):        {wr_notie:.1f}%")
    return {
        "mean_prod": mean_prod, "mean_opp": mean_opp, "delta": mean_diff,
        "se": se, "t": t_stat, "p": p_val, "W": wins, "L": losses, "T": ties,
        "wr_notie": wr_notie
    }


def run_honest_self_play(label: str, seeds: List[int]):
    print("\n" + "=" * 80)
    print(f"2. HONEST SELF-PLAY RE-BASELINE (NO SEED INJECTED): {label} ({len(seeds)} seeds)")
    print("=" * 80)

    p0_rewards = []
    p1_rewards = []
    avg_rewards = []

    for seed in seeds:
        # Default production instantiation: NO seed passed, exactly as Kaggle runner creates it
        agent0 = make_spatial_dispatcher_agent()
        agent1 = make_spatial_dispatcher_agent()

        r0, r1 = run_fast_match(agent0, agent1, seed)
        avg = (r0 + r1) / 2.0
        p0_rewards.append(r0)
        p1_rewards.append(r1)
        avg_rewards.append(avg)

        if len(seeds) <= 20:
            print(f"  Seed {seed:>5} | P0: ${r0:>10,.2f} | P1: ${r1:>10,.2f} | Match Avg: ${avg:>10,.2f}")

    all_rewards = p0_rewards + p1_rewards
    mean_player = float(np.mean(all_rewards))
    median_player = float(np.median(all_rewards))
    min_player = float(np.min(all_rewards))
    max_player = float(np.max(all_rewards))
    std_player = float(np.std(all_rewards, ddof=1))
    se_player = std_player / np.sqrt(len(all_rewards))

    print("-" * 80)
    print(f"  Player Mean:   ${mean_player:>10,.2f} (SE: ${se_player:,.2f})")
    print(f"  Player Median: ${median_player:>10,.2f}")
    print(f"  Player Min:    ${min_player:>10,.2f}")
    print(f"  Player Max:    ${max_player:>10,.2f}")
    print("=" * 80)
    return {
        "mean": mean_player, "median": median_player,
        "min": min_player, "max": max_player, "se": se_player
    }


def main():
    conf_res = run_confirmation_goose4_vs_dom_meta()
    sp_20 = run_honest_self_play("Official 20 Seeds", OFFICIAL_20_SEEDS)
    sp_100 = run_honest_self_play("100 Disjoint Seeds (10000..10099)", DISJOINT_100_SEEDS)

    print("\n" + "=" * 80)
    print("=== SUMMARY OF CONFIRMATION & RE-BASELINE ===")
    print("=" * 80)
    print(f"1. goose_cap=4 unsteered vs Dominant Meta (n=200):")
    print(f"   WR (ex-ties): {conf_res['wr_notie']:.1f}% ({conf_res['W']}W / {conf_res['L']}L / {conf_res['T']}T)")
    print(f"   Net Delta:    ${conf_res['delta']:>+10,.2f} (t = {conf_res['t']:>+.2f}, p = {conf_res['p']:.4e})")
    print(f"\n2. Honest Shippable Production Baseline (goose_cap=0, unsteered in competition):")
    print(f"   Official 20 Seeds:  ${sp_20['mean']:>10,.2f} (Median: ${sp_20['median']:>10,.2f})")
    print(f"   100 Disjoint Seeds: ${sp_100['mean']:>10,.2f} (Median: ${sp_100['median']:>10,.2f})")
    print("=" * 80)


if __name__ == "__main__":
    main()
