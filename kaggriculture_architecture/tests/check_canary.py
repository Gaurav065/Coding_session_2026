import os

with open(r'C:\Users\GauravPatel\.gemini\antigravity\brain\ded05206-e835-4338-8a74-19cad798c197\.system_generated\tasks\task-2605.log', 'r', encoding='utf-8', errors='ignore') as f:
    text = f.read()

lines = text.splitlines()
matches = [l for l in lines if any(k in l for k in ['PASS', 'FAIL', '1 ', '2 ', '3 ', '4 ', '5 ', '6 ', 'Summary', 'Score', 'reward', 'candidate', 'incumbent'])]
print(f"Matches count: {len(matches)}")
for m in matches:
    print(m)
