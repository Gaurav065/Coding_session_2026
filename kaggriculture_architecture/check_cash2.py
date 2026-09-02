from kaggle_environments import make
env = make('kaggriculture', configuration={'randomSeed': 42})
steps = env.run(['heuristic_agent5.py', 'random'])
print("Cash flow over time:")
for i in range(0, min(720, len(steps)), 24):
    obs = steps[i][0]['observation']
    if 'farms' in obs:
        print(f"Step {i} Cash: {obs['farms'][0]['money']}")
