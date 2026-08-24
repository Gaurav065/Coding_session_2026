"""Asymmetric Head-to-Head Validation of Shared-Resource Features

Tests whether supply-restraint features (downward cow cap and curve-aware selling)
suffer from free-rider exploitation when playing against non-restraining opponents.

Features Tested:
1. Downward-only Cow Cap (cow_cap_low=6 vs non-restraining cow_cap_low=10)
2. Curve-Aware AMM Selling (Paced AMM vs Unpaced Dumping)
"""

import sys
import numpy as np
from scipy import stats
from typing import Dict, List, Tuple, Any

sys.path.insert(0, r"C:\Coding")

from project_maestro.engine.fast_engine import FastGame
from project_maestro.agent.dispatcher_agent import (
    MaestroFullPortfolioAgent, make_spatial_dispatcher_agent
)

OFFICIAL_20_SEEDS = [10, 20, 30, 42, 55, 77, 99, 100, 123, 200, 250, 300, 333, 404, 500, 600, 700, 777, 888, 999]
DISJOINT_100_SEEDS = list(range(10000, 10100))


class FlatSellDispatcherAgent(MaestroFullPortfolioAgent):
    """Dispatcher agent with flat unpaced selling (dumps all produce up to 20/turn)."""
    def __call__(self, obs: Dict[str, Any]) -> Dict[str, Any]:
        res = super().__call__(obs)
        market_orders = []
        for op in res.get("market", []):
            if op[0] != "SELL":
                market_orders.append(op)
        
        shed = obs["private"].get("shed", {})
        for prod in ["EGG", "MILK", "WOOL", "STRAWBERRY", "MELON", "FERTILIZER", "CARROT", "TOMATO"]:
            qty = shed.get(prod, 0)
            if qty > 0 and len(market_orders) < 10:
                market_orders.append(["SELL", prod, min(qty, 20)])
        
        wheat_qty = shed.get("WHEAT", 0)
        if wheat_qty > 10 and len(market_orders) < 10:
            market_orders.append(["SELL", "WHEAT", min(20, wheat_qty - 10)])
            
        res["market"] = market_orders[:10]
        return res


def run_h2h_match(p0, p1, seed: int) -> Tuple[float, float]:
    game = FastGame(seed=seed)
    while not game.done:
        act0 = p0(game.get_observation(0))
        act1 = p1(game.get_observation(1))
        game.step_game(act0, act1)
    return float(game.farms[0].money), float(game.farms[1].money)


def evaluate_feature(
    feature_name: str,
    candidate_factory,
    opponent_factory,
    seeds: List[int],
    seed_set_name: str
) -> Dict[str, Any]:
    print(f"\nEvaluating: {feature_name} on {seed_set_name} ({len(seeds)} seeds x 2 seats = {len(seeds)*2} matches)", flush=True)
    print("-" * 80, flush=True)

    cand_scores = []
    opp_scores = []
    diffs = []
    wins = 0
    ties = 0

    for seed in seeds:
        # Seat 0: Candidate is P0, Opponent is P1
        c0 = candidate_factory(seed)
        o1 = opponent_factory(seed)
        r_c0, r_o1 = run_h2h_match(c0, o1, seed)
        cand_scores.append(r_c0)
        opp_scores.append(r_o1)
        d0 = r_c0 - r_o1
        diffs.append(d0)
        if d0 > 0: wins += 1
        elif d0 == 0: ties += 1

        # Seat 1: Opponent is P0, Candidate is P1
        o0 = opponent_factory(seed)
        c1 = candidate_factory(seed)
        r_o0, r_c1 = run_h2h_match(o0, c1, seed)
        opp_scores.append(r_o0)
        cand_scores.append(r_c1)
        d1 = r_c1 - r_o0
        diffs.append(d1)
        if d1 > 0: wins += 1
        elif d1 == 0: ties += 1

    total_matches = len(seeds) * 2
    losses = total_matches - wins - ties
    win_rate = (wins / total_matches) * 100.0
    mean_cand = float(np.mean(cand_scores))
    mean_opp = float(np.mean(opp_scores))
    mean_diff = float(np.mean(diffs))
    se_diff = float(np.std(diffs, ddof=1) / np.sqrt(total_matches))
    t_stat = mean_diff / se_diff if se_diff > 0 else 0.0
    p_val = 2 * (1 - stats.t.cdf(abs(t_stat), df=total_matches - 1)) if se_diff > 0 else 1.0

    print(f"  Candidate Mean (Restrained):     ${mean_cand:>10,.2f}", flush=True)
    print(f"  Opponent Mean (Non-Restrained):  ${mean_opp:>10,.2f}", flush=True)
    print(f"  Net Delta (Candidate - Opponent): ${mean_diff:>+10,.2f} (SE: ${se_diff:,.2f}, t = {t_stat:>+.2f}, p = {p_val:.4e})", flush=True)
    print(f"  Head-to-Head: {wins}W / {losses}L / {ties}T (Win Rate: {win_rate:.1f}%)", flush=True)

    return {
        "feature": feature_name,
        "seed_set": seed_set_name,
        "mean_cand": mean_cand,
        "mean_opp": mean_opp,
        "delta": mean_diff,
        "se": se_diff,
        "t_stat": t_stat,
        "p_val": p_val,
        "win_rate": win_rate,
        "wins": wins,
        "losses": losses,
        "ties": ties,
    }


def main():
    print("=" * 95, flush=True)
    print("=== ASYMMETRIC HEAD-TO-HEAD VALIDATION OF SHARED-RESOURCE FEATURES ===", flush=True)
    print("=" * 95, flush=True)

    results = []

    # 1. Downward-only Cow Cap vs Fixed 10-Cow Non-Restraining Opponent
    for seeds, name in [(OFFICIAL_20_SEEDS, "Official 20 Seeds"), (DISJOINT_100_SEEDS, "100 Disjoint Seeds")]:
        res = evaluate_feature(
            "Downward Cow Cap (cap_low=6 vs fixed 10-cow)",
            lambda s: make_spatial_dispatcher_agent(params={"cow_cap_low": 6, "cow_cap_base": 10}, seed=s),
            lambda s: make_spatial_dispatcher_agent(params={"cow_cap_low": 10, "cow_cap_base": 10}, seed=s),
            seeds,
            name
        )
        results.append(res)

    # 2. Curve-Aware AMM Selling vs Flat Unpaced Dumping
    for seeds, name in [(OFFICIAL_20_SEEDS, "Official 20 Seeds"), (DISJOINT_100_SEEDS, "100 Disjoint Seeds")]:
        res = evaluate_feature(
            "Curve-Aware Paced Selling vs Flat Dumping",
            lambda s: make_spatial_dispatcher_agent(seed=s),
            lambda s: FlatSellDispatcherAgent(seed=s),
            seeds,
            name
        )
        results.append(res)

    print("\n" + "=" * 95, flush=True)
    print("=== SUMMARY OF SHARED-RESOURCE ASYMMETRIC EVALUATIONS ===", flush=True)
    print("=" * 95, flush=True)
    header = f"{'Feature':<45} | {'Seed Set':<18} | {'Cand Mean':<12} | {'Opp Mean':<12} | {'Net Margin':<12} | {'W/L/T':<12} | {'Win Rate':<8}"
    print(header, flush=True)
    print("-" * len(header), flush=True)
    for r in results:
        wlt = f"{r['wins']}/{r['losses']}/{r['ties']}"
        print(
            f"{r['feature']:<45} | "
            f"{r['seed_set']:<18} | "
            f"${r['mean_cand']:>10,.2f} | "
            f"${r['mean_opp']:>10,.2f} | "
            f"${r['delta']:>+10,.2f} | "
            f"{wlt:<12} | "
            f"{r['win_rate']:>6.1f}%",
            flush=True
        )
    print("=" * 95, flush=True)


if __name__ == "__main__":
    main()
