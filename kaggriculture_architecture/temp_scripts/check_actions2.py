import json
d = json.load(open('episode-104541031-replay.json'))

actions = set()
for step in d['steps']:
    for seat in [0, 1]:
        if 'action' in step[seat] and 'market' in step[seat]['action']:
            for m in step[seat]['action']['market']:
                if len(m) > 0:
                    actions.add(m[0])

print("Unique market actions:", actions)
