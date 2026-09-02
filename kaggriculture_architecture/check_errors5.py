from kaggle_environments import make
env = make('kaggriculture', configuration={'randomSeed': 42})
steps = env.run(['heuristic_agent5.py', 'random'])
print("Final Score:", steps[-1][0]['reward'])
print("Status:", steps[-1][0]['status'])
for i in range(1, 10):
    if steps[i][0]['status'] != 'ACTIVE' and steps[i][0]['status'] != 'DONE':
        print(f"Step {i} Error:", steps[i][0]['status'], steps[i][0].get('observation', {}).get('error', ''))
