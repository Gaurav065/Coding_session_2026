import sys
import json
import glob
import os
import torch
import torch.nn as nn
import numpy as np

# Let's shift Y_data by 1 locally and train a quick model!
X_np = np.load("X_data.npy")
Y_np = np.load("Y_data.npy")

# Shift Y_data by 1 within each episode. Episodes are 30 days long.
# For simplicity, just shift everything by 1, dropping the last step of each episode.
# Or shift by 5 to predict 5 days in advance!
X_new = []
Y_new = []
for i in range(len(X_np) - 2):
    # Predict the target 2 days (48 steps) in the future to encourage buying!
    X_new.append(X_np[i])
    Y_new.append(Y_np[i+2])

X_tensor = torch.tensor(np.array(X_new), dtype=torch.float32)
Y_tensor = torch.tensor(np.array(Y_new), dtype=torch.float32)

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

model = MacroAgentNet()
optimizer = torch.optim.Adam(model.parameters(), lr=0.005)
criterion = nn.MSELoss()

print("Training shifted model locally...")
for epoch in range(150):
    optimizer.zero_grad()
    preds = model(X_tensor)
    loss = criterion(preds, Y_tensor)
    loss.backward()
    optimizer.step()

torch.save(model.state_dict(), "bc_shifted.pth")
print("Saved bc_shifted.pth")

# Now let's test it on Day 0!
model.eval()
out = model(X_tensor[0].unsqueeze(0))[0].detach().numpy()
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
print(f"Day 0 Shifted Targets: {targets}")
