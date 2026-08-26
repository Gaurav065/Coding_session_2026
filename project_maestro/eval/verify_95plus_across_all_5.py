"""Grandmaster 95%+ Benchmark Suite across ALL 5 Opponent Strategies

Tests the upgraded IDCMasterAgent with:
1. Dynamic Crash Hold Policy (holds produce when price < 0.40 * base, releasing on shop drain).
2. Strawberry Fertilizer Doubler (doubles Strawberry yield during peak harvest).
3. Synchronized Post-Drain Sales (Batch Cap 4).
4. Dynamic Flanking against all 5 adversary strategies (N=50 seeds each = 250 matches).
"""

import sys
import json
import time
import numpy as np
from collections import defaultdict

sys.path.insert(0, r'C:/Coding')
from project_maestro.engine.fast_engine import FastGame
from project_maestro.agent.dispatcher_agent import MaestroFullPortfolioAgent

STRATEGIES = {
    "1. Dominant Dairy Meta (10C/4S)": lambda s: MaestroFullPortfolioAgent(params={
        "cow_cap_base": 10, "sheep_cap": 4, "strawberry_target": 18, "melon_seed_target": 6, "enable_3b": False
    }, seed=s),
    "2. Balanced Pasture Hybrid (7C/7S)": lambda s: MaestroFullPortfolioAgent(params={
        "cow_cap_base": 7, "sheep_cap": 7, "strawberry_target": 18, "melon_seed_target": 6, "enable_3b": False
    }, seed=s),
    "3. All-In Sheep & Strawberries (14S/28Str)": lambda s: MaestroFullPortfolioAgent(params={
        "cow_cap_base": 0, "sheep_cap": 14, "strawberry_target": 28, "melon_seed_target": 0, "crew_mid": 11, "crew_late": 13
    }, seed=s),
    "4. All-In Cows & Melons (14C/20M)": lambda s: MaestroFullPortfolioAgent(params={
        "cow_cap_base": 14, "sheep_cap": 0, "strawberry_target": 6, "melon_seed_target": 20, "crew_mid": 11, "crew_late": 13
    }, seed=s),
    "5. Tomato Meta Spam": lambda s: MaestroFullPortfolioAgent(params={
        "cow_cap_base": 6, "sheep_cap": 4, "strawberry_target": 0, "melon_seed_target": 0, "crew_mid": 12, "crew_late": 14
    }, seed=s),
}

def run_95plus_benchmark(num_seeds: int = 50):
    print(f'Starting Full 95%+ Benchmark across ALL 5 Strategies (N={num_seeds} Seeds each, 250 Matches Total)...\n')

    all_results = []

    for name, make_opp in STRATEGIES.items():
        print(f'Evaluating N={num_seeds} games vs {name}...')
        t0 = time.time()
        wins = 0
        our_scores = []
        opp_scores = []

        for s in range(500, 500 + num_seeds):
            g = FastGame(seed=s)
            # Upgraded Grandmaster Agent
            agent = MaestroFullPortfolioAgent(params={
                "cow_cap_base": 9, "sheep_cap": 4, "strawberry_target": 22, "melon_seed_target": 10,
                "crew_mid": 10, "crew_late": 12, "enable_3b": True, "feed_protection": True
            }, seed=s)
            opp = make_opp(s)

            while not g.done:
                g.step_game(agent(g.get_observation(0)), opp(g.get_observation(1)))

            s0 = g.farms[0].money
            s1 = g.farms[1].money
            our_scores.append(s0)
            opp_scores.append(s1)
            if s0 > s1:
                wins += 1

        wr = (wins / num_seeds) * 100
        mean_our = float(np.mean(our_scores))
        mean_opp = float(np.mean(opp_scores))
        margin = mean_our - mean_opp
        p5_our = float(np.percentile(our_scores, 5))
        elapsed = time.time() - t0

        print(f'  Win Rate: {wr:5.1f}% ({wins}/{num_seeds} Wins) | Margin: +${margin:7.0f} | Our Mean: ${mean_our:7.0f} vs Opp: ${mean_opp:7.0f} | p5: ${p5_our:6.0f} ({elapsed:.1f}s)\n')

        all_results.append({
            "opponent": name,
            "win_rate": wr,
            "our_mean": round(mean_our, 2),
            "opp_mean": round(mean_opp, 2),
            "margin": round(margin, 2),
            "p5_floor": round(p5_our, 2)
        })

    print('=' * 115)
    print('GRANDMASTER 95%+ SCORECARD ACROSS ALL 5 STRATEGIES')
    print('=' * 115)
    print(f'{"Opponent Strategy Archetype":<42} | {"Win Rate":<8} | {"Our Mean":<11} | {"Opp Mean":<11} | {"Margin":<11} | {"p5 Floor":<10}')
    print('-' * 115)
    for r in all_results:
        print(f'{r["opponent"]:<42} | {r["win_rate"]:6.1f}%  | ${r["our_mean"]:9.0f} | ${r["opp_mean"]:9.0f} | +${r["margin"]:9.0f} | ${r["p5_floor"]:8.0f}')
    print('=' * 115)

    out_file = 'project_maestro/data/benchmark_95plus_across_all_5_results.json'
    with open(out_file, 'w', encoding='utf-8') as f:
        json.dump(all_results, f, indent=2)
    print(f'Report saved to {out_file}')

if __name__ == '__main__':
    run_95plus_benchmark(50)
