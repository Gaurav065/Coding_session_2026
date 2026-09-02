import os
import sys

# Need to make sure the local imports work
import gymnasium as gym
from stable_baselines3 import PPO
from hrl_wrapper import KaggricultureMacroEnv

env = KaggricultureMacroEnv(opponent="random", steps_per_macro=24)
model = PPO("MlpPolicy", env, verbose=1, device="cpu")

print("Training model locally for a quick preview (2048 steps)...")
model.learn(total_timesteps=2048)
