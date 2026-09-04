import json

cells = []

def add_md(text):
    cells.append({"cell_type": "markdown", "metadata": {}, "source": [text + "\n"]})

def add_code(code):
    cells.append({"cell_type": "code", "execution_count": None, "metadata": {}, "outputs": [], "source": [line + "\n" for line in code.split('\n')]})

add_md("# 🕵️‍♂️ Deep Research EDA: The Day 3-6 Crucible\nAnalyzing the transition from opening setup to early-game expansion. Do we buy land? Do we spam animals?")

add_code("""import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns

sns.set_theme(style="darkgrid")
plt.rcParams['figure.figsize'] = (12, 6)

df = pd.read_csv('eda_metrics.csv')
day30_scores = df[df['Day'] == 30][['Replay_ID', 'Player_ID', 'Net_Worth']].rename(columns={'Net_Worth': 'Final_Score'})
day6_df = df[df['Day'] == 6].merge(day30_scores, on=['Replay_ID', 'Player_ID'])
day6_df = day6_df[day6_df['Final_Score'] > 5000]
""")

add_md("## 1. Feature Distributions at Day 6")
add_code("""fig, axes = plt.subplots(2, 2, figsize=(16, 10))

sns.histplot(day6_df['Liquid_Cash'], bins=30, ax=axes[0, 0], color='skyblue')
axes[0, 0].set_title('Liquid Cash (Day 6)')

sns.histplot(day6_df['Planted_Crops'], bins=25, ax=axes[0, 1], color='lightgreen')
axes[0, 1].set_title('Planted Crops (Day 6)')

sns.histplot(day6_df['Animals'], bins=10, ax=axes[1, 0], color='salmon')
axes[1, 0].set_title('Animals Owned (Day 6)')

sns.histplot(day6_df['Farm_Size'], bins=10, ax=axes[1, 1], color='gold')
axes[1, 1].set_title('Farm Size (Day 6)')

plt.tight_layout()
plt.show()""")

add_md("## 2. Correlation Matrix")
add_code("""features = ['Liquid_Cash', 'Planted_Crops', 'Animals', 'Shed_Inventory', 'Farm_Size', 'Final_Score']
corr = day6_df[features].corr()

plt.figure(figsize=(8, 6))
sns.heatmap(corr, annot=True, cmap='coolwarm', fmt=".2f", linewidths=.5)
plt.title('Correlation Matrix: Day 6 Features vs Final Score')
plt.show()""")

add_md("## 3. The Elite Blueprint (> $120k Final Score)")
add_code("""elite_df = day6_df[day6_df['Final_Score'] >= 120000]

print("\\n--- ELITE DAY 6 AVERAGES ---")
print(elite_df[['Liquid_Cash', 'Planted_Crops', 'Animals', 'Shed_Inventory', 'Farm_Size']].mean().round(2))
""")

add_md("## 4. Land Expansion vs. Discipline")
add_code("""def assign_archetype(row):
    if row['Farm_Size'] > 25: return 'Early Expander'
    elif row['Animals'] >= 8: return 'Animal Spammer'
    elif row['Planted_Crops'] >= 22: return 'Crop Spammer'
    else: return 'The Disciplined Engine (6 Animals, 19 Crops)'

day6_df['Archetype'] = day6_df.apply(assign_archetype, axis=1)

plt.figure(figsize=(10, 6))
sns.boxplot(data=day6_df, x='Archetype', y='Final_Score', palette='Set2')
plt.title('Final Score by Day 6 Strategic Archetype')
plt.show()""")

notebook = {
    "cells": cells,
    "metadata": {
        "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
        "language_info": {"name": "python"}
    },
    "nbformat": 4,
    "nbformat_minor": 5
}
with open('Day_3_to_6_Deep_EDA.ipynb', 'w', encoding='utf-8') as f:
    json.dump(notebook, f, indent=2)

print("Notebook 3-6 generated successfully!")
