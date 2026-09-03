import sys
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from torch.distributions import Normal
import gymnasium as gym
from gymnasium import spaces

sys.path.insert(0, r"C:\Coding\kaggriculture_architecture")
sys.path.insert(0, r"C:\Coding\kaggriculture")

from custom_architecture import KaggricultureResNet
from train_day9_curriculum import Day9CurriculumEnv

def load_pretrained_weights(model, path="custom_bc_master.pth"):
    # Load BC weights into the new PPO-ready ResNet (handling the Critic Head mismatch)
    print(f"Loading Pre-trained BC weights from {path}...")
    bc_dict = torch.load(path, map_location="cpu", weights_only=True)
    model_dict = model.state_dict()
    
    # Map the old 'fusion' weights to 'actor_head'
    # Old: fusion.0 (Linear), fusion.1 (LayerNorm), fusion.3 (Linear)
    # New: fusion.0, fusion.1 (shared), actor_head.0 (Linear)
    
    mapped_dict = {}
    for k, v in bc_dict.items():
        if "fusion.3" in k:
            new_k = k.replace("fusion.3", "actor_head.0")
            mapped_dict[new_k] = v
        else:
            mapped_dict[k] = v
            
    # Graft mapped weights into current model
    for k, v in mapped_dict.items():
        if k in model_dict:
            model_dict[k] = v
        else:
            print(f"Skipping unknown key: {k}")
            
    model.load_state_dict(model_dict, strict=False)
    print("Pre-trained weights successfully loaded! (Critic Head initialized randomly)")
    return model

def compute_gae(rewards, values, dones, next_value, next_done, gamma=0.99, lam=0.95):
    advantages = torch.zeros_like(rewards)
    lastgaelam = 0
    for t in reversed(range(len(rewards))):
        if t == len(rewards) - 1:
            nextnonterminal = 1.0 - next_done
            nextvalues = next_value
        else:
            nextnonterminal = 1.0 - dones[t + 1]
            nextvalues = values[t + 1]
        delta = rewards[t] + gamma * nextvalues * nextnonterminal - values[t]
        advantages[t] = lastgaelam = delta + gamma * lam * nextnonterminal * lastgaelam
    returns = advantages + values
    return advantages, returns

def train_ppo():
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Running PPO Curriculum on {device}")
    
    env = Day9CurriculumEnv()
    
    model = KaggricultureResNet().to(device)
    model = load_pretrained_weights(model)
    
    optimizer = optim.Adam(model.parameters(), lr=3e-4, eps=1e-5)
    
    # PPO Hyperparams
    num_steps = 256
    batch_size = 64
    epochs_per_update = 4
    clip_coef = 0.2
    ent_coef = 0.01
    vf_coef = 0.5
    total_timesteps = 50000
    
    # Storage
    obs_spatial = torch.zeros((num_steps, 4, 10, 10)).to(device)
    obs_scalar = torch.zeros((num_steps, 50)).to(device)
    actions = torch.zeros((num_steps, 17)).to(device)
    logprobs = torch.zeros((num_steps, 17)).to(device)
    rewards = torch.zeros(num_steps).to(device)
    dones = torch.zeros(num_steps).to(device)
    values = torch.zeros(num_steps).to(device)
    
    global_step = 0
    num_updates = total_timesteps // num_steps
    
    # Action standard deviation (log scale, learnable)
    action_logstd = nn.Parameter(torch.zeros(17).to(device))
    optimizer.add_param_group({'params': [action_logstd]})
    
    obs_dict, _ = env.reset()
    next_spatial = torch.Tensor(obs_dict["spatial"]).unsqueeze(0).to(device)
    next_scalar = torch.Tensor(obs_dict["scalar"]).unsqueeze(0).to(device)
    next_done = torch.zeros(1).to(device)
    
    for update in range(1, num_updates + 1):
        model.eval()
        for step in range(0, num_steps):
            global_step += 1
            obs_spatial[step] = next_spatial[0]
            obs_scalar[step] = next_scalar[0]
            dones[step] = next_done[0]
            
            with torch.no_grad():
                action_mean, value = model(next_spatial, next_scalar)
                values[step] = value.flatten()
            
            # Sample continuous actions via Normal dist
            action_std = torch.exp(action_logstd)
            probs = Normal(action_mean, action_std)
            action = probs.sample()
            logprob = probs.log_prob(action)
            
            # Clip action to env bounds [0, 1]
            clipped_action = torch.clamp(action, 0.0, 1.0)
            
            actions[step] = action[0]
            logprobs[step] = logprob[0]
            
            obs_dict, reward, done, _, _ = env.step(clipped_action[0].cpu().numpy())
            
            rewards[step] = reward
            next_spatial = torch.Tensor(obs_dict["spatial"]).unsqueeze(0).to(device)
            next_scalar = torch.Tensor(obs_dict["scalar"]).unsqueeze(0).to(device)
            next_done = torch.Tensor([done]).to(device)
            
            if done:
                obs_dict, _ = env.reset()
                next_spatial = torch.Tensor(obs_dict["spatial"]).unsqueeze(0).to(device)
                next_scalar = torch.Tensor(obs_dict["scalar"]).unsqueeze(0).to(device)
                
        # Calculate Advantages
        with torch.no_grad():
            _, next_value = model(next_spatial, next_scalar)
            advantages, returns = compute_gae(rewards, values, dones, next_value.flatten(), next_done)
            
        # PPO Update
        model.train()
        b_inds = np.arange(num_steps)
        clipfracs = []
        
        for epoch in range(epochs_per_update):
            np.random.shuffle(b_inds)
            for start in range(0, num_steps, batch_size):
                end = start + batch_size
                mb_inds = b_inds[start:end]
                
                mb_spatial = obs_spatial[mb_inds]
                mb_scalar = obs_scalar[mb_inds]
                mb_actions = actions[mb_inds]
                mb_advantages = advantages[mb_inds]
                mb_returns = returns[mb_inds]
                mb_logprobs = logprobs[mb_inds]
                
                new_mean, new_value = model(mb_spatial, mb_scalar)
                new_std = torch.exp(action_logstd)
                probs = Normal(new_mean, new_std)
                
                new_logprob = probs.log_prob(mb_actions)
                entropy = probs.entropy().mean()
                logratio = new_logprob - mb_logprobs
                ratio = logratio.exp()
                
                # Advantage Normalization
                mb_advantages = (mb_advantages - mb_advantages.mean()) / (mb_advantages.std() + 1e-8)
                
                # Actor Loss
                pg_loss1 = -mb_advantages.unsqueeze(1) * ratio
                pg_loss2 = -mb_advantages.unsqueeze(1) * torch.clamp(ratio, 1 - clip_coef, 1 + clip_coef)
                pg_loss = torch.max(pg_loss1, pg_loss2).mean()
                
                # Critic Loss
                v_loss = 0.5 * ((new_value.flatten() - mb_returns) ** 2).mean()
                
                # Total Loss
                loss = pg_loss - ent_coef * entropy + v_loss * vf_coef
                
                optimizer.zero_grad()
                loss.backward()
                nn.utils.clip_grad_norm_(model.parameters(), 0.5)
                optimizer.step()
                
        print(f"Update {update}/{num_updates} | Mean Reward: {rewards.sum().item()/(dones.sum().item()+1e-8):.3f} | Value Loss: {v_loss.item():.4f}")

    print("Curriculum PPO Complete! Saving super-human weights...")
    torch.save(model.state_dict(), "ppo_day9_superhuman.pth")

if __name__ == "__main__":
    train_ppo()
