"""Decode and analyze the 167k tape from commit e8c14b9."""

import subprocess
import json
import zlib
import base64
import re
from collections import Counter

def decode_tape():
    res = subprocess.check_output(['git', 'show', 'e8c14b9:main.py'], text=True)
    m = re.search(r'TAPE_B64\s*=\s*(?:b)?["\']([A-Za-z0-9+/=]+)["\']', res)
    if not m:
        print("Could not find TAPE_B64 regex match")
        return
    b64_str = m.group(1)
    tape = json.loads(zlib.decompress(base64.b64decode(b64_str)).decode('utf-8'))
    print(f"Decoded tape with {len(tape)} turns.\n")

    # Analyze total purchases and sales
    purchases = Counter()
    sales = Counter()
    hires = 0
    land = 0

    for step, act in enumerate(tape):
        for o in act.get("market", []):
            if not o:
                continue
            op = o[0]
            if op == "BUY_SEED":
                purchases[f"SEED_{o[1]}"] += int(o[2])
            elif op == "BUY_ANIMAL":
                purchases[f"ANIMAL_{o[1]}"] += int(o[2])
            elif op == "BUY_PRODUCT":
                purchases[f"PROD_{o[1]}"] += int(o[2])
            elif op == "SELL":
                sales[o[1]] += int(o[2])
            elif op == "HIRE":
                hires += 1
            elif op == "BUY_LAND":
                land += 1

    print("--- 167k TAPE STRATEGY BREAKDOWN ---")
    print(f"Total Hires across game: {hires}")
    print(f"Total Land Unlocks: {land}")
    print("\nTotal Purchases:")
    for k, v in purchases.most_common():
        print(f"  {k}: {v}")
    print("\nTotal Sales:")
    for k, v in sales.most_common():
        print(f"  {k}: {v}")

    # Inspect First 5 Days of Actions
    print("\n--- FIRST 5 DAYS STEP-BY-STEP (STEPS 0-120) ---")
    for s in range(min(120, len(tape))):
        act = tape[s]
        orders = act.get("market", [])
        if orders:
            print(f"Step {s:3d} (Day {s//24:2d}, Hr {s%24:2d}): Market Orders: {orders}")

if __name__ == '__main__':
    decode_tape()
