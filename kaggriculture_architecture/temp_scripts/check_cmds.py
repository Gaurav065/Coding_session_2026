from kaggle_environments import make
import sys

sys.path.insert(0, r"C:\Coding\kaggriculture_architecture\extracted_notebook_agent")
from agents.e749a_niklita_consensus_network import SOURCE

cmds = set()
for action in SOURCE.TRACE_ACTIONS:
    for hand in action.get("hands", []):
        if hand:
            cmds.add(hand[0])
print("Hand commands used in tape:", cmds)
