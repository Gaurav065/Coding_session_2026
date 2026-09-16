#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Rebuilds payload.py with sanitized routes (No Geese, Tomatoes active) + Route 13 (Pizza SE expansion)."""

import base64
import copy
import json
import sys
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "kaggriculture_architecture"))

from modular_apex import payload
from develop_crop_pizza_dump_engine import build_sanitized_route0, build_route13_pizza_se_expansion

def rebuild():
    print("Loading original routes from payload.py...")
    orig_routes = payload.load_routes()
    
    sanitized_routes = {}
    print("Sanitizing all routes 0..12 (removing Geese/Coop/Egg, adding Tomatoes)...")
    for rid, tape in orig_routes.items():
        sanitized_routes[rid] = build_sanitized_route0(tape)
        
    print("Building Route 13 (4th-Quadrant SE Expansion for Pizza 2+)...")
    sanitized_routes[13] = build_route13_pizza_se_expansion(sanitized_routes[0])
    
    base_tape = sanitized_routes[0]
    
    # Compute patches relative to sanitized base tape
    patches = {}
    for rid in sorted(sanitized_routes.keys()):
        if rid == 0:
            continue
        tape = sanitized_routes[rid]
        patch = []
        for step in range(min(len(base_tape), len(tape))):
            if tape[step] != base_tape[step]:
                patch.append([step, tape[step]])
        patches[rid] = patch
        print(f"  Route {rid:2d}: {len(patch)} patched steps relative to Route 0")
        
    payload_obj = {
        "base": base_tape,
        "patches": patches
    }
    
    # Compress
    json_bytes = json.dumps(payload_obj, separators=(",", ":")).encode("utf-8")
    compressed = zlib.compress(json_bytes, level=9)
    encoded = base64.b85encode(compressed).decode("ascii")
    
    print(f"\nRaw JSON size : {len(json_bytes):,} bytes")
    print(f"Compressed size: {len(compressed):,} bytes")
    print(f"Base85 length  : {len(encoded):,} chars")
    
    payload_file = ROOT / "kaggriculture_architecture" / "modular_apex" / "payload.py"
    content = f'''# SPDX-License-Identifier: Apache-2.0
import base64
import json
import zlib

_PAYLOAD = json.loads(zlib.decompress(base64.b85decode({encoded!r})))

def load_routes():
    routes = {{0: list(_PAYLOAD['base'])}}
    for rid, patch in _PAYLOAD['patches'].items():
        tape = list(routes[0])
        for step, action in patch:
            tape[int(step)] = action
        routes[int(rid)] = tape
    return routes
'''
    payload_file.write_text(content, encoding="utf-8")
    print(f"Successfully wrote {payload_file}")
    
    # Verify reload
    # Clear sys.modules cache for modular_apex.payload
    if "modular_apex.payload" in sys.modules:
        del sys.modules["modular_apex.payload"]
    from modular_apex import payload as new_payload
    reloaded = new_payload.load_routes()
    assert len(reloaded) == 14, f"Expected 14 routes (0..13), got {len(reloaded)}"
    print(f"Reload verified! All {len(reloaded)} routes loaded successfully.")

if __name__ == "__main__":
    rebuild()
