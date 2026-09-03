import sys
from collections import deque
class PhaseFDispatcher:
    def __init__(self, grid_size=10):
        self.grid_size = grid_size
    def _bfs_path(self, start, target, obstacles):
        if start == target: return None
        queue = deque([(start[0], start[1], [])])
        visited = {start}
        while queue:
            x, y, path = queue.popleft()
            for dx, dy in [(0,1), (0,-1), (1,0), (-1,0)]:
                nx, ny = x + dx, y + dy
                if 0 <= nx < self.grid_size and 0 <= ny < self.grid_size:
                    if (nx, ny) == target: return (path + [(dx, dy)])[0]
                    if (nx, ny) not in visited and (nx, ny) not in obstacles:
                        visited.add((nx, ny))
                        queue.append((nx, ny, path + [(dx, dy)]))
        return None
        
d = PhaseFDispatcher()
res = d._bfs_path((5, 4), (0, 1), set())
print("Path from (5,4) to (0,1):", res)
