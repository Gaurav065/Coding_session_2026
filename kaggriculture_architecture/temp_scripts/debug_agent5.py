import sys
sys.path.insert(0, r"C:\Coding\kaggriculture_architecture")
sys.path.insert(0, r"C:\Coding\kaggriculture")

import hrl_heuristic_agent
hrl_heuristic_agent.TARGET_PORTFOLIO = {
    "BUY_TARGETS": {"WHEAT": 7, "CARROT": 2, "TOMATO": 0, "STRAWBERRY": 6, "MELON": 12, "COW": 2, "SHEEP": 2, "GOOSE": 0},
    "SELL_RATIOS": {"WHEAT": 1.0, "CARROT": 1.0, "TOMATO": 1.0, "STRAWBERRY": 1.0, "MELON": 1.0, "EGG": 1.0, "MILK": 1.0, "WOOL": 1.0},
    "HIRE_TARGET": 10
}
our_agent = hrl_heuristic_agent.agent

from project_maestro.engine.fast_engine import FastGame
g = FastGame(seed=42)

for i in range(250):
    obs0 = g.get_observation(0)
    act0 = our_agent(obs0, None)
    g.step_game(act0, {"farmer": ["PASS"], "hands": [], "market": []})
    if 235 <= i <= 245:
        print(f"Step {i}:", act0)
