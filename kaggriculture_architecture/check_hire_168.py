import sys
sys.path.insert(0, r"C:\Coding\kaggriculture_architecture\extracted_notebook_agent")
from agents.e749a_niklita_consensus_network import SOURCE
for step in range(168, 172):
    action = SOURCE.TRACE_ACTIONS[step]
    market = action.get("market", [])
    print(f"Step {step}: market = {market}")
