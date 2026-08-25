import sys, json, numpy as np
sys.path.insert(0, r'C:\Coding')
from project_maestro.engine.fast_engine import FastGame
from project_maestro.agent.dispatcher_agent import MaestroFullPortfolioAgent, make_spatial_dispatcher_agent

DISJOINT_100 = list(range(10000, 10100))
OFFICIAL_20  = [10,20,30,42,55,77,99,100,123,200,250,300,333,404,500,600,700,777,888,999]
FLOOR_GATE   = 32300.0

NW_COW = [(4,3),(3,4),(4,2),(3,3),(2,4),(4,1),(3,2),(2,3),(1,4),(3,1),(2,2),(1,3),(0,4),(4,0)]
NW_SHP = [(3,1),(2,2),(1,3),(0,4)]

class NW3b(MaestroFullPortfolioAgent):
    def __init__(self, **kw):
        super().__init__(**kw)
        self.cow_pastures = list(NW_COW)
        self.sheep_pastures = list(NW_SHP)
    def __call__(self, obs):
        act  = super().__call__(obs)
        shed = obs['private'].get('shed', {})
        money= obs['farms'][obs['player']]['money']
        day  = obs['day']
        hour = obs['hour']
        reserve = max(10, (self.params.get('cow_cap_base',9)+self.params.get('sheep_cap',4))*2)
        filtered = []
        for o in act.get('market', []):
            if isinstance(o, list) and len(o)>=3 and o[0]=='SELL' and o[1]=='WHEAT':
                surplus = shed.get('WHEAT',0) - reserve
                if surplus > 0:
                    filtered.append(['SELL','WHEAT', min(o[2], surplus)])
            else:
                filtered.append(o)
        if hour==0 and day<29 and shed.get('WHEAT',0)<reserve and money>=100:
            bq = min(reserve-shed.get('WHEAT',0), int(money//25), 8)
            if bq>0 and len(filtered)<10:
                filtered.append(['BUY_PRODUCT','WHEAT',bq])
        act['market'] = filtered[:10]
        return act

# Canary 1
g = FastGame(seed=123)
c = NW3b()
pa = lambda o: {'farmer':['PASS'],'hands':[],'market':[]}
while not g.done: g.step_game(c(g.get_observation(0)), pa(g.get_observation(1)))
c1 = g.farms[1].money
print('Canary 1:', 'PASS' if abs(c1-3000)<1 else 'FAIL', f'opp=')

# Canary 2
wins=losses=ties=0; deltas=[]
for s in OFFICIAL_20:
    for flip in [False,True]:
        a0,a1 = NW3b(),NW3b()
        g2 = FastGame(seed=s)
        while not g2.done: g2.step_game(a0(g2.get_observation(0)),a1(g2.get_observation(1)))
        d = g2.farms[0].money - g2.farms[1].money
        if flip: d = -d
        deltas.append(d)
        if d>0: wins+=1
        elif d<0: losses+=1
        else: ties+=1
wr = (wins+0.5*ties)/(wins+losses+ties)
md = sum(deltas)/len(deltas)
print('Canary 2:', 'PASS' if abs(md)<1 and abs(wr-0.5)<0.01 else 'FAIL', f'WR={wr*100:.1f}% D=')

# Floor scan
print(f'\nSeeds below :')
print(f'{"Seed":>6}  {"Score":>10}  {"Opp":>10}  {"Delta":>10}  {"MinCash(d10)":>14}  Shops')
print('-'*100)
all_scores = []
bad_seeds  = []
for s in DISJOINT_100:
    cand = NW3b()
    opp  = make_spatial_dispatcher_agent()
    g    = FastGame(seed=s)
    min_cash = 1e9
    final_shops = []
    while not g.done:
        obs0 = g.get_observation(0)
        if obs0['day'] <= 10: min_cash = min(min_cash, obs0['farms'][0]['money'])
        final_shops = obs0.get('town',{}).get('unlocked_shops',[])
        g.step_game(cand(obs0), opp(g.get_observation(1)))
    sc = g.farms[0].money
    op = g.farms[1].money
    all_scores.append(sc)
    if sc < FLOOR_GATE:
        bad_seeds.append((s, sc, op, sc-op, min_cash, final_shops))
        shops_str = ','.join(sorted(set(final_shops))) if final_shops else 'none'
        print(f'{s:>6}          [{shops_str}]')

all_scores.sort()
print('-'*100)
print(f'Bad seeds: {len(bad_seeds)}')
print(f'Floor (min): ')
print(f'p5:          ')
print(f'Median:      ')
print(f'Mean:        ')
print()
if len(bad_seeds) <= 2:
    print('DECISION RULE: 1-2 bad seeds -> inspect for bounded cause -> ADOPT if identified')
else:
    print('DECISION RULE: multiple bad seeds -> identify common trigger -> fix first')
