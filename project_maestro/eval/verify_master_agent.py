"""Comprehensive Tournament Benchmark for MasterCounterAgent - Project Maestro

Evaluates MasterCounterAgent against real-world Kaggle Grandmaster and Meta Archetypes:
1. Dominant Dairy Meta (10C / 4S / 18 Straw)
2. Balanced Pasture Hybrid (7C / 7S / 20 Straw)
3. Meta Calibrated (8C / 6S / 18 Straw)
4. Self-Play Mirror Match
"""

import sys
import json
import time
import numpy as np
from typing import Dict, List, Any

sys.path.insert(0, r'C:/Coding')
from project_maestro.engine.fast_engine import FastGame
from project_maestro.agent.master_counter_agent import MasterCounterAgent
from project_maestro.agent.dispatcher_agent import MaestroFullPortfolioAgent
from project_maestro.agent.meta_calibrated_opponent import make_meta_calibrated_opponent

def run_tournament_benchmarks(num_seeds: int = 100):
    test_seeds = list(range(30000, 30000 + num_seeds))
    print(f'Starting Comprehensive Tournament Benchmark on N={num_seeds} seeds...\n')

    opponents = [
        ('Dominant_Dairy_Meta (10C/4S)', lambda s: MaestroFullPortfolioAgent(params={'cow_cap_base': 10, 'sheep_cap': 4, 'strawberry_target': 18, 'melon_seed_target': 6, 'enable_3b': False}, seed=s)),
        ('Balanced_Pasture_Hybrid (7C/7S)', lambda s: MaestroFullPortfolioAgent(params={'cow_cap_base': 7, 'sheep_cap': 7, 'strawberry_target': 20, 'melon_seed_target': 4, 'enable_3b': False}, seed=s)),
        ('Meta_Calibrated_Opponent (8C/6S)', lambda s: make_meta_calibrated_opponent(seed=s)),
        ('Self_Play_Mirror', lambda s: MasterCounterAgent(seed=s))
    ]

    results_table = []

    for opp_name, opp_factory in opponents:
        print(f'Running N={num_seeds} games vs {opp_name}...')
        cand_scores = []
        opp_scores = []
        wins = 0
        ties = 0

        t0 = time.time()
        for s in test_seeds:
            g = FastGame(seed=s)
            a0 = MasterCounterAgent(seed=s)
            a1 = opp_factory(s)

            while not g.done:
                g.step_game(a0(g.get_observation(0)), a1(g.get_observation(1)))

            sc0 = g.farms[0].money
            sc1 = g.farms[1].money

            cand_scores.append(sc0)
            opp_scores.append(sc1)

            if sc0 > sc1:
                wins += 1
            elif sc0 == sc1:
                ties += 1

        elapsed = time.time() - t0
        wr = (wins + 0.5 * ties) / num_seeds * 100
        mean0 = float(np.mean(cand_scores))
        mean1 = float(np.mean(opp_scores))
        margin = mean0 - mean1
        p5 = float(np.percentile(cand_scores, 5))
        med = float(np.median(cand_scores))
        min_sc = float(np.min(cand_scores))
        max_sc = float(np.max(cand_scores))

        # Check Canaries
        canary1 = mean0 > 25000  # Non-trivial agent
        canary6 = mean1 > 20000 or 'Self' in opp_name  # Active opponent

        results_table.append({
            'opponent': opp_name,
            'win_rate': round(wr, 1),
            'cand_mean': round(mean0, 2),
            'opp_mean': round(mean1, 2),
            'margin': round(margin, 2),
            'cand_p5': round(p5, 2),
            'cand_median': round(med, 2),
            'min': round(min_sc, 2),
            'max': round(max_sc, 2),
            'canary_pass': canary1 and canary6,
            'elapsed_sec': round(elapsed, 2)
        })

        print(f'  Win Rate: {wr:5.1f}% | Margin: +${margin:7.0f} | Cand Mean: ${mean0:7.0f} vs Opp: ${mean1:7.0f} | p5: ${p5:7.0f} ({elapsed:.1f}s)\n')

    print('=' * 115)
    print(f'{"Opponent Archetype":<35} | {"Win Rate":<8} | {"Our Mean":<11} | {"Opp Mean":<11} | {"Margin":<11} | {"p5 Floor":<10} | {"Canaries"}')
    print('-' * 115)
    for r in results_table:
        can_str = "PASS" if r['canary_pass'] else "FAIL"
        print(f"{r['opponent']:<35} | {r['win_rate']:6.1f}%  | ${r['cand_mean']:9.0f} | ${r['opp_mean']:9.0f} | +${r['margin']:9.0f} | ${r['cand_p5']:8.0f} | {can_str}")
    print('=' * 115)

    out_file = 'project_maestro/data/master_agent_benchmark_results.json'
    with open(out_file, 'w', encoding='utf-8') as f:
        json.dump({'seeds': num_seeds, 'results': results_table}, f, indent=2)
    print(f'\nDetailed benchmark saved to {out_file}')

if __name__ == '__main__':
    run_tournament_benchmarks(100)
