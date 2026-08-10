# main.py
from typing import Dict, Any
from state import GameState
from strategy import Strategy, TaskScheduler

_strategy = Strategy()
_scheduler = TaskScheduler()
_state = {}

def agent(obs: Dict) -> Dict[str, Any]:
    player = obs["player"]
    
    if player not in _state:
        _state[player] = {"last_day": -1, "plan": None}
    
    pstate = _state[player]
    state = GameState(obs)
    
    if state.day != pstate["last_day"]:
        pstate["last_day"] = state.day
        pstate["plan"] = _strategy.create_plan(state)
    
    actions = _scheduler.schedule(state, pstate["plan"])
    
    # Debug print
    if state.hour == 0:
        print(f"Player {player} Day {state.day}: Shed={state.shed}, Market={actions['market']}")
    
    return actions