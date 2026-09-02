import numpy as np
from scipy.optimize import linear_sum_assignment
from collections import deque

class PhaseFDispatcher:
    def __init__(self, grid_size=15):
        self.grid_size = grid_size
        
    def _bfs_distance(self, start, target, obstacles):
        """Find shortest path distance ignoring other workers for now."""
        if start == target: return 0
        queue = deque([(start[0], start[1], 0)])
        visited = {start}
        
        while queue:
            x, y, dist = queue.popleft()
            for dx, dy in [(0,1), (0,-1), (1,0), (-1,0)]:
                nx, ny = x + dx, y + dy
                if 0 <= nx < self.grid_size and 0 <= ny < self.grid_size:
                    if (nx, ny) == target:
                        return dist + 1
                    if (nx, ny) not in visited and (nx, ny) not in obstacles:
                        visited.add((nx, ny))
                        queue.append((nx, ny, dist + 1))
        return 999 # Unreachable
        
    def assign_workers(self, workers, tasks, obstacles=set()):
        """
        workers: list of (x, y)
        tasks: list of (x, y)
        Returns list of (worker_idx, task_idx)
        """
        if not workers or not tasks:
            return []
            
        # Build cost matrix
        cost_matrix = np.zeros((len(workers), len(tasks)))
        for i, w in enumerate(workers):
            for j, t in enumerate(tasks):
                cost_matrix[i, j] = self._bfs_distance(w, t, obstacles)
                
        # Run Hungarian Algorithm
        row_ind, col_ind = linear_sum_assignment(cost_matrix)
        
        assignments = []
        for i, j in zip(row_ind, col_ind):
            # Only assign if reachable
            if cost_matrix[i, j] < 999:
                assignments.append((i, j, cost_matrix[i, j]))
                
        return assignments

# Quick Demonstration
if __name__ == "__main__":
    dispatcher = PhaseFDispatcher()
    workers = [(0, 0), (14, 14), (5, 5)]
    tasks = [(1, 0), (14, 12), (0, 14)] # Tasks at opposite ends
    obstacles = {(0, 1), (1, 1)} # Some random obstacles
    
    assignments = dispatcher.assign_workers(workers, tasks, obstacles)
    print("Hungarian Assignment Results:")
    for w_idx, t_idx, cost in assignments:
        print(f"Worker {w_idx} {workers[w_idx]} -> Task {t_idx} {tasks[t_idx]} (Distance: {cost})")
