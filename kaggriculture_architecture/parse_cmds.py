import json
import re

with open(r"C:\Coding\kaggriculture_architecture\extracted_notebook_agent\agents\e749a_niklita_consensus_network.py", "r") as f:
    code = f.read()

# Extract the TRACE_ACTIONS array which is a huge string
match = re.search(r"TRACE_ACTIONS\s*=\s*\[(.*?)\]\n", code, re.DOTALL)
if match:
    actions_str = match.group(0)
    print(actions_str[:100])
else:
    print("Not found")
