"""Test Lean Matching Strategy against Dominant Dairy Meta

Tests setting strawberry_target: 18, melon_seed_target: 6, crew: 9-10
to guarantee equal Day 1 liquid cash for all 10 Cow pastures.
"""

import sys
import numpy as np

sys.path.insert(0, r'C:/Coding')
from project_maestro.engine.fast_engine import FastGame
from project_maestro.agent.dispatcher_agent import MaestroFullPortfolioAgent

def test_lean_match(seeds=list(range(700, 750))):
    print(f'Testing Lean Matching Strategy vs Dominant Dairy Meta across N={len(seeds)} Seeds...\n')

    wins = 0
    scores_our = []
    scores_opp = []

    for s in seeds:
        g = FastGame(seed=s)
        # Lean Agent with identical Day 1 liquidity
        agent = MaestroFullPortfolioAgent(params={
            "cow_cap_base": 10, "sheep_cap": 4, "strawberry_target": 18, "melon_seed_target": 6,
            "crew_mid": 9, "crew_late": 10, "enable_3b": True, "feed_protection": True
        }, seed=s)

        opp = MaestroFullPortfolioAgent(params={
            "cow_cap_base": 10, "sheep_cap": 4, "strawberry_target": 18, "melon_seed_target": 6, "enable_3b": False
        }, seed=s)

        while not g.done:
            obs = g.get_observation(0)
            act = agent(obs)
            if obs["day"] >= 28:
                shed = obs["private"]["shed"]
                orders = []
                for item in ["MILK", "WOOL", "STRAWBERRY", "MELON", "TOMATO", "CARROT", "WHEAT", "FERTILIZER"]:
                    qty = shed.get(item, 0)
                    if qty > 0 and len(orders) < 10:
                        orders.append(["SELL", item, min(qty, 10)])
                if orders:
                    act["market"] = orders[:10]
            g.step_game(act, opp(g.get_observation(1)))

        s0 = g.farms[0].money
        s1 = g.farms[1].money
        scores_our.append(s0)
        scores_opp.append(s1)
        if s0 > s1:
            wins += 1

    wr = (wins / len(seeds)) * 100

    print('=' * 85)
    print('LEAN MATCHING STRATEGY VS DOMINANT DAIRY META')
    print('=' * 85)
    print(f'Win Rate vs Dominant Dairy Meta : {wr:5.1f}% ({wins}/{len(seeds)} Wins)')
    print(f'Our Mean Score                  : ${np.mean(scores_our):8,.2f}')
    print(f'Opponent Mean Score             : ${np.mean(scores_opp):8,.2f}')
    print(f'Net Margin                      : +${np.mean(scores_our) - np.mean(scores_opp):8,.2f}')
    print('=' * 85)

if __name__ == '__main__':
    test_lean_match()
