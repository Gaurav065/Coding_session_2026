import json
import sys

def analyze(fname):
    with open(fname, encoding='utf-8') as fin:
        d = json.load(fin)
    agents = d.get('info', {}).get('TeamNames', ['P1', 'P2'])
    s = d.get('steps', [])[-1]
    
    our_seat = 0 if 'Gaurav065' in agents[0] else 1
    opp_seat = 1 - our_seat
    
    obs = s[0]['observation']
    our_farm = obs['farms'][our_seat]
    opp_farm = obs['farms'][opp_seat]
    
    print(f'=== {fname} ===')
    print(f"Our Money: {our_farm.get('money')}")
    print(f"Opp Money: {opp_farm.get('money')}")
    print(f"Our Shed: {our_farm.get('inventory')}")
    print(f"Opp Shed: {opp_farm.get('inventory')}")
    
    s_pen = d.get('steps', [])[-3]
    obs_pen = s_pen[0]['observation']
    print(f"Penultimate Our Shed: {obs_pen.get('farms')[our_seat].get('inventory')}")
    print(f"Penultimate Opp Shed: {obs_pen.get('farms')[opp_seat].get('inventory')}")

analyze('episode-104527312-replay.json')
analyze('episode-104528972-replay.json')
analyze('episode-104528532-replay.json')
