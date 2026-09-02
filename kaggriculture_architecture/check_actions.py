import json
d = json.load(open('episode-104541031-replay.json'))

actions = set()
for step in d['steps']:
    for seat in [0, 1]:
        if 'action' in step[seat] and 'farmer' in step[seat]['action']:
            a = step[seat]['action']['farmer']
            if len(a) > 0:
                actions.add(a[0])

print("Unique farmer actions:", actions)
