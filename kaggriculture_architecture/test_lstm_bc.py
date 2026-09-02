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

class LSTMMacroAgentNet(nn.Module):
    def __init__(self, obs_dim=50, hidden_dim=128, act_dim=9, num_layers=2):
        super(LSTMMacroAgentNet, self).__init__()
        self.lstm = nn.LSTM(obs_dim, hidden_dim, num_layers, batch_first=True)
        self.fc = nn.Sequential(
            nn.Linear(hidden_dim, 64), nn.ReLU(),
            nn.Linear(64, act_dim), nn.Sigmoid()
        )
    def forward(self, x, hx=None):
        out, hidden = self.lstm(x, hx)
        pred = self.fc(out)
        return pred, hidden

model = LSTMMacroAgentNet()
model.load_state_dict(torch.load(r"C:\Users\GauravPatel\Downloads\lstm_bc_macro_agent.pth", map_location="cpu", weights_only=True))
model.eval()

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

def nn_agent(obs, conf=None):
    player_idx = hrl_heuristic_agent.get_seat(obs)
    step = obs.get("step", 0)
    
    if step == 0:
        nn_agent.hx = None
        
    if not hasattr(nn_agent, "last_targets") or step % 24 == 0:
        vec = get_observation_vector(obs, player_idx)
        # Sequence format: (Batch=1, Seq=1, Obs=50)
        t_vec = torch.tensor(vec).unsqueeze(0).unsqueeze(0)
        with torch.no_grad():
            out, nn_agent.hx = model(t_vec, nn_agent.hx)
            out = out[0][0].numpy()
            
        targets = {
            "WHEAT": int(out[0] * 50), "CARROT": int(out[1] * 50), "TOMATO": int(out[2] * 50),
            "STRAWBERRY": int(out[3] * 50), "MELON": int(out[4] * 50), "GOOSE": int(out[5] * 20),
            "COW": int(out[6] * 20), "SHEEP": int(out[7] * 20)
        }
        hire_target = max(2, int(out[8] * 10))
        
        nn_agent.last_targets = targets
        nn_agent.last_hire = hire_target
    
    hrl_heuristic_agent.TARGET_PORTFOLIO = {
        "BUY_TARGETS": nn_agent.last_targets,
        "SELL_RATIOS": {"WHEAT": 1.0, "CARROT": 1.0, "TOMATO": 1.0, "STRAWBERRY": 1.0, "MELON": 1.0, "EGG": 1.0, "MILK": 1.0, "WOOL": 1.0},
        "HIRE_TARGET": nn_agent.last_hire
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
                
        try:
            act0 = nn_agent(g.get_observation(0))
        except Exception as e:
            print("Error in nn_agent:", e)
            act0 = {"farmer": ["PASS"], "hands": [], "market": []}
            
        act1 = ghost(g.get_observation(1))
        g.step_game(act0, act1)
        
    return {"file": os.path.basename(replay_path), "orig_opp_money": orig_opp_money, "new_our_money": g.farms[0].money, "new_opp_money": g.farms[1].money}

print("Running LSTM Behavioral Cloning Agent in the ELO Arena...")
files = glob.glob(r"C:\Coding\kaggriculture_architecture\our_replays\*.json")
wins = 0
total = 0
for f in files[:9]:
    with open(f, "r") as tmp:
        d = json.load(tmp)
        obs = d["steps"][-1][0]["observation"]
        if max(obs["farms"][0]["money"], obs["farms"][1]["money"]) > 100000:
            res = run_shadow_match(f)
            win = "WIN" if res['new_our_money'] > res['new_opp_money'] else "LOSS"
            if win == "WIN": wins += 1
            total += 1
            print(f"[{win}] LSTM Net: ${res['new_our_money']:.0f} vs Ghost: ${res['new_opp_money']:.0f} | (Original Ghost was ${res['orig_opp_money']:.0f})")

print(f"\nFinal Result: {wins}/{total} Wins against Top Tier Opponents!")
