import json

nb_path = r'C:\Users\GauravPatel\Downloads\shape-the-shop-work-the-pasture-kaggriculture.ipynb'
with open(nb_path, 'r', encoding='utf-8') as f:
    nb = json.load(f)

for i in [3, 7, 9, 14, 16, 29]:
    if i < len(nb.get('cells', [])):
        src = ''.join(nb['cells'][i].get('source', []))
        print(f"\n{'='*60}\nCELL {i}\n{'='*60}")
        print(src[:1500])
