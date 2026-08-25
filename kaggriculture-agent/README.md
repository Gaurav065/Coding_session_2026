# Kaggriculture agent

Two-player farming-sim Kaggle agent. This README reflects the actual current state after a full cleanup pass — treat anything not listed here as historical.

## Layout

```
main.py                      Current submission entry point. STATUS: an older/intermediate
                              architecture (per-order shed-guard for front-running present,
                              but no scarcity-pricing fix, no drain-horizon fix, no tape
                              persistence) -- NOT the verified, 10/10-tested fixed version.
draft_main_v4.py              The VERIFIED FIXED agent: shed-quantity guard, horizon-correct
                              shop-drain forecast, below-I0 scarcity pricing, front-run tape
                              persistence, hardened __file__-relative tape loading. Beat the
                              unfixed logic 10/10 in head-to-head testing. If you want the
                              verified improvements live, promote this over main.py.
water_fill.py                 AMM shadow-price allocator (water_fill_allocate). Fixed to
                              handle both AMM branches (was flattening below-I0 scarcity to
                              a placeholder base price).
blind_hybrid_tape.json        Tape used by draft_main_v4.py / continuous_agent.
tape_151k.json                 Tape used by main.py's "151k" slot. Byte-identical to
                              blind_hybrid_tape.json -- same tape, different filename.
top_tape_143954.json          Tape used by main.py's "143k" slot.
tape_165k_straw_cow.json,
tape_154k_sheep_melon.json,
tape_134k_balanced.json        Three additional self-authored tape variants (NOT sourced
                              from any external "top tournament players" -- their reported
                              day-0 actions match a strategy report's "Rank 1/2/3" claims
                              exactly, confirming that framing was invented after the fact).
tape_comparison_data.json      Real self-play benchmark data across the four tapes above
                              (Our_Best_151k / Rank1 / Rank2 / Rank3 naming is internal only).
submission.tar.gz              Oldest packaged submission (original DP-replanner main.py).
submission_v4.tar.gz           Packaged submission from the v4-fixed main.py + tape, built
                              and extraction-tested earlier -- currently stale relative to
                              the CURRENT main.py, since main.py has since reverted.

continuous_agent/             Second, parallel architecture: water_fill_allocate as a
                              continuous online "brain" instead of a fixed tape.
  final_submission.py            Full continuous/dynamic agent -- reviewed, not yet fully
                                  verified (review was interrupted; known issues found:
                                  animal-product capacity conversion looked suspect, no
                                  confirmed PICKUP->FEED wiring, placement/PLACE sequencing
                                  needs a second pass).
  water_fill.py                  Local copy of the allocator.
  archive/main_dynamic_CORRUPTED.py   Broken file quarantined here -- it read itself, had
                                  a fictional SHOPS taxonomy, and the wrong MARKET_I0.
                                  Do not resurrect without a rewrite.

archive/                       Superseded code, tapes, docs, and two other stray subprojects
                              that were previously sitting loose in C:\Coding root
                              (kaggriculture-strategy/, a single-file self-contained tape
                              agent, an older 143k self-contained agent). Kept for reference,
                              not wired into anything.
scripts/                       Dev tooling: bench harness, replay-opponent loader, sweeps,
                              the old analyze/fix one-off patch scripts (their job is done).
tests/                         test*.py files.
temp/                          Debug logs and one-off debug_agent*.py scratch scripts.
replays/                       One real Kaggle replay (93924742.json, ~31MB) recovered from
                              a stray root-level folder. This is the only actual replay data
                              in this project -- the "34 top tournament replays" referenced
                              in an external strategy report do not exist anywhere here.
```

## Known current gaps (read before trusting any benchmark number)

- `main.py` is not the verified-fixed agent. Decide whether to promote `draft_main_v4.py`
  over it before relying on any fresh bench run.
- `tape_comparison_data.json`'s four tapes are self-play sparring partners, not independent
  "top player" intelligence -- treat h2h numbers there as internal comparison only.
- `continuous_agent/final_submission.py` review was left mid-way; see git/chat history for
  the specific open questions (capacity-gap conversion for animal products, PICKUP->FEED
  wiring, PLACE sequencing) before trusting its scores.
