import numpy as np
from scipy.optimize import linear_sum_assignment
from collections import deque

class PhaseFDispatcher:
    def __init__(self, grid_size=15):
        self.grid_size = grid_size
        
    def _bfs_path(self, start, target, obstacles):
        """
        Find shortest path avoiding obstacles.
        Returns the FIRST step (dx, dy) to take, or None if unreachable/at target.
        """
        if start == target:
            return None
            
        queue = deque([(start[0], start[1], [])])
        visited = {start}
        
        while queue:
            x, y, path = queue.popleft()
            for dx, dy in [(-1,0), (1,0), (0,-1), (0,1)]:
                nx, ny = x + dx, y + dy
                if 0 <= nx < self.grid_size and 0 <= ny < self.grid_size:
                    if (nx, ny) == target:
                        new_path = path + [(dx, dy)]
                        return new_path[0] # Return the first step to take!
                    if (nx, ny) not in visited and (nx, ny) not in obstacles:
                        visited.add((nx, ny))
                        queue.append((nx, ny, path + [(dx, dy)]))
        return None # Unreachable

    def _bfs_distance(self, start, target, obstacles):
        if start == target: return 0
        queue = deque([(start[0], start[1], 0)])
        visited = {start}
        
        while queue:
            x, y, dist = queue.popleft()
            for dx, dy in [(-1,0), (1,0), (0,-1), (0,1)]:
                nx, ny = x + dx, y + dy
                if 0 <= nx < self.grid_size and 0 <= ny < self.grid_size:
                    if (nx, ny) == target:
                        return dist + 1
                    if (nx, ny) not in visited and (nx, ny) not in obstacles:
                        visited.add((nx, ny))
                        queue.append((nx, ny, dist + 1))
        return 999
        
    def get_actions(self, workers, tasks, obstacles):
        """
        workers: dict mapping worker_id -> (x, y)
        tasks: dict mapping task_id -> (x, y, type) where type in ['HARVEST', 'PLANT', 'WATER', 'NONE']
        obstacles: set of (x, y)
        
        Returns dict mapping worker_id -> 'ACTION'
        """
        if not workers or not tasks:
            return {w_id: 'PASS' for w_id in workers}
            
        worker_ids = list(workers.keys())
        task_ids = list(tasks.keys())
        
        cost_matrix = np.zeros((len(worker_ids), len(task_ids)))
        for i, w_id in enumerate(worker_ids):
            for j, t_id in enumerate(task_ids):
                wx, wy = workers[w_id]
                tx, ty, _ = tasks[t_id]
                cost = self._bfs_distance((wx, wy), (tx, ty), obstacles)
                cost_matrix[i, j] = cost
                
        # Hungarian Assignment
        row_ind, col_ind = linear_sum_assignment(cost_matrix)
        
        actions = {}
        for i, j in zip(row_ind, col_ind):
            w_id = worker_ids[i]
            t_id = task_ids[j]
            cost = cost_matrix[i, j]
            
            if cost >= 999:
                actions[w_id] = 'PASS'
                continue
                
            wx, wy = workers[w_id]
            tx, ty, task_type = tasks[t_id]
            
            if (wx, wy) == (tx, ty):
                # Worker is exactly on the task tile! Perform the task.
                actions[w_id] = task_type
            else:
                # Need to move closer
                step = self._bfs_path((wx, wy), (tx, ty), obstacles)
                if step == (0, 1): actions[w_id] = 'NORTH'
                elif step == (0, -1): actions[w_id] = 'SOUTH'
                elif step == (1, 0): actions[w_id] = 'EAST'
                elif step == (-1, 0): actions[w_id] = 'WEST'
                else: actions[w_id] = 'PASS'
                
        # Any unassigned workers pass
        for w_id in worker_ids:
            if w_id not in actions:
                actions[w_id] = 'PASS'
                
        return actions
