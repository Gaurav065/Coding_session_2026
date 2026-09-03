import sys
sys.path.insert(0, r"C:\Coding\kaggriculture_architecture\extracted_notebook_agent")
from agents.e749a_niklita_consensus_network import SOURCE
trace = SOURCE.TRACE_ACTIONS
fpos = [4,4]
hpos = {}
for s, act in enumerate(trace):
    if s % 24 == 0: 
        fpos = [4,4]
        hpos = {}
    fcmd = act.get("farmer", [])
    if fcmd:
        op = fcmd[0]
        if op == "NORTH": fpos[1] = max(0, fpos[1]-1)
        elif op == "SOUTH": fpos[1] = min(9, fpos[1]+1)
        elif op == "EAST": fpos[0] = min(9, fpos[0]+1)
        elif op == "WEST": fpos[0] = max(0, fpos[0]-1)
    
    hands = act.get("hands", [])
    for i, hcmd in enumerate(hands):
        if i not in hpos: hpos[i] = [4,4]
        if hcmd:
            op = hcmd[0]
            if op == "NORTH": hpos[i][1] = max(0, hpos[i][1]-1)
            elif op == "SOUTH": hpos[i][1] = min(9, hpos[i][1]+1)
            elif op == "EAST": hpos[i][0] = min(9, hpos[i][0]+1)
            elif op == "WEST": hpos[i][0] = max(0, hpos[i][0]-1)
            
    mkt = act.get("market", [])
    for m in mkt:
        if m and m[0] == "HIRE":
            # Spawn calculation
            occ = { (4,4):0, (5,4):0, (4,5):0, (5,5):0 }
            all_p = [tuple(fpos)] + [tuple(hpos[j]) for j in hpos]
            for p in all_p:
                if p in occ: occ[p] += 1
            best = sorted(occ.items(), key=lambda kv: (kv[1], [(4,4),(5,4),(4,5),(5,5)].index(kv[0])))
            spawn = list(best[0][0])
            hpos[len(hpos)] = spawn
            if s == 169:
                print("SPAWN CALC AT 169:")
                print("fpos:", fpos)
                print("hpos:", hpos)
                print("occupants:", occ)
                print("SPAWN POS:", spawn)
