"""Per-Archetype Evaluation Harness - Project Maestro

Systematically evaluates the Production Dispatcher Agent (with integrated value-gated steering)
against representative meta and baseline archetypes across both seats (Seat 0 & Seat 1)
on the Official 20 Seeds.

Opponent Archetypes Evaluated:
1. Standing Production Baseline (Unsteered MaestroFullPortfolioAgent mirror)
2. Dominant Meta (10C / 4S / 0G) - 37.8% share of top meta trajectories
3. Wool-Heavy Meta (6C / 12S / 0G) - 13.0% share of top meta trajectories
4. Balanced Pasture Meta (6C / 8S / 0G) - 5.2% share of top meta trajectories
5. Built-in "starter" baseline (Deterministic benchmark)
6. Built-in "random" baseline
7. Built-in "pass" baseline
"""

import sys
import numpy as np
from scipy import stats
from typing import Dict, List, Tuple, Any, Callable
from kaggle_environments import make

sys.path.insert(0, r"C:\Coding")

from project_maestro.agent.dispatcher_agent import (
    MaestroFullPortfolioAgent, make_spatial_dispatcher_agent
)
from project_maestro.agent.parameterized_agent import make_agent

OFFICIAL_20_SEEDS = [10, 20, 30, 42, 55, 77, 99, 100, 123, 200, 250, 300, 333, 404, 500, 600, 700, 777, 888, 999]


def get_archetype_factories() -> Dict[str, Callable[[int], Any]]:
    """Return factory functions creating opponent instances for a given seed."""
    return {
        "Standing Baseline (Unsteered)": lambda s: make_spatial_dispatcher_agent(kw_early=10),
        "Dominant Meta (10C/4S/0G)": lambda s: make_spatial_dispatcher_agent(
            params={"cow_cap_base": 10, "sheep_cap": 4, "goose_cap": 0}, kw_early=10
        ),
        "Wool-Heavy (6C/12S/0G)": lambda s: make_spatial_dispatcher_agent(
            params={"cow_cap_base": 6, "sheep_cap": 12, "goose_cap": 0}, kw_early=10
        ),
        "Balanced Pasture (6C/8S/0G)": lambda s: make_spatial_dispatcher_agent(
            params={"cow_cap_base": 6, "sheep_cap": 8, "goose_cap": 0}, kw_early=10
        ),
        "Starter Baseline": lambda s: "starter",
        "Random Baseline": lambda s: "random",
        "Pass Baseline": lambda s: "pass",
    }


from project_maestro.engine.fast_engine import FastGame

def run_match(agent_0, agent_1, seed: int) -> Tuple[float, float]:
    """Run a match using FastGame if both are callables, or kaggle_environments otherwise."""
    if callable(agent_0) and callable(agent_1):
        game = FastGame(seed=seed)
        while not game.done:
            act0 = agent_0(game.get_observation(0))
            act1 = agent_1(game.get_observation(1))
            game.step_game(act0, act1)
        return float(game.farms[0].money), float(game.farms[1].money)
    else:
        env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": seed}, debug=False)
        env.run([agent_0, agent_1])
        s = env.steps[-1]
        return float(s[0].reward), float(s[1].reward)


def evaluate_archetype(
    arch_name: str,
    arch_factory: Callable[[int], Any],
    seeds: List[int] = OFFICIAL_20_SEEDS
) -> Dict[str, Any]:
    print(f"\nEvaluating vs Archetype: {arch_name} (20 seeds x 2 seats = 40 matches)")
    print("-" * 80)

    prod_rewards_s0 = []
    opp_rewards_s1 = []
    wins_s0 = 0

    prod_rewards_s1 = []
    opp_rewards_s0 = []
    wins_s1 = 0

    diffs_all = []

    for idx, seed in enumerate(seeds):
        # Seat 0: Production Agent is Player 0, Opponent is Player 1
        p0 = make_spatial_dispatcher_agent(seed=seed)
        p1 = arch_factory(seed)
        r0, r1 = run_match(p0, p1, seed)
        prod_rewards_s0.append(r0)
        opp_rewards_s1.append(r1)
        diff_s0 = r0 - r1
        diffs_all.append(diff_s0)
        if diff_s0 > 0:
            wins_s0 += 1

        # Seat 1: Opponent is Player 0, Production Agent is Player 1
        opp0 = arch_factory(seed)
        prod1 = make_spatial_dispatcher_agent(seed=seed)
        r_opp0, r_prod1 = run_match(opp0, prod1, seed)
        opp_rewards_s0.append(r_opp0)
        prod_rewards_s1.append(r_prod1)
        diff_s1 = r_prod1 - r_opp0
        diffs_all.append(diff_s1)
        if diff_s1 > 0:
            wins_s1 += 1

    total_matches = len(seeds) * 2
    total_wins = wins_s0 + wins_s1
    win_rate = (total_wins / total_matches) * 100.0

    prod_all = prod_rewards_s0 + prod_rewards_s1
    opp_all = opp_rewards_s1 + opp_rewards_s0

    mean_prod = float(np.mean(prod_all))
    mean_opp = float(np.mean(opp_all))
    mean_diff = float(np.mean(diffs_all))
    std_diff = float(np.std(diffs_all, ddof=1))
    se_diff = std_diff / np.sqrt(total_matches)
    t_stat = mean_diff / se_diff if se_diff > 0 else 0.0
    p_val = 2 * (1 - stats.t.cdf(abs(t_stat), df=total_matches - 1)) if se_diff > 0 else 1.0

    print(f"  Production Mean: ${mean_prod:>10,.2f}")
    print(f"  Opponent Mean:   ${mean_opp:>10,.2f}")
    print(f"  Net Delta:       ${mean_diff:>+10,.2f} (SE: ${se_diff:,.2f}, t = {t_stat:>+.2f}, p = {p_val:.4e})")
    print(f"  Win Rate:        {win_rate:>5.1f}% ({total_wins}/{total_matches} matches won)")

    return {
        "archetype": arch_name,
        "prod_mean": mean_prod,
        "opp_mean": mean_opp,
        "delta": mean_diff,
        "se": se_diff,
        "t_stat": t_stat,
        "p_val": p_val,
        "win_rate": win_rate,
        "total_wins": total_wins,
        "total_matches": total_matches,
    }


def main():
    print("=" * 95)
    print("=== PER-ARCHETYPE EVALUATION HARNESS - PRODUCTION DISPATCHER AGENT ===")
    print("=" * 95)

    factories = get_archetype_factories()
    results = []

    for name, factory in factories.items():
        res = evaluate_archetype(name, factory, OFFICIAL_20_SEEDS)
        results.append(res)

    print("\n" + "=" * 95)
    print("=== SUMMARY OF PER-ARCHETYPE HEAD-TO-HEAD EVALUATION ===")
    print("=" * 95)
    header = f"{'Archetype':<32} | {'Prod Mean':<12} | {'Opp Mean':<12} | {'Net Margin':<14} | {'Win Rate':<10} | {'t-stat':<8}"
    print(header)
    print("-" * len(header))
    for r in results:
        print(
            f"{r['archetype']:<32} | "
            f"${r['prod_mean']:>10,.2f} | "
            f"${r['opp_mean']:>10,.2f} | "
            f"${r['delta']:>+12,.2f} | "
            f"{r['win_rate']:>8.1f}% | "
            f"{r['t_stat']:>+7.2f}"
        )
    print("=" * 95)


if __name__ == "__main__":
    main()
