import sys

with open(r"C:\Coding\kaggriculture_architecture\phase_f_dynamic_agent\agent_core.py", "r") as f:
    content = f.read()

content = content.replace(
    "print(f'STEP {step}: Worker 2 is at {hands_pos[2]",
    "print(f'STEP {step}: Farmer is at {farm.get(\"farmer\")}, Worker 2 is at {hands_pos[2] if len(hands_pos) > 2 else \"NONE\"}"
)

with open(r"C:\Coding\kaggriculture_architecture\phase_f_dynamic_agent\agent_core.py", "w") as f:
    f.write(content)
