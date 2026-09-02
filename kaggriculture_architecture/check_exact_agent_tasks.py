import sys

from pathlib import Path
ROOT = Path(r"C:\Coding\kaggriculture_architecture\phase_f_dynamic_agent").resolve()
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "legacy"))

import importlib.util
spec = importlib.util.spec_from_file_location("agent_core", str(ROOT / "agent_core.py"))
agent_core = importlib.util.module_from_spec(spec)
sys.modules["agent_core"] = agent_core
spec.loader.exec_module(agent_core)

agent_core.init_tape_tasks()
print("W0 Tasks around Step 170 in agent_core:")
for t in agent_core._TAPE_TASKS[0]:
    if 160 <= t["step"] <= 200:
        print(t)
