with open('continuous_agent/main_dynamic.py', 'r') as f:
    text = f.read()

# Replace the GAP logic in efficiency_overlay
old_gap_logic = """    global _CURRENT_TAPE, _PLANNED_PLACEMENTS
    if _CURRENT_TAPE and not _PLANNED_PLACEMENTS:
        # Re-parse tape into dictionary
        for pos_str, item in _CURRENT_TAPE.get("placements", {}).items():
            try:
                x, y = map(int, pos_str.split(","))
                _PLANNED_PLACEMENTS[(x,y)] = item
            except:
                pass"""

new_gap_logic = """    global _CURRENT_GAP, _PLANNED_PLACEMENTS
    if _CURRENT_GAP and not _PLANNED_PLACEMENTS:
        empty_tiles = []
        size = len(farm["tiles"])
        for y in range(size):
            for x in range(size):
                if farm["tiles"][y][x] is None and (x, y) not in [(4,4), (5,4), (4,5), (5,5)]:
                    empty_tiles.append((x, y))
        sorted_gap = sorted(_CURRENT_GAP.items(), key=lambda kv: kv[1], reverse=True)
        for item, qty in sorted_gap:
            while qty > 0 and empty_tiles:
                pos = empty_tiles.pop(0)
                if item in CROPS:
                    _PLANNED_PLACEMENTS[pos] = item
                else:
                    _PLANNED_PLACEMENTS[pos] = PRODUCT_ANIMAL[item]
                qty -= 1"""

text = text.replace(old_gap_logic, new_gap_logic)

with open('continuous_agent/main_dynamic.py', 'w') as f:
    f.write(text)
print("FIX DYNAMIC DONE")
