import sys
from pathlib import Path
ROOT = Path(r"C:\Coding\kaggriculture_architecture\phase_f_dynamic_agent").resolve()
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "legacy"))
from agent_core import init_tape_tasks
import agent_core

agent_core.init_tape_tasks()
for t in agent_core._TAPE_TASKS[2]:
    if 48 <= t['step'] <= 56:
        print(f"Extracted Worker 2 task: {t}")
