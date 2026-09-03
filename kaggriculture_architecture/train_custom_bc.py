import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader
from custom_architecture import KaggricultureResNet

class ReplayDataset(Dataset):
    def __init__(self, X_scal, X_spat, Y):
        self.X_scal = torch.FloatTensor(X_scal)
        self.X_spat = torch.FloatTensor(X_spat)
        self.Y = torch.FloatTensor(Y)
        
    def __len__(self):
        return len(self.Y)
        
    def __getitem__(self, idx):
        return self.X_spat[idx], self.X_scal[idx], self.Y[idx]

def train():
    print("Loading extracted tensors...")
    X_scalar = np.load("X_scalar.npy")
    X_spatial = np.load("X_spatial.npy")
    Y_actions = np.load("Y_actions.npy")
    
    # 90-10 Split
    split = int(0.9 * len(X_scalar))
    train_ds = ReplayDataset(X_scalar[:split], X_spatial[:split], Y_actions[:split])
    val_ds = ReplayDataset(X_scalar[split:], X_spatial[split:], Y_actions[split:])
    
    train_loader = DataLoader(train_ds, batch_size=256, shuffle=True)
    val_loader = DataLoader(val_ds, batch_size=256, shuffle=False)
    
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Training on {device}...")
    
    model = KaggricultureResNet().to(device)
    optimizer = optim.AdamW(model.parameters(), lr=1e-3, weight_decay=1e-5)
    criterion = nn.MSELoss()
    
    epochs = 30
    best_loss = float('inf')
    
    for epoch in range(epochs):
        model.train()
        train_loss = 0
        for spat, scal, y in train_loader:
            spat, scal, y = spat.to(device), scal.to(device), y.to(device)
            optimizer.zero_grad()
            preds = model(spat, scal)
            loss = criterion(preds, y)
            loss.backward()
            optimizer.step()
            train_loss += loss.item()
            
        model.eval()
        val_loss = 0
        with torch.no_grad():
            for spat, scal, y in val_loader:
                spat, scal, y = spat.to(device), scal.to(device), y.to(device)
                preds = model(spat, scal)
                val_loss += criterion(preds, y).item()
                
        t_loss = train_loss / len(train_loader)
        v_loss = val_loss / len(val_loader)
        print(f"Epoch {epoch+1:02d}/{epochs} | Train Loss: {t_loss:.4f} | Val Loss: {v_loss:.4f}")
        
        if v_loss < best_loss:
            best_loss = v_loss
            torch.save(model.state_dict(), "custom_bc_master.pth")
            
    print("Training Complete! Best model saved as custom_bc_master.pth")

if __name__ == "__main__":
    train()
