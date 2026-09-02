import nbformat as nbf

nb = nbf.v4.new_notebook()

md_intro = nbf.v4.new_markdown_cell("""# Kaggriculture: Behavioral Cloning (Macro-Targets)
This notebook trains a PyTorch neural network to imitate the macro-level strategies (target portfolios) of top players.
We have pre-processed 72 high-ELO replays into `X_data.npy` and `Y_data.npy`.

**Requirements:**
1. Run this on a Kaggle GPU environment.
2. Ensure `X_data.npy` and `Y_data.npy` are uploaded as a Dataset.
""")

code_setup = nbf.v4.new_code_cell("""import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader
import matplotlib.pyplot as plt
import os
import glob

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
print(f"Using device: {device}")
""")

code_load = nbf.v4.new_code_cell("""# Dynamically search for the dataset files in /kaggle/input
x_paths = glob.glob("/kaggle/input/**/X_data.npy", recursive=True)
y_paths = glob.glob("/kaggle/input/**/Y_data.npy", recursive=True)

if not x_paths or not y_paths:
    # Fallback to current directory for local testing
    X_PATH = "X_data.npy"
    Y_PATH = "Y_data.npy"
else:
    X_PATH = x_paths[0]
    Y_PATH = y_paths[0]

print(f"Loading X from: {X_PATH}")
print(f"Loading Y from: {Y_PATH}")

X_np = np.load(X_PATH)
Y_np = np.load(Y_PATH)

X_tensor = torch.tensor(X_np, dtype=torch.float32)
Y_tensor = torch.tensor(Y_np, dtype=torch.float32)

print(f"Successfully loaded {len(X_tensor)} training samples.")
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

code_train = nbf.v4.new_code_cell("""epochs = 150
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

code_save = nbf.v4.new_code_cell("""# Save to /kaggle/working so it can be downloaded easily
out_path = "/kaggle/working/bc_macro_agent.pth"
if not os.path.exists("/kaggle/working"):
    out_path = "bc_macro_agent.pth"
    
torch.save(model.state_dict(), out_path)
print(f"Model successfully saved to {out_path}")
""")

nb.cells = [md_intro, code_setup, code_load, code_model, code_train, code_save]

with open('BC_Training.ipynb', 'w') as f:
    nbf.write(nb, f)
