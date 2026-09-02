import sys

with open(r"C:\Coding\kaggriculture_architecture\phase_f_dynamic_agent\phase_f_dispatcher.py", "r") as f:
    content = f.read()

content = content.replace(
    "for dx, dy in [(0,1), (0,-1), (1,0), (-1,0)]:",
    "for dx, dy in [(-1,0), (1,0), (0,-1), (0,1)]:"
)

with open(r"C:\Coding\kaggriculture_architecture\phase_f_dynamic_agent\phase_f_dispatcher.py", "w") as f:
    f.write(content)
