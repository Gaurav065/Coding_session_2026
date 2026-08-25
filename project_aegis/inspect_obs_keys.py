import json
from kaggle_environments import make

env = make("kaggriculture")
env.reset()
obs0 = env.steps[0][0]['observation']
print("Observation keys:", list(obs0.keys()))
print("Step:", obs0.get('step'))
print("Day:", obs0.get('day'))
print("Hour in obs?:", 'hour' in obs0)
