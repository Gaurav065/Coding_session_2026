"""Inspect Replay Tape Structure precisely"""

import json
import glob
import os

def inspect_format(tape_path):
    with open(tape_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    print(f"File: {os.path.basename(tape_path)}")
    if isinstance(data, dict):
        print(f"Dict keys: {list(data.keys())}")
        if "steps" in data:
            print(f"Steps length: {len(data['steps'])}, step 0 type: {type(data['steps'][0])}")
            if isinstance(data['steps'][0], list):
                print(f"step 0 list length: {len(data['steps'][0])}, element 0 keys: {list(data['steps'][0][0].keys()) if isinstance(data['steps'][0][0], dict) else type(data['steps'][0][0])}")
            elif isinstance(data['steps'][0], dict):
                print(f"step 0 dict keys: {list(data['steps'][0].keys())}")
    elif isinstance(data, list):
        print(f"List length: {len(data)}, element 0 type: {type(data[0])}")
        if isinstance(data[0], dict):
            print(f"element 0 dict keys: {list(data[0].keys())}")
        elif isinstance(data[0], list):
            print(f"element 0 list length: {len(data[0])}")

if __name__ == "__main__":
    tapes = glob.glob(r"C:\Coding\kaggriculture-agent\*.json") + glob.glob(r"C:\Coding\kaggriculture-agent\archive\*.json") + glob.glob(r"C:\Coding\kaggriculture-agent\replays\*.json")
    for t in tapes[:5]:
        inspect_format(t)
        print("-" * 50)
