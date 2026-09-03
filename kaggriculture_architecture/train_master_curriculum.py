import sys
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from torch.distributions import Normal
import gymnasium as gym
from gymnasium import spaces
import argparse
import os

sys.path.insert(0, r"C:\Coding\kaggriculture_architecture")
sys.path.insert(0, r"C:\Coding\kaggriculture")

from custom_architecture import KaggricultureLSTM
from project_maestro.engine.fast_engine import FastGame
import hrl_heuristic_agent

BOARD_SIZE = 10

class MasterCurriculumEnv(gym.Env):
    def __init__(self, start_day, end_day, base_weights_path):
        super().__init__()
        self.start_day = start_day
        self.end_day = end_day
        self.steps_per_macro = 24
        
        self.start_macro = start_day
        self.end_macro = end_day
        self.max_macro_steps = end_day - start_day 
        
        self.action_space = spaces.Box(low=0.0, high=1.0, shape=(13,), dtype=np.float32)
        self.observation_space = spaces.Dict({
            "scalar": spaces.Box(low=-np.inf, high=np.inf, shape=(50,), dtype=np.float32),
            "spatial": spaces.Box(low=-np.inf, high=np.inf, shape=(4, BOARD_SIZE, BOARD_SIZE), dtype=np.float32)
        })
        self.game = None
        self.current_ppo_step = 0
        
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.auto_pilot_model = KaggricultureLSTM(action_dim=13).to(self.device)
        self.auto_pilot_model.load_state_dict(torch.load(base_weights_path, map_location=self.device, weights_only=True))
        self.auto_pilot_model.eval()
        
    def _fast_forward(self):
        h0 = torch.zeros(1, 1, self.auto_pilot_model.hidden_size).to(self.device)
        c0 = torch.zeros(1, 1, self.auto_pilot_model.hidden_size).to(self.device)
        state = (h0, c0)
        
        for _ in range(self.start_macro):
            obs_dict = self._get_obs(self.game.get_observation(0))
            spat = torch.Tensor(obs_dict["spatial"]).unsqueeze(0).to(self.device)
            scal = torch.Tensor(obs_dict["scalar"]).unsqueeze(0).to(self.device)
            with torch.no_grad():
                action, _, state = self.auto_pilot_model(spat, scal, state)
            action = torch.clamp(action[0], 0.0, 1.0).cpu().numpy()
            self._apply_macro_action(action)
            self._run_micro_steps()
            
        self.last_hidden_state = state # Pass memory into the PPO active session!

    def reset(self, seed=None, options=None):
        super().reset(seed=seed)
        self.game = FastGame(seed=np.random.randint(0, 100000))
        self.current_ppo_step = 0
        
        # Default empty memory
        self.last_hidden_state = (
            torch.zeros(1, 1, self.auto_pilot_model.hidden_size).to(self.device),
            torch.zeros(1, 1, self.auto_pilot_model.hidden_size).to(self.device)
        )
        
        if self.start_macro > 0:
            self._fast_forward()
            
        return self._get_obs(self.game.get_observation(0)), {}

    def _run_micro_steps(self):
        for _ in range(self.steps_per_macro):
            obs0 = self.game.get_observation(0)
            try:
                micro0 = hrl_heuristic_agent.agent(obs0)
            except:
                micro0 = {"farmer": ["PASS"], "hands": [], "market": []}
            micro1 = {"farmer": ["PASS"], "hands": [], "market": []} 
            self.game.step_game(micro0, micro1)
        
    def _calculate_reward(self, done):
        if not done: return 0.0
        
        farm = self.game.farms[0]
        money = farm.money
        
        # THE FIX: If this is the final Day 27->30 chunk, reward PURE LIQUID CASH ONLY!
        if self.end_day >= 30:
            return money / 1000.0
            
        # Otherwise, reward Net Worth to encourage building a massive economy
        obs = self.game.get_observation(0)
        market = obs.get("market", {}).get("prices", {})
        net_worth = money
        net_worth += len(farm.hands) * 10
        priv = obs.get("private", {})
        for item, count in priv.get("shed", {}).items():
            if item in market: net_worth += count * market[item]
        for item, count in priv.get("seeds", {}).items():
            if item in market: net_worth += count * market[item] * 0.8
        for y in range(BOARD_SIZE):
            for x in range(BOARD_SIZE):
                tile = farm.tiles[y][x]
                if tile and isinstance(tile, dict) and "seed" in tile:
                    seed_name = tile["seed"]
                    if seed_name in market: net_worth += market[seed_name] * 3 
        return net_worth / 1000.0

    def _apply_macro_action(self, action):
        # 13D Action Mapping (Tomato, Goose, Egg removed)
        buy_items = ["WHEAT", "CARROT", "STRAWBERRY", "MELON", "COW", "SHEEP"]
        sell_items = ["WHEAT", "CARROT", "STRAWBERRY", "MELON", "MILK", "WOOL"]
        
        targets = {"TOMATO": 0, "GOOSE": 0} # Force 0 for removed buys
        for i, item in enumerate(buy_items[:4]): targets[item] = int(action[i] * 50)
        for i, item in enumerate(buy_items[4:]): targets[item] = int(action[i+4] * 20)
        
        sell_ratios = {"TOMATO": 1.0, "GOOSE": 1.0, "EGG": 1.0} # Dump if we somehow get them
        for i, item in enumerate(sell_items): sell_ratios[item] = float(action[7+i])
        
        hrl_heuristic_agent.TARGET_PORTFOLIO["BUY_TARGETS"] = targets
        hrl_heuristic_agent.TARGET_PORTFOLIO["SELL_RATIOS"] = sell_ratios
        hrl_heuristic_agent.TARGET_PORTFOLIO["HIRE_TARGET"] = max(2, int(action[6] * 10))

    def step(self, action):
        self._apply_macro_action(action)
        self._run_micro_steps()
        self.current_ppo_step += 1
        done = (self.current_ppo_step >= self.max_macro_steps)
        reward = self._calculate_reward(done)
        return self._get_obs(self.game.get_observation(0)), float(reward), done, False, {}

    def _get_obs(self, obs):
        farm = obs["farms"][0]
        vec = np.zeros(50, dtype=np.float32)
        vec[0] = obs.get("step", 0) / 2000.0
        vec[1] = farm.get("money", 0) / 10000.0
        for i, item in enumerate(["WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON", "EGG", "MILK", "WOOL", "COW", "SHEEP", "GOOSE"]):
            vec[2 + i] = obs.get("private", {}).get("shed", {}).get(item, 0) / 100.0
            vec[13 + i] = obs.get("private", {}).get("seeds", {}).get(item, 0) / 100.0
            vec[24 + i] = obs.get("market", {}).get("prices", {}).get(item, 0) / 100.0
        vec[35] = len(farm.get("hands", [])) / 10.0
        
        grid = np.zeros((4, BOARD_SIZE, BOARD_SIZE), dtype=np.float32)
        crop_to_idx = {"WHEAT": 1, "CARROT": 2, "TOMATO": 3, "STRAWBERRY": 4, "MELON": 5}
        for y in range(BOARD_SIZE):
            for x in range(BOARD_SIZE):
                t = farm["tiles"][y][x]
                if t == "LOCKED": grid[3, y, x] = -1
                elif isinstance(t, dict):
                    if t.get("kind") == "PLANT":
                        grid[0, y, x] = crop_to_idx.get(t.get("crop"), 0)
                        grid[1, y, x] = t.get("yield_units", 0)
                    elif t.get("kind") == "WEED": grid[3, y, x] = 1
                    elif t.get("kind") in ["COOP", "PASTURE"]:
                        grid[3, y, x] = 2
                        if "animal" in t:
                            grid[0, y, x] = 6 
                            grid[1, y, x] = t.get("yield_units", 0)
        fx, fy = farm.get("farmer", [0, 0])
        if 0 <= fx < BOARD_SIZE and 0 <= fy < BOARD_SIZE: grid[2, fy, fx] = 1
        for h in farm.get("hands", []):
            if 0 <= h[0] < BOARD_SIZE and 0 <= h[1] < BOARD_SIZE: grid[2, h[1], h[0]] = 1
            
        return {"scalar": vec, "spatial": grid}

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
    return advantages, advantages + values

def run_curriculum_chunk(start_day, end_day):
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"\n==================================================")
    print(f"🚀 STARTING LSTM CURRICULUM: Day {start_day} -> Day {end_day}")
    print(f"==================================================")
    
    # Load BC weights for Day 0->3, otherwise load the previous curriculum chunk
    base_weights = f"ppo_lstm_day{start_day}.pth" if start_day > 0 else "lstm_bc_master.pth"
    if not os.path.exists(base_weights):
        print(f"ERROR: Cannot find {base_weights}. Run previous days first!")
        return False
        
    env = MasterCurriculumEnv(start_day, end_day, base_weights)
    
    model = KaggricultureLSTM(action_dim=13).to(device)
    model.load_state_dict(torch.load(base_weights, map_location=device, weights_only=True))
    
    optimizer = optim.Adam(model.parameters(), lr=1e-4)
    action_logstd = nn.Parameter(torch.zeros(13).to(device))
    optimizer.add_param_group({'params': [action_logstd]})
    
    num_steps, batch_size, epochs_per_update, total_timesteps = 256, 64, 4, 30000
    
    obs_spat = torch.zeros((num_steps, 4, 10, 10)).to(device)
    obs_scal = torch.zeros((num_steps, 50)).to(device)
    actions, logprobs, rewards, dones, values = [torch.zeros((num_steps, 13 if i<2 else 1)).to(device) for i in range(5)]
    rewards = rewards.squeeze()
    dones = dones.squeeze()
    values = values.squeeze()
    
    # We must store the hidden states during rollouts for PPO
    hidden_h = torch.zeros((num_steps, model.hidden_size)).to(device)
    hidden_c = torch.zeros((num_steps, model.hidden_size)).to(device)
    
    print("Fast-forwarding to Start Day... (This may take a moment)")
    obs_dict, _ = env.reset()
    next_spat = torch.Tensor(obs_dict["spatial"]).unsqueeze(0).to(device)
    next_scal = torch.Tensor(obs_dict["scalar"]).unsqueeze(0).to(device)
    next_done = torch.zeros(1).to(device)
    
    # Grab the memory state passed from the auto-pilot
    next_state = env.last_hidden_state
    
    for update in range(1, total_timesteps // num_steps + 1):
        model.eval()
        for step in range(num_steps):
            obs_spat[step], obs_scal[step], dones[step] = next_spat[0], next_scal[0], next_done[0]
            hidden_h[step] = next_state[0].squeeze(0).squeeze(0)
            hidden_c[step] = next_state[1].squeeze(0).squeeze(0)
            
            with torch.no_grad():
                a_mean, v, next_state = model(next_spat, next_scal, next_state)
                values[step] = v.flatten()
                probs = Normal(a_mean, torch.exp(action_logstd))
                a = probs.sample()
                actions[step], logprobs[step] = a[0], probs.log_prob(a)[0]
            
            obs_dict, r, d, _, _ = env.step(torch.clamp(a, 0.0, 1.0)[0].cpu().numpy())
            rewards[step] = r
            
            if d: 
                obs_dict, _ = env.reset()
                next_state = env.last_hidden_state
                
            next_spat = torch.Tensor(obs_dict["spatial"]).unsqueeze(0).to(device)
            next_scal = torch.Tensor(obs_dict["scalar"]).unsqueeze(0).to(device)
            next_done = torch.Tensor([d]).to(device)
            
        with torch.no_grad():
            _, next_v, _ = model(next_spat, next_scal, next_state)
            adv, ret = compute_gae(rewards, values, dones, next_v.flatten(), next_done)
            
        model.train()
        b_inds = np.arange(num_steps)
        for _ in range(epochs_per_update):
            np.random.shuffle(b_inds)
            for start in range(0, num_steps, batch_size):
                mb = b_inds[start:start+batch_size]
                
                # Reconstruct memory state for batch
                b_h = hidden_h[mb].unsqueeze(0)
                b_c = hidden_c[mb].unsqueeze(0)
                
                new_mean, new_value, _ = model(obs_spat[mb], obs_scal[mb], (b_h, b_c))
                probs = Normal(new_mean, torch.exp(action_logstd))
                
                ratio = torch.exp(probs.log_prob(actions[mb]) - logprobs[mb])
                mb_adv = (adv[mb] - adv[mb].mean()) / (adv[mb].std() + 1e-8)
                
                pg_loss = torch.max(-mb_adv.unsqueeze(1) * ratio, -mb_adv.unsqueeze(1) * torch.clamp(ratio, 0.8, 1.2)).mean()
                v_loss = 0.5 * ((new_value.flatten() - ret[mb]) ** 2).mean()
                loss = pg_loss - 0.01 * probs.entropy().mean() + v_loss * 0.5
                
                optimizer.zero_grad()
                loss.backward()
                nn.utils.clip_grad_norm_(model.parameters(), 0.5)
                optimizer.step()
                
        if update % 20 == 0 or update == total_timesteps // num_steps:
            print(f"Update {update:03d} | Mean Reward: {rewards.sum().item()/(dones.sum().item()+1e-8):.3f}")

    out_name = f"ppo_lstm_day{end_day}.pth"
    torch.save(model.state_dict(), out_name)
    print(f"✅ Saved LSTM Superhuman Weights to {out_name}\n")
    return True

if __name__ == "__main__":
    print("Initializing LSTM Master Curriculum Automation...")
    # Day 0->3 uses BC master, then cascades
    success = run_curriculum_chunk(0, 3)
    if success:
        for day in range(3, 30, 3):
            start_d = day
            end_d = day + 3
            success = run_curriculum_chunk(start_d, end_d)
            if not success:
                break
    print("🏆 LSTM MASTER CURRICULUM COMPLETE!")
