import sys
sys.path.insert(0, r"C:\Coding\kaggriculture_architecture\phase_f_dynamic_agent")
from phase_f_dispatcher import PhaseFDispatcher
d = PhaseFDispatcher(grid_size=10)
print(d._bfs_path((5,4), (4,4), set()))
