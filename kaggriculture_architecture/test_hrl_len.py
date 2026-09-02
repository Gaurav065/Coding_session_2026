import numpy as np
from hrl_wrapper import KaggricultureMacroEnv

env = KaggricultureMacroEnv(opponent="random")
obs, _ = env.reset(seed=42)

for i in range(100):
    # random action
    action = env.action_space.sample()
    obs, reward, done, _, info = env.step(action)
    print(f"Macro step {i}, reward: {reward}, done: {done}")
    if done:
        print("Episode ended!")
        # Let's inspect the final observation
        final_obs = env.current_obs
        print("Status of player:", final_obs.get("status"))
        print("Status of opponent:", final_obs.get("info", {}).get("statuses"))
        break
