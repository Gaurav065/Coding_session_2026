import base64
import json
import os
import zlib

def inspect_agent(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        text = f.read()

    # extract b85 payload
    # Find _V44_MODULES = json.loads(zlib.decompress(base64.b85decode(
    # ...
    # )))
    lines = text.splitlines()
    b85_chunks = []
    in_b85 = False
    tail_lines = []
    
    for i, line in enumerate(lines):
        if '_V44_MODULES' in line:
            in_b85 = True
            continue
        if in_b85:
            stripped = line.strip()
            if stripped.startswith("'''") or stripped.startswith('"""') or stripped.startswith("'") or stripped.startswith('"'):
                chunk = stripped.strip("'\")")
                b85_chunks.append(chunk)
            elif stripped.startswith(')))'):
                in_b85 = False
            elif stripped == '':
                continue
            else:
                in_b85 = False
                tail_lines.append(line)
        else:
            if b85_chunks:
                tail_lines.append(line)

    b85_str = ''.join(b85_chunks)
    print(f"File: {filepath}")
    print(f"Total lines: {len(lines)}, b85 payload len: {len(b85_str)}")
    print(f"Tail lines count: {len(tail_lines)}")
    if tail_lines:
        print("Tail preview:")
        print("\n".join(tail_lines[:40]))
    
    # Try decompressing
    try:
        data = json.loads(zlib.decompress(base64.b85decode(b85_str.encode('ascii'))))
        print("Decompressed modules:")
        for mod_name in sorted(data.keys()):
            print(f"  - {mod_name} ({len(data[mod_name])} chars)")
        return data, "\n".join(tail_lines)
    except Exception as e:
        print(f"Decompression error: {e}")
        return None, None

if __name__ == '__main__':
    for path in [
        r'C:\Coding\main.py',
        r'C:\Users\GauravPatel\Downloads\main (2).py',
        r'C:\Coding\main_v49_phase_window.py',
        r'C:\Coding\main_v50_phase_batch.py'
    ]:
        if os.path.exists(path):
            print("="*60)
            inspect_agent(path)
