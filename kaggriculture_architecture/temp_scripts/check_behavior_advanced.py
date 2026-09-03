from kaggle_environments import make
env = make('kaggriculture', configuration={'randomSeed': 42}, debug=True)
steps = env.run(['heuristic_agent4.py', 'random'])
print("Final Score:", steps[-1][0]['reward'])
for i in range(1, 10):
    act = steps[i][0]['action']
    if act['market'] or act['hands'] or act['farmer']:
        print(f"Step {i} Mkt: {act.get('market', [])} Hands: {act.get('hands', [])}")
