import time
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
import sys
sys.path.insert(0, r"C:\Coding")
from project_maestro.engine.fast_engine import FastGame
from project_maestro.agent.dispatcher_agent import make_spatial_dispatcher_agent

def run_single(seed):
    a0 = make_spatial_dispatcher_agent()
    a1 = make_spatial_dispatcher_agent()
    game = FastGame(seed=seed)
    while not game.done:
        game.step_game(a0(game.get_observation(0)), a1(game.get_observation(1)))
    return float(game.farms[0].money), float(game.farms[1].money)

if __name__ == "__main__":
    seeds = list(range(10000, 10020)) # 20 matches
    
    t0 = time.time()
    for s in seeds:
        run_single(s)
    t_seq = time.time() - t0
    print(f"Sequential 20 matches: {t_seq:.3f}s")
    
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=8) as ex:
        res = list(ex.map(run_single, seeds))
    t_thread = time.time() - t0
    print(f"ThreadPool 20 matches: {t_thread:.3f}s")
    
    t0 = time.time()
    with ProcessPoolExecutor(max_workers=8) as ex:
        res = list(ex.map(run_single, seeds))
    t_proc = time.time() - t0
    print(f"ProcessPool 20 matches: {t_proc:.3f}s")
