import json
d = json.load(open('episode-104541031-replay.json'))
agents = d.get('info', {}).get('TeamNames', ['P1', 'P2'])
our_seat = 0 if 'Gaurav065' in agents[0] else 1
opp_seat = 1 - our_seat

hires = {0: 0, 1: 0}
hire_cost = 0

for i, step in enumerate(d['steps']):
    if i == 0: continue
    
    for seat in [0, 1]:
        farmer_action = step[seat]['action'].get('farmer', [])
        if len(farmer_action) > 0 and farmer_action[0] == 'HIRE':
            hires[seat] += 1
            # Check money drop between i-1 and i
            prev_money = d['steps'][i-1][0]['observation']['farms'][seat]['money']
            curr_money = step[0]['observation']['farms'][seat]['money']
            
print(f"Total Hires - Us: {hires[our_seat]}, Nator X: {hires[opp_seat]}")
