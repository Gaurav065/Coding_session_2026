import json
import zlib
import base64
import glob

# Check tape files
for path in glob.glob(r'C:\Coding\project_aegis\tapes\*.json') + glob.glob(r'C:\Coding\project_aegis\tapes\*.zlib'):
    print("Checking:", path)
    if path.endswith('.zlib'):
        with open(path, 'rb') as f:
            data = json.loads(zlib.decompress(f.read()).decode('utf-8'))
    else:
        with open(path, 'r') as f:
            data = json.load(f)
            
    # Trace farmer and hand positions when planting MELON
    # Farmer starts at (4,4) or (0,0)
    fx, fy = 4, 4
    melon_tiles = set()
    for s_idx, step in enumerate(data[:150]):
        # Update farmer pos
        f_act = step.get('farmer', ['PASS'])
        if f_act[0] == 'NORTH': fy -= 1
        elif f_act[0] == 'SOUTH': fy += 1
        elif f_act[0] == 'EAST': fx += 1
        elif f_act[0] == 'WEST': fx -= 1
        elif f_act[0] == 'PLANT' and len(f_act) > 1 and f_act[1] == 'MELON':
            melon_tiles.add((fx, fy))
    print(f"  Wave-1 Melon Coordinates found ({len(melon_tiles)}): {sorted(list(melon_tiles))}")
