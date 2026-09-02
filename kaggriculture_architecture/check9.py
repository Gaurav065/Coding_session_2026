import json
d = json.load(open('episode-104541031-replay.json'))
agents = d.get('info', {}).get('TeamNames', ['P1', 'P2'])

max_animals = {0: 0, 1: 0}
for i in range(0, 720, 50):
    obs = d['steps'][i][0]['observation']
    for seat in [0, 1]:
        farm = obs['farms'][seat]
        tiles = farm.get('tiles', [])
        c = 0
        for row in tiles:
            for cell in row:
                if isinstance(cell, dict) and cell.get('kind') == 'ANIMAL':
                    c += 1
        if c > max_animals[seat]: max_animals[seat] = c

print("Max animals Nator X:", max_animals[0])
print("Max animals Us:", max_animals[1])
