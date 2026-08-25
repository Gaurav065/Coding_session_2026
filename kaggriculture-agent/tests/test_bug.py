from kaggle_environments import make
import continuous_agent.main_dynamic as md
import json

env = make('kaggriculture', configuration={'episodeSteps': 100}, debug=False)
env.run([md.agent, 'random'])
print("Done")
