import json

def read_file(name):
    with open(name, "r") as f:
        return f.read()

train_py_content = f"""
import traceback
import sys

def run():
    import os
    import sys
    sys.path.insert(0, os.getcwd())
    
    def write_file(path, content):
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)

    write_file("phase_f_dispatcher.py", {repr(read_file('phase_f_dynamic_agent/phase_f_dispatcher.py'))})
    write_file("hrl_heuristic_agent.py", {repr(read_file('hrl_heuristic_agent.py'))})
    write_file("hrl_wrapper.py", {repr(read_file('hrl_wrapper.py'))})

    print("Files created. Starting training...")

    # Only install if missing to prevent overriding Kaggle's custom torch wheels
    try:
        import stable_baselines3
    except ImportError:
        os.system("pip install stable-baselines3 kaggle-environments")

    import gymnasium as gym
    from stable_baselines3 import PPO
    from hrl_wrapper import KaggricultureMacroEnv

    env = KaggricultureMacroEnv(opponent="random", steps_per_macro=24)
    # Force CPU to avoid PyTorch CUDA Compute Capability mismatches on Kaggle P100s
    model = PPO("MlpPolicy", env, verbose=1, device="cpu")

    print("Training model...")
    model.learn(total_timesteps=100000)

    model.save("ppo_kaggriculture_hrl")
    print("Model saved.")

try:
    run()
except Exception as e:
    err = traceback.format_exc()
    print("CAUGHT ERROR:\\n", err)
    with open("error_traceback.log", "w") as f:
        f.write(err)
"""

with open("train_debug.py", "w", encoding="utf-8") as f:
    f.write(train_py_content)

print("train_debug.py generated successfully.")
