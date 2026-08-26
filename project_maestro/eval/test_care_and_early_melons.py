"""Test: Integrating Daily CARE and Day 1 Early Melons

Tests if adding persistent animal CARE and Day 1 early melon plantings
elevates IDCMasterAgent score from $79k to $120k+.
"""

import sys
import json
import numpy as np

sys.path.insert(0, r'C:/Coding')
from project_maestro.engine.fast_engine import FastGame
from project_maestro.agent.dispatcher_agent import MaestroFullPortfolioAgent

def test_care_impact(seeds=[101, 102, 103, 104, 105]):
    print('Testing Impact of Daily Animal CARE and Early Melons across 5 Seeds...\n')

    # Baseline without persistent care
    scores_base = []
    # Enhanced with persistent care & early melons
    scores_enhanced = []

    for s in seeds:
        # 1. Baseline
        g1 = FastGame(seed=s)
        a1 = MaestroFullPortfolioAgent(seed=s)
        passive = {"farmer": ["PASS"], "hands": [], "market": []}
        while not g1.done:
            g1.step_game(a1(g1.get_observation(0)), passive)
        scores_base.append(g1.farms[0].money)

        # 2. Enhanced Agent with Care + Early Melons
        g2 = FastGame(seed=s)
        a2 = MaestroFullPortfolioAgent(params={
            "cow_cap_base": 8, "sheep_cap": 6, "strawberry_target": 18, "melon_seed_target": 8,
            "crew_mid": 10, "crew_late": 11, "enable_3b": True
        }, seed=s)
        while not g2.done:
            g2.step_game(a2(g2.get_observation(0)), passive)
        scores_enhanced.append(g2.farms[0].money)

    print('=' * 75)
    print('SCORE COMPARISON: BASELINE VS ENHANCED CARE AGENT')
    print('=' * 75)
    for i, s in enumerate(seeds):
        print(f'Seed {s}: Baseline: ${scores_base[i]:9.2f} | Enhanced: ${scores_enhanced[i]:9.2f} (Delta: +${scores_enhanced[i] - scores_base[i]:7.2f})')
    print('-' * 75)
    print(f'Mean Baseline : ${np.mean(scores_base):10,.2f}')
    print(f'Mean Enhanced : ${np.mean(scores_enhanced):10,.2f}')
    print('=' * 75)

if __name__ == '__main__':
    test_care_impact()
