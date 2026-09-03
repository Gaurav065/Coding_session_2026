import sys
from kaggle_environments import make
import json
env = make("kaggriculture")
trainer = env.train([None, "random"])
obs = trainer.reset()
act = {"farmer": ["PASS"], "hands": [], "market": [["BUY_SEED", "WHEAT", 1]]}
obs, _, _, _ = trainer.step(act)
act = {"farmer": ["PASS"], "hands": [], "market": [["HIRE"]]}
obs, _, _, _ = trainer.step(act)
# walk to center and plant
for i in range(5):
    act = {"farmer": ["PASS"], "hands": [["NORTH"]], "market": []}
    obs, _, _, _ = trainer.step(act)
for i in range(5):
    act = {"farmer": ["PASS"], "hands": [["WEST"]], "market": []}
    obs, _, _, _ = trainer.step(act)
act = {"farmer": ["PASS"], "hands": [["PLANT", "WHEAT"]], "market": []}
obs, _, _, _ = trainer.step(act)

tiles = obs["farms"][obs["player"]]["tiles"]
for r in tiles:
    for t in r:
        if isinstance(t, dict):
            print(t)
