import json

cells = []

def add_md(text):
    cells.append({"cell_type": "markdown", "metadata": {}, "source": [text + "\n"]})

def add_code(code):
    cells.append({"cell_type": "code", "execution_count": None, "metadata": {}, "outputs": [], "source": [line + "\n" for line in code.split('\n')]})

add_md("# 🕵️‍♂️ Deep Research EDA: The Day 0-3 Crucible\nThis notebook exhaustively analyzes the critical first 72 steps (Days 0-3) of the Kaggriculture Grandmaster replays. The goal is to determine exactly how early-game portfolio decisions (Crops vs. Animals vs. Cash hoarding) deterministically predict the Final Day 30 Score.")

add_code("""import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns

# Set style
sns.set_theme(style="darkgrid")
plt.rcParams['figure.figsize'] = (12, 6)""")

add_md("## 1. Data Processing & Target Mapping\nWe must map the **Final Score (Day 30 Net Worth)** back to the **Day 3 State** so we can see which early-game strategies actually win the game.")

add_code("""# Load data
df = pd.read_csv('eda_metrics.csv')

# Extract Final Score (Day 30 Net Worth) for each Player in each Replay
day30_scores = df[df['Day'] == 30][['Replay_ID', 'Player_ID', 'Net_Worth']].rename(columns={'Net_Worth': 'Final_Score'})

# Filter for Day 3 and merge the Final Score
day3_df = df[df['Day'] == 3].merge(day30_scores, on=['Replay_ID', 'Player_ID'])

# Drop rows where the opponent clearly crashed (Final Score < 1000)
day3_df = day3_df[day3_df['Final_Score'] > 5000]

day3_df.head()""")

add_md("## 2. Feature Distributions at Day 3\nWhat are the most common states at the end of Day 3? How much cash do players usually hold? How many crops do they plant?")

add_code("""fig, axes = plt.subplots(1, 3, figsize=(18, 5))

sns.histplot(day3_df['Liquid_Cash'], bins=30, ax=axes[0], color='skyblue')
axes[0].set_title('Liquid Cash Distribution (Day 3)')

sns.histplot(day3_df['Planted_Crops'], bins=25, ax=axes[1], color='lightgreen')
axes[1].set_title('Planted Crops Distribution (Day 3)')

sns.histplot(day3_df['Animals'], bins=10, ax=axes[2], color='salmon')
axes[2].set_title('Animals Owned Distribution (Day 3)')

plt.tight_layout()
plt.show()""")

add_md("## 3. The Grandmaster Predictors (Correlation Matrix)\nWhich Day 3 metric has the highest mathematical correlation with winning the game 27 days later?")

add_code("""# Calculate correlation with Final Score
features = ['Liquid_Cash', 'Net_Worth', 'Planted_Crops', 'Animals', 'Shed_Inventory', 'Final_Score']
corr = day3_df[features].corr()

plt.figure(figsize=(8, 6))
sns.heatmap(corr, annot=True, cmap='coolwarm', fmt=".2f", linewidths=.5)
plt.title('Correlation Matrix: Day 3 Features vs Final Score')
plt.show()""")

add_md("## 4. Bivariate Analysis: Crop Spammers vs. Animal Rushers\nLet's visualize the direct relationship between Day 3 portfolio choices and the Final Score.")

add_code("""fig, axes = plt.subplots(1, 2, figsize=(16, 6))

sns.scatterplot(data=day3_df, x='Planted_Crops', y='Final_Score', alpha=0.6, ax=axes[0], color='green')
sns.regplot(data=day3_df, x='Planted_Crops', y='Final_Score', scatter=False, ax=axes[0], color='darkgreen')
axes[0].set_title('Day 3 Planted Crops vs Final Score')

sns.scatterplot(data=day3_df, x='Animals', y='Final_Score', alpha=0.6, ax=axes[1], color='red')
sns.regplot(data=day3_df, x='Animals', y='Final_Score', scatter=False, ax=axes[1], color='darkred')
axes[1].set_title('Day 3 Animals vs Final Score')

plt.tight_layout()
plt.show()""")

add_md("## 5. Archetype Clustering\nWe categorize players into 3 distinct Day 3 strategies:\n1. **Animal Rushers**: Have > 3 animals by Day 3.\n2. **Crop Spammers**: Have > 15 crops but <= 3 animals.\n3. **Cash Hoarders**: Low crops, low animals (high liquid cash).")

add_code("""def assign_archetype(row):
    if row['Animals'] > 3:
        return 'Animal Rusher'
    elif row['Planted_Crops'] > 15:
        return 'Crop Spammer'
    else:
        return 'Cash Hoarder / Slow Start'

day3_df['Archetype'] = day3_df.apply(assign_archetype, axis=1)

plt.figure(figsize=(10, 6))
sns.boxplot(data=day3_df, x='Archetype', y='Final_Score', palette='Set2')
plt.title('Final Score by Day 3 Strategic Archetype')
plt.show()""")

add_md("## 6. The Elite Blueprint (> $120k Final Score)\nIf we isolate ONLY the absolute highest-scoring replays, what exactly did their Day 3 look like? This is the blueprint for our agent.")

add_code("""elite_df = day3_df[day3_df['Final_Score'] >= 120000]

print(f"Number of Elite Runs (>120k): {len(elite_df)}")
print("\\n--- ELITE DAY 3 AVERAGES ---")
print(elite_df[['Liquid_Cash', 'Planted_Crops', 'Animals', 'Shed_Inventory']].mean().round(2))

# Plot the Elite footprint
fig, ax = plt.subplots(figsize=(8, 8))
elite_means = elite_df[['Planted_Crops', 'Animals', 'Shed_Inventory']].mean()
elite_means.plot.pie(autopct='%1.1f%%', ax=ax, cmap='Pastel1', startangle=90)
ax.set_ylabel('')
ax.set_title('Day 3 Asset Distribution for 120k+ Grandmasters')
plt.show()""")

notebook = {
    "cells": cells,
    "metadata": {
        "kernelspec": {
            "display_name": "Python 3",
            "language": "python",
            "name": "python3"
        },
        "language_info": {
            "codemirror_mode": {"name": "ipython", "version": 3},
            "file_extension": ".py",
            "mimetype": "text/x-python",
            "name": "python",
            "nbconvert_exporter": "python",
            "pygments_lexer": "ipython3",
            "version": "3.9.0"
        }
    },
    "nbformat": 4,
    "nbformat_minor": 5
}

with open('Day_0_to_3_Deep_EDA.ipynb', 'w', encoding='utf-8') as f:
    json.dump(notebook, f, indent=2)

print("Notebook generated successfully!")
