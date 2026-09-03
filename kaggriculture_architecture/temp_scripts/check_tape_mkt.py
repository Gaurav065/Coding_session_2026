import sys
from pathlib import Path
sys.path.insert(0, r"C:\Coding\kaggriculture_architecture\extracted_notebook_agent\artifacts\e706_top10_tapes")
import episode_101408728_seat1

m_acts = episode_101408728_seat1.TRACE_ACTIONS[0].get("market", [])
print(m_acts)
