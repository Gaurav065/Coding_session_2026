import pandas as pd

df = pd.read_csv('eda_metrics.csv')
day30 = df[df['Day'] == 30][['Replay_ID', 'Player_ID', 'Net_Worth']].rename(columns={'Net_Worth': 'Final_Score'})
day9 = df[df['Day'] == 9].merge(day30, on=['Replay_ID', 'Player_ID'])
day9 = day9[day9['Final_Score'] > 5000]

features = ['Liquid_Cash', 'Planted_Crops', 'Animals', 'Shed_Inventory', 'Farm_Size']

print("=== CORRELATION WITH FINAL SCORE (DAY 30) ===")
print(day9[features + ['Final_Score']].corr()['Final_Score'].to_markdown())

elite = day9[day9['Final_Score'] >= 120000]
print("\n=== ELITE MEANS (>120k FINAL SCORE) ===")
print(elite[features].mean().to_markdown())

def archetype(row):
    if row['Farm_Size'] >= 75: return 'Mega-Expander (75+ tiles)'
    elif row['Farm_Size'] >= 50: return 'Standard Expander (50 tiles)'
    elif row['Farm_Size'] > 25: return 'Slow Expander (26-49 tiles)'
    else: return 'Trapped (25 tiles)'

day9['Archetype'] = day9.apply(archetype, axis=1)
print("\n=== ARCHETYPES ===")
print(day9.groupby('Archetype')['Final_Score'].mean().sort_values(ascending=False).to_markdown())
