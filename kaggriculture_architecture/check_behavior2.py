from kaggle_environments import make
import sys
import os

env = make("kaggriculture", debug=True)
states = env.reset()
obs = states[0]["observation"]

sys.path.insert(0, r"C:\Coding\kaggriculture_architecture")
import submission_phase_f

for i in range(25):
    action = submission_phase_f.agent(obs)
    opp_action = {"farmer": ["PASS"], "hands": [], "market": []}
    states = env.step([action, opp_action])
    obs = states[0]["observation"]
    
    print(f"Turn {i}:")
    print(f"  Farmer: {action.get('farmer')}")
    print(f"  Hands:  {action.get('hands')}")
    
    farm = obs["farms"][0]
    inventories = obs.get("private", {}).get("inventories", [])
    print(f"  Workers: {farm.get('hands', [])}")
    print(f"  Hand Invs: {inventories}")
    print(f"  Seeds: {obs.get('private', {}).get('seeds')}")
    print(f"  Shed Inv: {obs.get('private', {}).get('shed')}")
    print("---")
