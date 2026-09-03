from kaggle_environments import make
env = make('kaggriculture', configuration={'randomSeed': 42}, debug=True)
steps = env.run(['heuristic_agent4.py', 'random'])
print("Total steps:", len(steps))
