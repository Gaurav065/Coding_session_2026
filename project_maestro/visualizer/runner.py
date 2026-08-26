import sys, json, time, os
from typing import Dict, List, Any, Optional

sys.path.insert(0, r'C:/Coding')
from project_maestro.engine.fast_engine import FastGame, MARKET_PARAMS, market_price
from project_maestro.agent.dispatcher_agent import MaestroFullPortfolioAgent
from project_maestro.agent.meta_calibrated_opponent import make_meta_calibrated_opponent

AHMAD_ACTIONS = []
replay_path = 'replays/episode-99064717-replay.json'
if os.path.exists(replay_path):
    with open(replay_path, encoding='utf-8') as f:
        d = json.load(f)
    steps = d.get('steps', [])
    AHMAD_ACTIONS = [steps[t][0].get('action', {}) for t in range(1, len(steps))]

class ReplayAhmadAliAgent:
    def __init__(self):
        self.step_idx = 0
    def __call__(self, obs):
        if self.step_idx < len(AHMAD_ACTIONS):
            act = AHMAD_ACTIONS[self.step_idx]
            self.step_idx += 1
            return act
        return {'farmer': ['PASS'], 'hands': [], 'market': []}

def get_opponent_builder(opp_type: str):
    if opp_type == 'self':
        return lambda: MaestroFullPortfolioAgent()
    elif opp_type == 'meta_calibrated':
        return lambda: make_meta_calibrated_opponent()
    elif opp_type == 'ahmad_ali':
        return lambda: ReplayAhmadAliAgent()
    elif opp_type == 'dominant_meta':
        return lambda: MaestroFullPortfolioAgent(params={'cow_cap_base': 10, 'sheep_cap': 4, 'enable_3b': False})
    elif opp_type == 'gould':
        return lambda: MaestroFullPortfolioAgent(params={'cow_cap_base': 12, 'sheep_cap': 6, 'enable_3b': False})
    elif opp_type == 'ayushk':
        return lambda: MaestroFullPortfolioAgent(params={'cow_cap_base': 3, 'sheep_cap': 13, 'enable_3b': False})
    elif opp_type == 'random':
        from project_maestro.agent.dispatcher_agent import MOVES
        import random
        return lambda: lambda obs: {
            'farmer': [random.choice(list(MOVES.values()) + ['PASS'])],
            'hands': [[random.choice(list(MOVES.values()) + ['PASS'])] for _ in obs['farms'][obs['player']]['hands']],
            'market': []
        }
    else:
        return lambda: MaestroFullPortfolioAgent()

def run_live_match(seed: int = 42, opp_type: str = 'meta_calibrated') -> Dict[str, Any]:
    t0 = time.time()
    g = FastGame(seed=seed)
    a0 = MaestroFullPortfolioAgent(seed=seed)
    a1_builder = get_opponent_builder(opp_type)
    a1 = a1_builder()

    steps_telemetry = []

    def format_tile(t):
        if t is None: return None
        if t == 'LOCKED': return 'LOCKED'
        if isinstance(t, dict): return dict(t)
        return dict(t)

    while not g.done:
        obs0 = g.get_observation(0)
        obs1 = g.get_observation(1)

        act0 = a0(obs0)
        act1 = a1(obs1)

        prices = {k: market_price(k, g.market_inv[k]) for k in MARKET_PARAMS}

        step_state = {
            'step': g.step,
            'day': g.day,
            'hour': g.hour,
            'p0': {
                'money': round(g.farms[0].money, 2),
                'farmer': list(g.farms[0].farmer),
                'hands': [list(h) for h in g.farms[0].hands],
                'farmer_act': act0.get('farmer', ['PASS']),
                'hands_act': act0.get('hands', []),
                'market_act': act0.get('market', []),
                'tiles': [[format_tile(t) for t in row] for row in g.farms[0].tiles],
                'seeds': dict(g.farms[0].seeds),
                'shed': dict(g.farms[0].shed),
                'inventories': [dict(inv) for inv in g.farms[0].inventories]
            },
            'p1': {
                'money': round(g.farms[1].money, 2),
                'farmer': list(g.farms[1].farmer),
                'hands': [list(h) for h in g.farms[1].hands],
                'farmer_act': act1.get('farmer', ['PASS']),
                'hands_act': act1.get('hands', []),
                'market_act': act1.get('market', []),
                'tiles': [[format_tile(t) for t in row] for row in g.farms[1].tiles],
                'seeds': dict(g.farms[1].seeds),
                'shed': dict(g.farms[1].shed),
                'inventories': [dict(inv) for inv in g.farms[1].inventories]
            },
            'market': {
                'prices': prices,
                'inventory': dict(g.market_inv)
            },
            'town': {
                'unlocked_shops': list(g.unlocked_shops)
            }
        }
        steps_telemetry.append(step_state)
        g.step_game(act0, act1)

    prices = {k: market_price(k, g.market_inv[k]) for k in MARKET_PARAMS}
    steps_telemetry.append({
        'step': g.step,
        'day': g.day,
        'hour': g.hour,
        'p0': {
            'money': round(g.farms[0].money, 2),
            'farmer': list(g.farms[0].farmer),
            'hands': [list(h) for h in g.farms[0].hands],
            'tiles': [[format_tile(t) for t in row] for row in g.farms[0].tiles],
            'seeds': dict(g.farms[0].seeds),
            'shed': dict(g.farms[0].shed),
            'inventories': [dict(inv) for inv in g.farms[0].inventories]
        },
        'p1': {
            'money': round(g.farms[1].money, 2),
            'farmer': list(g.farms[1].farmer),
            'hands': [list(h) for h in g.farms[1].hands],
            'tiles': [[format_tile(t) for t in row] for row in g.farms[1].tiles],
            'seeds': dict(g.farms[1].seeds),
            'shed': dict(g.farms[1].shed),
            'inventories': [dict(inv) for inv in g.farms[1].inventories]
        },
        'market': {'prices': prices, 'inventory': dict(g.market_inv)},
        'town': {'unlocked_shops': list(g.unlocked_shops)}
    })

    elapsed = time.time() - t0
    return {
        'seed': seed,
        'opponent': opp_type,
        'elapsed_seconds': round(elapsed, 3),
        'p0_final_score': round(g.farms[0].money, 2),
        'p1_final_score': round(g.farms[1].money, 2),
        'winner': 'Player 0 (Our Agent)' if g.farms[0].money > g.farms[1].money else ('Player 1 (Opponent)' if g.farms[1].money > g.farms[0].money else 'Tie'),
        'total_steps': len(steps_telemetry),
        'steps': steps_telemetry
    }
