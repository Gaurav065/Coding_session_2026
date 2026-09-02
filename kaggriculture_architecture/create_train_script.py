import json

def read_file(name):
    with open(name, "r") as f:
        return f.read()

train_py_content = f"""
import os
import sys

def write_file(path, content):
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)

write_file("phase_f_dispatcher.py", {repr(read_file('phase_f_dynamic_agent/phase_f_dispatcher.py'))})
write_file("hrl_heuristic_agent.py", {repr(read_file('hrl_heuristic_agent.py'))})
write_file("hrl_wrapper.py", {repr(read_file('hrl_wrapper.py'))})

print("Files created. Starting training...")

# Need to install stable-baselines3 if not present. Kaggle environments might have it, but just in case.
os.system("pip install stable-baselines3 kaggle-environments")

import gymnasium as gym
from stable_baselines3 import PPO
from stable_baselines3.common.env_util import make_vec_env
from hrl_wrapper import KaggricultureMacroEnv
import torch

print(f"CUDA available: {{torch.cuda.is_available()}}")

# Create environment
env = KaggricultureMacroEnv(opponent="random", steps_per_macro=24)

# Instantiate the agent
model = PPO("MlpPolicy", env, verbose=1, tensorboard_log="./ppo_kaggriculture_tensorboard/")

print("Training model...")
# Train the agent
model.learn(total_timesteps=100000)

# Save the agent
model.save("ppo_kaggriculture_hrl")
print("Model saved.")

"""

with open("train.py", "w", encoding="utf-8") as f:
    f.write(train_py_content)

print("train.py generated successfully.")
