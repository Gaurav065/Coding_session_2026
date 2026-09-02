from kaggle_environments import make
env = make('kaggriculture', configuration={'randomSeed': 42}, debug=True)
steps = env.run(['heuristic_agent2.py', 'random'])
print("Inventory at step 5:")
print(steps[5][0]['observation']['farms'][0]['inventory'])
print("Cash at step 5:")
print(steps[5][0]['observation']['farms'][0]['money'])
