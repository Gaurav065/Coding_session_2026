import sys
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from torch.distributions import Normal
import gymnasium as gym
from gymnasium import spaces

sys.path.insert(0, r"c:\Programming\Coding_session_2026\kaggriculture_architecture")
sys.path.insert(0, r"c:\Programming\Coding_session_2026")

from custom_architecture import KaggricultureResNet
from project_maestro.engine.fast_engine import FastGame
import hrl_heuristic_agent

BOARD_SIZE = 10

class ResNetDay6Env(gym.Env):
    def __init__(self, day3_weights_path="ppo_resnet_day3.pth", steps_per_macro=24):
        super().__init__()
        self.steps_per_macro = steps_per_macro
        self.max_macro_steps = 3 # 3 macros for Day 3 -> Day 6 (Steps 72 -> 144)
        self.action_space = spaces.Box(low=0.0, high=1.0, shape=(17,), dtype=np.float32)
        self.observation_space = spaces.Dict({
            "scalar": spaces.Box(low=-np.inf, high=np.inf, shape=(50,), dtype=np.float32),
            "spatial": spaces.Box(low=-np.inf, high=np.inf, shape=(4, BOARD_SIZE, BOARD_SIZE), dtype=np.float32)
        })
        self.game = None
        self.macro_step = 0
        
        # Load Frozen Day 3 Model for Fast-Forwarding
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.day3_model = KaggricultureResNet().to(self.device)
        self.day3_model.load_state_dict(torch.load(day3_weights_path, map_location=self.device, weights_only=True))
        self.day3_model.eval()
        
    def _fast_forward_to_day3(self):
        # Play 3 macros (Day 0 to Day 3) using the frozen model
        for _ in range(3):
            obs_dict = self._get_obs(self.game.get_observation(0))
            spat = torch.Tensor(obs_dict["spatial"]).unsqueeze(0).to(self.device)
            scal = torch.Tensor(obs_dict["scalar"]).unsqueeze(0).to(self.device)
            with torch.no_grad():
                action, _ = self.day3_model(spat, scal)
            action = torch.clamp(action[0], 0.0, 1.0).cpu().numpy()
            self._apply_macro_action(action)
            self._run_micro_steps()

    def reset(self, seed=None, options=None):
        super().reset(seed=seed)
        self.game = FastGame(seed=np.random.randint(0, 100000))
        self.macro_step = 0
        
        # Auto-pilot the first 3 days
        self._fast_forward_to_day3()
        
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
        
    def _calculate_net_worth(self):
        farm = self.game.farms[0]
        obs = self.game.get_observation(0)
        market = obs.get("market", {}).get("prices", {})
        net_worth = farm.money
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
        return net_worth

    def _apply_macro_action(self, action):
        buy_items = ["WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON", "GOOSE", "COW", "SHEEP"]
        sell_items = ["WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON", "EGG", "MILK", "WOOL"]
        targets = {}
        for i, item in enumerate(buy_items[:5]): targets[item] = int(action[i] * 50)
        for i, item in enumerate(buy_items[5:]): targets[item] = int(action[i+5] * 20)
        hrl_heuristic_agent.TARGET_PORTFOLIO["BUY_TARGETS"] = targets
        hrl_heuristic_agent.TARGET_PORTFOLIO["SELL_RATIOS"] = {item: float(action[9+i]) for i, item in enumerate(sell_items)}
        hrl_heuristic_agent.TARGET_PORTFOLIO["HIRE_TARGET"] = max(2, int(action[8] * 10))

    def step(self, action):
        self._apply_macro_action(action)
        self._run_micro_steps()
        self.macro_step += 1
        done = (self.macro_step >= self.max_macro_steps)
        reward = self._calculate_net_worth() / 1000.0 if done else 0.0
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

def train_ppo():
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Running PPO Curriculum (Day 3-6) on {device}")
    
    # Initialize the Day 6 Env (it will load ppo_resnet_day3.pth automatically)
    env = ResNetDay6Env()
    
    # Create the active model for Day 6
    model = KaggricultureResNet().to(device)
    # We initialize it with the Day 3 weights so it starts exactly where Day 3 left off
    print("Loading Day 3 weights into Active Model...")
    model.load_state_dict(torch.load("ppo_resnet_day3.pth", map_location=device, weights_only=True))
    
    optimizer = optim.Adam(model.parameters(), lr=1e-4)
    action_logstd = nn.Parameter(torch.zeros(17).to(device))
    optimizer.add_param_group({'params': [action_logstd]})
    
    num_steps, batch_size, epochs_per_update, total_timesteps = 256, 64, 4, 30000
    
    obs_spat = torch.zeros((num_steps, 4, 10, 10)).to(device)
    obs_scal = torch.zeros((num_steps, 50)).to(device)
    actions, logprobs, rewards, dones, values = [torch.zeros((num_steps, 17 if i<2 else 1)).to(device) for i in range(5)]
    rewards = rewards.squeeze()
    dones = dones.squeeze()
    values = values.squeeze()
    
    print("Initializing environment fast-forward... (This may take a moment)")
    obs_dict, _ = env.reset()
    next_spat = torch.Tensor(obs_dict["spatial"]).unsqueeze(0).to(device)
    next_scal = torch.Tensor(obs_dict["scalar"]).unsqueeze(0).to(device)
    next_done = torch.zeros(1).to(device)
    
    for update in range(1, total_timesteps // num_steps + 1):
        model.eval()
        for step in range(num_steps):
            obs_spat[step], obs_scal[step], dones[step] = next_spat[0], next_scal[0], next_done[0]
            with torch.no_grad():
                a_mean, v = model(next_spat, next_scal)
                values[step] = v.flatten()
                probs = Normal(a_mean, torch.exp(action_logstd))
                a = probs.sample()
                actions[step], logprobs[step] = a[0], probs.log_prob(a)[0]
            
            obs_dict, r, d, _, _ = env.step(torch.clamp(a, 0.0, 1.0)[0].cpu().numpy())
            rewards[step] = r
            
            if d: obs_dict, _ = env.reset()
            next_spat = torch.Tensor(obs_dict["spatial"]).unsqueeze(0).to(device)
            next_scal = torch.Tensor(obs_dict["scalar"]).unsqueeze(0).to(device)
            next_done = torch.Tensor([d]).to(device)
            
        with torch.no_grad():
            _, next_v = model(next_spat, next_scal)
            adv, ret = compute_gae(rewards, values, dones, next_v.flatten(), next_done)
            
        model.train()
        b_inds = np.arange(num_steps)
        for _ in range(epochs_per_update):
            np.random.shuffle(b_inds)
            for start in range(0, num_steps, batch_size):
                mb = b_inds[start:start+batch_size]
                new_mean, new_value = model(obs_spat[mb], obs_scal[mb])
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
                
        print(f"Update {update} | Mean Reward: {rewards.sum().item()/(dones.sum().item()+1e-8):.3f}")

    torch.save(model.state_dict(), "ppo_resnet_day6.pth")
    print("Saved ppo_resnet_day6.pth")

if __name__ == "__main__":
    train_ppo()
