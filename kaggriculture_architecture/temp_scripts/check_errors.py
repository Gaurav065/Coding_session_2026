from kaggle_environments import make
env = make('kaggriculture', configuration={'randomSeed': 42}, debug=True)
steps = env.run(['heuristic_agent2.py', 'random'])
for i in range(1, 10):
    print(f"Step {i} errors:", steps[i][0].get('info', {}).get('error', ''))
