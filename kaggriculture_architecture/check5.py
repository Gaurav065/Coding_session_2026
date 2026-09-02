import json
d = json.load(open('episode-104541031-replay.json'))
agents = d.get('info', {}).get('TeamNames', ['P1', 'P2'])
our_seat = 0 if 'Gaurav065' in agents[0] else 1
act_718 = d['steps'][718][our_seat]['action']
print("Our hands 718:", act_718.get("hands"))
