import os
import sys
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

# --- 1. ResNet Architecture ---
BOARD_SIZE = 10

class ResBlock(nn.Module):
    def __init__(self, channels):
        super().__init__()
        self.conv1 = nn.Conv2d(channels, channels, 3, padding=1)
        self.bn1 = nn.BatchNorm2d(channels)
        self.conv2 = nn.Conv2d(channels, channels, 3, padding=1)
        self.bn2 = nn.BatchNorm2d(channels)

    def forward(self, x):
        res = x
        x = F.relu(self.bn1(self.conv1(x)))
        x = self.bn2(self.conv2(x))
        return F.relu(x + res)

class KaggricultureResNet(nn.Module):
    def __init__(self, scalar_dim=50, spatial_channels=4, action_dim=17):
        super().__init__()
        self.spatial_stem = nn.Sequential(nn.Conv2d(spatial_channels, 32, 3, padding=1), nn.BatchNorm2d(32), nn.ReLU())
        self.res1 = ResBlock(32)
        self.res2 = ResBlock(32)
        self.spatial_pool = nn.AdaptiveAvgPool2d((1, 1))
        
        self.scalar_mlp = nn.Sequential(
            nn.Linear(scalar_dim, 128), nn.LayerNorm(128), nn.ReLU(),
            nn.Linear(128, 128), nn.LayerNorm(128), nn.ReLU()
        )
        self.fusion = nn.Sequential(nn.Linear(32 + 128, 256), nn.LayerNorm(256), nn.ReLU())
        self.actor_head = nn.Sequential(nn.Linear(256, action_dim), nn.Sigmoid())
        self.critic_head = nn.Linear(256, 1)

    def forward(self, spatial, scalar):
        x_sp = self.spatial_pool(self.res2(self.res1(self.spatial_stem(spatial)))).view(spatial.size(0), -1)
        shared = self.fusion(torch.cat([x_sp, self.scalar_mlp(scalar)], dim=1))
        return self.actor_head(shared), self.critic_head(shared)

# --- 2. Global State & Pre-loaded Weights ---
device = torch.device("cpu") # Kaggle submission runs on CPU
model = KaggricultureResNet().to(device)

# When submitting to Kaggle, we zip this script with the .pth file
WEIGHTS_FILE = "ppo_resnet_day30.pth"
if os.path.exists(WEIGHTS_FILE):
    model.load_state_dict(torch.load(WEIGHTS_FILE, map_location=device, weights_only=True))
    model.eval()

# To connect our PyTorch model to the Heuristic, we track the target portfolio globally
GLOBAL_TARGET_PORTFOLIO = {
    "BUY_TARGETS": {},
    "SELL_RATIOS": {},
    "HIRE_TARGET": 0
}

# --- 3. Observation Parsing ---
def get_obs_tensors(obs):
    farm = obs["farms"][0]
    vec = np.zeros(50, dtype=np.float32)
    vec[0] = obs.get("step", 0) / 2000.0
    vec[1] = farm.get("money", 0) / 10000.0
    for i, item in enumerate(["WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON", "EGG", "MILK", "WOOL", "COW", "SHEEP", "GOOSE"]):
        vec[2 + i] = obs.get("private", {}).get("shed", {}).get(item, 0) / 100.0
        vec[13 + i] = obs.get("private", {}).get("seeds", {}).get(item, 0) / 100.0
        vec[24 + i] = obs.get("market", {}).get("prices", {}).get(item, 0) / 100.0
    vec[35] = len(farm.get("hands", [])) / 10.0
    
    grid = np.zeros((4, BOARD_SIZE, BOARD_SIZE), dtype=np.float32)
    crop_to_idx = {"WHEAT": 1, "CARROT": 2, "TOMATO": 3, "STRAWBERRY": 4, "MELON": 5}
    for y in range(BOARD_SIZE):
        for x in range(BOARD_SIZE):
            t = farm["tiles"][y][x]
            if t == "LOCKED": grid[3, y, x] = -1
            elif isinstance(t, dict):
                if t.get("kind") == "PLANT":
                    grid[0, y, x] = crop_to_idx.get(t.get("crop"), 0)
                    grid[1, y, x] = t.get("yield_units", 0)
                elif t.get("kind") == "WEED": grid[3, y, x] = 1
                elif t.get("kind") in ["COOP", "PASTURE"]:
                    grid[3, y, x] = 2
                    if "animal" in t:
                        grid[0, y, x] = 6 
                        grid[1, y, x] = t.get("yield_units", 0)
    fx, fy = farm.get("farmer", [0, 0])
    if 0 <= fx < BOARD_SIZE and 0 <= fy < BOARD_SIZE: grid[2, fy, fx] = 1
    for h in farm.get("hands", []):
        if 0 <= h[0] < BOARD_SIZE and 0 <= h[1] < BOARD_SIZE: grid[2, h[1], h[0]] = 1
        
    return torch.Tensor(grid).unsqueeze(0), torch.Tensor(vec).unsqueeze(0)

# --- 4. Fallback Heuristic Pathfinding (Miniaturized for Kaggle) ---
# We simulate the exact BFS low-level logic here to execute the Macro actions.
def fallback_bfs_agent(obs):
    # This is a simplified fallback that executes the GLOBAL_TARGET_PORTFOLIO
    # In a real submission, we would paste the full hrl_heuristic_agent.py BFS logic here.
    # We will just do a basic implementation to satisfy the Kaggle API for now.
    commands = {"farmer": ["PASS"], "hands": [], "market": []}
    
    farm = obs["farms"][0]
    money = farm.get("money", 0)
    market_prices = obs.get("market", {}).get("prices", {})
    
    # 1. HIRE
    current_hands = len(farm.get("hands", []))
    if current_hands < GLOBAL_TARGET_PORTFOLIO["HIRE_TARGET"] and money >= 100:
        commands["market"].append(["HIRE"])
        money -= 100
        
    # 2. BUY
    for item, target_amt in GLOBAL_TARGET_PORTFOLIO["BUY_TARGETS"].items():
        if target_amt > 0:
            cost = market_prices.get(item, 999)
            if money >= cost:
                prefix = "BUY_ANIMAL" if item in ["COW", "SHEEP", "GOOSE"] else "BUY_SEED"
                commands["market"].append([prefix, item, 1])
                money -= cost
                
    # 3. SELL
    shed = obs.get("private", {}).get("shed", {})
    for item, ratio in GLOBAL_TARGET_PORTFOLIO["SELL_RATIOS"].items():
        count = shed.get(item, 0)
        sell_amt = int(count * ratio)
        if sell_amt > 0:
            commands["market"].append(["SELL", item, sell_amt])
            
    # Keep hands passing (BFS logic would replace this with actual movement)
    for _ in range(current_hands):
        commands["hands"].append(["PASS"])
        
    return commands

# --- 5. The Main Kaggle Entrypoint ---
def agent(obs):
    step = obs.get("step", 0)
    
    # Every 24 micro-steps (1 macro-step / 1 day), we ask the PyTorch Brain for a new strategy
    if step % 24 == 0:
        spat, scal = get_obs_tensors(obs)
        with torch.no_grad():
            action_mean, _ = model(spat, scal)
            action = torch.clamp(action_mean[0], 0.0, 1.0).numpy()
            
        # Decode PyTorch [0,1] vector into discrete economic targets
        buy_items = ["WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON", "GOOSE", "COW", "SHEEP"]
        sell_items = ["WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON", "EGG", "MILK", "WOOL"]
        
        targets = {}
        for i, item in enumerate(buy_items[:5]): targets[item] = int(action[i] * 50)
        for i, item in enumerate(buy_items[5:]): targets[item] = int(action[i+5] * 20)
        
        GLOBAL_TARGET_PORTFOLIO["BUY_TARGETS"] = targets
        GLOBAL_TARGET_PORTFOLIO["SELL_RATIOS"] = {item: float(action[9+i]) for i, item in enumerate(sell_items)}
        GLOBAL_TARGET_PORTFOLIO["HIRE_TARGET"] = max(2, int(action[8] * 10))
        
    # Execute the portfolio strategy using the low-level BFS Pathfinder
    return fallback_bfs_agent(obs)
