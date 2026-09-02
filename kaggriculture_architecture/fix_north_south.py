import sys

with open(r"C:\Coding\kaggriculture_architecture\phase_f_dynamic_agent\agent_core.py", "r") as f:
    content = f.read()

# Fix the extractor
content = content.replace('op == "NORTH": positions[i][1] = (positions[i][1] + 1) % 10', 'op == "NORTH": positions[i][1] = (positions[i][1] - 1) % 10')
content = content.replace('op == "SOUTH": positions[i][1] = (positions[i][1] - 1) % 10', 'op == "SOUTH": positions[i][1] = (positions[i][1] + 1) % 10')

# Fix the dispatcher mapping
content = content.replace("if d == (0, 1): action = ['NORTH']", "if d == (0, 1): action = ['SOUTH']")
content = content.replace("elif d == (0, -1): action = ['SOUTH']", "elif d == (0, -1): action = ['NORTH']")

with open(r"C:\Coding\kaggriculture_architecture\phase_f_dynamic_agent\agent_core.py", "w") as f:
    f.write(content)
