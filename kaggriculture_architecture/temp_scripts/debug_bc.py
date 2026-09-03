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

model_path = r"C:\Users\GauravPatel\Downloads\bc_macro_agent.pth"
model = MacroAgentNet()
model.load_state_dict(torch.load(model_path, map_location="cpu", weights_only=True))
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

g = FastGame(seed=42)
for step in range(24):
    obs = g.get_observation(0)
    vec = get_observation_vector(obs, 0)
    out = model(torch.tensor(vec).unsqueeze(0))[0].detach().numpy()
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
    if step == 0:
        print(f"Day 0 Targets: {targets} | Hires: {hire_target}")
    g.step_game({"farmer": ["PASS"], "hands": [], "market": []}, {"farmer": ["PASS"], "hands": [], "market": []})
