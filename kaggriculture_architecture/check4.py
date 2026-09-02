import json
d = json.load(open('episode-104541031-replay.json'))
agents = d.get('info', {}).get('TeamNames', ['P1', 'P2'])
our_seat = 0 if 'Gaurav065' in agents[0] else 1
opp_seat = 1 - our_seat

act_718 = d['steps'][718][our_seat]['action']
act_719 = d['steps'][719][our_seat]['action']

print("Our 719 market:", act_719.get("market"))

opp_719 = d['steps'][719][opp_seat]['action']
print("Opp 719 market:", opp_719.get("market"))
