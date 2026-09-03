import sys
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader
from stable_baselines3 import PPO
from stable_baselines3.common.torch_layers import BaseFeaturesExtractor
import gymnasium as gym
from gymnasium import spaces

BOARD_SIZE = 10

class CNN_MLP_Extractor(BaseFeaturesExtractor):
    def __init__(self, observation_space: gym.Space, features_dim: int = 128):
        super().__init__(observation_space, features_dim)
        spatial_shape = observation_space.spaces["spatial"].shape
        scalar_dim = observation_space.spaces["scalar"].shape[0]
        
        self.cnn = nn.Sequential(
            nn.Conv2d(spatial_shape[0], 16, kernel_size=3, stride=1, padding=1),
            nn.ReLU(),
            nn.Conv2d(16, 32, kernel_size=3, stride=1, padding=1),
            nn.ReLU(),
            nn.Flatten(),
        )
        with torch.no_grad():
            sample_spatial = torch.zeros(1, *spatial_shape)
            n_flatten = self.cnn(sample_spatial).shape[1]
            
        self.mlp = nn.Sequential(
            nn.Linear(scalar_dim, 256),
            nn.LayerNorm(256),
            nn.ReLU(),
            nn.Linear(256, 256),
            nn.LayerNorm(256),
            nn.ReLU()
        )
        self.fc = nn.Sequential(
            nn.Linear(n_flatten + 256, features_dim),
            nn.ReLU()
        )

    def forward(self, observations) -> torch.Tensor:
        spatial = observations["spatial"]
        scalar = observations["scalar"]
        cnn_out = self.cnn(spatial)
        mlp_out = self.mlp(scalar)
        combined = torch.cat((cnn_out, mlp_out), dim=1)
        return self.fc(combined)

class ReplayDataset(Dataset):
    def __init__(self, X_scal, X_spat, Y):
        self.X_scal = torch.FloatTensor(X_scal)
        self.X_spat = torch.FloatTensor(X_spat)
        self.Y = torch.FloatTensor(Y)
        
    def __len__(self):
        return len(self.Y)
        
    def __getitem__(self, idx):
        return {"scalar": self.X_scal[idx], "spatial": self.X_spat[idx]}, self.Y[idx]

def train_behavioral_cloning():
    print("Loading Tensors...")
    X_scalar = np.load("X_scalar.npy")
    X_spatial = np.load("X_spatial.npy")
    Y_actions = np.load("Y_actions.npy")
    print(f"Loaded {len(X_scalar)} frames of Grandmaster data!")
    
    # 90-10 Split
    split = int(0.9 * len(X_scalar))
    train_ds = ReplayDataset(X_scalar[:split], X_spatial[:split], Y_actions[:split])
    val_ds = ReplayDataset(X_scalar[split:], X_spatial[split:], Y_actions[split:])
    
    train_loader = DataLoader(train_ds, batch_size=256, shuffle=True)
    val_loader = DataLoader(val_ds, batch_size=256, shuffle=False)

    # Initialize a dummy Gym Environment to create the SB3 model architecture
    env = gym.make("CartPole-v1") # Doesn't matter, we will override spaces
    env.observation_space = spaces.Dict({
        "scalar": spaces.Box(low=-np.inf, high=np.inf, shape=(50,), dtype=np.float32),
        "spatial": spaces.Box(low=-np.inf, high=np.inf, shape=(4, BOARD_SIZE, BOARD_SIZE), dtype=np.float32)
    })
    env.action_space = spaces.Box(low=0.0, high=1.0, shape=(17,), dtype=np.float32)
    
    policy_kwargs = dict(
        features_extractor_class=CNN_MLP_Extractor,
        features_extractor_kwargs=dict(features_dim=128),
    )
    
    print("Initializing Stable Baselines 3 Policy Network...")
    model = PPO("MultiInputPolicy", env, policy_kwargs=policy_kwargs, verbose=0)
    policy = model.policy
    
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    policy.to(device)
    
    optimizer = optim.AdamW(policy.parameters(), lr=1e-3, weight_decay=1e-5)
    criterion = nn.MSELoss()
    
    epochs = 20
    for epoch in range(epochs):
        policy.train()
        train_loss = 0
        for obs_dict, y in train_loader:
            obs_dict = {k: v.to(device) for k, v in obs_dict.items()}
            y = y.to(device)
            
            # Extract features using our CNN_MLP_Extractor
            features = policy.extract_features(obs_dict)
            # The continuous action head outputs mean and log_std (we only care about mean)
            action_mean = policy.action_net(policy.mlp_extractor.forward_actor(features))
            
            loss = criterion(action_mean, y)
            
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
            train_loss += loss.item()
            
        policy.eval()
        val_loss = 0
        with torch.no_grad():
            for obs_dict, y in val_loader:
                obs_dict = {k: v.to(device) for k, v in obs_dict.items()}
                y = y.to(device)
                features = policy.extract_features(obs_dict)
                action_mean = policy.action_net(policy.mlp_extractor.forward_actor(features))
                val_loss += criterion(action_mean, y).item()
                
        print(f"Epoch {epoch+1}/{epochs} | Train Loss: {train_loss/len(train_loader):.4f} | Val Loss: {val_loss/len(val_loader):.4f}")

    print("Training Complete! Saving as SB3 zip format...")
    model.save("ppo_bc_master")
    print("Successfully saved ppo_bc_master.zip. Ready for Curriculum Fine-Tuning!")

if __name__ == "__main__":
    train_behavioral_cloning()
