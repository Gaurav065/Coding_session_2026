from kaggle_environments import make

env = make('kaggriculture', configuration={'episodeSteps': 720}, debug=False)
env.run(['continuous_agent/main_dynamic.py', 'random'])

final = env.steps[-1]
print(f"P0 money: {final[0].observation['farms'][0]['money']}")
print(f"P0 seeds: {final[0].observation['private']['seeds']}")
print(f"P0 shed: {final[0].observation['private']['shed']}")
