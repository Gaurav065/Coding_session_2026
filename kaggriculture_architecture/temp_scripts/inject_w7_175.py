import sys

with open(r"C:\Coding\kaggriculture_architecture\phase_f_dynamic_agent\agent_core.py", "r") as f:
    content = f.read()

content = content.replace(
    "print(f'ENGINE STEP {step}: hands={hands_pos}, unlocked={farm.get(\"unlocked_quadrants\")}', file=sys.stderr)",
    "if 169 <= step <= 175: print(f'ENGINE STEP {step}: w7={hands_pos[7] if len(hands_pos) > 7 else \"NONE\"}', file=sys.stderr)"
)

with open(r"C:\Coding\kaggriculture_architecture\phase_f_dynamic_agent\agent_core.py", "w") as f:
    f.write(content)
