import json, os
if os.path.exists('trace.json'):
    d = json.load(open('trace.json'))
    for i in range(20, 31):
        step = d['steps'][i*24 - 1]
        market = step[0]['observation']['market']['prices']
        print(f"Day {i}: Strawberry={market.get('STRAWBERRY', 120)}")
