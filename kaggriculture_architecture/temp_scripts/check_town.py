from kaggle_environments import make
env = make('kaggriculture', configuration={'randomSeed': 42}, debug=True)
steps = env.run(['heuristic_agent2.py', 'random'])
print("Town obs at step 5:")
print(steps[5][0]['observation'].get('town'))
