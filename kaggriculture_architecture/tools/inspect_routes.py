import sys
import os

sys.path.insert(0, r'C:\Coding\kaggriculture_architecture\unpacked_main2')
sys.path.insert(0, r'C:\Coding\kaggriculture_architecture\unpacked_main2\scripts')

def inspect_routes():
    with open(r'C:\Coding\main_restore.py', 'r', encoding='utf-8') as f:
        code = f.read()
    g = {}
    exec(code, g)
    routes = g['_V44_ROUTES']
    print(f"Routes available: {list(routes.keys())}")
    for rname, rdata in routes.items():
        print(f"\n--- Route: {rname} ---")
        print(f"Total steps defined: {len(rdata)}")
        total_sells = {}
        total_seeds = {}
        total_animals = {}
        total_buys = {}
        total_hires = 0
        total_land = 0
        for t, act in enumerate(rdata):
            for m in act.get('market', []):
                if not m: continue
                op = m[0]
                if op == 'SELL':
                    total_sells[m[1]] = total_sells.get(m[1], 0) + (m[2] if len(m) > 2 else 1)
                elif op == 'BUY_SEED':
                    total_seeds[m[1]] = total_seeds.get(m[1], 0) + (m[2] if len(m) > 2 else 1)
                elif op == 'BUY_ANIMAL':
                    total_animals[m[1]] = total_animals.get(m[1], 0) + (m[2] if len(m) > 2 else 1)
                elif op == 'BUY_PRODUCT':
                    total_buys[m[1]] = total_buys.get(m[1], 0) + (m[2] if len(m) > 2 else 1)
                elif op == 'HIRE':
                    total_hires += 1
                elif op == 'BUY_LAND':
                    total_land += 1
        print(f"  Seeds: {total_seeds}")
        print(f"  Animals: {total_animals}")
        print(f"  Buys: {total_buys}")
        print(f"  Sells: {total_sells}")
        print(f"  Hires: {total_hires}, Land buys: {total_land}")

if __name__ == '__main__':
    inspect_routes()
