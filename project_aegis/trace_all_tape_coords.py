import sys
sys.path.insert(0, r'C:\Coding')

from project_aegis.tape_loader import (
    _ACTIONS_10C4S_3Q,
    _ACTIONS_8C6S_3Q,
    _ACTIONS_6C8S_3Q,
    _ACTIONS_6C12S_4Q_FIRST_YARN,
    _ACTIONS_6C12S_4Q_SECOND_YARN
)

tapes = {
    '10c4s': _ACTIONS_10C4S_3Q,
    '8c6s': _ACTIONS_8C6S_3Q,
    '6c8s': _ACTIONS_6C8S_3Q,
    'yarn1': _ACTIONS_6C12S_4Q_FIRST_YARN,
    'yarn2': _ACTIONS_6C12S_4Q_SECOND_YARN
}

for name, tape in tapes.items():
    fx, fy = 4, 4
    melon_coords = set()
    strawberry_coords = set()
    pasture_coords = set()
    for s in tape:
        f_act = s.get('farmer', ['PASS'])
        if f_act[0] == 'NORTH': fy -= 1
        elif f_act[0] == 'SOUTH': fy += 1
        elif f_act[0] == 'EAST': fx += 1
        elif f_act[0] == 'WEST': fx -= 1
        elif f_act[0] == 'PLANT' and len(f_act) > 1:
            if f_act[1] == 'MELON': melon_coords.add((fx, fy))
            elif f_act[1] == 'STRAWBERRY': strawberry_coords.add((fx, fy))
        elif f_act[0] == 'BUILD_PASTURE':
            pasture_coords.add((fx, fy))
    print(f"Tape {name}:")
    print(f"  Melon Coords ({len(melon_coords)}): {sorted(list(melon_coords))}")
    print(f"  Pasture Coords ({len(pasture_coords)}): {sorted(list(pasture_coords))}")
    print(f"  Strawberry Coords ({len(strawberry_coords)}): {sorted(list(strawberry_coords))}")
