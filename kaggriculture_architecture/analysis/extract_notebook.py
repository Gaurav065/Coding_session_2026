import json
import sys

sys.stdout.reconfigure(encoding='utf-8')

nb_path = r'C:\Users\GauravPatel\Downloads\shape-the-shop-work-the-pasture-kaggriculture.ipynb'
with open(nb_path, 'r', encoding='utf-8') as f:
    nb = json.load(f)

for i, cell in enumerate(nb.get('cells', [])):
    src = ''.join(cell.get('source', []))
    ctype = cell.get('cell_type')
    if ctype == 'code':
        print(f"\n{'='*80}\nCODE CELL {i}\n{'='*80}")
        print(src[:3000])
    elif any(k in src for k in ['SUBMISSION', 'pasture', 'guard', 'demand', 'closeout', 'Takeaways', 'Four questions']):
        print(f"\n{'='*80}\nMARKDOWN CELL {i}\n{'='*80}")
        print(src[:1500])
