import sys
sys.path.insert(0, r"C:\Coding\kaggriculture_architecture\extracted_notebook_agent")
from agents.e749a_niklita_consensus_network import SOURCE

action = SOURCE.TRACE_ACTIONS[27]
print(f"Step 27: hands = {action.get('hands')}")
