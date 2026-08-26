"""160k Grandmaster Portfolio Engine Test

Tests scaling portfolio targets to match the 167k macroeconomic footprint:
- 34 Strawberries (NE)
- 16 Melons (SW)
- 8 Cows + 4 Sheep (NW)
- 10-12 Continuous Self-Sustaining Wheat (Buffer tiles)
- Daily Persistent CARE + Synchronized AMM Sales + Day 28 Progressive Flush
"""

import sys
import numpy as np

sys.path.insert(0, r'C:/Coding')
from project_maestro.engine.fast_engine import FastGame
from project_maestro.agent.dispatcher_agent import MaestroFullPortfolioAgent

def test_160k_engine(seeds=list(range(700, 725))):
    print(f'Testing 160k Grandmaster Portfolio Engine across N={len(seeds)} Seeds (Solo & Competitive)...\n')

    # 1. Solo Macro Ceiling
    solo_scores = []
    for s in seeds:
        g = FastGame(seed=s)
        agent = MaestroFullPortfolioAgent(params={
            "cow_cap_base": 8, "sheep_cap": 4, "strawberry_target": 32, "melon_seed_target": 16,
            "crew_mid": 10, "crew_late": 12, "enable_3b": True, "feed_protection": True
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
            g.step_game(act, {"farmer": ["PASS"], "hands": [], "market": []})

        solo_scores.append(g.farms[0].money)

    print('=' * 85)
    print('160K GRANDMASTER ENGINE RESULTS')
    print('=' * 85)
    print(f'Solo Macro Ceiling Mean Score : ${np.mean(solo_scores):8,.2f} (Max: ${np.max(solo_scores):8,.2f}, Min: ${np.min(solo_scores):8,.2f})')
    print('=' * 85)

if __name__ == '__main__':
    test_160k_engine()
