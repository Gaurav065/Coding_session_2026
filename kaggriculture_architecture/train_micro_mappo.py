import torch
import torch.nn as nn
import torch.optim as optim
import numpy as np
from spatial_micro_agent import NeuralSpatialMicroAgent
import torch.nn.functional as F

# --- ISOLATED MICRO ENVIRONMENT ---
class MicroEnv:
    """
    Isolated 10x10 grid environment to train the Micro-Agent's spatial navigation
    using Potential-Based Reward Shaping (PBRS).
    """
    def __init__(self):
        self.grid_size = 10
        self.max_steps = 50
        self.gamma = 0.99
        self.reset()

    def reset(self):
        self.steps = 0
        # Random spawn
        self.wx, self.wy = np.random.randint(0, self.grid_size, size=2)
        
        # Random target (e.g., pretending to go to a crop or the shed)
        self.tx, self.ty = np.random.randint(0, self.grid_size, size=2)
        while self.tx == self.wx and self.ty == self.wy:
            self.tx, self.ty = np.random.randint(0, self.grid_size, size=2)
            
        self.potential = self._calculate_potential()
        return self._get_obs(), self._get_mask(), self._get_goal()

    def _calculate_potential(self):
        # Manhattan distance to target
        dist = abs(self.wx - self.tx) + abs(self.wy - self.ty)
        # Potential increases as distance decreases
        return 100.0 - dist

    def _get_obs(self):
        # 10 Channels: [Ego, Allies, Shed, Wheat, Water, Fertilizer, Q1, Q2, Q3, Q4]
        obs = np.zeros((10, self.grid_size, self.grid_size), dtype=np.float32)
        obs[0, self.wy, self.wx] = 1.0 # Ego
        obs[3, self.ty, self.tx] = 1.0 # Target (Pretending it's a wheat crop)
        
        # Quadrants
        obs[6, 0:5, 0:5] = 1.0
        obs[7, 0:5, 5:10] = 1.0
        obs[8, 5:10, 0:5] = 1.0
        obs[9, 5:10, 5:10] = 1.0
        return obs

    def _get_mask(self):
        # Actions: 0:N, 1:S, 2:E, 3:W, 4:PICKUP, 5:DROP, 6:PLANT, 7:WATER, 8:DIG, 9:FERTILIZE, 10:NOOP
        mask = np.ones(11, dtype=bool)
        if self.wy == 0: mask[0] = False # NORTH blocked
        if self.wy == self.grid_size - 1: mask[1] = False # SOUTH blocked
        if self.wx == self.grid_size - 1: mask[2] = False # EAST blocked
        if self.wx == 0: mask[3] = False # WEST blocked
        
        # We only care about movement in this isolated navigation test
        for i in range(4, 10): mask[i] = False 
        return mask

    def _get_goal(self):
        # 13-dim Goal vector from Macro-Agent. 
        # For this test, we just pass a normalized coordinate representation of the target.
        goal = np.zeros(13, dtype=np.float32)
        goal[0] = self.tx / 10.0
        goal[1] = self.ty / 10.0
        return goal

    def step(self, action):
        self.steps += 1
        
        # Execute Movement
        if action == 0 and self.wy > 0: self.wy -= 1
        elif action == 1 and self.wy < self.grid_size - 1: self.wy += 1
        elif action == 2 and self.wx < self.grid_size - 1: self.wx += 1
        elif action == 3 and self.wx > 0: self.wx -= 1
            
        # PBRS Reward Calculation: F = gamma * Phi(s') - Phi(s)
        new_potential = self._calculate_potential()
        reward = (self.gamma * new_potential) - self.potential
        self.potential = new_potential
        
        done = False
        # Terminal condition: Reached target
        if self.wx == self.tx and self.wy == self.ty:
            reward += 10.0 # Massive spike for completion
            done = True
        elif self.steps >= self.max_steps:
            done = True
            
        return self._get_obs(), reward, done, self._get_mask(), self._get_goal()

# --- MAPPO TRAINING LOOP ---
def train_mappo():
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Training Spatial Micro-Agent on {device}...")
    
    agent = NeuralSpatialMicroAgent().to(device)
    optimizer = optim.Adam(agent.parameters(), lr=5e-4)
    
    env = MicroEnv()
    
    epochs = 1000
    batch_size = 64
    
    for epoch in range(epochs):
        # Rollout buffers
        b_obs, b_goal, b_mask, b_act, b_logprob, b_ret, b_adv = [], [], [], [], [], [], []
        
        # Collect trajectories
        for _ in range(batch_size):
            obs, mask, goal = env.reset()
            
            ep_obs, ep_goal, ep_mask, ep_act, ep_logp, ep_rew, ep_val = [], [], [], [], [], [], []
            
            while True:
                o_t = torch.tensor(obs, dtype=torch.float32).unsqueeze(0).to(device)
                g_t = torch.tensor(goal, dtype=torch.float32).unsqueeze(0).to(device)
                m_t = torch.tensor(mask, dtype=torch.bool).unsqueeze(0).to(device)
                
                with torch.no_grad():
                    dist = agent.forward_actor(o_t, g_t, m_t)
                    val = agent.forward_critic(o_t)
                    
                    action = dist.sample()
                    logp = dist.log_prob(action)
                    
                a = action.item()
                next_obs, reward, done, next_mask, next_goal = env.step(a)
                
                ep_obs.append(obs)
                ep_goal.append(goal)
                ep_mask.append(mask)
                ep_act.append(a)
                ep_logp.append(logp.item())
                ep_rew.append(reward)
                ep_val.append(val.item())
                
                obs, mask, goal = next_obs, next_mask, next_goal
                if done: break
                    
            # Compute GAE & Returns for the episode
            returns = []
            advantages = []
            gae = 0
            for t in reversed(range(len(ep_rew))):
                if t == len(ep_rew) - 1:
                    next_val = 0.0
                else:
                    next_val = ep_val[t+1]
                
                delta = ep_rew[t] + 0.99 * next_val - ep_val[t]
                gae = delta + 0.99 * 0.95 * gae
                
                returns.insert(0, gae + ep_val[t])
                advantages.insert(0, gae)
                
            b_obs.extend(ep_obs)
            b_goal.extend(ep_goal)
            b_mask.extend(ep_mask)
            b_act.extend(ep_act)
            b_logprob.extend(ep_logp)
            b_ret.extend(returns)
            b_adv.extend(advantages)
            
        # --- PPO UPDATE ---
        b_obs = torch.tensor(np.array(b_obs), dtype=torch.float32).to(device)
        b_goal = torch.tensor(np.array(b_goal), dtype=torch.float32).to(device)
        b_mask = torch.tensor(np.array(b_mask), dtype=torch.bool).to(device)
        b_act = torch.tensor(b_act, dtype=torch.long).to(device)
        b_logprob = torch.tensor(b_logprob, dtype=torch.float32).to(device)
        b_ret = torch.tensor(b_ret, dtype=torch.float32).to(device).unsqueeze(1)
        b_adv = torch.tensor(b_adv, dtype=torch.float32).to(device).unsqueeze(1)
        
        # Normalize advantages
        b_adv = (b_adv - b_adv.mean()) / (b_adv.std() + 1e-8)
        
        # Forward pass for optimization
        dist = agent.forward_actor(b_obs, b_goal, b_mask)
        values = agent.forward_critic(b_obs)
        
        new_logprob = dist.log_prob(b_act)
        ratio = torch.exp(new_logprob - b_logprob)
        
        # Clipped Surrogate Loss
        clip_adv = torch.clamp(ratio, 1 - 0.2, 1 + 0.2) * b_adv
        actor_loss = -torch.min(ratio * b_adv, clip_adv).mean()
        
        # Critic Loss
        critic_loss = F.mse_loss(values, b_ret)
        
        # Entropy Regularization (Decaying from 0.01 to 0.001)
        entropy_coef = max(0.001, 0.01 * (1.0 - epoch / epochs))
        entropy_loss = -dist.entropy().mean() * entropy_coef
        
        loss = actor_loss + critic_loss + entropy_loss
        
        optimizer.zero_grad()
        loss.backward()
        optimizer.step()
        
        if epoch % 20 == 0:
            print(f"Epoch {epoch:3d}/1000 | Mean Return: {b_ret.mean().item():.3f} | Actor Loss: {actor_loss.item():.4f} | Critic Loss: {critic_loss.item():.4f}")

    torch.save(agent.state_dict(), "micro_agent_mappo.pth")
    print("Training Complete! Saved 'micro_agent_mappo.pth'")

if __name__ == '__main__':
    train_mappo()
