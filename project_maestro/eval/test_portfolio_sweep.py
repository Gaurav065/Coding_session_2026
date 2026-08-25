
import sys, json, time, math, numpy as np
from scipy import stats

sys.path.insert(0, r'C:/Coding')
from project_maestro.engine.fast_engine import FastGame
from project_maestro.agent.dispatcher_agent import (
    MaestroFullPortfolioAgent,
    make_spatial_dispatcher_agent,
    COW_PASTURES,
    SHEEP_PASTURES,
    SHED_ACCESS_TILES,
)
from project_maestro.agent.meta_calibrated_opponent import make_meta_calibrated_opponent

DISJOINT_100 = list(range(10000, 10100))
OFFICIAL_20  = [10, 20, 30, 42, 55, 77, 99, 100, 123, 200,
                250, 300, 333, 404, 500, 600, 700, 777, 888, 999]

BASELINE_COW_PASTURES = [
    (4, 3), (3, 4),
    (4, 2), (3, 3), (2, 4),
    (4, 1), (3, 2), (2, 3), (1, 4),
    (4, 0)
]
BASELINE_SHEEP_PASTURES = [
    (3, 1), (2, 2), (1, 3), (0, 4)
]

NW_CLUSTERED_COW_PASTURES = [
    (4, 3), (3, 4),
    (4, 2), (3, 3), (2, 4),
    (4, 1), (3, 2), (2, 3), (1, 4),
    (3, 1), (2, 2), (1, 3), (0, 4), (4, 0)
]
NW_CLUSTERED_SHEEP_PASTURES = [
    (3, 1), (2, 2), (1, 3), (0, 4)
]

with open('replays/episode-99064717-replay.json', encoding='utf-8') as f:
    d = json.load(f)
steps = d.get('steps', [])
ahmad_actions = [steps[t][0].get('action', {}) for t in range(1, len(steps))]

class ReplayAhmadAliAgent:
    def __init__(self):
        self.step_idx = 0
    def __call__(self, obs):
        if self.step_idx < len(ahmad_actions):
            act = ahmad_actions[self.step_idx]
            self.step_idx += 1
            return act
        return {'farmer': ['PASS'], 'hands': [], 'market': []}

class LegacyBaselineAgent(MaestroFullPortfolioAgent):
    def __init__(self, params=None, kw_early=10, seed=None):
        if params is None:
            params = {}
        params['enable_3b'] = False
        params['enable_3c'] = False
        super().__init__(params=params, kw_early=kw_early, seed=seed)
        self.cow_pastures = list(BASELINE_COW_PASTURES)
        self.sheep_pastures = list(BASELINE_SHEEP_PASTURES)

def make_portfolio_candidate_class(c_cap, s_cap, yarn_gate=True, label=''):
    class CustomCandidate(MaestroFullPortfolioAgent):
        def __init__(self, params=None, kw_early=10, seed=None):
            p = {
                'cow_cap_base': c_cap,
                'sheep_cap': s_cap,
                'cow_cap_low': min(6, c_cap),
                'cow_cap_zero': min(4, c_cap),
                'yarn_gate_sheep': yarn_gate,
                'enable_3b': True,
            }
            if params:
                p.update(params)
            super().__init__(params=p, kw_early=kw_early, seed=seed)
            self.cow_pastures = list(NW_CLUSTERED_COW_PASTURES[:c_cap])
            self.sheep_pastures = list(NW_CLUSTERED_COW_PASTURES[c_cap : c_cap + s_cap])
    CustomCandidate.__name__ = label or f'Cand_{c_cap}C_{s_cap}S'
    return CustomCandidate

PORTFOLIO_ARMS = [
    ('Control: 9C / 4S (Current Production)', make_portfolio_candidate_class(9, 4, yarn_gate=True, label='Ctrl_9C_4S')),
    ('Candidate 1: 10C / 4S (Max Cow)', make_portfolio_candidate_class(10, 4, yarn_gate=True, label='Cand_10C_4S')),
    ('Candidate 2: 8C / 6S (Balanced-Cow)', make_portfolio_candidate_class(8, 6, yarn_gate=True, label='Cand_8C_6S')),
    ('Candidate 3: 7C / 7S (Balanced-YarnGated)', make_portfolio_candidate_class(7, 7, yarn_gate=True, label='Cand_7C_7S_gated')),
    ('Candidate 4: 7C / 7S (Balanced-Ungated)', make_portfolio_candidate_class(7, 7, yarn_gate=False, label='Cand_7C_7S_ungated')),
    ('Candidate 5: 6C / 8S (Sheep-Leaning)', make_portfolio_candidate_class(6, 8, yarn_gate=False, label='Cand_6C_8S_ungated')),
    ('Candidate 6: 5C / 9S (Ladder-Specialist)', make_portfolio_candidate_class(5, 9, yarn_gate=False, label='Cand_5C_9S_ungated')),
]

ARCHETYPES = [
    ('Ahmad Ali Specialist (14S / 0C)', lambda: ReplayAhmadAliAgent()),
    ('Dominant Meta (10C / 4S)', lambda: LegacyBaselineAgent(params={'cow_cap_base': 10, 'sheep_cap': 4, 'goose_cap': 0, 'cow_gate_day_early': 99, 'cow_gate_day_mid': 99})),
    ('Gould Research Pastoral (12C / 6S)', lambda: LegacyBaselineAgent(params={'cow_cap_base': 12, 'sheep_cap': 6, 'goose_cap': 0, 'cow_gate_day_early': 99, 'cow_gate_day_mid': 99})),
    ('Ayushk Empire Diversified (3C / 13S)', lambda: LegacyBaselineAgent(params={'cow_cap_base': 3, 'sheep_cap': 13, 'goose_cap': 0, 'cow_gate_day_early': 99, 'cow_gate_day_mid': 99})),
    ('Meta-Calibrated Opponent (8C / 6S)', lambda: make_meta_calibrated_opponent()),
]

def run_canaries_1_2(agent_cls, name):
    g1 = FastGame(seed=123)
    cand = agent_cls()
    pass_a = lambda obs: {'farmer': ['PASS'], 'hands': [], 'market': []}
    while not g1.done:
        g1.step_game(cand(g1.get_observation(0)), pass_a(g1.get_observation(1)))
    c1_opp = g1.farms[1].money
    c1_ok = abs(c1_opp - 3000.0) < 1e-6
    assert c1_ok, f'Canary 1 failed for {name}'

    deltas, wins, losses, ties = [], 0, 0, 0
    for s in OFFICIAL_20:
        for flip in [False, True]:
            a0, a1 = agent_cls(), agent_cls()
            g2 = FastGame(seed=s)
            while not g2.done:
                g2.step_game(a0(g2.get_observation(0)), a1(g2.get_observation(1)))
            d = g2.farms[0].money - g2.farms[1].money
            d = d if not flip else -d
            deltas.append(d)
            if d > 0: wins += 1
            elif d < 0: losses += 1
            else: ties += 1
    wr = (wins + 0.5 * ties) / (wins + losses + ties)
    mean_d = np.mean(deltas)
    c2_ok = abs(mean_d) < 1e-6 and abs(wr - 0.5) < 1e-6
    assert c2_ok, f'Canary 2 failed for {name}'

def run_suite_eval(agent_cls, name):
    print('\n' + '=' * 105)
    print('EVALUATING: ' + name)
    print('=' * 105)
    results = {}
    
    for arch_name, arch_builder in ARCHETYPES:
        deltas, c_scores, o_scores = [], [], []
        wins, losses, ties = 0, 0, 0

        for s in DISJOINT_100:
            for seat in [0, 1]:
                cand = agent_cls()
                opp = arch_builder()
                g = FastGame(seed=s)
                a = [cand, opp] if seat == 0 else [opp, cand]
                
                while not g.done:
                    g.step_game(a[0](g.get_observation(0)), a[1](g.get_observation(1)))

                r_cand = g.farms[seat].money
                r_opp = g.farms[1 - seat].money
                c_scores.append(r_cand)
                o_scores.append(r_opp)
                delta = r_cand - r_opp
                deltas.append(delta)

                if delta > 0: wins += 1
                elif delta < 0: losses += 1
                else: ties += 1

        n_games = len(deltas)
        wr = (wins + 0.5 * ties) / n_games * 100
        mean_d = np.mean(deltas)
        t_stat, p_val = stats.ttest_1samp(deltas, 0.0)
        c_mean = np.mean(c_scores)
        o_mean = np.mean(o_scores)

        print(f'vs {arch_name.ljust(38)} | WR: {wr:5.1f}% ({wins:3d}W/{losses:3d}L/{ties:2d}T) | Margin: ${mean_d:9.2f} | Cand: ${c_mean:7.0f} vs Opp: ${o_mean:7.0f} | t={t_stat:5.2f}')
        results[arch_name] = {
            'wr': wr, 'wins': wins, 'losses': losses, 'ties': ties,
            'mean_d': mean_d, 'c_mean': c_mean, 'o_mean': o_mean,
            't_stat': t_stat, 'p_val': p_val
        }
    return results

def run_selfplay_floor(agent_cls, label):
    c_scores = []
    for s in DISJOINT_100:
        a0 = agent_cls()
        a1 = agent_cls()
        g = FastGame(seed=s)
        while not g.done:
            g.step_game(a0(g.get_observation(0)), a1(g.get_observation(1)))
        c_scores.append(g.farms[0].money)

    c_scores.sort()
    mean_s = np.mean(c_scores)
    med_s  = np.median(c_scores)
    min_s  = np.min(c_scores)
    p5_s   = np.percentile(c_scores, 5)

    print(f'  Floor ({label}) | Mean: ${mean_s:7.0f} | Median: ${med_s:7.0f} | p5: ${p5_s:7.0f} | Min: ${min_s:7.0f}')
    return {'mean': mean_s, 'median': med_s, 'floor': min_s, 'p5': p5_s}

if __name__ == '__main__':
    t_start = time.time()
    all_results = {}
    all_floors = {}

    print('=== RUNNING CANARIES 1 & 2 FOR ALL ARMS ===')
    for label, cls in PORTFOLIO_ARMS:
        run_canaries_1_2(cls, label)
        print(f'  {label.ljust(45)} -> Canaries 1 & 2: PASS')
    print('All Canaries 1 & 2 PASSED successfully.')

    for label, cls in PORTFOLIO_ARMS:
        res = run_suite_eval(cls, label)
        flr = run_selfplay_floor(cls, label)
        all_results[label] = res
        all_floors[label] = flr

    ctrl_res = all_results['Control: 9C / 4S (Current Production)']
    print('\nChecking Canary 6 (Archetype Opponent Floor > $20,000 in Control)...')
    canary_6_pass = True
    for arch_name, res in ctrl_res.items():
        o_m = res['o_mean']
        ok = o_m > 20000.0
        print(f'  Opponent {arch_name.ljust(38)} Mean Score: ${o_m:7.0f} -> {("PASS" if ok else "FAIL")}')
        if not ok: canary_6_pass = False
    assert canary_6_pass, 'Canary 6 FAILED'
    print('Canary 6: ALL ARCHETYPES PASS')

    print('\n' + '=' * 125)
    print('=== LIVESTOCK PORTFOLIO ALLOCATION LADDER SWEEP SUMMARY (n=200 per cell, post-Canary-6) ===')
    print('=' * 125)
    header = 'Portfolio Arm'.ljust(42) + ' | vs AhmadAli | vs DomMeta | vs Gould | vs Ayushk | vs MetaCal | Self Mean | Self p5 | Self Min'
    print(header)
    print('-' * 125)

    for label, _ in PORTFOLIO_ARMS:
        res = all_results[label]
        flr = all_floors[label]
        wr_ahmad = res['Ahmad Ali Specialist (14S / 0C)']['wr']
        wr_dm    = res['Dominant Meta (10C / 4S)']['wr']
        wr_gould = res['Gould Research Pastoral (12C / 6S)']['wr']
        wr_ayush = res['Ayushk Empire Diversified (3C / 13S)']['wr']
        wr_mcal  = res['Meta-Calibrated Opponent (8C / 6S)']['wr']
        row = f'{label.ljust(42)} | {wr_ahmad:9.1f}% | {wr_dm:8.1f}% | {wr_gould:6.1f}% | {wr_ayush:7.1f}% | {wr_mcal:8.1f}% | ${flr["mean"]:7.0f} | ${flr["p5"]:6.0f} | ${flr["floor"]:6.0f}'
        print(row)

    print('\nTotal Sweep Wall Time: ' + str(round(time.time() - t_start, 1)) + 's')
