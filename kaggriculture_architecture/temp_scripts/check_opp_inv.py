from kaggle_environments import make
env = make('kaggriculture', configuration={'randomSeed': 42}, debug=True)
steps = env.run(['heuristic_agent2.py', 'random'])
print("Opponent inventory at step 5:")
print(steps[5][1]['observation']['farms'][1].get('inventory'))
