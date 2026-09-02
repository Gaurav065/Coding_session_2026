import json
d = json.load(open('episode-104541031-replay.json'))
agents = d.get('info', {}).get('TeamNames', ['P1', 'P2'])
our_seat = 0 if 'Gaurav065' in agents[0] else 1
opp_seat = 1 - our_seat
obs = d['steps'][719][0]['observation']
for i in range(2):
    print(f"Seat {i} hands:", obs['farms'][i]['hands'])
    print(f"Seat {i} money:", obs['farms'][i]['money'])
