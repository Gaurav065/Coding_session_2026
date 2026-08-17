# Kaggriculture agent

Single-file heuristic agent for the Kaggle Kaggriculture competition.

## Layout

```
main.py                # THE submission. Greedy value/(1+distance) task scheduler
                       # with per-product reserve prices and simple animal EV.
bench.py               # Measurement harness: N seeds x all opponents in
                       # `Performance test/`, reports per-opponent + aggregate
                       # win rate. Run: `python bench.py -n 3`
test.py                # Single-opponent eval. `python test.py -o pass -n 5`
sweep.py               # Parameter sweep. `python sweep.py res_MILK 100 130 160`
replay_opponent.py     # Loads REPLAY_PATH env var, plays back that replay's
                       # winner actions - used by bench.py as opponent.
Performance test/      # Primary opponent pool (12 replays). Used by bench.py.
replays/               # Historical archive; not used by the current harness.
```

## Current baseline

Against `Performance test/` opponent pool (12 replays x 2 seeds = 24 games):

| metric | value |
|---|---|
| win rate | 22/24 (92%) |
| my mean score | $106,822 |
| opp mean score | $32,287 |
| mean delta | +$74,535 |

The only reliable loss is `92615092` (-$18k mean).

## Iterating

1. Edit `main.py`.
2. `python bench.py -n 2` (~3 min) or `python bench.py -n 4` for tighter numbers.
3. Anything that drops below 22/24 wins gets reverted.
4. Push to Kaggle only after the aggregate holds or improves.

## What's known

Winners in the replay pool consistently follow this shape: 8-10 cows + 4-7
sheep, ~30 strawberries mid-game, ~14 melons, 2 land buys (Q2 by day 7-8,
Q3 by day 11-12), and preserve milk/wool prices by not oversupplying.
