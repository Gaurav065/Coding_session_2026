import sys
import numpy as np
import gymnasium as gym
from gymnasium import spaces
from stable_baselines3 import PPO
from stable_baselines3.common.callbacks import BaseCallback

sys.path.insert(0, r"C:\Programming\Coding_session_2026\kaggriculture_architecture")
sys.path.insert(0, r"C:\Programming\Coding_session_2026")

import hrl_heuristic_agent
from project_maestro.engine.fast_engine import FastGame, BOARD_SIZE

class Day3CurriculumEnv(gym.Env):
    def __init__(self, steps_per_macro=24):
        super().__init__()
        self.steps_per_macro = steps_per_macro
        
        self.max_macro_steps = 3 
        
        self.action_space = spaces.Box(low=0.0, high=1.0, shape=(17,), dtype=np.float32)
        self.observation_space = spaces.Box(low=-np.inf, high=np.inf, shape=(50,), dtype=np.float32)
        
        self.game = None
        self.macro_step = 0
        
    def reset(self, seed=None, options=None):
        super().reset(seed=seed)
        self.game = FastGame(seed=np.random.randint(0, 100000))
        self.macro_step = 0
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
                        # Assuming a standard yield of 3 per crop to incentivize planting
                        net_worth += market[seed_name] * 3 
        return net_worth

    def step(self, action):
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

    def _get_obs(self, obs):
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

if __name__ == "__main__":
    env = Day3CurriculumEnv()
    model = PPO("MlpPolicy", env, verbose=1, learning_rate=0.0003, ent_coef=0.01, batch_size=64, n_steps=300)
    print("Training Day 0-3 Curriculum Opening Model...")
    model.learn(total_timesteps=30000)
    model.save("ppo_day3_opening")
    print("Training finished! Saved ppo_day3_opening.zip")
