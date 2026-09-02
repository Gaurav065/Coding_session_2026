import sys
import json
import glob
import os
import torch
import torch.nn as nn
import numpy as np

sys.path.insert(0, r"C:\Coding\kaggriculture_architecture")
sys.path.insert(0, r"C:\Coding\kaggriculture")

import hrl_heuristic_agent
from project_maestro.engine.fast_engine import FastGame

# 1. Define the Neural Network
class MacroAgentNet(nn.Module):
    def __init__(self, obs_dim=50, act_dim=17):
        super(MacroAgentNet, self).__init__()
        self.net = nn.Sequential(
            nn.Linear(obs_dim, 128),
            nn.ReLU(),
            nn.LayerNorm(128),
            nn.Linear(128, 128),
            nn.ReLU(),
            nn.LayerNorm(128),
            nn.Linear(128, act_dim),
            nn.Sigmoid()
        )
    def forward(self, x):
        return self.net(x)

# 2. Load the trained weights
model_path = r"C:\Users\GauravPatel\Downloads\bc_macro_agent.pth"
model = MacroAgentNet()
try:
    model.load_state_dict(torch.load(model_path, map_location="cpu", weights_only=True))
    model.eval()
    print("Successfully loaded Behavioral Cloning model!")
except Exception as e:
    print(f"Failed to load model: {e}")
    sys.exit(1)

# 3. Observation Extraction
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

# 4. Neural Network Agent Wrapper
def nn_agent(obs, conf=None):
    player_idx = hrl_heuristic_agent.get_seat(obs)
    
    # Only query the neural network once per day to save compute and stabilize targets
    step = obs.get("step", 0)
    if not hasattr(nn_agent, "last_targets") or step % 24 == 0:
        vec = get_observation_vector(obs, player_idx)
        with torch.no_grad():
            out = model(torch.tensor(vec).unsqueeze(0))[0].numpy()
            
        targets = {
            "WHEAT": int(out[0] * 50),
            "CARROT": int(out[1] * 50),
            "TOMATO": int(out[2] * 50),
            "STRAWBERRY": int(out[3] * 50),
            "MELON": int(out[4] * 50),
            "GOOSE": int(out[5] * 20),
            "COW": int(out[6] * 20),
            "SHEEP": int(out[7] * 20)
        }
        hire_target = max(2, int(out[8] * 10))
        nn_agent.last_targets = targets
        nn_agent.last_hire = hire_target
    
    hrl_heuristic_agent.TARGET_PORTFOLIO = {
        "BUY_TARGETS": nn_agent.last_targets,
        "SELL_RATIOS": {"WHEAT": 1.0, "CARROT": 1.0, "TOMATO": 1.0, "STRAWBERRY": 1.0, "MELON": 1.0, "EGG": 1.0, "MILK": 1.0, "WOOL": 1.0},
        "HIRE_TARGET": nn_agent.last_hire
    }
    
    # Enforce safe cash buffer to prevent neural net from starving the farm
    farm = obs.get("farms", [])[player_idx]
    orig_cash = farm.get("money", 0)
    farm["money"] = max(0, orig_cash - 50)
    
    act = hrl_heuristic_agent.agent(obs, conf)
    farm["money"] = orig_cash
    return act

# 5. ELO Arena Engine
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
        
    opp_idx = 1 # Force opponent to 1
    
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
                
        obs0 = g.get_observation(0)
        obs1 = g.get_observation(1)
        
        try:
            act0 = nn_agent(obs0)
        except Exception:
            act0 = {"farmer": ["PASS"], "hands": [], "market": []}
            
        act1 = ghost(obs1)
        g.step_game(act0, act1)
        
    return {
        "file": os.path.basename(replay_path),
        "orig_opp_money": orig_opp_money,
        "new_our_money": g.farms[0].money,
        "new_opp_money": g.farms[1].money,
    }

replay_dir = r"C:\Coding\kaggriculture_architecture\our_replays"
files = glob.glob(os.path.join(replay_dir, "*.json"))

print("Running Behavioral Cloning Agent in the ELO Arena...")
wins = 0
total = 0
for f in files[:15]:
    with open(f, "r") as tmp:
        d = json.load(tmp)
        obs = d["steps"][-1][0]["observation"]
        if "farms" not in obs: continue
        m_our = obs["farms"][0]["money"]
        m_opp = obs["farms"][1]["money"]
        
        # Test against games where the opponent scored highly (>100k)
        if max(m_our, m_opp) > 100000:
            res = run_shadow_match(f)
            win = "WIN" if res['new_our_money'] > res['new_opp_money'] else "LOSS"
            if win == "WIN": wins += 1
            total += 1
            print(f"[{win}] BC Neural Net: ${res['new_our_money']:.0f} vs Ghost: ${res['new_opp_money']:.0f} | (Original Ghost was ${res['orig_opp_money']:.0f})")

print(f"\nFinal Result: {wins}/{total} Wins against Top Tier Opponents!")
