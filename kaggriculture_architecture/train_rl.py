import os
import torch
import torch.nn as nn
import torch.optim as optim
import numpy as np
import time

# Import our custom architectures
from spatial_micro_agent import NeuralSpatialMicroAgent
from macro_agent import MacroEconomyAgent

class RolloutBuffer:
    def __init__(self):
        self.spatial_states = []
        self.scalar_states = []
        self.actions = []
        self.logprobs = []
        self.rewards = []
        self.values = []
        self.dones = []

    def clear(self):
        self.spatial_states.clear()
        self.scalar_states.clear()
        self.actions.clear()
        self.logprobs.clear()
        self.rewards.clear()
        self.values.clear()
        self.dones.clear()

def train_ppo():
    print("Initializing Phase 3: MAPPO Reinforcement Learning...")
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Targeting device: {device}")

    # 1. Load the Pre-Trained Micro-Agent (Frozen executioner)
    print("Loading pre-trained Micro-Agent (BC Epoch 3)...")
    micro_agent = NeuralSpatialMicroAgent(in_channels=20, goal_dim=100, action_dim=11).to(device)
    
    weights_path = "training_weights/micro_agent_bc_epoch_3.pth"
    if os.path.exists(weights_path):
        micro_agent.load_state_dict(torch.load(weights_path, map_location=device))
        print("Micro-Agent weights loaded successfully!")
    else:
        print(f"WARNING: Could not find {weights_path}. Make sure it is in the working directory on Kaggle!")
    
    # Freeze Micro-Agent to save VRAM and focus training on the Macro-Agent
    micro_agent.eval()
    for param in micro_agent.parameters():
        param.requires_grad = False

    # 2. Initialize the Blank-Slate Macro-Agent (The Manager)
    print("Initializing Autoregressive Macro-Economy Agent...")
    macro_agent = MacroEconomyAgent(input_dim=100, d_model=256, n_layers=4).to(device)
    
    # 3. PPO Optimizer
    optimizer = optim.AdamW(macro_agent.parameters(), lr=3e-4, weight_decay=1e-4)
    scaler = torch.cuda.amp.GradScaler(enabled=torch.cuda.is_available())
    
    print("\n" + "="*50)
    print("RL Pipeline Ready for Kaggle Environments Simulation!")
    print("To execute full training, we must connect this to the Kaggle kaggle_environments engine.")
    print("="*50 + "\n")
    
    # This acts as the entry point wrapper for Kaggle's environment unrolling
    return micro_agent, macro_agent, optimizer

if __name__ == "__main__":
    train_ppo()
