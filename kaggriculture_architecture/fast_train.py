import sys
import numpy as np
import gymnasium as gym
from gymnasium import spaces
from stable_baselines3 import PPO

sys.path.insert(0, r"C:\Coding\kaggriculture_architecture")
sys.path.insert(0, r"C:\Coding\kaggriculture")

import hrl_heuristic_agent
from project_maestro.engine.fast_engine import FastGame

def random_agent(obs):
    return {"farmer": ["PASS"], "hands": [], "market": []}

class FastKaggricultureMacroEnv(gym.Env):
    def __init__(self, opponent_fn=random_agent, steps_per_macro=24):
        super().__init__()
        self.opponent_fn = opponent_fn
        self.steps_per_macro = steps_per_macro
        
        self.action_space = spaces.Box(low=0.0, high=1.0, shape=(17,), dtype=np.float32)
        self.observation_space = spaces.Box(low=-np.inf, high=np.inf, shape=(50,), dtype=np.float32)
        
        self.game = None
        
    def reset(self, seed=None, options=None):
        super().reset(seed=seed)
        self.game = FastGame(seed=seed if seed is not None else 42)
        return self._get_obs(self.game.get_observation(0)), {}
        
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
        
        start_cash = self.game.farms[0].money
        
        for _ in range(self.steps_per_macro):
            obs0 = self.game.get_observation(0)
            obs1 = self.game.get_observation(1)
            try:
                micro0 = hrl_heuristic_agent.agent(obs0)
            except Exception as e:
                micro0 = {"farmer": ["PASS"], "hands": [], "market": []}
            micro1 = self.opponent_fn(obs1)
            
            self.game.step_game(micro0, micro1)
            if self.game.done:
                break
                
        end_cash = self.game.farms[0].money
        reward = end_cash - start_cash
        
        # Give a massive bonus for finishing the game with >$100k
        if self.game.done and end_cash > 100000:
            reward += 10000
            
        return self._get_obs(self.game.get_observation(0)), float(reward), self.game.done, False, {}

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
    import torch
    print(f"CUDA available: {torch.cuda.is_available()}")
    env = FastKaggricultureMacroEnv()
    model = PPO("MlpPolicy", env, verbose=1, learning_rate=0.0003, batch_size=64, ent_coef=0.01)
    
    print("Starting fast RL training...")
    model.learn(total_timesteps=30000)
    model.save("ppo_fast_hrl")
    print("Training finished! Saved ppo_fast_hrl.zip")
