import sys

with open(r"C:\Coding\kaggriculture_architecture\phase_f_dynamic_agent\agent_core.py", "r") as f:
    content = f.read()

importlib_code = """import importlib.util
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent.parent
SOURCE_PATH = ROOT / "artifacts/e706_top10_tapes/episode_101408728_seat1.py"
SPEC = importlib.util.spec_from_file_location("e749a_attributed_niklita_trace", SOURCE_PATH)
SOURCE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = SOURCE
SPEC.loader.exec_module(SOURCE)"""

content = content.replace(
    "from legacy.agents.e749a_niklita_consensus_network import SOURCE",
    importlib_code
)

with open(r"C:\Coding\kaggriculture_architecture\phase_f_dynamic_agent\agent_core.py", "w") as f:
    f.write(content)
