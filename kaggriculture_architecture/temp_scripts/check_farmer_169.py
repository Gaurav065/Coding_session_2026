import sys
sys.path.insert(0, r"C:\Coding\kaggriculture_architecture\extracted_notebook_agent")
from agents.e749a_niklita_consensus_network import SOURCE
trace = SOURCE.TRACE_ACTIONS
print("Farmer at 169:", trace[169].get("farmer", []))
