import sys, json, time, math, numpy as np
from scipy import stats

sys.path.insert(0, 'C:/Coding')
from project_maestro.engine.fast_engine import FastGame
from project_maestro.agent.dispatcher_agent import (
    MaestroFullPortfolioAgent,
    make_spatial_dispatcher_agent,
    COW_PASTURES,
    SHEEP_PASTURES,
    SHED_ACCESS_TILES,
)

EVAL_SEEDS_100 = list(range(1000, 1100))
DISJOINT_100   = list(range(10000, 10100))
OFFICIAL_20    = [10, 20, 30, 42, 55, 77, 99, 100, 123, 200,
                  250, 300, 333, 404, 500, 600, 700, 777, 888, 999]

try:
    with open('project_maestro/replays/episode-99062443-replay.json') as f:
        rep = json.load(f)
    ahmad_actions = [s[0]['action'] for s in rep['steps'][1:]]
except Exception:
    ahmad_actions = []

class AhmadAliSpecialistReplayAgent:
    def __init__(self):
        self.step_idx = 0
    def __call__(self, obs):
        if self.step_idx < len(ahmad_actions):
            act = ahmad_actions[self.step_idx]
            self.step_idx += 1
            return act
        return {'farmer': ['PASS'], 'hands': [], 'market': []}

def make_archetype(cow_cap, sheep_cap, goose_cap=0):
    p = {
        'cow_cap_base': cow_cap,
        'sheep_cap': sheep_cap,
        'goose_cap': goose_cap,
        'milk_batch_cap': 4,
        'wool_batch_cap': 2,
    }
    return lambda: MaestroFullPortfolioAgent(params=p)

ARCHETYPES = {
    'Ahmad Ali Specialist (14S / 0C)': AhmadAliSpecialistReplayAgent,
    'Dominant Meta (10C / 4S)': make_archetype(10, 4),
    'Gould Research Pastoral (12C / 6S)': make_archetype(12, 6),
    'Ayushk Empire Diversified (3C / 13S)': make_archetype(3, 13),
    'Meta-Calibrated Opponent (8C / 6S)': make_archetype(8, 6),
}

class AgentControlStrict(MaestroFullPortfolioAgent):
    def __call__(self, obs):
        act = super().__call__(obs)
        if act.get('farmer') == ['FERTILIZE']:
            act['farmer'] = ['PASS']
        nh = []
        for h in act.get('hands', []):
            if h == ['FERTILIZE']:
                nh.append(['PASS'])
            else:
                nh.append(h)
        act['hands'] = nh
        return act

class AgentCandidate(MaestroFullPortfolioAgent):
    pass

def run_canaries(agent_cls, name):
    print('Running Canaries for: ' + name)
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

def run_ladder_eval(agent_cls, name):
    print('\n' + '=' * 100)
    print('BENCHMARK: ' + name)
    print('=' * 100)
    results = {}
    
    for arch_name, arch_builder in ARCHETYPES.items():
        deltas, c_scores, o_scores = [], [], []
        wins, losses, ties = 0, 0, 0
        fert_actions_total = 0

        for seed in EVAL_SEEDS_100:
            for flip in [False, True]:
                cand = agent_cls()
                opp = arch_builder()
                g = FastGame(seed=seed)
                
                while not g.done:
                    obs0 = g.get_observation(0)
                    obs1 = g.get_observation(1)
                    
                    if not flip:
                        act0 = cand(obs0)
                        act1 = opp(obs1)
                        if act0.get('farmer') == ['FERTILIZE']: fert_actions_total += 1
                        for h in act0.get('hands', []):
                            if h == ['FERTILIZE']: fert_actions_total += 1
                        g.step_game(act0, act1)
                    else:
                        act0 = opp(obs0)
                        act1 = cand(obs1)
                        if act1.get('farmer') == ['FERTILIZE']: fert_actions_total += 1
                        for h in act1.get('hands', []):
                            if h == ['FERTILIZE']: fert_actions_total += 1
                        g.step_game(act0, act1)

                c_score = g.farms[1 if flip else 0].money
                o_score = g.farms[0 if flip else 1].money
                delta = c_score - o_score

                c_scores.append(c_score)
                o_scores.append(o_score)
                deltas.append(delta)

                if delta > 0: wins += 1
                elif delta < 0: losses += 1
                else: ties += 1

        n_games = len(deltas)
        wr = (wins + 0.5 * ties) / n_games * 100
        mean_d = np.mean(deltas)
        t_stat, p_val = stats.ttest_1samp(deltas, 0)
        c_mean = np.mean(c_scores)
        o_mean = np.mean(o_scores)
        avg_fert = fert_actions_total / n_games

        print('  vs ' + arch_name.ljust(40) + ' | WR: ' + str(round(wr, 1)).rjust(5) + '% (' + str(wins).rjust(3) + 'W/' + str(losses).rjust(3) + 'L/' + str(ties).rjust(2) + 'T) | Delta: $' + str(round(mean_d, 2)).rjust(9) + ' | Cand: $' + str(round(c_mean)).rjust(7) + ' vs Opp: $' + str(round(o_mean)).rjust(7) + ' | t=' + str(round(t_stat, 2)).rjust(5) + ' | avg_fert=' + str(round(avg_fert, 1)))
        results[arch_name] = {'wr': wr, 'wins': wins, 'losses': losses, 'ties': ties, 'mean_d': mean_d, 'c_mean': c_mean, 'o_mean': o_mean, 't_stat': t_stat, 'p_val': p_val, 'avg_fert': avg_fert}
    return results

def run_selfplay_floor_check(agent_cls, label):
    print('\n--- Self-Play Floor Check: ' + label + ' ---')
    c_scores = []
    
    for s in DISJOINT_100:
        a0 = agent_cls()
        a1 = agent_cls()
        g = FastGame(seed=s)
        while not g.done:
            act0 = a0(g.get_observation(0))
            act1 = a1(g.get_observation(1))
            g.step_game(act0, act1)
        c_scores.append(g.farms[0].money)

    mean_s = np.mean(c_scores)
    med_s  = np.median(c_scores)
    min_s  = np.min(c_scores)
    p5_s   = np.percentile(c_scores, 5)

    print('  Disjoint-100 | Mean: $' + str(round(mean_s, 2)) + ' | Median: $' + str(round(med_s, 2)) + ' | Floor (Min): $' + str(round(min_s, 2)) + ' | p5: $' + str(round(p5_s, 2)))
    return {'mean': mean_s, 'median': med_s, 'floor': min_s, 'p5': p5_s}

if __name__ == '__main__':
    t_start = time.time()
    run_canaries(AgentControlStrict, 'Control (s3c Disabled)')
    run_canaries(AgentCandidate, 'Candidate (s3c Enabled)')

    ctrl_ladder = run_ladder_eval(AgentControlStrict, 'Control (s3c Disabled)')
    cand_ladder = run_ladder_eval(AgentCandidate, 'Candidate (s3c Enabled)')

    ctrl_floor = run_selfplay_floor_check(AgentControlStrict, 'Control (s3c Disabled)')
    cand_floor = run_selfplay_floor_check(AgentCandidate, 'Candidate (s3c Enabled)')

    print('\n' + '=' * 90)
    print('=== SUMMARY OF s3c MELON FERTILIZATION IMPACT ===')
    print('=' * 90)
    for k in ctrl_ladder:
        c_wr = ctrl_ladder[k]['wr']
        cand_wr = cand_ladder[k]['wr']
        diff = cand_wr - c_wr
        print('  ' + k.ljust(40) + ' | Control WR: ' + str(round(c_wr, 1)).rjust(5) + '% | Candidate WR: ' + str(round(cand_wr, 1)).rjust(5) + '% | Delta: ' + ('+' if diff>=0 else '') + str(round(diff, 1)) + 'pp')

    print('\n--- Floor & Distribution (Disjoint-100) ---')
    print('Control   | Mean: $' + str(round(ctrl_floor['mean'])) + ' | p5: $' + str(round(ctrl_floor['p5'])) + ' | Min: $' + str(round(ctrl_floor['floor'])))
    print('Candidate | Mean: $' + str(round(cand_floor['mean'])) + ' | p5: $' + str(round(cand_floor['p5'])) + ' | Min: $' + str(round(cand_floor['floor'])))

    p5d_pct = (cand_floor['p5'] - ctrl_floor['p5']) / ctrl_floor['p5'] * 100
    meand_pct = (cand_floor['mean'] - ctrl_floor['mean']) / ctrl_floor['mean'] * 100
    print('Delta     | Mean: ' + ('+' if meand_pct>=0 else '') + str(round(meand_pct, 2)) + '% | p5: ' + ('+' if p5d_pct>=0 else '') + str(round(p5d_pct, 2)) + '%')
    print('Total elapsed: ' + str(round(time.time() - t_start, 1)) + 's')
