import sys

with open(r"C:\Coding\kaggriculture_architecture\phase_f_dynamic_agent\agent_core.py", "r") as f:
    content = f.read()

content = content.replace(
    "print(f'ENGINE STEP {step}: Worker 7 is at {hands_pos[7] if len(hands_pos) > 7 else \"NONE\"}', file=sys.stderr)",
    "print(f'ENGINE STEP {step}: hands={hands_pos}', file=sys.stderr)"
)

with open(r"C:\Coding\kaggriculture_architecture\phase_f_dynamic_agent\agent_core.py", "w") as f:
    f.write(content)
