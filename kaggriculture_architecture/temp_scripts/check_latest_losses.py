import json
import glob
import pandas as pd

df = pd.read_csv('eps_new.csv', encoding='utf-16')
latest_ids = df['id'].astype(str).tolist()

for f in sorted(glob.glob('episode-*-replay.json')):
    id = f.split('-')[1]
    if id not in latest_ids:
        continue
    try:
        with open(f, encoding='utf-8') as fin:
            d = json.load(fin)
    except: continue
    agents = d.get('info', {}).get('TeamNames', ['P1', 'P2'])
    our_seat = 0 if 'Gaurav065' in agents[0] else 1
    opp_seat = 1-our_seat
    s = d.get('steps', [])[-1]
    p_our = s[our_seat].get('reward', 0)
    p_opp = s[opp_seat].get('reward', 0)
    
    if p_our < p_opp:
        opp_name = agents[opp_seat].encode('ascii','replace').decode()
        print(f'{f}: {opp_name} won ({p_opp} vs {p_our} -> margin {p_opp - p_our})')
