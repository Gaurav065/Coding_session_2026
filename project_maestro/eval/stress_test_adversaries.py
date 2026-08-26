"""Stress-Test Suite: 4 Extreme Opponent Archetypes & Dynamic Counter Engine

Tests:
1. Adversary 1: All-In Cows + Melons (14 Cows, 24 Melons).
2. Adversary 2: All-In Sheep + Strawberries (14 Sheep, 30 Strawberries).
3. Adversary 3: Tomato Meta Spam (35 Tomatoes, high daily labor).
4. Adversary 4: Hyper-Hiring Over-Expansion (16 hands/day, 4-quadrant spam).
"""

import sys
import json
import time
import numpy as np
from collections import defaultdict
from typing import Dict, List, Any

sys.path.insert(0, r'C:/Coding')
from project_maestro.engine.fast_engine import FastGame
from project_maestro.agent.idc_master_agent import IDCMasterAgent
from project_maestro.agent.dispatcher_agent import MaestroFullPortfolioAgent

# Adversary 1: All-in Cows & Melons
def make_cows_melons_adversary(seed):
    return MaestroFullPortfolioAgent(params={
        "cow_cap_base": 14, "sheep_cap": 0, "strawberry_target": 6, "melon_seed_target": 20, "crew_mid": 11, "crew_late": 13
    }, seed=seed)

# Adversary 2: All-in Sheep & Strawberries
def make_sheep_strawberries_adversary(seed):
    return MaestroFullPortfolioAgent(params={
        "cow_cap_base": 0, "sheep_cap": 14, "strawberry_target": 28, "melon_seed_target": 0, "crew_mid": 11, "crew_late": 13
    }, seed=seed)

# Adversary 3: Tomato Meta
def make_tomato_meta_adversary(seed):
    return MaestroFullPortfolioAgent(params={
        "cow_cap_base": 6, "sheep_cap": 4, "strawberry_target": 0, "melon_seed_target": 0, "crew_mid": 12, "crew_late": 14
    }, seed=seed)

# Adversary 4: Hyper-Hiring Overexpansion (Spends $2k+/day on labor)
def make_hyper_hiring_adversary(seed):
    return MaestroFullPortfolioAgent(params={
        "cow_cap_base": 10, "sheep_cap": 4, "strawberry_target": 25, "melon_seed_target": 15, "crew_mid": 16, "crew_late": 16
    }, seed=seed)

def run_stress_test_benchmarks(num_seeds: int = 50):
    print(f'Starting Stress-Test Suite against 4 Extreme Opponent Archetypes across N={num_seeds} Seeds...\n')

    adversaries = [
        ("1. All-In Cows + Melons (14C / 20M)", make_cows_melons_adversary),
        ("2. All-In Sheep + Strawberries (14S / 28Str)", make_sheep_strawberries_adversary),
        ("3. Tomato Meta Spam", make_tomato_meta_adversary),
        ("4. Hyper-Hiring Overexpansion (16 Hands)", make_hyper_hiring_adversary),
    ]

    all_results = []

    for name, make_adv in adversaries:
        print(f'Evaluating N={num_seeds} matches vs {name}...')
        t0 = time.time()
        wins = 0
        our_scores = []
        adv_scores = []

        for s in range(400, 400 + num_seeds):
            g = FastGame(seed=s)
            agent = IDCMasterAgent(seed=s)
            adv = make_adv(s)

            while not g.done:
                g.step_game(agent(g.get_observation(0)), adv(g.get_observation(1)))

            s0 = g.farms[0].money
            s1 = g.farms[1].money
            our_scores.append(s0)
            adv_scores.append(s1)
            if s0 > s1:
                wins += 1

        wr = (wins / num_seeds) * 100
        mean_our = float(np.mean(our_scores))
        mean_adv = float(np.mean(adv_scores))
        margin = mean_our - mean_adv
        p5_our = float(np.percentile(our_scores, 5))
        elapsed = time.time() - t0

        print(f'  Win Rate: {wr:5.1f}% ({wins}/{num_seeds} Wins) | Margin: +${margin:7.0f} | Our Mean: ${mean_our:7.0f} vs Adv: ${mean_adv:7.0f} | p5: ${p5_our:6.0f} ({elapsed:.1f}s)\n')

        all_results.append({
            "adversary": name,
            "win_rate": wr,
            "our_mean": round(mean_our, 2),
            "adv_mean": round(mean_adv, 2),
            "margin": round(margin, 2),
            "p5_floor": round(p5_our, 2)
        })

    print('=' * 110)
    print('STRESS-TEST BENCHMARK SCORECARD ACROSS 4 EXTREME ARCHETYPES')
    print('=' * 110)
    print(f'{"Adversary Strategy Archetype":<42} | {"Win Rate":<8} | {"Our Mean":<11} | {"Opp Mean":<11} | {"Margin":<11} | {"p5 Floor":<10}')
    print('-' * 110)
    for r in all_results:
        print(f'{r["adversary"]:<42} | {r["win_rate"]:6.1f}%  | ${r["our_mean"]:9.0f} | ${r["adv_mean"]:9.0f} | +${r["margin"]:9.0f} | ${r["p5_floor"]:8.0f}')
    print('=' * 110)

    out_file = 'project_maestro/data/extreme_adversaries_stress_test_report.json'
    with open(out_file, 'w', encoding='utf-8') as f:
        json.dump(all_results, f, indent=2)
    print(f'Report saved to {out_file}')

if __name__ == '__main__':
    run_stress_test_benchmarks(50)
