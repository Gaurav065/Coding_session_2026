from kaggle_environments import make
import sys

sys.path.insert(0, r"C:\Coding\kaggriculture_architecture")
from extracted_notebook_agent import main as legacy_main

env = make("kaggriculture", debug=True)
states = env.reset()
obs = states[0]["observation"]

pass_counts = {i: 0 for i in range(5)}
active_counts = {i: 0 for i in range(5)}

for step in range(720):
    try:
        action = legacy_main.kaggriculture_e777_agent(obs)
    except Exception:
        funcs = [getattr(legacy_main, f) for f in dir(legacy_main) if callable(getattr(legacy_main, f)) and not f.startswith('_')]
        action = funcs[-1](obs)
        
    hands = action.get("hands", [])
    for i in range(5):
        if i < len(hands):
            cmd = hands[i]
            if cmd == [] or cmd == ['PASS']:
                pass_counts[i] += 1
            else:
                active_counts[i] += 1
        else:
            pass_counts[i] += 1
            
    states = env.step([action, {"farmer": ["PASS"], "hands": [], "market": []}])
    obs = states[0]["observation"]

print("Pass Counts:", pass_counts)
print("Active Counts:", active_counts)
