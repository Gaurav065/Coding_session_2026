# kaggriculture-strategy

Strategy work for the Kaggriculture competition, derived from the shipped
environment source rather than the README prose.

- **[STRATEGY.md](STRATEGY.md)** — the strategy. Start here.
- `analysis/market_analysis.py` — glut curves, town demand, per-tile-day unit
  economics, the hire cost curve, and the melon race.
- `analysis/verify_mechanics.py` — runs the real `kaggle_environments`
  interpreter to check every mechanic the strategy depends on.
- `analysis/portfolio_sim.py` — season cash-flow model; sweeps tile allocations,
  runs sensitivity on each strategic choice, and right-sizes the herd.

```bash
pip install -U kaggle-environments
python analysis/market_analysis.py
python analysis/verify_mechanics.py
python analysis/portfolio_sim.py
```

## Headline findings

| Finding | Impact |
| :--- | :--- |
| `CARE` multiplies animal output by `1 + interval`, not 2× (README is wrong) | −$67k without it |
| Buy all three land quadrants | −$72k to skip |
| Grow your own wheat rather than buying feed | fatal to skip |
| Meter sales against town demand instead of dumping | −$14k to dump |
| Melon and fertilizer pools never refill — race the opponent for them | −73% if beaten to melon |
