import json
d = json.load(open(r'C:\Users\LENOVO\Downloads\92023176.json'))
max_hands = 0
for i, step in enumerate(d['steps']):
    final = step[0]['observation']['farms'][0]
    hands = final.get("hands", 0)
    if hands > max_hands:
        max_hands = hands
print(f"Opponent max hands: {max_hands}")
