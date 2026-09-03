from kaggle_environments import make
env = make('kaggriculture', configuration={'randomSeed': 42}, debug=True)
steps = env.run(['heuristic_agent2.py', 'random'])
print("Final Score:", steps[-1][0]['reward'])
print("First 20 steps for Agent 0:")
for i in range(1, 20):
    act = steps[i][0]['action']
    if act['market'] or act['hands']:
        print(f"Step {i} Mkt: {act.get('market', [])} Hands: {act.get('hands', [])}")
