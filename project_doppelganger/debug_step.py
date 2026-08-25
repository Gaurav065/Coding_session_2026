import sys
sys.path.insert(0, r'C:\Coding\project_doppelganger')

from kaggle_environments import make
from main import agent as doppelganger_agent

env = make("kaggriculture", configuration={"episodeSteps": 10}, debug=True)
env.run([doppelganger_agent, "starter"])
print("Step 0 action output:", env.steps[0])
print("Step 1 action output:", env.steps[1])
print("Final step output:", env.steps[-1])
