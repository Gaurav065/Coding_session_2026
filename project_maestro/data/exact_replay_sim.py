"""Exact Closed-Form Replay Simulator

Replays the exact actions of both players through FastGame/engine to verify 100% exact
cash reconciliation against steps[-1].reward.
"""

import sys
import json
sys.path.insert(0, r"C:\Coding")
from project_maestro.engine.fast_engine import FastGame

def exact_replay(path):
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    steps = data["steps"]
    info = data.get("info", {})
    seed = info.get("seed", 42) # Or from obs

    # Extract all actions
    p0_acts = [s[0].get("action", {}) for s in steps]
    p1_acts = [s[1].get("action", {}) for s in steps]
    
    # Check if seed is in step 0 observation
    obs0 = steps[0][0].get("observation", {})
    env_seed = obs0.get("seed", seed)

    print(f"Replaying {len(steps)} steps with seed {env_seed}...")
    
    # We can track exact sales by instrumenting FastGame or matching step-by-step
    game = FastGame(seed=env_seed)
    
    sales_by_prod = [{p: 0 for p in ["WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON", "EGG", "MILK", "WOOL", "FERTILIZER"]} for _ in (0, 1)]
    rev_by_prod = [{p: 0.0 for p in ["WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON", "EGG", "MILK", "WOOL", "FERTILIZER"]} for _ in (0, 1)]
    
    for t in range(len(steps) - 1):
        a0 = p0_acts[t] if t < len(p0_acts) else {"farmer": ["PASS"], "hands": [], "market": []}
        a1 = p1_acts[t] if t < len(p1_acts) else {"farmer": ["PASS"], "hands": [], "market": []}
        
        # Track shed before market
        # FastGame step:
        game.step_game(a0, a1)

    print(f"\nFinal Simulated Money: P0 = ${game.farms[0].money:,.2f} | P1 = ${game.farms[1].money:,.2f}")
    print(f"Actual Tape Rewards:   P0 = ${steps[-1][0]['reward']:,.2f} | P1 = ${steps[-1][1]['reward']:,.2f}")
    print(f"Delta P0: ${game.farms[0].money - steps[-1][0]['reward']:,.2f}")
    print(f"Delta P1: ${game.farms[1].money - steps[-1][1]['reward']:,.2f}")

if __name__ == "__main__":
    exact_replay(r"C:\Coding\kaggriculture-agent\replays\93924742.json")
