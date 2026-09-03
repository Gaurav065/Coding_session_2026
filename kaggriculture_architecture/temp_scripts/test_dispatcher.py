from phase_f_dynamic_agent.phase_f_dispatcher import PhaseFDispatcher

dispatcher = PhaseFDispatcher()

workers = {"w_0": (4, 4), "w_1": (5, 4), "w_2": (4, 5), "w_3": (5, 5), "w_4": (4, 4)}
tasks = {"task_0": (0, 0, "PLANT"), "task_1": (0, 1, "PLANT"), "task_2": (0, 2, "PLANT"), "task_3": (0, 3, "PLANT"), "task_4": (0, 4, "PLANT"), "task_5": (0, 5, "PLANT"), "task_6": (0, 6, "PLANT")}
obstacles = set()

# Let's say (1,0) is blocked by LOCKED tiles, wait, if obstacles is empty...
actions = dispatcher.get_actions(workers, tasks, obstacles)
print("Actions:", actions)

# What if obstacles block it?
# In Kaggriculture, if NW is unlocked, coordinates are x in 0..7, y in 0..7.
# wait, NW is x=0..7, y=0..7. But (4,4) is inside!
