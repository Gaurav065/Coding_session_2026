import sys, json, time, math, numpy as np
from scipy import stats

sys.path.insert(0, r'C:/Coding')
from project_maestro.engine.fast_engine import FastGame
from project_maestro.agent.dispatcher_agent import (
    MaestroFullPortfolioAgent,
    COW_PASTURES,
    SHEEP_PASTURES,
    SHED_ACCESS_TILES,
)
from project_maestro.agent.meta_calibrated_opponent import make_meta_calibrated_opponent

DISJOINT_100 = list(range(10000, 10100))
OFFICIAL_20  = [10, 20, 30, 42, 55, 77, 99, 100, 123, 200,
                250, 300, 333, 404, 500, 600, 700, 777, 888, 999]

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

ARCHETYPES = [
    ('Ahmad Ali Specialist (14S / 0C)', lambda: ReplayAhmadAliAgent()),
    ('Dominant Meta (10C / 4S)', lambda: MaestroFullPortfolioAgent(params={'cow_cap_base': 10, 'sheep_cap': 4, 'enable_3b': False})),
    ('Gould Research Pastoral (12C / 6S)', lambda: MaestroFullPortfolioAgent(params={'cow_cap_base': 12, 'sheep_cap': 6, 'enable_3b': False})),
    ('Ayushk Empire Diversified (3C / 13S)', lambda: MaestroFullPortfolioAgent(params={'cow_cap_base': 3, 'sheep_cap': 13, 'enable_3b': False})),
    ('Meta-Calibrated Opponent (8C / 6S)', lambda: make_meta_calibrated_opponent()),
]

def run_canaries_1_2(agent_cls, name):
    print(f'Checking Canaries 1 & 2 for {name}...')
    pass_scores = []
    for s in OFFICIAL_20:
        g = FastGame(seed=s)
        a = agent_cls()
        while not g.done:
            g.step_game(a(g.get_observation(0)), {'farmer': ['PASS'], 'hands': [], 'market': []})
        pass_scores.append(g.farms[0].money)
    mean_pass = np.mean(pass_scores)
    assert mean_pass >= 85000.0, f'Canary 1 FAIL: mean vs pass =  < '
    print(f'  Canary 1 PASS: Mean vs Pass =  >= ,000')

    g1 = FastGame(seed=42)
    a0_1, a1_1 = agent_cls(), agent_cls()
    while not g1.done:
        g1.step_game(a0_1(g1.get_observation(0)), a1_1(g1.get_observation(1)))

    g2 = FastGame(seed=42)
    a0_2, a1_2 = agent_cls(), agent_cls()
    while not g2.done:
        g2.step_game(a0_2(g2.get_observation(0)), a1_2(g2.get_observation(1)))

    assert g1.farms[0].money == g2.farms[0].money, 'Canary 2 FAIL: Non-deterministic self-play'
    print(f'  Canary 2 PASS: Deterministic self-play on seed 42 = ')

def eval_candidate_vs_archetypes(cand_cls, label):
    print(f'\n=========================================================================================================')
    print(f'EVALUATING: {label}')
    print(f'=========================================================================================================')
    results = {}
    opp_control_scores = {}

    for arch_name, arch_builder in ARCHETYPES:
        cand_scores = []
        opp_scores = []
        wins = 0
        losses = 0
        ties = 0

        for s in DISJOINT_100:
            # Seat 0
            g0 = FastGame(seed=s)
            c0 = cand_cls()
            o0 = arch_builder()
            while not g0.done:
                g0.step_game(c0(g0.get_observation(0)), o0(g0.get_observation(1)))
            cand_scores.append(g0.farms[0].money)
            opp_scores.append(g0.farms[1].money)
            if g0.farms[0].money > g0.farms[1].money: wins += 1
            elif g0.farms[0].money < g0.farms[1].money: losses += 1
            else: ties += 1

            # Seat 1
            g1 = FastGame(seed=s)
            c1 = cand_cls()
            o1 = arch_builder()
            while not g1.done:
                g1.step_game(o1(g1.get_observation(0)), c1(g1.get_observation(1)))
            cand_scores.append(g1.farms[1].money)
            opp_scores.append(g1.farms[0].money)
            if g1.farms[1].money > g1.farms[0].money: wins += 1
            elif g1.farms[1].money < g1.farms[0].money: losses += 1
            else: ties += 1

        n_games = len(cand_scores)
        wr = (wins + 0.5 * ties) / n_games * 100
        diffs = np.array(cand_scores) - np.array(opp_scores)
        margin = np.mean(diffs)
        t_stat = stats.ttest_1samp(diffs, 0.0).statistic if np.std(diffs) > 0 else 0.0

        results[arch_name] = {
            'wr': wr, 'wins': wins, 'losses': losses, 'ties': ties,
            'margin': margin, 'cand_mean': np.mean(cand_scores),
            'opp_mean': np.mean(opp_scores), 't_stat': t_stat
        }
        opp_control_scores[arch_name] = np.mean(opp_scores)

        print(f'vs {arch_name:<40} | WR: {wr:5.1f}% ({wins:3d}W/{losses:3d}L/{ties:2d}T) | Margin:  | Cand:  vs Opp:  | t={t_stat:5.2f}')

    # Self-play Floor Evaluation on Disjoint-100 (Seat 0 only, N=100)
    self_scores = []
    for s in DISJOINT_100:
        g = FastGame(seed=s)
        a0 = cand_cls()
        a1 = cand_cls()
        while not g.done:
            g.step_game(a0(g.get_observation(0)), a1(g.get_observation(1)))
        self_scores.append(g.farms[0].money)

    self_mean = np.mean(self_scores)
    self_med = np.median(self_scores)
    self_p5 = np.percentile(self_scores, 5)
    self_min = np.min(self_scores)
    results['self_play'] = {
        'mean': self_mean, 'median': self_med, 'p5': self_p5, 'min': self_min
    }
    print(f'  Floor ({label}) | Mean:  | Median:  | p5:  | Min: ')
    return results, opp_control_scores

if __name__ == '__main__':
    t0 = time.time()
    print('Starting Benchmark for Integrated Fixes (Coop Purge + Seed Optimization + Center-First Crop Sorting)...')

    # Canaries 1 & 2
    run_canaries_1_2(MaestroFullPortfolioAgent, 'Candidate (Fixed Production Agent)')

    cand_results, cand_opp_scores = eval_candidate_vs_archetypes(MaestroFullPortfolioAgent, 'Candidate: Fixed Production Agent')

    # Verify Canary 6 on Candidate
    print('\nChecking Canary 6 (Archetype Opponent Floor > ,000)...')
    for arch_name, score in cand_opp_scores.items():
        assert score >= 20000.0, f'Canary 6 FAIL: {arch_name} score =  < ,000'
        print(f'  Opponent {arch_name:<45} Mean Score:  -> PASS')
    print('Canary 6: ALL ARCHETYPES PASS')

    print('\n' + '=' * 135)
    print('=== INTEGRATED FIXES EVALUATION MATRIX (n=200 per archetype, Disjoint-100 x 2 seats flipped) ===')
    print('=' * 135)
    print('Metric / Archetype                          | Candidate (Fixed Production) | Control Baseline (9C/4S Pre-Fix)')
    print('-' * 135)

    control_baselines = {
        'Ahmad Ali Specialist (14S / 0C)': 'WR:  53.0% (Margin: $ -1700)',
        'Dominant Meta (10C / 4S)': 'WR:  76.0% (Margin: $ +3702)',
        'Gould Research Pastoral (12C / 6S)': 'WR:  89.0% (Margin: $ +9761)',
        'Ayushk Empire Diversified (3C / 13S)': 'WR:  98.5% (Margin: $+17342)',
        'Meta-Calibrated Opponent (8C / 6S)': 'WR:  96.0% (Margin: $ +9120)',
    }

    for arch_name, _ in ARCHETYPES:
        k_wr = cand_results[arch_name]['wr']
        k_mar = cand_results[arch_name]['margin']
        ctrl_str = control_baselines.get(arch_name, 'N/A')
        print(f'{arch_name:<43} | WR: {k_wr:5.1f}% (Margin: )   | {ctrl_str}')

    print('-' * 135)
    k_self = cand_results['self_play']
    print(f'Self-Play Mean (Disjoint-100)               |                        | $  61294')
    print(f'Self-Play p5 Floor (Disjoint-100)           |                        | $  41045')
    print(f'Self-Play Min Floor (Disjoint-100)          |                        | $  28847')
    print('=' * 135)
    print(f'Benchmark Completed in {time.time() - t0:.1f}s')
