import sys
sys.path.insert(0, r'C:/Coding')
from project_maestro.engine.fast_engine import FastGame
from project_maestro.agent.master_counter_agent import MasterCounterAgent
from project_maestro.agent.meta_calibrated_opponent import make_meta_calibrated_opponent
from project_maestro.agent.dispatcher_agent import MaestroFullPortfolioAgent

g = FastGame(seed=42)
a0 = MasterCounterAgent(seed=42)
a1 = make_meta_calibrated_opponent(seed=42)

for day in range(30):
    for hour in range(24):
        obs0 = g.get_observation(0)
        obs1 = g.get_observation(1)
        act0 = a0(obs0)
        act1 = a1(obs1)
        g.step_game(act0, act1)
        
    f0 = g.farms[0]
    f1 = g.farms[1]
    c0 = sum(1 for row in f0.tiles for t in row if isinstance(t, dict) and t.get('kind')=='PASTURE' and t.get('animal')=='COW')
    s0 = sum(1 for row in f0.tiles for t in row if isinstance(t, dict) and t.get('kind')=='PASTURE' and t.get('animal')=='SHEEP')
    b0 = sum(1 for row in f0.tiles for t in row if isinstance(t, dict) and t.get('kind')=='PLANT' and t.get('crop')=='STRAWBERRY')
    milk = f0.shed.get('MILK', 0)
    wool = f0.shed.get('WOOL', 0)
    straw = f0.shed.get('STRAWBERRY', 0)
    wheat = f0.shed.get('WHEAT', 0)
    print(f'Day {day:2d}: P0 Money={f0.money:7.0f} | Cows={c0} Sheep={s0} Straw={b0} | Shed[M={milk},W={wool},S={straw},Wh={wheat}] | P1 Money={f1.money:7.0f}')

print(f'FINAL SCORE: P0={g.farms[0].money} vs P1={g.farms[1].money}')
