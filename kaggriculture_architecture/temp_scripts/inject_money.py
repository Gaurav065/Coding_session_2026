import sys

with open(r"C:\Coding\kaggriculture_architecture\phase_f_dynamic_agent\agent_core.py", "r") as f:
    content = f.read()

content = content.replace(
    "print(f'STEP {step}: hands={hands_pos}, market={market_action}', file=sys.stderr)",
    "print(f'STEP {step}: hands={hands_pos}, money={farm.get(\"money\")}, market={market_action}', file=sys.stderr)"
)

with open(r"C:\Coding\kaggriculture_architecture\phase_f_dynamic_agent\agent_core.py", "w") as f:
    f.write(content)
