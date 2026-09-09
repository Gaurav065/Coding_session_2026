import os
import glob
import json
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader
import multiprocessing
from spatial_micro_agent import NeuralSpatialMicroAgent

# Optimize PyTorch CPU threading
num_cores = multiprocessing.cpu_count()
torch.set_num_threads(num_cores)

class ChunkedKaggricultureDataset(Dataset):
    """
    Optimized Dataset that lazily loads .npz chunks into memory.
    Using map-style dataset requires loading all data to index it, 
    so we load one chunk at a time, but since DataLoader workers 
    fork, we must handle chunk memory carefully.
    To maximize CPU threading, we load all metadata and map indices.
    """
    def __init__(self, data_dir="data"):
        self.chunk_files = sorted(glob.glob(os.path.join(data_dir, "elite_1900_chunk_*.npz")))
        print(f"Found {len(self.chunk_files)} chunks for training.")
        
        # Build an index map
        self.chunk_sizes = []
        for file in self.chunk_files:
            # We assume exactly 50000 frames per chunk except the last one
            # To be precise, we can check file sizes, but let's assume 50000 
            # to avoid opening all 150+ files during init.
            # Actually, opening .npz just to read shape is fast enough.
            with np.load(file) as data:
                self.chunk_sizes.append(data['spatial'].shape[0])
                
        self.cumulative_sizes = np.cumsum(self.chunk_sizes)
        self.total_samples = self.cumulative_sizes[-1]
        
        # Cache for the currently loaded chunk to avoid disk I/O bottlenecks
        self.current_chunk_idx = -1
        self.current_data = None
        
        # Action mappings
        self.action_to_idx = {
            "NORTH": 0, "SOUTH": 1, "EAST": 2, "WEST": 3,
            "PICKUP": 4, "DROP": 5, "PLANT": 6, "WATER": 7, 
            "DIG": 8, "FERTILIZE": 9
        }

    def __len__(self):
        return self.total_samples

    def _load_chunk(self, chunk_idx):
        if self.current_chunk_idx != chunk_idx:
            # print(f"Worker loading chunk {chunk_idx}...")
            data = np.load(self.chunk_files[chunk_idx])
            self.current_data = {
                'spatial': data['spatial'],
                'scalar': data['scalar'],
                'micro': data['micro']
            }
            self.current_chunk_idx = chunk_idx

    def __getitem__(self, idx):
        # Find which chunk this index belongs to
        chunk_idx = np.searchsorted(self.cumulative_sizes, idx, side='right')
        
        # Calculate local index within the chunk
        if chunk_idx == 0:
            local_idx = idx
        else:
            local_idx = idx - self.cumulative_sizes[chunk_idx - 1]
            
        self._load_chunk(chunk_idx)
        
        spatial = self.current_data['spatial'][local_idx]
        scalar = self.current_data['scalar'][local_idx]
        micro_str = self.current_data['micro'][local_idx]
        
        # --- Multi-threaded CPU Parsing ---
        # The CPU workers will handle this heavy JSON parsing in parallel
        try:
            action_dict = json.loads(micro_str)
        except:
            action_dict = {}
            
        action_idx = 10 # Default to NOOP
        if isinstance(action_dict, dict) and "type" in action_dict:
            atype = action_dict["type"]
            if atype in self.action_to_idx:
                action_idx = self.action_to_idx[atype]
                
        # Generate dummy mask for BC (all valid)
        mask = np.ones(11, dtype=bool)
        
        # Cast to proper torch types
        spatial_tensor = torch.tensor(spatial, dtype=torch.float32) # Network expects float32
        scalar_tensor = torch.tensor(scalar, dtype=torch.float32)
        mask_tensor = torch.tensor(mask, dtype=torch.bool)
        action_target = torch.tensor(action_idx, dtype=torch.long)
        
        return spatial_tensor, scalar_tensor, mask_tensor, action_target

def train_bc():
    print(f"Initializing Multi-Threaded CPU Training across {num_cores} cores...")
    
    # Initialize the SOTA Architecture
    model = NeuralSpatialMicroAgent(in_channels=20, goal_dim=100, action_dim=11)
    
    # Automatically use Kaggle GPU if available
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Targeting device: {device}")
    model.to(device)
    
    optimizer = optim.AdamW(model.parameters(), lr=1e-3, weight_decay=1e-4)
    criterion = nn.CrossEntropyLoss()
    
    dataset = ChunkedKaggricultureDataset("data")
    
    # Multi-threaded DataLoader
    # num_workers allows parallel CPU processes to read chunks and parse JSON simultaneously
    workers = min(8, num_cores) 
    dataloader = DataLoader(
        dataset, 
        batch_size=256, 
        shuffle=True, 
        num_workers=workers,
        pin_memory=False
    )
    
    epochs = 3
    print(f"Starting Behavioral Cloning (Bootstrapping) for {epochs} epochs on {dataset.total_samples} frames...")
    
    model.train()
    for epoch in range(epochs):
        total_loss = 0.0
        correct = 0
        total = 0
        
        for batch_idx, (spatial, scalar, mask, target) in enumerate(dataloader):
            spatial, scalar, mask, target = spatial.to(device), scalar.to(device), mask.to(device), target.to(device)
            
            optimizer.zero_grad()
            
            # Forward pass
            action_logits, _ = model(spatial, scalar)
            
            # Apply invalid action mask (though all are valid in BC parsing currently)
            action_logits = torch.where(mask, action_logits, torch.tensor(-1e9, device=device))
            
            loss = criterion(action_logits, target)
            loss.backward()
            
            # Gradient clipping to ensure stability
            torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=0.5)
            optimizer.step()
            
            total_loss += loss.item()
            
            # Calculate accuracy
            _, predicted = action_logits.max(1)
            total += target.size(0)
            correct += predicted.eq(target).sum().item()
            
            if batch_idx % 100 == 0:
                acc = 100. * correct / total
                print(f"Epoch: {epoch+1}/{epochs} | Batch: {batch_idx}/{len(dataloader)} | Loss: {loss.item():.4f} | Acc: {acc:.2f}%")
                
        # Save checkpoint after each epoch
        torch.save(model.state_dict(), f"micro_agent_bc_epoch_{epoch+1}.pth")
        print(f"Epoch {epoch+1} completed. Average Loss: {total_loss/len(dataloader):.4f}. Model saved.")

if __name__ == '__main__':
    # Required for Windows multiprocessing
    multiprocessing.freeze_support()
    train_bc()
