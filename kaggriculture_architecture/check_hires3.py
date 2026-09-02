import json
d = json.load(open('episode-104541031-replay.json'))
agents = d.get('info', {}).get('TeamNames', ['P1', 'P2'])
our_seat = 0 if 'Gaurav065' in agents[0] else 1
opp_seat = 1 - our_seat

hires = {0: 0, 1: 0}
for i, step in enumerate(d['steps']):
    if i == 0: continue
    for seat in [0, 1]:
        market = step[seat]['action'].get('market', [])
        for m in market:
            if m[0] == 'HIRE':
                hires[seat] += 1

print(f"Total Hires - Us (Seat {our_seat}): {hires[our_seat]}, Nator X (Seat {opp_seat}): {hires[opp_seat]}")
