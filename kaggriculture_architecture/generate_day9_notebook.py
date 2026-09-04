import json

cells = []

def add_md(text):
    cells.append({"cell_type": "markdown", "metadata": {}, "source": [text + "\n"]})

def add_code(code):
    cells.append({"cell_type": "code", "execution_count": None, "metadata": {}, "outputs": [], "source": [line + "\n" for line in code.split('\n')]})

add_md("# 🕵️‍♂️ Deep Research EDA: The Day 6-9 Explosion\nAnalyzing the pivotal Day 6 to Day 9 window. This is where the early game engine is converted into raw economic power and physical territory.")

add_code("""import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns

sns.set_theme(style="darkgrid")
plt.rcParams['figure.figsize'] = (12, 6)

df = pd.read_csv('eda_metrics.csv')
day30_scores = df[df['Day'] == 30][['Replay_ID', 'Player_ID', 'Net_Worth']].rename(columns={'Net_Worth': 'Final_Score'})
day9_df = df[df['Day'] == 9].merge(day30_scores, on=['Replay_ID', 'Player_ID'])
day9_df = day9_df[day9_df['Final_Score'] > 5000]
""")

add_md("## 1. Feature Distributions at Day 9\nNotice the massive bifurcation in Farm Size. Players are finally buying land.")
add_code("""fig, axes = plt.subplots(2, 2, figsize=(16, 10))

sns.histplot(day9_df['Liquid_Cash'], bins=30, ax=axes[0, 0], color='skyblue')
axes[0, 0].set_title('Liquid Cash (Day 9)')

sns.histplot(day9_df['Planted_Crops'], bins=25, ax=axes[0, 1], color='lightgreen')
axes[0, 1].set_title('Planted Crops (Day 9)')

sns.histplot(day9_df['Animals'], bins=10, ax=axes[1, 0], color='salmon')
axes[1, 0].set_title('Animals Owned (Day 9)')

sns.histplot(day9_df['Farm_Size'], bins=10, ax=axes[1, 1], color='gold')
axes[1, 1].set_title('Farm Size (Day 9)')

plt.tight_layout()
plt.show()""")

add_md("## 2. Correlation Matrix: The Shift to Capital\nAt Day 3, hoarding cash was negatively correlated with winning. At Day 9, having high cash and shed inventory is highly correlated with winning. The engine is online.")
add_code("""features = ['Liquid_Cash', 'Planted_Crops', 'Animals', 'Shed_Inventory', 'Farm_Size', 'Final_Score']
corr = day9_df[features].corr()

plt.figure(figsize=(8, 6))
sns.heatmap(corr, annot=True, cmap='coolwarm', fmt=".2f", linewidths=.5)
plt.title('Correlation Matrix: Day 9 Features vs Final Score')
plt.show()""")

add_md("## 3. The Elite Blueprint (> $120k Final Score)\nThe >$120k players double their farm size and scale their assets aggressively.")
add_code("""elite_df = day9_df[day9_df['Final_Score'] >= 120000]

print("\\n--- ELITE DAY 9 AVERAGES ---")
print(elite_df[['Liquid_Cash', 'Planted_Crops', 'Animals', 'Shed_Inventory', 'Farm_Size']].mean().round(2))
""")

add_md("## 4. The Land Grab Archetypes\nIf you haven't bought land by Day 9, do you lose? Let's look at Final Score by Day 9 Farm Size.")
add_code("""def assign_archetype(row):
    if row['Farm_Size'] >= 75: return 'Mega-Expander (75+ tiles)'
    elif row['Farm_Size'] >= 50: return 'Standard Expander (50 tiles)'
    else: return 'Trapped (25 tiles)'

day9_df['Archetype'] = day9_df.apply(assign_archetype, axis=1)

plt.figure(figsize=(10, 6))
sns.boxplot(data=day9_df, x='Archetype', y='Final_Score', palette='Set2')
plt.title('Final Score by Day 9 Expansion Archetype')
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
with open('Day_6_to_9_Deep_EDA.ipynb', 'w', encoding='utf-8') as f:
    json.dump(notebook, f, indent=2)

print("Notebook 6-9 generated successfully!")
