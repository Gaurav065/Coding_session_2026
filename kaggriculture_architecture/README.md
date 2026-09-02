# Kaggriculture Top-Tier Architecture & Submission Suite

This workspace contains the validated top-tier agent, test suites, replay analysis tools, and architecture documentation.

## Directory Hierarchy

- **submission/**
  - main.py — The verified, battle-tested submission agent (93.5 KB, self-contained). Ready for submission.
- **	ests/**
  - alidate_canary.py — The 5-stage comprehensive canary test suite (Canary 1-5).
  - sync_bench.py — Head-to-head benchmark harness across game seeds.
  - ench_vs_main2.py — Verification benchmark vs incumbent leaderboard code.
  - 	est_suite.py — Parallel test suite.
- **nalysis/**
  - nalyze_game_mechanics.py — Deep replay analyzer for game mechanics, crop yields, and market dumps.
  - nalyze_blowout.py — Step-by-step diagnostic of high-margin winning games.
  - mine_fast.py / mine_replays.py — Multiprocess replay miners for parsing match tapes.
  - 
eplay_summary.json — Parsed results and scores from 182 August 31 match replays.
- **	ools/**
  - unpack_agent.py / inspect_core.py / inspect_routes.py — Codebase inspection and module decompilation utilities.
  - compare_agents.py — AST & diff comparator across agent versions.
- **unpacked/**
  - Unpacked modular source code for inspection and debugging.
- **rchitecture_plan.md**
  - Detailed architecture blueprint and strategy guide.
