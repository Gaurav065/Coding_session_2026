import pandas as pd

df = pd.read_csv('eda_metrics.csv')
day30 = df[df['Day'] == 30][['Replay_ID', 'Player_ID', 'Net_Worth']].rename(columns={'Net_Worth': 'Final_Score'})
day6 = df[df['Day'] == 6].merge(day30, on=['Replay_ID', 'Player_ID'])
day6 = day6[day6['Final_Score'] > 5000]

features = ['Liquid_Cash', 'Planted_Crops', 'Animals', 'Shed_Inventory', 'Farm_Size']

print("=== CORRELATION WITH FINAL SCORE (DAY 30) ===")
print(day6[features + ['Final_Score']].corr()['Final_Score'].to_markdown())

elite = day6[day6['Final_Score'] >= 120000]
print("\n=== ELITE MEANS (>120k FINAL SCORE) ===")
print(elite[features].mean().to_markdown())

def archetype(row):
    if row['Farm_Size'] > 25: return 'Early Expander (Bought Land)'
    elif row['Animals'] >= 8: return 'Animal Baron'
    elif row['Planted_Crops'] >= 20: return 'Crop Aggressor'
    else: return 'Passive'

day6['Archetype'] = day6.apply(archetype, axis=1)
print("\n=== ARCHETYPES ===")
print(day6.groupby('Archetype')['Final_Score'].mean().sort_values(ascending=False).to_markdown())
