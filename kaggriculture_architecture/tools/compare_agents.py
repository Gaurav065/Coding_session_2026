import os
import difflib

def compare_agents(file1, file2):
    print(f"Comparing {os.path.basename(file1)} vs {os.path.basename(file2)}")
    with open(file1, 'r', encoding='utf-8') as f:
        t1 = f.read()
    with open(file2, 'r', encoding='utf-8') as f:
        t2 = f.read()

    # Compare non-b85 parts
    lines1 = [l for l in t1.splitlines() if not (l.startswith("    '") or l.startswith('    "'))]
    lines2 = [l for l in t2.splitlines() if not (l.startswith("    '") or l.startswith('    "'))]

    diff = list(difflib.unified_diff(lines1, lines2, lineterm='', fromfile=file1, tofile=file2))
    print(f"Diff lines count: {len(diff)}")
    for line in diff[:60]:
        print(line)

if __name__ == '__main__':
    compare_agents(r'C:\Coding\main_restore.py', r'C:\Coding\main.py')
    print("\n" + "="*80 + "\n")
    compare_agents(r'C:\Coding\main.py', r'C:\Coding\main_v50_phase_batch.py')
