from kaggle_environments import make
env = make('kaggriculture', configuration={'randomSeed': 42})
steps = env.run(['heuristic_agent5.py', 'random'])
print("Cash flow over time:")
for i in range(0, min(720, len(steps)), 24):
    reward = steps[i][0]['reward']
    print(f"Step {i}: {reward}")
