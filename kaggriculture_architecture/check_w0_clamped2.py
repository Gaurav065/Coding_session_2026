import sys

from pathlib import Path
ROOT = Path(r"C:\Coding\kaggriculture_architecture\phase_f_dynamic_agent").resolve()
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "legacy"))

import agent_core
agent_core.init_tape_tasks()
print("W0 tasks:")
for t in agent_core._TAPE_TASKS[0]:
    if 160 <= t["step"] <= 200:
        print(t)
