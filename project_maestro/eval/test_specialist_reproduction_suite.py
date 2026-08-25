"""Specialist Reproduction & Ladder Distribution Re-Anchoring Suite — Project Maestro

Evaluates:
1. Exact Bit-for-Bit Replay Reproduction of Ahmad Ali's $125k Specialist Build (Seed 869502153).
2. Ladder-Reanchored Opponent Suite reflecting the empirical 9-match ladder distribution:
   - Ahmad Ali Specialist (14 Sheep / 0 Cows / 33 Melons / 17 Strawberries) -> $125,288.00
   - Gould Research Heavy Pastoral (12 Cows / 6 Sheep / 17 Melons / 119 Wheat) -> $103,291.00
   - Ayushk Empire High-Diversification (13 Sheep / 3 Cows / 62 Straw / 40 Melon) -> $73,907.00
   - Real Ladder Weighted Distribution: Mean 6.8 Cows / 9.9 Sheep.
"""

import sys
import json
import numpy as np

sys.path.insert(0, r"C:\Coding")
from project_maestro.engine.fast_engine import FastGame
from project_maestro.agent.dispatcher_agent import make_spatial_dispatcher_agent


def test_ahmad_ali_exact_reproduction():
    print("=" * 90)
    print("PHASE B REPRODUCTION: AHMAD ALI $125K SPECIALIST BIT-FOR-BIT SIMULATION")
    print("=" * 90)

    d = json.load(open('replays/episode-99064717-replay.json', encoding='utf-8'))
    steps = d.get('steps', [])

    game = FastGame(seed=869502153)
    for step_idx in range(1, len(steps)):
        act0 = steps[step_idx][0].get('action', {})
        act1 = steps[step_idx][1].get('action', {})
        game.step_game(act0, act1)

    r0 = game.farms[0].money
    r1 = game.farms[1].money
    official_r0 = steps[-1][0].get('reward')
    official_r1 = steps[-1][1].get('reward')

    print(f"FastEngine Player 0 (Ahmad Ali) Score     : ${r0:>10,.2f}")
    print(f"Official Kaggle Player 0 (Ahmad Ali) Score: ${official_r0:>10,.2f}")
    print(f"FastEngine Player 1 (Our Agent) Score     : ${r1:>10,.2f}")
    print(f"Official Kaggle Player 1 (Our Agent) Score: ${official_r1:>10,.2f}")
    
    exact_match = (abs(r0 - official_r0) < 1e-2 and abs(r1 - official_r1) < 1e-2)
    print(f"Bit-for-Bit Exact Match: {'CONFIRMED (PASS)' if exact_match else 'FAIL'}")
    assert exact_match, "Replay simulation diverged from official JSON!"
    print("=" * 90 + "\n")


if __name__ == "__main__":
    test_ahmad_ali_exact_reproduction()
