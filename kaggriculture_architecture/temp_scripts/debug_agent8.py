import sys
import json
import traceback

sys.path.insert(0, r"C:\Coding\kaggriculture_architecture")
sys.path.insert(0, r"C:\Coding\kaggriculture")

import hrl_heuristic_agent

def patched_agent(obs, conf=None):
    hrl_heuristic_agent.TARGET_PORTFOLIO = {
        "BUY_TARGETS": {"WHEAT": 7, "CARROT": 2, "TOMATO": 0, "STRAWBERRY": 6, "MELON": 12, "COW": 0, "SHEEP": 0, "GOOSE": 0},
        "SELL_RATIOS": {"WHEAT": 1.0, "CARROT": 1.0, "TOMATO": 1.0, "STRAWBERRY": 1.0, "MELON": 1.0, "EGG": 1.0, "MILK": 1.0, "WOOL": 1.0},
        "HIRE_TARGET": 8
    }
    farm = obs.get("farms", [])[hrl_heuristic_agent.get_seat(obs)]
    orig_cash = farm.get("money", 0)
    farm["money"] = max(0, orig_cash - 50)
    act = hrl_heuristic_agent.agent(obs, conf)
    farm["money"] = orig_cash
    return act

from project_maestro.engine.fast_engine import FastGame
g = FastGame(seed=42)

for i in range(120):
    obs0 = g.get_observation(0)
    act0 = patched_agent(obs0)
    
    # Check yield units
    if i % 24 == 0:
        tiles = obs0["farms"][0]["tiles"]
        print(f"Step {i}:")
        weeds = 0
        plants = 0
        for r in tiles:
            for t in r:
                if isinstance(t, dict):
                    if t.get("kind") == "WEED": weeds += 1
                    if t.get("kind") == "PLANT": plants += 1
        print(f"  Plants: {plants}, Weeds: {weeds}")
            
    g.step_game(act0, {"farmer": ["PASS"], "hands": [], "market": []})
