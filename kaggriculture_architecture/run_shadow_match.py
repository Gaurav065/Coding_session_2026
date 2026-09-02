import json
import os
import glob
from kaggle_environments import make

import sys
sys.path.insert(0, r"C:\Coding\kaggriculture_architecture")
from hrl_heuristic_agent import agent as our_agent

def make_ghost_agent(replay_path, opponent_idx):
    with open(replay_path, "r", encoding="utf-8") as f:
        replay = json.load(f)
        
    # Extract actions for the opponent from steps 1 to N
    steps = replay.get("steps", [])
    actions = []
    for step in steps[1:]:
        actions.append(step[opponent_idx].get("action", {}))
        
    class GhostAgent:
        def __init__(self):
            self.step_idx = 0
            
        def __call__(self, obs, conf):
            # obs.step is the current step we are generating an action for
            # step 0 generates actions for step 1
            if self.step_idx < len(actions):
                act = actions[self.step_idx]
                self.step_idx += 1
                return act
            return {"farmer": ["PASS"], "hands": [], "market": []}
            
    return GhostAgent()

replay_dir = r"C:\Coding\kaggriculture_architecture\our_replays"
files = glob.glob(os.path.join(replay_dir, "*.json"))

# Find a replay where opponent was P1
target_replay = files[0]
print(f"Running Shadow Match against {os.path.basename(target_replay)}")

ghost = make_ghost_agent(target_replay, 1)

env = make("kaggriculture", configuration={"episodeSteps": 720})

# Run the match: Our Agent is P0, Ghost is P1
print("Starting match...")
steps = env.run([our_agent, ghost])

final_obs = steps[-1][0]["observation"]
m0 = final_obs["farms"][0]["money"]
m1 = final_obs["farms"][1]["money"]

print(f"Match Finished!")
print(f"Our Agent (P0) Money: {m0:.2f}")
print(f"Ghost Agent (P1) Money: {m1:.2f}")

