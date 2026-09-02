import sys
import json
import glob
import os
from collections import defaultdict
import statistics

sys.path.insert(0, r"C:\Coding\kaggriculture_architecture")
sys.path.insert(0, r"C:\Coding\kaggriculture")

import hrl_heuristic_agent
# Set the exact Phase E portfolio we used on Kaggle!
hrl_heuristic_agent.TARGET_PORTFOLIO = {
    "BUY_TARGETS": {"WHEAT": 7, "CARROT": 2, "TOMATO": 0, "STRAWBERRY": 6, "MELON": 12, "COW": 2, "SHEEP": 2, "GOOSE": 0},
    "SELL_RATIOS": {"WHEAT": 1.0, "CARROT": 1.0, "TOMATO": 1.0, "STRAWBERRY": 1.0, "MELON": 1.0, "EGG": 1.0, "MILK": 1.0, "WOOL": 1.0},
    "HIRE_TARGET": 10  # Starts with 2 hands, hires 10 -> 12 hands
}
our_agent = hrl_heuristic_agent.agent

from project_maestro.engine.fast_engine import FastGame

replay_dir = r"C:\Coding\kaggriculture_architecture\our_replays"
files = glob.glob(os.path.join(replay_dir, "*.json"))

# The exact signature to find our agent
OUR_TARGETS = {'CARROT': 2, 'MELON': 12, 'STRAWBERRY': 6, 'TOMATO': 0, 'WHEAT': 7}
def identify_our_agent(replay_data):
    s0_score = 0
    s1_score = 0
    for step in replay_data["steps"]:
        obs = step[0]["observation"]
        if "farms" not in obs: continue
        for p, score in zip([0, 1], [s0_score, s1_score]):
            priv = step[p]["observation"].get("private", {})
            seeds = priv.get("seeds", {})
            for k, v in OUR_TARGETS.items():
                if seeds.get(k, 0) == v:
                    if p == 0: s0_score += 1
                    else: s1_score += 1
    return 0 if s0_score > s1_score else 1

class GhostAgent:
    def __init__(self, replay_data, opp_idx):
        self.actions = [s[opp_idx].get("action", {}) for s in replay_data["steps"][1:]]
        self.step_idx = 0
        
    def __call__(self, obs):
        if self.step_idx < len(self.actions):
            act = self.actions[self.step_idx]
            self.step_idx += 1
            return act
        return {"farmer": ["PASS"], "hands": [], "market": []}

def run_shadow_match(replay_path):
    with open(replay_path, "r", encoding="utf-8") as f:
        replay_data = json.load(f)
        
    our_original_idx = identify_our_agent(replay_data)
    opp_idx = 1 - our_original_idx
    
    final_obs = replay_data["steps"][-1][0]["observation"]
    orig_our_money = final_obs["farms"][our_original_idx]["money"]
    orig_opp_money = final_obs["farms"][opp_idx]["money"]
    
    ghost = GhostAgent(replay_data, opp_idx)
    g = FastGame(seed=42)
    
    def safe_our_agent(obs):
        try:
            return our_agent(obs, None)
        except Exception as e:
            return {"farmer": ["PASS"], "hands": [], "market": []}
            
    while not g.done:
        step = g.step
        if step < len(replay_data["steps"]):
            robs = replay_data["steps"][step][0]["observation"]
            if "town" in robs and "unlocked_shops" in robs["town"]:
                g.unlocked_shops = robs["town"]["unlocked_shops"]
                
        obs0 = g.get_observation(0)
        obs1 = g.get_observation(1)
        
        act0 = safe_our_agent(obs0)
        act1 = ghost(obs1)
        
        g.step_game(act0, act1)
        
    return {
        "file": os.path.basename(replay_path),
        "orig_our_money": orig_our_money,
        "orig_opp_money": orig_opp_money,
        "new_our_money": g.farms[0].money,
        "new_opp_money": g.farms[1].money,
    }

print("Starting Local ELO Arena against Marginal Loss opponents...")
count = 0
for f in files:
    with open(f, "r") as tmp:
        d = json.load(tmp)
        our_idx = identify_our_agent(d)
        opp_idx = 1 - our_idx
        obs = d["steps"][-1][0]["observation"]
        if "farms" not in obs: continue
        m_our = obs["farms"][our_idx]["money"]
        m_opp = obs["farms"][opp_idx]["money"]
        margin = m_our - m_opp
        if -20000 < margin < 0:
            res = run_shadow_match(f)
            print(f"[{res['file']}]")
            print(f"  Original: Us ${res['orig_our_money']:.0f} vs Them ${res['orig_opp_money']:.0f}")
            print(f"  Shadow:   Us ${res['new_our_money']:.0f} vs Them ${res['new_opp_money']:.0f}")
            count += 1
            if count >= 5: break
print("Done!")
