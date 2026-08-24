"""Goose Cap Experiment — Project Maestro (§2t)

Tests goose_cap=0 vs DEFAULT (goose_cap=4). Evidence base:
- Accidental control row from §2s: Standing Baseline uses DEFAULT_PARAMS (goose_cap=4)
  vs Dominant Meta (goose_cap=0, 10C/4S/0G). Both kw_early=10, cow=10, sheep=4.
  Sole difference: geese. Result: -$3,206, t=-2.47, p=0.018, 15% WR.
  This is the first statistically significant portfolio-composition result in the project.

Experiment scope:
  A) Self-play mirror: goose_cap=0 agent vs itself. Official 20 + 100 Disjoint seeds.
     Compare vs known baselines: Official=$56,743.07, Disjoint=$62,293.33.
  B) Head-to-head vs Dominant Meta (10C/4S/0G): 20 seeds x 2 seats = 40 matches.
     Prediction: removing geese from us + steering should flip 30% -> winning record.
  C) Head-to-head vs Wool-Heavy (6C/12S/0G): 20 seeds x 2 seats. Confirm no regression (was 67.5%).
  D) Head-to-head vs Balanced Pasture (6C/8S/0G): 20 seeds x 2 seats. Confirm no regression (was 65.0%).

All runs via FastEngine (FastGame) for speed.
"""
import sys
import numpy as np
from scipy import stats
from typing import Tuple, List, Callable, Any

sys.path.insert(0, r"C:\Coding")

from project_maestro.engine.fast_engine import FastGame
from project_maestro.agent.dispatcher_agent import make_spatial_dispatcher_agent

OFFICIAL_20  = [10, 20, 30, 42, 55, 77, 99, 100, 123, 200,
                250, 300, 333, 404, 500, 600, 700, 777, 888, 999]
DISJOINT_100 = list(range(10000, 10100))

KNOWN_BASELINE_OFFICIAL  = 56743.07   # steered, goose_cap=4, official 20
KNOWN_BASELINE_DISJOINT  = 62293.33   # steered, goose_cap=4, disjoint 100

def run(a0, a1, seed: int) -> Tuple[float, float]:
    game = FastGame(seed=seed)
    while not game.done:
        game.step_game(a0(game.get_observation(0)), a1(game.get_observation(1)))
    return float(game.farms[0].money), float(game.farms[1].money)


def make_no_goose(seed=None, kw=None):
    """Production agent with goose_cap=0 (and default steering unless kw overridden)."""
    return make_spatial_dispatcher_agent(params={"goose_cap": 0}, seed=seed, kw_early=kw)


# ── Section A: Self-play mirror ───────────────────────────────────────────────
def run_self_play(label: str, seeds: List[int], known_baseline: float) -> dict:
    print(f"\n{'='*70}")
    print(f"A) SELF-PLAY MIRROR — {label} ({len(seeds)} seeds)")
    print(f"   Known baseline (goose_cap=4, steered): ${known_baseline:,.2f}")
    print(f"{'='*70}")
    scores = []
    for seed in seeds:
        a0 = make_no_goose(seed=seed)
        a1 = make_no_goose(seed=seed)
        r0, r1 = run(a0, a1, seed)
        avg = (r0 + r1) / 2.0
        scores.append(avg)
        # Print every 10th seed for disjoint, every seed for official-20
        if len(seeds) <= 20 or seed % 1000 == 0:
            print(f"  seed={seed:>5} P0=${r0:>9,.0f} P1=${r1:>9,.0f} avg=${avg:>9,.0f}")
    mean = float(np.mean(scores))
    med  = float(np.median(scores))
    mn   = float(np.min(scores))
    mx   = float(np.max(scores))
    print(f"  --- Mean: ${mean:>9,.2f}  Median: ${med:>9,.2f}  Min: ${mn:>9,.2f}  Max: ${mx:>9,.2f}")
    print(f"  vs baseline: {mean - known_baseline:>+,.2f}")
    return {"mean": mean, "median": med, "min": mn, "max": mx, "n": len(seeds),
            "delta_vs_baseline": mean - known_baseline}


# ── Section B/C/D: Head-to-head vs archetype ─────────────────────────────────
def run_h2h(label: str,
            our_factory: Callable[[int], Any],
            opp_factory: Callable[[int], Any],
            seeds: List[int],
            prior_win_rate: float = None) -> dict:
    print(f"\n{'='*70}")
    print(f"H2H — no-goose production vs {label} ({len(seeds)*2} matches)")
    if prior_win_rate is not None:
        print(f"   Prior win rate (goose_cap=4 steered): {prior_win_rate:.1f}%")
    print(f"{'='*70}")
    diffs, prod_sc, opp_sc = [], [], []
    wins = losses = ties = 0
    for seed in seeds:
        # Seat 0
        r0, r1 = run(our_factory(seed), opp_factory(seed), seed)
        d = r0 - r1; diffs.append(d); prod_sc.append(r0); opp_sc.append(r1)
        if d > 0: wins += 1
        elif d < 0: losses += 1
        else: ties += 1
        # Seat 1
        r_o, r_p = run(opp_factory(seed), our_factory(seed), seed)
        d2 = r_p - r_o; diffs.append(d2); prod_sc.append(r_p); opp_sc.append(r_o)
        if d2 > 0: wins += 1
        elif d2 < 0: losses += 1
        else: ties += 1

    n = len(diffs)
    mean_d  = float(np.mean(diffs))
    se      = float(np.std(diffs, ddof=1) / np.sqrt(n))
    t_stat  = mean_d / se if se > 0 else 0.0
    p_val   = 2 * (1 - stats.t.cdf(abs(t_stat), df=n-1))
    mean_p  = float(np.mean(prod_sc))
    mean_o  = float(np.mean(opp_sc))
    wr_all  = 100.0 * wins / n
    wr_notie = 100.0 * wins / (wins + losses) if (wins + losses) > 0 else 0.0
    print(f"  Production mean: ${mean_p:>10,.2f}")
    print(f"  Opponent mean:   ${mean_o:>10,.2f}")
    print(f"  Delta:           ${mean_d:>+10,.2f}  SE ${se:,.2f}")
    print(f"  t={t_stat:>+.3f}  p={p_val:.4f}")
    print(f"  W/L/T: {wins}/{losses}/{ties}  Win rate (all): {wr_all:.1f}%  (ex-ties): {wr_notie:.1f}%")
    if prior_win_rate is not None:
        print(f"  Change vs prior: {wr_notie - prior_win_rate:>+.1f}pp")
    return {"label": label, "prod_mean": mean_p, "opp_mean": mean_o,
            "delta": mean_d, "se": se, "t": t_stat, "p": p_val,
            "W": wins, "L": losses, "T": ties, "wr_notie": wr_notie}


def main():
    print("=" * 70)
    print("GOOSE CAP EXPERIMENT (Section 2t): goose_cap=0 vs DEFAULT (goose_cap=4)")
    print("=" * 70)

    # A: Self-play mirror
    res_sp_20   = run_self_play("Official 20 Seeds",   OFFICIAL_20,  KNOWN_BASELINE_OFFICIAL)
    res_sp_100  = run_self_play("100 Disjoint Seeds",  DISJOINT_100, KNOWN_BASELINE_DISJOINT)

    # B: vs Dominant Meta (10C/4S/0G, kw=10) — prior 30.0% with geese, 15.0% without
    dom_meta = lambda s: make_spatial_dispatcher_agent(
        params={"cow_cap_base": 10, "sheep_cap": 4, "goose_cap": 0}, kw_early=10, seed=s)
    res_dm = run_h2h("Dominant Meta (10C/4S/0G)",
                     lambda s: make_no_goose(seed=s),
                     dom_meta, OFFICIAL_20, prior_win_rate=30.0)

    # C: vs Wool-Heavy (6C/12S/0G) — prior 67.5%
    wool_heavy = lambda s: make_spatial_dispatcher_agent(
        params={"cow_cap_base": 6, "sheep_cap": 12, "goose_cap": 0}, kw_early=10, seed=s)
    res_wh = run_h2h("Wool-Heavy (6C/12S/0G)",
                     lambda s: make_no_goose(seed=s),
                     wool_heavy, OFFICIAL_20, prior_win_rate=67.5)

    # D: vs Balanced Pasture (6C/8S/0G) — prior 65.0%
    balanced = lambda s: make_spatial_dispatcher_agent(
        params={"cow_cap_base": 6, "sheep_cap": 8, "goose_cap": 0}, kw_early=10, seed=s)
    res_bp = run_h2h("Balanced Pasture (6C/8S/0G)",
                     lambda s: make_no_goose(seed=s),
                     balanced, OFFICIAL_20, prior_win_rate=65.0)

    # ── Final Summary ────────────────────────────────────────────────────────
    print("\n" + "=" * 70)
    print("GOOSE EXPERIMENT — FINAL SUMMARY")
    print("=" * 70)
    print(f"  Self-play Official 20:  ${res_sp_20['mean']:>10,.2f}  "
          f"(vs baseline ${KNOWN_BASELINE_OFFICIAL:,.2f}: "
          f"{res_sp_20['delta_vs_baseline']:>+,.2f})")
    print(f"  Self-play Disjoint 100: ${res_sp_100['mean']:>10,.2f}  "
          f"(vs baseline ${KNOWN_BASELINE_DISJOINT:,.2f}: "
          f"{res_sp_100['delta_vs_baseline']:>+,.2f})")
    print()
    for r in [res_dm, res_wh, res_bp]:
        print(f"  vs {r['label']:<32} "
              f"WR={r['wr_notie']:.1f}%  "
              f"delta=${r['delta']:>+,.0f}  "
              f"t={r['t']:>+.2f}  p={r['p']:.4f}  "
              f"W{r['W']}/L{r['L']}/T{r['T']}")
    print("=" * 70)
    print("\nINTERPRETATION:")
    dm_wr = res_dm['wr_notie']
    sp_delta = res_sp_20['delta_vs_baseline']
    if dm_wr >= 50.0 and sp_delta >= -2000:
        print(f"  goose_cap=0 wins vs Dominant Meta ({dm_wr:.1f}% WR) with no self-play regression.")
        print("  VERDICT: SET goose_cap=0 AS NEW DEFAULT. Geese -> CLOSED DOORS (HANDOVER ss6).")
    elif dm_wr >= 45.0:
        print(f"  goose_cap=0 shows improvement vs Dominant Meta ({dm_wr:.1f}% WR).")
        print("  Consider adopting; check self-play delta before deciding.")
    else:
        print(f"  goose_cap=0 does not flip Dominant Meta ({dm_wr:.1f}% WR). "
              "Geese not the key differentiator.")


if __name__ == "__main__":
    main()
