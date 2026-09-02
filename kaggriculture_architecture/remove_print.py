import sys
import re

with open(r"C:\Coding\kaggriculture_architecture\phase_f_dynamic_agent\agent_core.py", "r") as f:
    content = f.read()

# Remove the broken print statement completely.
content = re.sub(r"print\(f'STEP \{step\}: Farmer is at.*?\)\n", "", content)

with open(r"C:\Coding\kaggriculture_architecture\phase_f_dynamic_agent\agent_core.py", "w") as f:
    f.write(content)
