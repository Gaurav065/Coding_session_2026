import sys
from pathlib import Path
ROOT = Path(r"C:\Coding\kaggriculture_architecture\phase_f_dynamic_agent").resolve()
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "legacy"))

import agent_core

# mock obs
obs = {
    "step": 0,
    "player": 1,
    "farms": [{"tiles": [], "farmer": [4,4], "hands": []}, {"tiles": [[None]*10 for _ in range(10)], "farmer": [4,4], "hands": []}],
    "private": {"seeds": {}}
}

action = agent_core.agent(obs)
print("Action returned:", action)
print("Tasks dict size:", len(agent_core._TAPE_TASKS))
