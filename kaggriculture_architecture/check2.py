import json

def get_terminal_loss(fname):
    try:
        with open(fname, encoding='utf-8') as fin:
            d = json.load(fin)
    except:
        return
        
    agents = d.get('info', {}).get('TeamNames', ['P1', 'P2'])
    our_seat = 0 if 'Gaurav065' in agents[0] else 1
    opp_seat = 1 - our_seat
    
    act_718 = d['steps'][718][our_seat]['action']
    drops = 0
    hands = act_718.get('hands', [])
    for h in hands:
        if isinstance(h, list) and h and h[0] == 'DROP': drops += 1
    if act_718.get('farmer') and act_718['farmer'][0] == 'DROP': drops += 1
    
    print(f'{fname} (vs {agents[opp_seat].encode("ascii","replace").decode()}):')
    print(f'  Turn 718 worker DROP actions: {drops}')
    
    act_719 = d['steps'][719][our_seat]['action']
    print(f"  Turn 719 Market Sales: {act_719.get('market', [])}")
    print('')

for f in ['episode-104529416-replay.json', 'episode-104528972-replay.json', 'episode-104528532-replay.json', 'episode-104530263-replay.json']:
    get_terminal_loss(f)
