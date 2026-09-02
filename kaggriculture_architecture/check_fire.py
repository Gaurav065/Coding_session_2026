import sys
sys.path.insert(0, r"C:\Coding\kaggriculture_architecture\extracted_notebook_agent")
from agents.e749a_niklita_consensus_network import SOURCE
trace = SOURCE.TRACE_ACTIONS
print("Market at 167:", trace[167].get("market", []))
print("Market at 168:", trace[168].get("market", []))
