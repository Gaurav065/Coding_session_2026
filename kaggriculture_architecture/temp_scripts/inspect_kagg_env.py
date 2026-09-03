from kaggle_environments import make
import json
env = make("kaggriculture", debug=True)
obs = env.reset()[0]["observation"]
with open("sample_obs.json", "w") as f:
    json.dump(obs, f, indent=2)
