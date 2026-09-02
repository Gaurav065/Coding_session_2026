import json
d = json.load(open('episode-104541031-replay.json'))
agents = d.get('info', {}).get('TeamNames', ['P1', 'P2'])

harvests = {0: {}, 1: {}}
sells = {0: {}, 1: {}}

for i, step in enumerate(d['steps']):
    if i == 0: continue
    for seat in [0, 1]:
        action = step[seat]['action']
        hands = action.get('hands', [])
        for h in hands:
            if isinstance(h, list) and len(h) > 0 and h[0] == 'HARVEST':
                # We don't know what they harvested easily, but we can count SELLs
                pass
        for m in action.get('market', []):
            if m[0] == 'SELL':
                item = m[1]
                qty = m[2]
                sells[seat][item] = sells[seat].get(item, 0) + qty

print("Sells by Nator X (Seat 0):", sells[0])
print("Sells by Us (Seat 1):", sells[1])
