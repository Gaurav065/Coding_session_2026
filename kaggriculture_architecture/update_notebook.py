import nbformat as nbf

nb = nbf.v4.new_notebook()

md_intro = nbf.v4.new_markdown_cell("""# Kaggriculture: Behavioral Cloning (Macro-Targets)
This notebook trains a PyTorch neural network to imitate the macro-level strategies (target portfolios) of top players.
We have pre-processed 200+ high-ELO replays locally into `X_data.npy` and `Y_data.npy` to save you from parsing 6GB of JSONs on Kaggle!

**Requirements:**
1. Run this on a Kaggle GPU environment.
2. Upload `X_data.npy` and `Y_data.npy` as a Dataset.
""")

code_setup = nbf.v4.new_code_cell("""import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader
import matplotlib.pyplot as plt
import os

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
print(f"Using device: {device}")
""")

code_load = nbf.v4.new_code_cell("""# Load pre-processed NumPy arrays
# Update this path to wherever you mount the dataset in Kaggle!
DATA_DIR = "/kaggle/input/kaggriculture-bc-data" 

if not os.path.exists(DATA_DIR):
    DATA_DIR = "." # Fallback for local testing

X_np = np.load(os.path.join(DATA_DIR, "X_data.npy"))
Y_np = np.load(os.path.join(DATA_DIR, "Y_data.npy"))

X_tensor = torch.tensor(X_np, dtype=torch.float32)
Y_tensor = torch.tensor(Y_np, dtype=torch.float32)

print(f"Loaded {len(X_tensor)} training samples.")
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

code_save = nbf.v4.new_code_cell("""torch.save(model.state_dict(), "bc_macro_agent.pth")
print("Model saved to bc_macro_agent.pth")
""")

nb.cells = [md_intro, code_setup, code_load, code_model, code_train, code_save]

with open('BC_Training.ipynb', 'w') as f:
    nbf.write(nb, f)
