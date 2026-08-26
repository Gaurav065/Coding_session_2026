"""Test Mirror Domination: Instant Morning Front-Running & Melon Fertilization

Tests if selling harvested milk/wool immediately on morning hour (hour 1-3)
and fertilizing melons on Day 6-8 breaks the mirror tie and gives an overwhelming lead.
"""

import sys
import numpy as np

sys.path.insert(0, r'C:/Coding')
from project_maestro.engine.fast_engine import FastGame
from project_maestro.agent.dispatcher_agent import MaestroFullPortfolioAgent

def test_mirror_domination(seeds=list(range(700, 750))):
    print(f'Testing Morning Front-Running vs Dominant Dairy Meta across N={len(seeds)} Seeds...\n')

    wins = 0
    scores_our = []
    scores_opp = []

    opp_dairy = lambda s: MaestroFullPortfolioAgent(params={
        "cow_cap_base": 10, "sheep_cap": 4, "strawberry_target": 18, "melon_seed_target": 6, "enable_3b": False
    }, seed=s)

    for s in seeds:
        g = FastGame(seed=s)
        # Upgraded Front-Running Agent (Morning Sales + FERTILIZE_MELON)
        agent = MaestroFullPortfolioAgent(params={
            "cow_cap_base": 10, "sheep_cap": 4, "strawberry_target": 18, "melon_seed_target": 8,
            "crew_mid": 9, "crew_late": 10, "enable_3b": True, "feed_protection": True
        }, seed=s)

        opp = opp_dairy(s)

        while not g.done:
            obs0 = g.get_observation(0)
            act0 = agent(obs0)
            hour = obs0["hour"]
            day = obs0["day"]

            # Morning Front-Running: Dump milk/wool as soon as it enters shed on hours 1-4
            if hour in (1, 2, 3, 4) and day < 28:
                shed = obs0["private"]["shed"]
                frontrun_orders = []
                for item in ["MILK", "WOOL", "STRAWBERRY"]:
                    qty = shed.get(item, 0)
                    if qty > 0 and len(frontrun_orders) < 10:
                        frontrun_orders.append(["SELL", item, min(qty, 4)])
                if frontrun_orders:
                    act0["market"] = frontrun_orders[:10]

            # Day 28+ Progressive Flush
            if day >= 28:
                shed = obs0["private"]["shed"]
                flush_orders = []
                for item in ["MILK", "WOOL", "STRAWBERRY", "MELON", "TOMATO", "CARROT", "WHEAT", "FERTILIZER"]:
                    qty = shed.get(item, 0)
                    if qty > 0 and len(flush_orders) < 10:
                        flush_orders.append(["SELL", item, min(qty, 10)])
                if flush_orders:
                    act0["market"] = flush_orders[:10]

            g.step_game(act0, opp(g.get_observation(1)))

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
    print('MORNING FRONT-RUNNING VS DOMINANT DAIRY META RESULTS')
    print('=' * 85)
    print(f'Win Rate vs Dominant Dairy Meta : {wr:5.1f}% ({wins}/{len(seeds)} Wins)')
    print(f'Our Mean Score                  : ${mean_our:8,.2f}')
    print(f'Opponent Mean Score             : ${mean_opp:8,.2f}')
    print(f'Net Score Margin (Our Lead)     : +${mean_our - mean_opp:8,.2f}')
    print('=' * 85)

if __name__ == '__main__':
    test_mirror_domination()
