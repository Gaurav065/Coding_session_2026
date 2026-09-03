import sys
import numpy as np
import gymnasium as gym
from gymnasium import spaces
from stable_baselines3 import PPO
from stable_baselines3.common.torch_layers import BaseFeaturesExtractor
import torch
import torch.nn as nn

sys.path.insert(0, r"C:\Coding\kaggriculture_architecture")
sys.path.insert(0, r"C:\Coding\kaggriculture")

import hrl_heuristic_agent
from project_maestro.engine.fast_engine import FastGame

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

class Day9CurriculumEnv(gym.Env):
    def __init__(self, steps_per_macro=24, day3_model_path="ppo_day3_opening", day6_model_path="ppo_day6_curriculum"):
        super().__init__()
        self.steps_per_macro = steps_per_macro
        
        self.max_macro_steps = 9  # 9 macro steps * 24 = 216 total steps (End of Day 9)
        
        self.action_space = spaces.Box(low=0.0, high=1.0, shape=(17,), dtype=np.float32)
        self.observation_space = spaces.Dict({
            "scalar": spaces.Box(low=-np.inf, high=np.inf, shape=(50,), dtype=np.float32),
            "spatial": spaces.Box(low=-np.inf, high=np.inf, shape=(4, BOARD_SIZE, BOARD_SIZE), dtype=np.float32)
        })
        
        self.game = None
        self.macro_step = 0
        
        # We need BOTH historical models to fast-forward
        self.day3_model = PPO.load(day3_model_path, device='cpu')
        self.day6_model = PPO.load(day6_model_path, device='cpu') 
        
    def reset(self, seed=None, options=None):
        super().reset(seed=seed)
        self.game = FastGame(seed=np.random.randint(0, 100000))
        
        # 1. Fast-forward Days 0-3 (Macro steps 0, 1, 2)
        for _ in range(3):
            obs_dict = self.game.get_observation(0)
            scalar_obs = self._get_scalar_obs(obs_dict)
            action, _ = self.day3_model.predict(scalar_obs, deterministic=True)
            self._apply_macro_action(action)
            self._run_micro_steps()
            
        # 2. Fast-forward Days 3-6 (Macro steps 3, 4, 5)
        for _ in range(3):
            obs_dict = self.game.get_observation(0)
            full_obs = self._get_obs(obs_dict)
            # Add batch dimension for manual prediction
            for k in full_obs.keys():
                full_obs[k] = np.expand_dims(full_obs[k], axis=0)
            action, _ = self.day6_model.predict(full_obs, deterministic=True)
            self._apply_macro_action(action[0])
            self._run_micro_steps()
            
        self.macro_step = 6
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
        self._run_micro_steps()
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
    env = Day9CurriculumEnv()
    policy_kwargs = dict(
        features_extractor_class=CNN_MLP_Extractor,
        features_extractor_kwargs=dict(features_dim=128),
    )
    
    # 50k timesteps for Day 9 to learn the advanced shop items
    model = PPO("MultiInputPolicy", env, policy_kwargs=policy_kwargs, verbose=1, learning_rate=0.0003, ent_coef=0.01, batch_size=64, n_steps=300)
    print("Training Day 6-9 Curriculum Model...")
    model.learn(total_timesteps=50000)
    model.save("ppo_day9_curriculum")
    print("Training finished! Saved ppo_day9_curriculum.zip")
