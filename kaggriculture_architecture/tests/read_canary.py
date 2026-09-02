import os

with open(r'C:\Users\GauravPatel\.gemini\antigravity\brain\ded05206-e835-4338-8a74-19cad798c197\.system_generated\tasks\task-2605.log', 'r', encoding='utf-8', errors='ignore') as f:
    text = f.read()

lines = text.splitlines()
canary_lines = [l for l in lines if 'CANARY' in l or 'PASS' in l or 'differs' in l or 'mean delta' in l or 'seat-balanced' in l or 'SHIP' in l or 'BLOCK' in l or 'p0 wins' in l or 'p1 wins' in l]
print(f"Total canary lines: {len(canary_lines)}")
for l in canary_lines:
    print(l)
