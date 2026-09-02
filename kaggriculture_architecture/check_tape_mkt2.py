import sys
from pathlib import Path
sys.path.insert(0, r"C:\Coding\kaggriculture_architecture\extracted_notebook_agent\artifacts\e706_top10_tapes")
import episode_101408728_seat1

for i, act in enumerate(episode_101408728_seat1.TRACE_ACTIONS[:100]):
    for m in act.get("market", []):
        if "BUY" in m[0] or "BUY_SEED" in m[0]:
            print(f"Step {i}: {m}")
