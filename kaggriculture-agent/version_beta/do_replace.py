import sys
with open('main.py') as f:
    code = f.read()

old = '''    if day < P["sim_days"] - 3: return 1.0
    return max(0.1, 1.0 - 0.25 * (day - (P["sim_days"] - 3)))'''

new = '''    if day < P["sim_days"] - 8: return 1.0
    return max(0.1, 1.0 - 0.15 * (day - (P["sim_days"] - 8)))'''

code = code.replace(old, new)

with open('main.py', 'w') as f:
    f.write(code)
