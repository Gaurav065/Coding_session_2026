"""Goose/Steering Attribution Runs — Project Maestro

Three runs required before any goose or steering verdict:

RUN 1 — Identity Control (sanity check)
  goose_cap=0, kw_early=10 (no steering) vs Dominant Meta (10C/4S/0G, kw_early=10)
  Parameters are IDENTICAL. Expected: ~50% win rate (within noise).
  If result deviates significantly, harness has a bug and prior conclusions need revisiting.

RUN 2-4 — goose_cap=0 STEERED vs three archetypes on 100 disjoint seeds
  (20-seed §2t runs were underpowered: +10pp on Dominant Meta ≈ p=0.35, borderline on others)
  goose_cap=0 steered vs Dominant Meta (10C/4S/0G)   — 100 seeds × 2 seats = 200 matches
  goose_cap=0 steered vs Wool-Heavy (6C/12S/0G)       — 100 seeds × 2 seats = 200 matches
  goose_cap=0 steered vs Balanced Pasture (6C/8S/0G)  — 100 seeds × 2 seats = 200 matches
  Prior (20-seed §2t): DM 40%, WH 82.5%, BP 82.5%

All runs via FastEngine. Absolute means and W/L/T reported throughout.
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


def run(a0, a1, seed: int) -> Tuple[float, float]:
    game = FastGame(seed=seed)
    while not game.done:
        game.step_game(a0(game.get_observation(0)), a1(game.get_observation(1)))
    return float(game.farms[0].money), float(game.farms[1].money)


def make_no_goose_steered(seed=None):
    """Production agent, goose_cap=0, steering active (default kw_early)."""
    return make_spatial_dispatcher_agent(params={"goose_cap": 0}, seed=seed)


def make_no_goose_unsteered(seed=None):
    """Production agent, goose_cap=0, kw_early=10 (no steering)."""
    return make_spatial_dispatcher_agent(params={"goose_cap": 0}, kw_early=10, seed=seed)


def run_h2h(label: str,
            our_factory: Callable[[int], Any],
            opp_factory: Callable[[int], Any],
            seeds: List[int],
            prior_wr: float = None) -> dict:
    print(f"\n{'='*72}")
    n_matches = len(seeds) * 2
    print(f"H2H: {label}")
    print(f"  {len(seeds)} seeds x 2 seats = {n_matches} matches via FastEngine")
    if prior_wr is not None:
        print(f"  Prior (20-seed §2t): {prior_wr:.1f}%")
    print(f"{'='*72}")

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

    print(f"  Production mean:   ${mean_p:>10,.2f}")
    print(f"  Opponent mean:     ${mean_o:>10,.2f}")
    print(f"  Delta:             ${mean_d:>+10,.2f}  SE ${se:,.2f}")
    print(f"  t={t_stat:>+.3f}  p={p_val:.4f}")
    print(f"  W/L/T: {wins}/{losses}/{ties}  "
          f"Win rate (all): {wr_all:.1f}%  (ex-ties): {wr_notie:.1f}%")
    if prior_wr is not None:
        pp = wr_notie - prior_wr
        print(f"  vs prior {prior_wr:.1f}%: {pp:>+.1f}pp")
    return {"label": label, "n": n, "prod_mean": mean_p, "opp_mean": mean_o,
            "delta": mean_d, "se": se, "t": t_stat, "p": p_val,
            "W": wins, "L": losses, "T": ties,
            "wr_notie": wr_notie, "prior_wr": prior_wr}


def main():
    print("=" * 72)
    print("GOOSE / STEERING ATTRIBUTION RUNS")
    print("=" * 72)

    # ── RUN 1: Identity Control ──────────────────────────────────────────────
    # our agent: goose_cap=0, kw_early=10  →  cow=10, sheep=4, goose=0
    # Dominant Meta: cow=10, sheep=4, goose=0, kw_early=10
    # Parameters IDENTICAL — expect ~50% WR
    print("\n" + "=" * 72)
    print("RUN 1 — IDENTITY CONTROL (sanity check)")
    print("  our: goose_cap=0, kw_early=10 (no steer)")
    print("  opp: Dominant Meta (10C/4S/0G, kw_early=10)")
    print("  Parameters IDENTICAL -> expect ~50% WR")
    print("=" * 72)

    identity_opp = lambda s: make_spatial_dispatcher_agent(
        params={"cow_cap_base": 10, "sheep_cap": 4, "goose_cap": 0},
        kw_early=10, seed=s)

    res_id = run_h2h(
        "Identity Control (no-goose no-steer vs Dominant Meta)",
        lambda s: make_no_goose_unsteered(seed=s),
        identity_opp,
        OFFICIAL_20
    )

    if abs(res_id["wr_notie"] - 50.0) <= 10.0:
        print("  [PASS] Identity control near 50% — harness OK.")
    else:
        print(f"  [WARN] Identity control at {res_id['wr_notie']:.1f}% — "
              f"investigate harness or agent asymmetry before trusting H2H results.")

    # ── RUN 2-4: goose_cap=0 STEERED vs archetypes, 100 disjoint seeds ──────
    dom_meta = lambda s: make_spatial_dispatcher_agent(
        params={"cow_cap_base": 10, "sheep_cap": 4, "goose_cap": 0},
        kw_early=10, seed=s)
    wool_heavy = lambda s: make_spatial_dispatcher_agent(
        params={"cow_cap_base": 6, "sheep_cap": 12, "goose_cap": 0},
        kw_early=10, seed=s)
    balanced   = lambda s: make_spatial_dispatcher_agent(
        params={"cow_cap_base": 6, "sheep_cap": 8, "goose_cap": 0},
        kw_early=10, seed=s)

    res_dm = run_h2h("goose_cap=0 steered vs Dominant Meta (10C/4S/0G)",
                     lambda s: make_no_goose_steered(seed=s),
                     dom_meta, DISJOINT_100, prior_wr=40.0)

    res_wh = run_h2h("goose_cap=0 steered vs Wool-Heavy (6C/12S/0G)",
                     lambda s: make_no_goose_steered(seed=s),
                     wool_heavy, DISJOINT_100, prior_wr=82.5)

    res_bp = run_h2h("goose_cap=0 steered vs Balanced Pasture (6C/8S/0G)",
                     lambda s: make_no_goose_steered(seed=s),
                     balanced, DISJOINT_100, prior_wr=82.5)

    # ── Final Summary ─────────────────────────────────────────────────────────
    print("\n" + "=" * 72)
    print("ATTRIBUTION RUN SUMMARY")
    print("=" * 72)
    print(f"\nRUN 1 — Identity Control ({res_id['W']}W/{res_id['L']}L/{res_id['T']}T):")
    print(f"  WR (ex-ties): {res_id['wr_notie']:.1f}%  "
          f"Prod ${res_id['prod_mean']:,.0f}  Opp ${res_id['opp_mean']:,.0f}  "
          f"D ${res_id['delta']:>+,.0f}  t={res_id['t']:>+.2f}  p={res_id['p']:.3f}")

    print(f"\nRUN 2-4 — goose_cap=0 STEERED vs archetypes (100 disjoint seeds, n=200 each):")
    for r in [res_dm, res_wh, res_bp]:
        print(f"  {r['label'][:42]:<42}  WR={r['wr_notie']:.1f}%  "
              f"({r['W']}W/{r['L']}L/{r['T']}T)  "
              f"Prod ${r['prod_mean']:,.0f}  Opp ${r['opp_mean']:,.0f}  "
              f"D ${r['delta']:>+,.0f}  t={r['t']:>+.2f}  p={r['p']:.4f}")

    # ── Steering cost estimate ────────────────────────────────────────────────
    print(f"\nSTEERING COST ESTIMATE:")
    id_wr   = res_id["wr_notie"]
    dm_wr   = res_dm["wr_notie"]
    cost_pp = id_wr - dm_wr
    print(f"  Identity control (no steer): {id_wr:.1f}%")
    print(f"  Steered vs same build:       {dm_wr:.1f}%")
    print(f"  Steering effect (WR delta):  {-cost_pp:>+.1f}pp "
          f"({'costs' if cost_pp > 0 else 'gains'} win rate vs identical no-steer opponent)")

    print("\n" + "=" * 72)


if __name__ == "__main__":
    main()
