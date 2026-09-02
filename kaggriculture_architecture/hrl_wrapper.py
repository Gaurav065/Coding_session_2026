import gymnasium as gym
from gymnasium import spaces
import numpy as np
from kaggle_environments import make

import hrl_heuristic_agent

class KaggricultureMacroEnv(gym.Env):
    """
    A Hierarchical RL environment wrapper for Kaggriculture.
    The RL agent chooses "macro" targets (allocations and sell ratios) 
    once a day (every 24 steps).
    The underlying Phase F heuristic agent perfectly executes these targets using BFS.
    """
    def __init__(self, opponent="random", steps_per_macro=24):
        super(KaggricultureMacroEnv, self).__init__()
        self.env = make("kaggriculture")
        self.opponent = opponent
        self.steps_per_macro = steps_per_macro
        
        # Action Space: 17 dimensions (continuous [0, 1])
        # [0-4]: Seed targets (WHEAT, CARROT, TOMATO, STRAWBERRY, MELON) -> mapped to [0, 50]
        # [5-7]: Animal targets (GOOSE, COW, SHEEP) -> mapped to [0, 20]
        # [8]: Hire target -> mapped to [2, 10]
        # [9-16]: Sell ratios for 8 items -> mapped to [0, 1]
        self.action_space = spaces.Box(low=0.0, high=1.0, shape=(17,), dtype=np.float32)
        
        # Observation Space: 50 dimensions
        self.observation_space = spaces.Box(low=-np.inf, high=np.inf, shape=(50,), dtype=np.float32)
        
        self.trainer = None
        self.current_obs = None
        
    def reset(self, seed=None, options=None):
        super().reset(seed=seed)
        if seed is not None:
            self.env = make("kaggriculture", configuration={"randomSeed": seed})
        
        self.trainer = self.env.train([None, self.opponent])
        self.current_obs = self.trainer.reset()
        
        return self._get_obs(self.current_obs), {}
        
    def step(self, action):
        # 1. Decode continuous action into TARGET_PORTFOLIO
        buy_items = ["WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON", "GOOSE", "COW", "SHEEP"]
        sell_items = ["WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON", "EGG", "MILK", "WOOL"]
        
        targets = {}
        for i, item in enumerate(buy_items[:5]):
            targets[item] = int(action[i] * 50)
        for i, item in enumerate(buy_items[5:]):
            targets[item] = int(action[i+5] * 20)
            
        hire_target = max(2, int(action[8] * 10))
        
        ratios = {}
        for i, item in enumerate(sell_items):
            ratios[item] = float(action[9+i])
            
        # Update the target portfolio inside the heuristic agent module
        hrl_heuristic_agent.TARGET_PORTFOLIO["BUY_TARGETS"] = targets
        hrl_heuristic_agent.TARGET_PORTFOLIO["SELL_RATIOS"] = ratios
        hrl_heuristic_agent.TARGET_PORTFOLIO["HIRE_TARGET"] = hire_target
        
        # 2. Step the environment `steps_per_macro` times using the heuristic agent
        done = False
        
        start_cash = 0
        if "farms" in self.current_obs and len(self.current_obs["farms"]) > self.current_obs["player"]:
            start_cash = self.current_obs["farms"][self.current_obs["player"]]["money"]
        
        for _ in range(self.steps_per_macro):
            micro_action = hrl_heuristic_agent.agent(self.current_obs)
            self.current_obs, rew, done, info = self.trainer.step(micro_action)
            if done:
                break
                
        # 3. Calculate macro reward (profit over the day)
        end_cash = 0
        if "farms" in self.current_obs and len(self.current_obs["farms"]) > self.current_obs["player"]:
            end_cash = self.current_obs["farms"][self.current_obs["player"]]["money"]
            
        reward = end_cash - start_cash
        
        return self._get_obs(self.current_obs), float(reward), done, False, {}

    def _get_obs(self, obs):
        vec = np.zeros(50, dtype=np.float32)
        if not obs or "farms" not in obs:
            return vec
            
        player_idx = obs.get("player", 0)
        farm = obs["farms"][player_idx]
        priv = obs.get("private", {})
        shed = priv.get("shed", {})
        seeds = priv.get("seeds", {})
        market = obs.get("market", {})
        
        vec[0] = obs.get("step", 0) / 2000.0
        vec[1] = farm.get("money", 0) / 10000.0
        
        # Items and Seeds
        items = ["WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON", "EGG", "MILK", "WOOL", "COW", "SHEEP", "GOOSE"]
        for i, item in enumerate(items):
            vec[2 + i] = shed.get(item, 0) / 100.0
            vec[13 + i] = seeds.get(item, 0) / 100.0
            
            # Market prices (average over day if needed, but current price is fine)
            prices = market.get("prices", {})
            vec[24 + i] = prices.get(item, 0) / 100.0
            
        # Additional features like opponent money, total workers, etc.
        vec[35] = len(farm.get("hands", [])) / 10.0
        
        return vec
