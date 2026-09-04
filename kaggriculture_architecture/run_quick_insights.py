import pandas as pd

df = pd.read_csv('eda_metrics.csv')
day30 = df[df['Day'] == 30][['Replay_ID', 'Player_ID', 'Net_Worth']].rename(columns={'Net_Worth': 'Final_Score'})
day3 = df[df['Day'] == 3].merge(day30, on=['Replay_ID', 'Player_ID'])

day3 = day3[day3['Final_Score'] > 5000]

print("=== CORRELATION WITH FINAL SCORE (DAY 30) ===")
features = ['Liquid_Cash', 'Planted_Crops', 'Animals', 'Shed_Inventory']
print(day3[features + ['Final_Score']].corr()['Final_Score'].to_markdown())

elite = day3[day3['Final_Score'] >= 120000]
print("\n=== ELITE MEANS (>120k FINAL SCORE) ===")
print(elite[features].mean().to_markdown())

print("\n=== ARCHETYPES ===")
day3['Archetype'] = day3.apply(lambda r: 'Animal Rusher' if r['Animals'] > 3 else ('Crop Spammer' if r['Planted_Crops'] > 15 else 'Cash Hoarder'), axis=1)
print(day3.groupby('Archetype')['Final_Score'].mean().sort_values(ascending=False).to_markdown())

