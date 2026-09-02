import sys
sys.path.insert(0, r"C:\Coding\kaggriculture_architecture\extracted_notebook_agent\artifacts\e706_top10_tapes")
import episode_101408728_seat1 as source

cmds = set()
for action in source.TRACE_ACTIONS:
    for hand in action.get("hands", []):
        if hand:
            cmds.add(hand[0])
print("Hand commands used in tape:", cmds)
