import json
import os
import nbformat as nbf

nb = nbf.v4.new_notebook()

md_intro = nbf.v4.new_markdown_cell("""# Kaggriculture: Behavioral Cloning (Macro-Targets)
This notebook trains a PyTorch neural network to imitate the macro-level strategies (target portfolios) of top players, using their Kaggle replays as training data. 

**Requirements:**
1. Run this on a Kaggle GPU environment.
2. Upload the `our_replays` JSON files as a Kaggle Dataset and attach it to this notebook.
""")

code_setup = nbf.v4.new_code_cell("""import os
import json
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader
import matplotlib.pyplot as plt

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
print(f"Using device: {device}")
""")

md_dataset = nbf.v4.new_markdown_cell("""## 1. Dataset Generation (Inverse HRL)
We don't want to clone raw micro-actions (like `['NORTH']`). Instead, we want to extract their **Target Portfolios**. 
For every day (24 steps), we look at the opponent's farm and count how many plants of each type they currently own or have planted. We use this as the "Target" the network should learn to predict given the current observation (cash, day, market prices).""")

code_dataset = nbf.v4.new_code_cell("""def extract_macro_targets(obs_dict, player_idx):
    farm = obs_dict["farms"][player_idx]
    priv = obs_dict.get("private", {})
    shed = priv.get("shed", {})
    seeds = priv.get("seeds", {})
    
    # Count planted crops
    planted = {"WHEAT": 0, "CARROT": 0, "TOMATO": 0, "STRAWBERRY": 0, "MELON": 0}
    for row in farm.get("tiles", []):
        for tile in row:
            if isinstance(tile, dict) and tile.get("kind") == "PLANT":
                crop = tile.get("crop")
                if crop in planted:
                    planted[crop] += 1
                    
    # The target is what they have planted + what they hold in seeds
    targets = {
        "WHEAT": planted["WHEAT"] + seeds.get("WHEAT", 0),
        "CARROT": planted["CARROT"] + seeds.get("CARROT", 0),
        "TOMATO": planted["TOMATO"] + seeds.get("TOMATO", 0),
        "STRAWBERRY": planted["STRAWBERRY"] + seeds.get("STRAWBERRY", 0),
        "MELON": planted["MELON"] + seeds.get("MELON", 0),
        "GOOSE": shed.get("GOOSE", 0),
        "COW": shed.get("COW", 0),
        "SHEEP": shed.get("SHEEP", 0),
        "HIRE": len(farm.get("hands", []))
    }
    return targets

def get_observation_vector(obs, player_idx):
    vec = np.zeros(50, dtype=np.float32)
    farm = obs["farms"][player_idx]
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

# Load Replays
REPLAY_DIR = "/kaggle/input/kaggriculture-marginal-losses" # Update this to your dataset path
if not os.path.exists(REPLAY_DIR):
    REPLAY_DIR = r"C:\\Coding\\kaggriculture_architecture\\our_replays" # Local fallback

X_data = []
Y_data = []

if os.path.exists(REPLAY_DIR):
    for file in os.listdir(REPLAY_DIR):
        if not file.endswith(".json"): continue
        with open(os.path.join(REPLAY_DIR, file), "r", encoding="utf-8") as f:
            data = json.load(f)
            
        # Determine which player is the opponent (we assume the opponent won, so they had more money at the end)
        final_obs = data["steps"][-1][0]["observation"]
        m0 = final_obs["farms"][0]["money"]
        m1 = final_obs["farms"][1]["money"]
        opp_idx = 0 if m0 > m1 else 1
        
        # Extract once per day (macro step)
        for step_data in data["steps"]:
            obs = step_data[0]["observation"]
            step_num = obs.get("step", 0)
            if step_num % 24 == 0:
                vec = get_observation_vector(obs, opp_idx)
                targets = extract_macro_targets(obs, opp_idx)
                
                # Normalize targets to [0, 1] to match our HRL action space
                y_vec = np.zeros(17, dtype=np.float32)
                y_vec[0] = targets["WHEAT"] / 50.0
                y_vec[1] = targets["CARROT"] / 50.0
                y_vec[2] = targets["TOMATO"] / 50.0
                y_vec[3] = targets["STRAWBERRY"] / 50.0
                y_vec[4] = targets["MELON"] / 50.0
                y_vec[5] = targets["GOOSE"] / 20.0
                y_vec[6] = targets["COW"] / 20.0
                y_vec[7] = targets["SHEEP"] / 20.0
                y_vec[8] = targets["HIRE"] / 10.0
                # We can leave sell ratios at 1.0 for BC
                for i in range(9, 17): y_vec[i] = 1.0 
                
                X_data.append(vec)
                Y_data.append(y_vec)

X_tensor = torch.tensor(np.array(X_data), dtype=torch.float32)
Y_tensor = torch.tensor(np.array(Y_data), dtype=torch.float32)
print(f"Generated {len(X_tensor)} training samples.")
""")

code_model = nbf.v4.new_code_cell("""class MacroAgentNet(nn.Module):
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
            nn.Sigmoid() # Bound outputs to [0, 1]
        )
        
    def forward(self, x):
        return self.net(x)

class ReplayDataset(Dataset):
    def __init__(self, x, y):
        self.x = x
        self.y = y
    def __len__(self): return len(self.x)
    def __getitem__(self, idx): return self.x[idx], self.y[idx]

dataset = ReplayDataset(X_tensor, Y_tensor)
dataloader = DataLoader(dataset, batch_size=32, shuffle=True)
model = MacroAgentNet().to(device)
optimizer = optim.Adam(model.parameters(), lr=0.001)
criterion = nn.MSELoss()
""")

code_train = nbf.v4.new_code_cell("""epochs = 100
losses = []

model.train()
for epoch in range(epochs):
    epoch_loss = 0
    for batch_x, batch_y in dataloader:
        batch_x, batch_y = batch_x.to(device), batch_y.to(device)
        
        optimizer.zero_grad()
        preds = model(batch_x)
        loss = criterion(preds, batch_y)
        loss.backward()
        optimizer.step()
        
        epoch_loss += loss.item()
        
    avg_loss = epoch_loss / len(dataloader)
    losses.append(avg_loss)
    if epoch % 10 == 0:
        print(f"Epoch {epoch}/{epochs} | MSE Loss: {avg_loss:.4f}")

plt.plot(losses)
plt.title("Behavioral Cloning Loss")
plt.xlabel("Epoch")
plt.ylabel("MSE Loss")
plt.show()
""")

code_save = nbf.v4.new_code_cell("""torch.save(model.state_dict(), "bc_macro_agent.pth")
print("Model saved to bc_macro_agent.pth")
""")

nb.cells = [md_intro, code_setup, md_dataset, code_dataset, code_model, code_train, code_save]

with open('BC_Training.ipynb', 'w') as f:
    nbf.write(nb, f)
