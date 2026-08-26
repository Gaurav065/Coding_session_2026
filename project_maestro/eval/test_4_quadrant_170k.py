"""4-Quadrant 100-Tile Super-Farm Simulation Test

Simulates uncontested matches unlocking all 4 quadrants (NW, NE, SW, SE)
to verify if 100-tile expansion breaks $170,000+ net bank score.
"""

import sys
import json
import numpy as np
from collections import defaultdict

sys.path.insert(0, r'C:/Coding')
from project_maestro.engine.fast_engine import FastGame
from project_maestro.agent.dispatcher_agent import MaestroFullPortfolioAgent

def run_4quadrant_superfarm_test(num_seeds: int = 50):
    print(f'Testing 4-Quadrant 100-Tile Super-Farm across N={num_seeds} Seeds...\n')

    scores_3quad = []
    scores_4quad = []

    for seed in range(700, 700 + num_seeds):
        # 1. 3-Quadrant Baseline (NW, NE, SW)
        g3 = FastGame(seed=seed)
        a3 = MaestroFullPortfolioAgent(params={
            "cow_cap_base": 12, "sheep_cap": 2, "strawberry_target": 22, "melon_seed_target": 8, "crew_mid": 10, "crew_late": 12
        }, seed=seed)
        passive_opp = {"farmer": ["PASS"], "hands": [], "market": []}
        while not g3.done:
            g3.step_game(a3(g3.get_observation(0)), passive_opp)
        scores_3quad.append(g3.farms[0].money)

        # 2. 4-Quadrant Super-Farm (NW, NE, SW, SE)
        g4 = FastGame(seed=seed)
        a4 = MaestroFullPortfolioAgent(params={
            "cow_cap_base": 14, "sheep_cap": 0, "strawberry_target": 35, "melon_seed_target": 18, "crew_mid": 12, "crew_late": 15
        }, seed=seed)
        # Enable SE unlock in parameters if money allows
        while not g4.done:
            obs = g4.get_observation(0)
            act = a4(obs)
            # Add SE unlock if Day >= 10 and money >= 4500 and SE locked
            if obs["day"] >= 10 and "SE" not in obs["farms"][0]["unlocked_quadrants"] and obs["farms"][0]["money"] >= 4500:
                act["market"].append(["BUY_LAND"])
            g4.step_game(act, passive_opp)
        scores_4quad.append(g4.farms[0].money)

    print('=' * 85)
    print('3-QUADRANT (75 TILES) VS 4-QUADRANT SUPER-FARM (100 TILES)')
    print('=' * 85)
    print(f'3-Quadrant Mean Score : ${np.mean(scores_3quad):,.2f} | Max: ${np.max(scores_3quad):,.2f}')
    print(f'4-Quadrant Mean Score : ${np.mean(scores_4quad):,.2f} | Max: ${np.max(scores_4quad):,.2f}')
    print('=' * 85)

if __name__ == '__main__':
    run_4quadrant_superfarm_test(30)
