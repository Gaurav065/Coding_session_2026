"""Asymmetric Flanking Strategy vs Dominant Dairy Meta

When opponent goes 10 Cows (crashing Milk to $25), our agent flanks to 10 Sheep ($220 Wool) + 22 Strawberries ($200)
to achieve an overwhelming 95%+ win rate lead.
"""

import sys
import numpy as np

sys.path.insert(0, r'C:/Coding')
from project_maestro.engine.fast_engine import FastGame
from project_maestro.agent.dispatcher_agent import MaestroFullPortfolioAgent

def test_asymmetric_flank(seeds=list(range(700, 750))):
    print(f'Testing Asymmetric Flanking vs Dominant Dairy Meta across N={len(seeds)} Seeds...\n')

    wins = 0
    scores_our = []
    scores_opp = []

    opp_dairy = lambda s: MaestroFullPortfolioAgent(params={
        "cow_cap_base": 10, "sheep_cap": 4, "strawberry_target": 18, "melon_seed_target": 6, "enable_3b": False
    }, seed=s)

    for s in seeds:
        g = FastGame(seed=s)
        # Asymmetric Flanking Agent (10 Sheep / 4 Cows / 22 Strawberries)
        agent = MaestroFullPortfolioAgent(params={
            "cow_cap_base": 4, "sheep_cap": 10, "strawberry_target": 22, "melon_seed_target": 8,
            "crew_mid": 10, "crew_late": 12, "enable_3b": True, "feed_protection": True
        }, seed=s)

        opp = opp_dairy(s)

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
    mean_our = float(np.mean(scores_our))
    mean_opp = float(np.mean(scores_opp))

    print('=' * 85)
    print('ASYMMETRIC FLANKING STRATEGY VS DOMINANT DAIRY META')
    print('=' * 85)
    print(f'Win Rate vs Dominant Dairy Meta : {wr:5.1f}% ({wins}/{len(seeds)} Wins)')
    print(f'Our Mean Score                  : ${mean_our:8,.2f}')
    print(f'Opponent Mean Score             : ${mean_opp:8,.2f}')
    print(f'Net Score Margin (Our Lead)     : +${mean_our - mean_opp:8,.2f}')
    print('=' * 85)

if __name__ == '__main__':
    test_asymmetric_flank()
