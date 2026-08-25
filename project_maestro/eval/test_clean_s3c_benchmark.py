
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

class AgentControl_NW3b(MaestroFullPortfolioAgent):
    def __init__(self, params=None, kw_early=10, seed=None):
        if params is None:
            params = {}
        params['enable_3b'] = True
        params['enable_3c'] = False
        super().__init__(params=params, kw_early=kw_early, seed=seed)
        self.cow_pastures = list(NW_CLUSTERED_COW_PASTURES)
        self.sheep_pastures = list(NW_CLUSTERED_SHEEP_PASTURES)

class AgentCandidate_NW3b_3c(MaestroFullPortfolioAgent):
    def __init__(self, params=None, kw_early=10, seed=None):
        if params is None:
            params = {}
        params['enable_3b'] = True
        params['enable_3c'] = True
        super().__init__(params=params, kw_early=kw_early, seed=seed)
        self.cow_pastures = list(NW_CLUSTERED_COW_PASTURES)
        self.sheep_pastures = list(NW_CLUSTERED_SHEEP_PASTURES)

ARCHETYPES = [
    ('Ahmad Ali Specialist (14S / 0C)', lambda: ReplayAhmadAliAgent()),
    ('Dominant Meta (10C / 4S)', lambda: LegacyBaselineAgent(params={'cow_cap_base': 10, 'sheep_cap': 4, 'goose_cap': 0, 'cow_gate_day_early': 99, 'cow_gate_day_mid': 99})),
    ('Gould Research Pastoral (12C / 6S)', lambda: LegacyBaselineAgent(params={'cow_cap_base': 12, 'sheep_cap': 6, 'goose_cap': 0, 'cow_gate_day_early': 99, 'cow_gate_day_mid': 99})),
    ('Ayushk Empire Diversified (3C / 13S)', lambda: LegacyBaselineAgent(params={'cow_cap_base': 3, 'sheep_cap': 13, 'goose_cap': 0, 'cow_gate_day_early': 99, 'cow_gate_day_mid': 99})),
    ('Meta-Calibrated Opponent (8C / 6S)', lambda: make_meta_calibrated_opponent()),
]

def run_canaries_1_2(agent_cls, name):
    print('Running Canaries 1 & 2 for: ' + name)
    g1 = FastGame(seed=123)
    cand = agent_cls()
    pass_a = lambda obs: {'farmer': ['PASS'], 'hands': [], 'market': []}
    while not g1.done:
        g1.step_game(cand(g1.get_observation(0)), pass_a(g1.get_observation(1)))
    c1_opp = g1.farms[1].money
    c1_ok = abs(c1_opp - 3000.0) < 1e-6
    print('  Canary 1 (Pass opp = ,000.00): ' + ('PASS' if c1_ok else 'FAIL') + ' (opp=$' + str(round(c1_opp, 2)) + ')')
    assert c1_ok, 'Canary 1 failed'

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
    print('  Canary 2 (Identity 50%/D=): ' + ('PASS' if c2_ok else 'FAIL') + ' (WR=' + str(round(wr*100, 1)) + '%, D=$' + str(round(mean_d, 2)) + ')')
    assert c2_ok, 'Canary 2 failed'

def run_suite_eval(agent_cls, name):
    print('\n' + '=' * 105)
    print('BENCHMARK: ' + name)
    print('=' * 105)
    results = {}
    
    for arch_name, arch_builder in ARCHETYPES:
        deltas, c_scores, o_scores = [], [], []
        wins, losses, ties = 0, 0, 0
        fert_actions_total = 0

        for s in DISJOINT_100:
            for seat in [0, 1]:
                cand = agent_cls()
                opp = arch_builder()
                g = FastGame(seed=s)
                a = [cand, opp] if seat == 0 else [opp, cand]
                
                while not g.done:
                    obs0 = g.get_observation(0)
                    obs1 = g.get_observation(1)
                    act0 = a[0](obs0)
                    act1 = a[1](obs1)
                    
                    cand_act = act0 if seat == 0 else act1
                    if cand_act.get('farmer') == ['FERTILIZE']: fert_actions_total += 1
                    for h in cand_act.get('hands', []):
                        if h == ['FERTILIZE']: fert_actions_total += 1
                        
                    g.step_game(act0, act1)

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
        avg_fert = fert_actions_total / n_games

        print('vs ' + arch_name.ljust(40) + ' | WR: ' + str(round(wr, 1)).rjust(5) + '% (' + str(wins).rjust(3) + 'W/' + str(losses).rjust(3) + 'L/' + str(ties).rjust(2) + 'T) | Delta: $' + str(round(mean_d, 2)).rjust(9) + ' | Cand: $' + str(round(c_mean)).rjust(7) + ' vs Opp: $' + str(round(o_mean)).rjust(7) + ' | t=' + str(round(t_stat, 2)).rjust(5) + ' | avg_fert=' + str(round(avg_fert, 1)))
        results[arch_name] = {
            'wr': wr, 'wins': wins, 'losses': losses, 'ties': ties,
            'mean_d': mean_d, 'c_mean': c_mean, 'o_mean': o_mean,
            't_stat': t_stat, 'p_val': p_val, 'avg_fert': avg_fert
        }
    return results

def run_selfplay_floor(agent_cls, label):
    print('\n--- Floor Check: ' + label + ' ---')
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

    print('  Disjoint-100 | Mean: $' + str(round(mean_s, 2)) + ' | Median: $' + str(round(med_s, 2)) + ' | Floor (Min): $' + str(round(min_s, 2)) + ' | p5: $' + str(round(p5_s, 2)))
    return {'mean': mean_s, 'median': med_s, 'floor': min_s, 'p5': p5_s}

if __name__ == '__main__':
    t_start = time.time()
    
    run_canaries_1_2(AgentControl_NW3b, 'Control (NW+3b, s3c Disabled)')
    run_canaries_1_2(AgentCandidate_NW3b_3c, 'Candidate (NW+3b + s3c, s3c Enabled)')
    
    ctrl_results = run_suite_eval(AgentControl_NW3b, 'Control: NW+3b Baseline (enable_3c=False)')
    
    print('\nChecking Canary 6 (Archetype Opponent Floor > ,000)...')
    canary_6_pass = True
    for arch_name, res in ctrl_results.items():
        o_m = res['o_mean']
        ok = o_m > 20000.0
        print('  Opponent ' + arch_name.ljust(40) + ' Mean Score: $' + str(round(o_m)) + ' -> ' + ('PASS' if ok else 'FAIL'))
        if not ok: canary_6_pass = False
    assert canary_6_pass, 'Canary 6 FAILED -- Archetype opponent scored <= ,000!'
    print('Canary 6: ALL ARCHETYPES PASS (all > ,000)')

    cand_results = run_suite_eval(AgentCandidate_NW3b_3c, 'Candidate: NW+3b + s3c (enable_3c=True)')

    ctrl_floor = run_selfplay_floor(AgentControl_NW3b, 'Control (NW+3b, s3c Disabled)')
    cand_floor = run_selfplay_floor(AgentCandidate_NW3b_3c, 'Candidate (NW+3b + s3c, s3c Enabled)')

    print('\n' + '=' * 105)
    print('=== s3c MELON FERTILIZATION ABLATION BENCHMARK SUMMARY ===')
    print('=' * 105)
    print('Archetype'.ljust(40) + ' | Control WR | Cand WR  | Delta (pp) | Control Margin | Cand Margin | Margin Delta')
    print('-' * 105)
    for arch_name, _ in ARCHETYPES:
        c_wr = ctrl_results[arch_name]['wr']
        k_wr = cand_results[arch_name]['wr']
        d_wr = k_wr - c_wr
        c_m  = ctrl_results[arch_name]['mean_d']
        k_m  = cand_results[arch_name]['mean_d']
        d_m  = k_m - c_m
        print(arch_name.ljust(40) + ' | ' + str(round(c_wr, 1)).rjust(8) + '% | ' + str(round(k_wr, 1)).rjust(6) + '% | ' + (('+' if d_wr>=0 else '') + str(round(d_wr, 1))).rjust(8) + 'pp | $' + str(round(c_m, 2)).rjust(12) + ' | $' + str(round(k_m, 2)).rjust(9) + ' | $' + str(round(d_m, 2)).rjust(10))

    print('\n--- Floor & Distribution (Disjoint-100 Self-Play) ---')
    print('Control   | Mean: $' + str(round(ctrl_floor['mean'])) + ' | p5: $' + str(round(ctrl_floor['p5'])) + ' | Min: $' + str(round(ctrl_floor['floor'])))
    print('Candidate | Mean: $' + str(round(cand_floor['mean'])) + ' | p5: $' + str(round(cand_floor['p5'])) + ' | Min: $' + str(round(cand_floor['floor'])))
    p5_pct = (cand_floor['p5'] - ctrl_floor['p5']) / ctrl_floor['p5'] * 100
    mean_pct = (cand_floor['mean'] - ctrl_floor['mean']) / ctrl_floor['mean'] * 100
    print('Delta     | Mean: ' + ('+' if mean_pct>=0 else '') + str(round(mean_pct, 2)) + '% | p5: ' + ('+' if p5_pct>=0 else '') + str(round(p5_pct, 2)) + '%')
    print('Total Elapsed Time: ' + str(round(time.time() - t_start, 1)) + 's')
