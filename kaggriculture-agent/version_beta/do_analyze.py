import json

with open(r'C:\Users\LENOVO\Downloads\92023176.json') as f:
    replay = json.load(f)

print('Winner:', replay.get('rewards'))
steps = replay['steps']
for i, step in enumerate(steps):
    if i % 100 == 0 or i > len(steps) - 20:
        if len(step) > 0 and 'observation' in step[0]:
            obs = step[0]['observation']
            if 'players' in obs:
                p0_money = obs["players"][0][0]
                p1_money = obs["players"][1][0]
                print(f'Step {i}: Player 0 money {p0_money} | Player 1 money {p1_money}')
