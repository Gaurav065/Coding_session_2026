import sys
sys.path.insert(0, r"C:\Coding\kaggriculture_architecture\extracted_notebook_agent")
from agents.e749a_niklita_consensus_network import SOURCE

for step, action in enumerate(SOURCE.TRACE_ACTIONS):
    market = action.get('market', [])
    for m in market:
        if m and m[0] == 'BUY_LAND':
            print(f"Step {step}: {m}")
