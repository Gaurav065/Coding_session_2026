import json
d = json.load(open(r'C:\Users\LENOVO\Downloads\92023176.json'))
for i in range(1, 31):
    step = d['steps'][i*24 - 1]
    final = step[0]['observation']['market']['prices']
    print(f"Day {i}: Strawberry={final.get('STRAWBERRY', 120)}, Melon={final.get('MELON', 250)}, Wheat={final.get('WHEAT', 25)}")
