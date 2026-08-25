with open('continuous_agent/main_dynamic.py', 'r') as f:
    text = f.read()

text = text.replace('EPISODE_STEPS', '720')

if '_CURRENT_GAP = {}' not in text:
    globals_decl = "_CURRENT_GAP = {}\n_LAST_SHADOW_PRICE = 50.0\n_PLANNED_PLACEMENTS = {}\n"
    text = globals_decl + text

with open('continuous_agent/main_dynamic.py', 'w') as f:
    f.write(text)
print("FIXED EPISODE STEPS")
