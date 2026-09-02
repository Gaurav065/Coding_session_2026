import os

def read_module(path):
    print(f"=== {os.path.basename(path)} ===")
    with open(path, 'r', encoding='utf-8') as f:
        text = f.read()
    print(f"Length: {len(text)} chars")
    lines = text.splitlines()
    print("First 35 lines:")
    print("\n".join(lines[:35]))
    print("...")
    # Search for classes and defs
    for i, line in enumerate(lines):
        if line.startswith("def ") or line.startswith("class ") or "def act" in line or "def step" in line:
            print(f"L{i+1}: {line}")

if __name__ == '__main__':
    base_dir = r'C:\Coding\kaggriculture_architecture\unpacked_main2'
    read_module(os.path.join(base_dir, 'v44', 'gold_floor.py'))
    print("\n" + "="*80 + "\n")
    read_module(os.path.join(base_dir, 'v24', 'market_maker.py'))
