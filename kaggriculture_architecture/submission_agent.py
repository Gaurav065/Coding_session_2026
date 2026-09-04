import os
import sys
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
import hrl_heuristic_agent

# --- 1. LSTM Architecture (13D) ---
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

class KaggricultureLSTM(nn.Module):
    def __init__(self, scalar_dim=50, spatial_channels=4, action_dim=13, hidden_size=256):
        super().__init__()
        self.hidden_size = hidden_size
        
        self.spatial_stem = nn.Sequential(nn.Conv2d(spatial_channels, 32, 3, padding=1), nn.BatchNorm2d(32), nn.ReLU())
        self.res1 = ResBlock(32)
        self.res2 = ResBlock(32)
        self.spatial_pool = nn.AdaptiveAvgPool2d((1, 1))
        
        self.scalar_mlp = nn.Sequential(
            nn.Linear(scalar_dim, 128), nn.LayerNorm(128), nn.ReLU(),
            nn.Linear(128, 128), nn.LayerNorm(128), nn.ReLU()
        )
        self.fusion = nn.Sequential(nn.Linear(32 + 128, 256), nn.LayerNorm(256), nn.ReLU())
        self.lstm = nn.LSTM(input_size=256, hidden_size=hidden_size, num_layers=1, batch_first=True)
        self.actor_head = nn.Sequential(nn.Linear(hidden_size, action_dim), nn.Sigmoid())
        self.critic_head = nn.Linear(hidden_size, 1)

    def forward(self, spatial, scalar, hidden_state=None):
        is_sequence = len(spatial.shape) == 5
        if is_sequence:
            B, S, C, H, W = spatial.shape
            spatial = spatial.view(B*S, C, H, W)
            scalar = scalar.view(B*S, -1)
            
        x_sp = self.spatial_pool(self.res2(self.res1(self.spatial_stem(spatial)))).view(spatial.size(0), -1)
        x_sc = self.scalar_mlp(scalar)
        fused = self.fusion(torch.cat([x_sp, x_sc], dim=1))
        
        if is_sequence:
            fused = fused.view(B, S, -1)
        else:
            fused = fused.unsqueeze(1)
            
        lstm_out, hidden_state = self.lstm(fused, hidden_state)
        
        if is_sequence:
            lstm_out = lstm_out.view(B*S, -1)
        else:
            lstm_out = lstm_out.squeeze(1)
            
        actions = self.actor_head(lstm_out)
        return actions, None, hidden_state

# --- 2. Global State & Weights ---
device = torch.device("cpu")
model = KaggricultureLSTM(action_dim=13).to(device)

WEIGHTS_FILE = "ppo_lstm_day30.pth"
if os.path.exists(WEIGHTS_FILE):
    model.load_state_dict(torch.load(WEIGHTS_FILE, map_location=device, weights_only=True))
    model.eval()

# Kaggle agent is stateful, we must persist the LSTM memory across steps
GLOBAL_MEMORY_STATE = None

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

# --- 4. Kaggle Entrypoint ---

def get_graph_targets(day, current_cash):
    '''
    Overrides the RL model with the exact mathematical milestones 
    discovered in the 159k Grandmaster EDA Graph.
    '''
    # Default array (13D)
    # [WHEAT, CARROT, STRAWBERRY, MELON, COW, SHEEP, HIRE, sWHEAT, sCARROT, sSTRAW, sMELON, sMILK, sWOOL]
    targets = [0.0] * 13
    
    # Sell ratios are always high for products
    targets[11] = 1.0 # Sell Milk
    targets[12] = 1.0 # Sell Wool
    
    if day < 3:
        # Day 0-3: Wheat Rush & Early Animals
        targets[0] = 0.8  # Buy Wheat
        targets[4] = 0.3  # Buy Cow (target 5)
        targets[7] = 1.0  # Sell Wheat immediately for cash
    elif day >= 3 and day < 12:
        # Expansion Phase (BUY_LAND triggers at 1500)
        # Transition to Strawberries/Carrots to build cash faster
        targets[2] = 0.8  # Strawberry
        targets[4] = 0.6  # Buy more cows
        targets[9] = 1.0  # Sell Strawberry
    elif day >= 12 and day < 27:
        # The Engine Phase (Target 60 planted, 14 animals)
        targets[3] = 0.9  # Melon max
        targets[4] = 0.9  # Cows max (14)
        targets[10] = 1.0 # Sell Melon
    elif day >= 27:
        # Liquidation Phase
        targets = [0.0] * 13 # Buy nothing
        # Sell absolutely everything
        for i in range(7, 13):
            targets[i] = 1.0
            
    # Target 10 hands by late game if we have cash
    if current_cash > 5000:
        targets[6] = 1.0 # Max hires
    elif current_cash > 1000:
        targets[6] = 0.5 # 5 hires
    else:
        targets[6] = 0.2 # 2 hires
        
    return targets

def agent(obs):
    global GLOBAL_MEMORY_STATE
    step = obs.get("step", 0)
    
    if step == 0:
        h0 = torch.zeros(1, 1, model.hidden_size).to(device)
        c0 = torch.zeros(1, 1, model.hidden_size).to(device)
        GLOBAL_MEMORY_STATE = (h0, c0)
    
    if step % 24 == 0:
        spat, scal = get_obs_tensors(obs)
        with torch.no_grad():
            action_mean, _, GLOBAL_MEMORY_STATE = model(spat, scal, GLOBAL_MEMORY_STATE)
            action = torch.clamp(action_mean[0], 0.0, 1.0).numpy()
            
        buy_items = ["WHEAT", "CARROT", "STRAWBERRY", "MELON", "COW", "SHEEP"]
        sell_items = ["WHEAT", "CARROT", "STRAWBERRY", "MELON", "MILK", "WOOL"]
        
        targets = {"TOMATO": 0, "GOOSE": 0}
        for i, item in enumerate(buy_items[:4]): targets[item] = int(action[i] * 50)
        for i, item in enumerate(buy_items[4:]): targets[item] = int(action[i+4] * 20)
        
        sell_ratios = {"TOMATO": 1.0, "GOOSE": 1.0, "EGG": 1.0}
        for i, item in enumerate(sell_items): sell_ratios[item] = float(action[7+i])
        
        # Hardcoded Liquidation on Day 29 (Step 690+) just to be absolutely safe
        if step >= 690:
            for item in sell_ratios: sell_ratios[item] = 1.0
            
        hrl_heuristic_agent.TARGET_PORTFOLIO["BUY_TARGETS"] = targets
        hrl_heuristic_agent.TARGET_PORTFOLIO["SELL_RATIOS"] = sell_ratios
        hrl_heuristic_agent.TARGET_PORTFOLIO["HIRE_TARGET"] = max(2, int(action[6] * 10))
        
    try:
        return hrl_heuristic_agent.agent(obs)
    except:
        return {"farmer": ["PASS"], "hands": [], "market": []}
