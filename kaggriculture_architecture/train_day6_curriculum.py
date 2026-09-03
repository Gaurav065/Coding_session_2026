import sys
import numpy as np
import gymnasium as gym
import torch
import torch.nn as nn
from gymnasium import spaces
from stable_baselines3 import PPO
from stable_baselines3.common.torch_layers import BaseFeaturesExtractor

sys.path.insert(0, r"c:\Programming\Coding_session_2026\kaggriculture_architecture")
sys.path.insert(0, r"c:\Programming\Coding_session_2026")

import hrl_heuristic_agent
from project_maestro.engine.fast_engine import FastGame, BOARD_SIZE

class ResidualBlock(nn.Module):
    def __init__(self, channels):
        super().__init__()
        self.conv1 = nn.Conv2d(channels, channels, kernel_size=3, padding=1)
        self.conv2 = nn.Conv2d(channels, channels, kernel_size=3, padding=1)

    def forward(self, x):
        out = nn.functional.relu(x)
        out = self.conv1(out)
        out = nn.functional.relu(out)
        out = self.conv2(out)
        return x + out

class ImpalaBlock(nn.Module):
    def __init__(self, in_channels, out_channels):
        super().__init__()
        self.conv = nn.Conv2d(in_channels, out_channels, kernel_size=3, padding=1)
        self.pool = nn.MaxPool2d(kernel_size=3, stride=2, padding=1)
        self.res1 = ResidualBlock(out_channels)
        self.res2 = ResidualBlock(out_channels)

    def forward(self, x):
        x = self.conv(x)
        x = self.pool(x)
        x = self.res1(x)
        x = self.res2(x)
        return x

class CNN_MLP_Extractor(BaseFeaturesExtractor):
    def __init__(self, observation_space: gym.spaces.Dict, features_dim: int = 512):
        super().__init__(observation_space, features_dim)
        
        spatial_shape = observation_space.spaces["spatial"].shape
        n_input_channels = spatial_shape[0]
        
        # IMPALA-style CNN (Espeholt et al., 2018) for effective grid-based RL
        self.cnn = nn.Sequential(
            ImpalaBlock(n_input_channels, 16),
            ImpalaBlock(16, 32),
            nn.ReLU(),
            nn.Flatten()
        )
        
        with torch.no_grad():
            sample_spatial = torch.as_tensor(observation_space.spaces["spatial"].sample()[None]).float()
            n_flatten = self.cnn(sample_spatial).shape[1]
            
        scalar_dim = observation_space.spaces["scalar"].shape[0]
        
        # Advanced MLP with LayerNorm
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

class Day6CurriculumEnv(gym.Env):
    def __init__(self, steps_per_macro=24, day3_model_path="ppo_day3_opening"):
        super().__init__()
        self.steps_per_macro = steps_per_macro
        
        self.max_macro_steps = 6
        
        self.action_space = spaces.Box(low=0.0, high=1.0, shape=(17,), dtype=np.float32)
        self.observation_space = spaces.Dict({
            "scalar": spaces.Box(low=-np.inf, high=np.inf, shape=(50,), dtype=np.float32),
            "spatial": spaces.Box(low=-np.inf, high=np.inf, shape=(4, BOARD_SIZE, BOARD_SIZE), dtype=np.float32)
        })
        
        self.game = None
        self.macro_step = 0
        
        self.day3_model = PPO.load(day3_model_path, device='cpu') # Use CPU to avoid context issues during fast-forward
        
    def reset(self, seed=None, options=None):
        super().reset(seed=seed)
        self.game = FastGame(seed=np.random.randint(0, 100000))
        
        for _ in range(3):
            obs_dict = self.game.get_observation(0)
            scalar_obs = self._get_scalar_obs(obs_dict)
            action, _ = self.day3_model.predict(scalar_obs, deterministic=True)
            self._apply_macro_action(action)
            
            for _ in range(self.steps_per_macro):
                obs0 = self.game.get_observation(0)
                try:
                    micro0 = hrl_heuristic_agent.agent(obs0)
                except:
                    micro0 = {"farmer": ["PASS"], "hands": [], "market": []}
                micro1 = {"farmer": ["PASS"], "hands": [], "market": []} 
                self.game.step_game(micro0, micro1)
                
        self.macro_step = 3
        return self._get_obs(self.game.get_observation(0)), {}
        
    def _calculate_net_worth(self):
        farm = self.game.farms[0]
        obs = self.game.get_observation(0)
        market = obs.get("market", {}).get("prices", {})
        
        net_worth = farm.money
        net_worth += len(farm.hands) * 10
        
        priv = obs.get("private", {})
        shed = priv.get("shed", {})
        seeds = priv.get("seeds", {})
        for item, count in shed.items():
            if item in market: net_worth += count * market[item]
        for item, count in seeds.items():
            if item in market: net_worth += count * market[item] * 0.8
            
        for y in range(BOARD_SIZE):
            for x in range(BOARD_SIZE):
                tile = farm.tiles[y][x]
                if tile and isinstance(tile, dict) and "seed" in tile:
                    seed_name = tile["seed"]
                    if seed_name in market:
                        net_worth += market[seed_name] * 3 
        return net_worth

    def _apply_macro_action(self, action):
        buy_items = ["WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON", "GOOSE", "COW", "SHEEP"]
        sell_items = ["WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON", "EGG", "MILK", "WOOL"]
        
        targets = {}
        for i, item in enumerate(buy_items[:5]): targets[item] = int(action[i] * 50)
        for i, item in enumerate(buy_items[5:]): targets[item] = int(action[i+5] * 20)
            
        hire_target = max(2, int(action[8] * 10))
        ratios = {}
        for i, item in enumerate(sell_items): ratios[item] = float(action[9+i])
            
        hrl_heuristic_agent.TARGET_PORTFOLIO["BUY_TARGETS"] = targets
        hrl_heuristic_agent.TARGET_PORTFOLIO["SELL_RATIOS"] = ratios
        hrl_heuristic_agent.TARGET_PORTFOLIO["HIRE_TARGET"] = hire_target

    def step(self, action):
        self._apply_macro_action(action)
        
        for _ in range(self.steps_per_macro):
            obs0 = self.game.get_observation(0)
            try:
                micro0 = hrl_heuristic_agent.agent(obs0)
            except:
                micro0 = {"farmer": ["PASS"], "hands": [], "market": []}
            micro1 = {"farmer": ["PASS"], "hands": [], "market": []} 
            
            self.game.step_game(micro0, micro1)
            
        self.macro_step += 1
        
        done = (self.macro_step >= self.max_macro_steps)
        
        reward = 0.0
        if done:
            net_worth = self._calculate_net_worth()
            reward = net_worth / 1000.0
            
        return self._get_obs(self.game.get_observation(0)), float(reward), done, False, {}

    def _get_scalar_obs(self, obs):
        vec = np.zeros(50, dtype=np.float32)
        farm = obs["farms"][0]
        priv = obs.get("private", {})
        shed = priv.get("shed", {})
        seeds = priv.get("seeds", {})
        market = obs.get("market", {})
        vec[0] = obs.get("step", 0) / 2000.0
        vec[1] = farm.get("money", 0) / 10000.0
        items = ["WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON", "EGG", "MILK", "WOOL", "COW", "SHEEP", "GOOSE"]
        for i, item in enumerate(items):
            vec[2 + i] = shed.get(item, 0) / 100.0
            vec[13 + i] = seeds.get(item, 0) / 100.0
            prices = market.get("prices", {})
            vec[24 + i] = prices.get(item, 0) / 100.0
        vec[35] = len(farm.get("hands", [])) / 10.0
        return vec

    def _get_spatial_obs(self, obs):
        grid = np.zeros((4, BOARD_SIZE, BOARD_SIZE), dtype=np.float32)
        farm = obs["farms"][0]
        
        crop_to_idx = {"WHEAT": 1, "CARROT": 2, "TOMATO": 3, "STRAWBERRY": 4, "MELON": 5}
        
        for y in range(BOARD_SIZE):
            for x in range(BOARD_SIZE):
                tile = farm["tiles"][y][x]
                if tile == "LOCKED":
                    grid[3, y, x] = -1
                elif isinstance(tile, dict):
                    if tile.get("kind") == "PLANT":
                        crop = tile.get("crop")
                        grid[0, y, x] = crop_to_idx.get(crop, 0)
                        grid[1, y, x] = tile.get("yield_units", 0)
                    elif tile.get("kind") == "WEED":
                        grid[3, y, x] = 1
                    elif tile.get("kind") in ["COOP", "PASTURE"]:
                        grid[3, y, x] = 2
                        if "animal" in tile:
                            grid[0, y, x] = 6 
                            grid[1, y, x] = tile.get("yield_units", 0)
                            
        fx, fy = farm.get("farmer", [0, 0])
        if 0 <= fx < BOARD_SIZE and 0 <= fy < BOARD_SIZE:
            grid[2, fy, fx] = 1
        for h in farm.get("hands", []):
            hx, hy = h[0], h[1]
            if 0 <= hx < BOARD_SIZE and 0 <= hy < BOARD_SIZE:
                grid[2, hy, hx] = 1
            
        return grid

    def _get_obs(self, obs):
        return {
            "scalar": self._get_scalar_obs(obs),
            "spatial": self._get_spatial_obs(obs)
        }

if __name__ == "__main__":
    env = Day6CurriculumEnv()
    policy_kwargs = dict(
        features_extractor_class=CNN_MLP_Extractor,
        features_extractor_kwargs=dict(features_dim=128),
    )
    
    model = PPO("MultiInputPolicy", env, policy_kwargs=policy_kwargs, verbose=1, learning_rate=0.0003, ent_coef=0.01, batch_size=64, n_steps=300)
    print("Training Day 3-6 Curriculum Model...")
    model.learn(total_timesteps=30000)
    model.save("ppo_day6_curriculum")
    print("Training finished! Saved ppo_day6_curriculum.zip")
