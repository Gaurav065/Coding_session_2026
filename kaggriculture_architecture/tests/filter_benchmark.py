import os
import glob

log_files = glob.glob(r'C:\Users\GauravPatel\.gemini\antigravity\brain\ded05206-e835-4338-8a74-19cad798c197\.system_generated\tasks\task-*.log')
log_files.sort(key=os.path.getmtime, reverse=True)

# Find latest log containing BENCHMARK or Seed
for lf in log_files[:5]:
    with open(lf, 'r', encoding='utf-8', errors='ignore') as f:
        text = f.read()
    if 'BENCHMARK' in text or 'Seed ' in text:
        print(f"=== {os.path.basename(lf)} ===")
        lines = text.splitlines()
        for l in lines:
            if any(k in l for k in ['BENCHMARK:', 'Seed ', 'SUMMARY:', 'AVERAGE', 'Wins:', 'ERROR', '====']):
                print(l)
        break
