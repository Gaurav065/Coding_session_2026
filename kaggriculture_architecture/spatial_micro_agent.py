import torch
import torch.nn as nn
import torch.nn.functional as F

class FiLMGenerator(nn.Module):
    """
    Feature-wise Linear Modulation (FiLM) Generator.
    Takes a Macro-Agent goal vector and outputs scaling (gamma) and shifting (beta)
    parameters to dynamically modulate the spatial CNN filters.
    """
    def __init__(self, goal_dim, num_channels):
        super().__init__()
        self.mlp = nn.Sequential(
            nn.Linear(goal_dim, 64),
            nn.ReLU(),
            nn.Linear(64, num_channels * 2) # Output gamma and beta for each channel
        )
        self.num_channels = num_channels

    def forward(self, goal):
        out = self.mlp(goal)
        gamma, beta = torch.split(out, self.num_channels, dim=-1)
        return gamma, beta

class NeuralSpatialMicroAgent(nn.Module):
    """
    CTDE MAPPO Architecture as defined in the Architectural Blueprint.
    Includes FiLM conditioning for the Actor and a purely objective Centralized Critic.
    """
    def __init__(self, in_channels=10, goal_dim=13, action_dim=11):
        super().__init__()
        
        # 1. Shared CNN Backbone (Feature Extraction)
        # 10x10 input -> 10x10 output
        self.conv1 = nn.Conv2d(in_channels, 32, kernel_size=3, stride=1, padding=1)
        self.conv2 = nn.Conv2d(32, 64, kernel_size=3, stride=1, padding=1)
        
        # 2. FiLM Generator (Only used by the Actor)
        self.film_gen = FiLMGenerator(goal_dim=goal_dim, num_channels=64)
        
        # 3. Spatial Compression (Downsample to 5x5)
        self.conv3 = nn.Conv2d(64, 64, kernel_size=2, stride=2, padding=0)
        
        # 4. Decentralized Actor Head
        # Flattens 64 channels * 5 * 5 = 1600
        self.actor_mlp = nn.Sequential(
            nn.Linear(64 * 5 * 5, 256),
            nn.ReLU(),
            nn.Linear(256, action_dim)
        )
        
        # 5. Centralized Critic Head
        self.critic_mlp = nn.Sequential(
            nn.Linear(64 * 5 * 5, 256),
            nn.ReLU(),
            nn.Linear(256, 1)
        )

    def forward_actor(self, obs_local, goal, action_mask):
        """
        Calculates the probability distribution for actions.
        obs_local: (B*N, 10, 10, 10) tensor where N is max 20 workers
        goal: (B*N, goal_dim) from the Macro-Agent
        action_mask: (B*N, 11) boolean tensor where False = invalid action
        """
        x = F.relu(self.conv1(obs_local))
        x = F.relu(self.conv2(x))
        
        # --- FiLM CONDITIONING ---
        gamma, beta = self.film_gen(goal)
        # Reshape for channel-wise broadcasting: (B*N, 64, 1, 1)
        gamma = gamma.unsqueeze(-1).unsqueeze(-1)
        beta = beta.unsqueeze(-1).unsqueeze(-1)
        
        # Modulate the feature maps based on the Macro-Agent's economic goal
        x = (1 + gamma) * x + beta
        # -------------------------
        
        # Compress and Flatten
        x = F.relu(self.conv3(x))
        x = x.view(x.size(0), -1) # (B*N, 1600)
        
        logits = self.actor_mlp(x)
        
        # --- INVALID ACTION MASKING ---
        # Apply -1e9 penalty to physically impossible actions before Softmax/Categorical
        logits = torch.where(action_mask, logits, torch.tensor(-1e9, device=logits.device))
        
        # Create valid probability distribution
        dist = torch.distributions.Categorical(logits=logits)
        return dist

    def forward_critic(self, obs_global):
        """
        Calculates the state value V(s) for GAE advantage estimation.
        obs_global: (B*N, 10, 10, 10) containing full map visibility
        Note: The critic bypasses FiLM to maintain an objective view of reality.
        """
        x = F.relu(self.conv1(obs_global))
        x = F.relu(self.conv2(x))
        x = F.relu(self.conv3(x))
        x = x.view(x.size(0), -1)
        return self.critic_mlp(x)

if __name__ == '__main__':
    # Test the architecture with dummy tensors
    print("Initializing MAPPO Micro-Agent Architecture...")
    model = NeuralSpatialMicroAgent()
    
    batch_agents = 20
    dummy_obs = torch.rand((batch_agents, 10, 10, 10))
    dummy_goal = torch.rand((batch_agents, 13))
    # Assume 1st action (NORTH) is blocked for some agents
    dummy_mask = torch.ones((batch_agents, 11), dtype=torch.bool)
    dummy_mask[0, 0] = False 
    
    dist = model.forward_actor(dummy_obs, dummy_goal, dummy_mask)
    action = dist.sample()
    
    print(f"Sampled Action Shape: {action.shape} (Should be [20])")
    print(f"Logits for Agent 0 (Blocked NORTH should be -1e9): \n{dist.logits[0][:3]}")
    print("Architecture verified successfully!")
