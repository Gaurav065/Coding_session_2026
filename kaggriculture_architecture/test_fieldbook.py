import sys
import json
import glob
import os

sys.path.insert(0, r"C:\Coding\kaggriculture_architecture")
sys.path.insert(0, r"C:\Coding\kaggriculture")

from project_maestro.engine.fast_engine import FastGame
import fieldbook_agent

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
    opp_idx = 1
    final_obs = replay_data["steps"][-1][0]["observation"]
    orig_opp_money = final_obs["farms"][opp_idx]["money"]
    ghost = GhostAgent(replay_data, opp_idx)
    g = FastGame(seed=42)
    while not g.done:
        step = g.step
        if step < len(replay_data["steps"]):
            robs = replay_data["steps"][step][0]["observation"]
            if "town" in robs and "unlocked_shops" in robs["town"]:
                g.unlocked_shops = robs["town"]["unlocked_shops"]
                
        # FastGame observation for fieldbook agent
        obs0 = g.get_observation(0)
        # We need to manually inject "town" into obs0 so the fieldbook agent can track shop unlocks!
        if step < len(replay_data["steps"]):
            robs = replay_data["steps"][step][0]["observation"]
            if "town" in robs:
                obs0["town"] = robs["town"]
                
        try:
            act0 = fieldbook_agent.agent(obs0)
        except Exception as e:
            print("Error in fieldbook agent:", e)
            act0 = {"farmer": ["PASS"], "hands": [], "market": []}
            
        act1 = ghost(g.get_observation(1))
        g.step_game(act0, act1)
        
    return {"file": os.path.basename(replay_path), "orig_opp_money": orig_opp_money, "new_our_money": g.farms[0].money, "new_opp_money": g.farms[1].money}

files = glob.glob(r"C:\Coding\kaggriculture_architecture\our_replays\*.json")
wins = 0
total = 0
for f in files[:5]:
    with open(f, "r") as tmp:
        d = json.load(tmp)
        obs = d["steps"][-1][0]["observation"]
        if max(obs["farms"][0]["money"], obs["farms"][1]["money"]) > 100000:
            res = run_shadow_match(f)
            win = "WIN" if res['new_our_money'] > res['new_opp_money'] else "LOSS"
            if win == "WIN": wins += 1
            total += 1
            print(f"[{win}] Fieldbook: ${res['new_our_money']:.0f} vs Ghost: ${res['new_opp_money']:.0f} | (Original Ghost was ${res['orig_opp_money']:.0f})")

print(f"\nFinal Result: {wins}/{total} Wins against Top Tier Opponents!")
