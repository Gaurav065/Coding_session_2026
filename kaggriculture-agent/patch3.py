with open('version_beta/main.py', 'r') as f:
    text = f.read()

text = text.replace('added_actions_per_day / P["work_per_hand"]', 'added_actions_per_day / effective_work_per_hand')
text = text.replace('2.8 / P["work_per_hand"]', '2.8 / effective_work_per_hand')
text = text.replace('work / P["work_per_hand"]', 'work / effective_work_per_hand')
text = text.replace('MAV * P["work_per_hand"] * 0.85', 'MAV * effective_work_per_hand * 0.85')

with open('version_beta/main.py', 'w') as f:
    f.write(text)
