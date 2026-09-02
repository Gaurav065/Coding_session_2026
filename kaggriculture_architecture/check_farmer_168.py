import sys
sys.path.insert(0, r"C:\Coding\kaggriculture_architecture\extracted_notebook_agent")
from agents.e749a_niklita_consensus_network import SOURCE
trace = SOURCE.TRACE_ACTIONS
fpos = [4,4]
for s, act in enumerate(trace):
    if s % 24 == 0: fpos = [4,4]
    fcmd = act.get("farmer", [])
    if fcmd:
        op = fcmd[0]
        if op == "NORTH": fpos[1] = max(0, fpos[1]-1)
        elif op == "SOUTH": fpos[1] = min(9, fpos[1]+1)
        elif op == "EAST": fpos[0] = min(9, fpos[0]+1)
        elif op == "WEST": fpos[0] = max(0, fpos[0]-1)
    if s == 168: print("Farmer at 168:", fpos)
