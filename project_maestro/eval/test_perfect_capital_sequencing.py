"""Test: Perfect Capital Sequencing & Early Livestock Blitz

Tests if prioritizing 100% of Day 0-3 capital on instant 9C/4S livestock ramp
recovers the -$12,000 Milk / -$6,000 Wool deficit and elevates Win Rate to 95%+.
"""

import sys
import numpy as np

sys.path.insert(0, r'C:/Coding')
from project_maestro.engine.fast_engine import FastGame
from project_maestro.agent.dispatcher_agent import MaestroFullPortfolioAgent

def test_capital_sequencing(seeds=list(range(600, 640))):
    print(f'Testing Perfect Capital Sequencing against Dominant Dairy Meta across N={len(seeds)} Seeds...\n')

    # Baseline IDCMasterAgent
    wins_base = 0
    scores_base = []
    opp_scores_base = []

    # Perfect Capital Sequencing Agent
    wins_seq = 0
    scores_seq = []
    opp_scores_seq = []

    for s in seeds:
        opp = MaestroFullPortfolioAgent(params={
            "cow_cap_base": 10, "sheep_cap": 4, "strawberry_target": 18, "melon_seed_target": 6, "enable_3b": False
        }, seed=s)

        # 1. Baseline
        g1 = FastGame(seed=s)
        a1 = MaestroFullPortfolioAgent(params={
            "cow_cap_base": 9, "sheep_cap": 4, "strawberry_target": 22, "melon_seed_target": 12, "crew_mid": 10, "crew_late": 12
        }, seed=s)
        while not g1.done:
            g1.step_game(a1(g1.get_observation(0)), opp(g1.get_observation(1)))
        s0_1 = g1.farms[0].money
        s1_1 = g1.farms[1].money
        scores_base.append(s0_1)
        opp_scores_base.append(s1_1)
        if s0_1 > s1_1:
            wins_base += 1

        # 2. Perfect Capital Sequencing Agent (Livestock First, NE Day 5, SW Day 8)
        g2 = FastGame(seed=s)
        a2 = MaestroFullPortfolioAgent(params={
            "cow_cap_base": 9, "sheep_cap": 4, "strawberry_target": 18, "melon_seed_target": 8, "crew_mid": 9, "crew_late": 10,
            "enable_3b": True, "feed_protection": True
        }, seed=s)
        while not g2.done:
            g2.step_game(a2(g2.get_observation(0)), opp(g2.get_observation(1)))
        s0_2 = g2.farms[0].money
        s1_2 = g2.farms[1].money
        scores_seq.append(s0_2)
        opp_scores_seq.append(s1_2)
        if s0_2 > s1_2:
            wins_seq += 1

    wr_base = (wins_base / len(seeds)) * 100
    wr_seq = (wins_seq / len(seeds)) * 100

    print('=' * 85)
    print('CAPITAL SEQUENCING IMPACT: BASELINE VS PERFECT SEQUENCING AGENT')
    print('=' * 85)
    print(f'Baseline Win Rate vs Dominant Dairy Meta : {wr_base:5.1f}% ({wins_base}/{len(seeds)} Wins) | Mean: ${np.mean(scores_base):8,.2f}')
    print(f'Perfect Sequencing Win Rate             : {wr_seq:5.1f}% ({wins_seq}/{len(seeds)} Wins) | Mean: ${np.mean(scores_seq):8,.2f}')
    print(f'Net Score Increase                      : +${np.mean(scores_seq) - np.mean(scores_base):8,.2f}')
    print('=' * 85)

if __name__ == '__main__':
    test_capital_sequencing()
