# Kaggriculture agent

Single-file agent for the Kaggle **Kaggriculture** competition.

## Files

| File | Purpose |
|------|---------|
| `main.py` | **The submission.** Self-contained agent (`agent(obs)`); no local imports. |
| `test.py` | Local evaluation harness (vs `starter` / `random` / `pass` / `self`). |
| `sweep.py` | Parallel parameter sweep used to tune `main.P`. |

## Submit

```bash
kaggle competitions submit kaggriculture -f main.py -m "demand-driven livestock agent"
```

## Test locally

```bash
python test.py -n 12            # 12 seeds vs the built-in starter
python test.py -n 4 -o self     # self-play
python test.py -v               # per-day trace of player 0
python sweep.py work_per_hand 12 13 14   # sweep one tunable in main.P
```

## Strategy (one paragraph)

The season's money is bounded by what the **town** drains from the market, not
by what you can grow. Milk, wool and strawberry are ~75% of that pool and stay
*undersupplied* (their sell price sits above base all game), so the plan is:
raise animals — cows first — because `CARE` makes a well-tended animal worth
3-4x a crop tile; keep the herd capped (~24) at the size the hired crew can
actually feed/care/harvest every day, since **labour, not cash, is the ceiling**;
dump spare actions into geese/eggs and melon, whose glut curves never crash; and
hold every product above a per-item reserve price until the final days, then
liquidate the shed completely. Execution is a greedy `value / (1+distance)^p`
task scheduler that assigns every farmer and hand each turn.

Current local result: **~90k mean final score over 12 seeds** (min ~77k),
versus ~3.5k for the built-in `starter` baseline.

All tunables live in the `P` dict at the top of `main.py`.
