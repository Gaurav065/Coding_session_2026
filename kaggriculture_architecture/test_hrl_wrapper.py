import numpy as np
from hrl_wrapper import KaggricultureMacroEnv

env = KaggricultureMacroEnv(opponent="random")
obs, info = env.reset(seed=42)
print("Obs shape:", obs.shape)

action = np.random.uniform(0, 1, size=(17,))
next_obs, reward, done, _, _ = env.step(action)
print("Reward:", reward)
print("Next obs shape:", next_obs.shape)
