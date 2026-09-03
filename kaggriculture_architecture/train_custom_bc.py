import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader
from custom_architecture import KaggricultureLSTM

class LSTMReplayDataset(Dataset):
    def __init__(self, X_scal, X_spat, Y):
        self.X_scal = torch.FloatTensor(X_scal)
        self.X_spat = torch.FloatTensor(X_spat)
        
        # SLICE THE 17D Y TENSOR TO 13D (Remove Tomato, Goose, Egg)
        # 17D Indices: 
        # Buy: [0:W, 1:C, 2:T, 3:S, 4:M, 5:G, 6:Cow, 7:Sheep] -> Drop 2, 5
        # Hire: [8] -> Keep 8
        # Sell: [9:W, 10:C, 11:T, 12:S, 13:M, 14:E, 15:Milk, 16:Wool] -> Drop 11, 14
        indices_to_keep = [0, 1, 3, 4, 6, 7, 8, 9, 10, 12, 13, 15, 16]
        self.Y = torch.FloatTensor(Y)[:, :, indices_to_keep]
        
    def __len__(self):
        return len(self.Y)
        
    def __getitem__(self, idx):
        return self.X_spat[idx], self.X_scal[idx], self.Y[idx]

def train():
    print("Loading sequential tensors...")
    try:
        X_scalar = np.load("X_scalar_seq.npy")
        X_spatial = np.load("X_spatial_seq.npy")
        Y_actions = np.load("Y_actions_seq.npy")
    except FileNotFoundError:
        print("ERROR: Sequential tensors not found. Please run 'python prepare_lstm_data.py' first.")
        return
        
    print(f"Loaded {len(X_scalar)} sequences of length 10.")
    
    split = int(0.9 * len(X_scalar))
    train_ds = LSTMReplayDataset(X_scalar[:split], X_spatial[:split], Y_actions[:split])
    val_ds = LSTMReplayDataset(X_scalar[split:], X_spatial[split:], Y_actions[split:])
    
    train_loader = DataLoader(train_ds, batch_size=64, shuffle=True)
    val_loader = DataLoader(val_ds, batch_size=64, shuffle=False)
    
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Training 13D LSTM on {device}...")
    
    model = KaggricultureLSTM().to(device)
    optimizer = optim.AdamW(model.parameters(), lr=5e-4, weight_decay=1e-5)
    criterion = nn.MSELoss()
    
    epochs = 30
    best_loss = float('inf')
    
    for epoch in range(epochs):
        model.train()
        train_loss = 0
        for spat, scal, y in train_loader:
            spat, scal, y = spat.to(device), scal.to(device), y.to(device)
            optimizer.zero_grad()
            
            batch_size = spat.size(0)
            h0 = torch.zeros(1, batch_size, model.hidden_size).to(device)
            c0 = torch.zeros(1, batch_size, model.hidden_size).to(device)
            
            preds, _, _ = model(spat, scal, (h0, c0))
            
            loss = criterion(preds, y)
            loss.backward()
            optimizer.step()
            train_loss += loss.item()
            
        model.eval()
        val_loss = 0
        with torch.no_grad():
            for spat, scal, y in val_loader:
                spat, scal, y = spat.to(device), scal.to(device), y.to(device)
                batch_size = spat.size(0)
                h0 = torch.zeros(1, batch_size, model.hidden_size).to(device)
                c0 = torch.zeros(1, batch_size, model.hidden_size).to(device)
                preds, _, _ = model(spat, scal, (h0, c0))
                val_loss += criterion(preds, y).item()
                
        t_loss = train_loss / len(train_loader)
        v_loss = val_loss / len(val_loader)
        print(f"Epoch {epoch+1:02d}/{epochs} | Train Loss: {t_loss:.4f} | Val Loss: {v_loss:.4f}")
        
        if v_loss < best_loss:
            best_loss = v_loss
            torch.save(model.state_dict(), "lstm_bc_master.pth")
            
    print("Training Complete! Best model saved as lstm_bc_master.pth")

if __name__ == "__main__":
    train()
