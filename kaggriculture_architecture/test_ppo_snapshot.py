import sys
import json
import glob
import os
import numpy as np

sys.path.insert(0, r"C:\Coding\kaggriculture_architecture")
sys.path.insert(0, r"C:\Coding\kaggriculture")

import hrl_heuristic_agent
from project_maestro.engine.fast_engine import FastGame
from stable_baselines3 import PPO

model = PPO.load("ppo_best_model.zip")

def get_observation_vector(obs, player_idx):
    vec = np.zeros(50, dtype=np.float32)
    farm = obs.get("farms", [{}, {}])[player_idx]
    priv = obs.get("private", {})
    shed = priv.get("shed", {})
    seeds = priv.get("seeds", {})
    market = obs.get("market", {})
    vec[0] = obs.get("step", 0) / 2000.0
    vec[1] = farm.get("money", 0) / 10000.0
    items = ["WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON", "EGG", "MILK", "WOOL", "COW", "SHEEP", "GOOSE"]
    for i, item in enumerate(items):
        vec[2 + i] = shed.get(item, 0) / 100.0
        vec[13 + i] = seeds.get(item, 0) / 100.0
        prices = market.get("prices", {})
        vec[24 + i] = prices.get(item, 0) / 100.0
    vec[35] = len(farm.get("hands", [])) / 10.0
    return vec

def ppo_agent(obs, conf=None):
    player_idx = hrl_heuristic_agent.get_seat(obs)
    step = obs.get("step", 0)
    
    if not hasattr(ppo_agent, "last_targets") or step % 24 == 0:
        vec = get_observation_vector(obs, player_idx)
        
        # PPO predict
        action, _ = model.predict(vec, deterministic=True)
        
        buy_items = ["WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON", "GOOSE", "COW", "SHEEP"]
        sell_items = ["WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON", "EGG", "MILK", "WOOL"]
        
        targets = {}
        for i, item in enumerate(buy_items[:5]): targets[item] = int(action[i] * 50)
        for i, item in enumerate(buy_items[5:]): targets[item] = int(action[i+5] * 20)
            
        hire_target = max(2, int(action[8] * 10))
        ratios = {}
        for i, item in enumerate(sell_items): ratios[item] = float(action[9+i])
        
        ppo_agent.last_targets = targets
        ppo_agent.last_ratios = ratios
        ppo_agent.last_hire = hire_target
    
    hrl_heuristic_agent.TARGET_PORTFOLIO = {
        "BUY_TARGETS": ppo_agent.last_targets,
        "SELL_RATIOS": ppo_agent.last_ratios,
        "HIRE_TARGET": ppo_agent.last_hire
    }
    
    return hrl_heuristic_agent.agent(obs, conf)

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

print("Testing Current PPO Snapshot in the ELO Arena...")
files = glob.glob(r"C:\Coding\kaggriculture_architecture\our_replays\*.json")

for f in files[:3]:
    with open(f, "r", encoding="utf-8") as tmp:
        d = json.load(tmp)
        obs = d["steps"][-1][0]["observation"]
        if max(obs["farms"][0]["money"], obs["farms"][1]["money"]) > 100000:
            opp_idx = 1
            orig_opp_money = obs["farms"][opp_idx]["money"]
            ghost = GhostAgent(d, opp_idx)
            g = FastGame(seed=42)
            while not g.done:
                step = g.step
                if step < len(d["steps"]):
                    robs = d["steps"][step][0]["observation"]
                    if "town" in robs and "unlocked_shops" in robs["town"]:
                        g.unlocked_shops = robs["town"]["unlocked_shops"]
                try:
                    act0 = ppo_agent(g.get_observation(0))
                except Exception as e:
                    act0 = {"farmer": ["PASS"], "hands": [], "market": []}
                act1 = ghost(g.get_observation(1))
                g.step_game(act0, act1)
            
            res_our = g.farms[0].money
            res_opp = g.farms[1].money
            print(f"File: {os.path.basename(f)}")
            print(f"PPO Agent: ${res_our:.0f} vs Ghost: ${res_opp:.0f}")
            print("-" * 50)
