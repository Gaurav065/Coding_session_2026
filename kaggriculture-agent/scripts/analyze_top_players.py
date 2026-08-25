"""Batch analyze top-player replays. Extract winner patterns."""
import json
import glob
import os
import collections
import statistics
import sys

def analyze_one(path):
    d = json.load(open(path))
    rewards = d["rewards"]
    win = 0 if rewards[0] >= rewards[1] else 1
    steps = d["steps"]
    result = {
        "file": os.path.basename(path),
        "winner_reward": rewards[win],
        "loser_reward": rewards[1-win],
        "day_snapshots": [],
        "sells": collections.Counter(),
        "buys": collections.Counter(),
        "hires": 0, "land_buys": 0,
    }
    for i, st in enumerate(steps):
        a = st[win].get("action") or {}
        for m in (a.get("market") or []):
            if not m: continue
            if m[0] == "HIRE": result["hires"] += 1
            elif m[0] == "BUY_LAND": result["land_buys"] += 1
            elif m[0] == "SELL" and len(m) >= 3:
                result["sells"][m[1]] += int(m[2])
            elif m[0] in ("BUY_PRODUCT","BUY_SEED","BUY_ANIMAL") and len(m) >= 3:
                result["buys"][m[0]+" "+m[1]] += int(m[2])
    for i in range(0, len(steps), 24):
        obs = steps[i][0]["observation"]
        farms = obs.get("farms")
        if not farms: continue
        farm = farms[win]
        c = collections.Counter()
        for row in farm["tiles"]:
            for t in row:
                if isinstance(t, dict):
                    if t.get("animal"): c[t["animal"]] += 1
                    elif t.get("kind") == "PLANT": c[t["crop"]] += 1
        result["day_snapshots"].append({
            "day": obs["day"],
            "money": farm["money"],
            "land": len(farm["unlocked_quadrants"]),
            "counts": dict(c),
        })
    return result

files = sorted(glob.glob("top_player_replays/*.json"))
all_results = [analyze_one(f) for f in files]

# ---- report ----
print("=" * 76)
print(f"{'file':<15} {'winner$':>8} {'loser$':>8} {'sheep':>6} {'cow':>4} {'stra':>5} {'melo':>5} {'whea':>5} {'land':>5}")
print("-" * 76)
for r in all_results:
    final = r["day_snapshots"][-1] if r["day_snapshots"] else {"counts":{},"land":1}
    c = final["counts"]
    print(f"{r['file'][:15]:<15} {r['winner_reward']:>8.0f} {r['loser_reward']:>8.0f} "
          f"{c.get('SHEEP',0):>6} {c.get('COW',0):>4} {c.get('STRAWBERRY',0):>5} "
          f"{c.get('MELON',0):>5} {c.get('WHEAT',0):>5} {final.get('land',1):>5}")
print("=" * 76)

# aggregate stats
print("\n-- winner reward stats --")
scores = [r["winner_reward"] for r in all_results]
print(f"mean {statistics.mean(scores):.0f}  median {statistics.median(scores):.0f}  "
      f"min {min(scores):.0f}  max {max(scores):.0f}")

# day 1 build (what they buy on day 0-1)
print("\n-- day 1 board (post day 0 actions) --")
for r in all_results[:5]:
    if len(r["day_snapshots"]) > 1:
        d1 = r["day_snapshots"][1]
        parts = [f"{k[:4]}={v}" for k,v in sorted(d1["counts"].items())]
        print(f"  {r['file'][:15]}: ${d1['money']:.0f}  {' '.join(parts)}")

# land timing
print("\n-- land purchase days (median across top players) --")
land_days = {2: [], 3: [], 4: []}
for r in all_results:
    prev = 1
    for snap in r["day_snapshots"]:
        for q in range(prev+1, snap["land"]+1):
            if q in land_days: land_days[q].append(snap["day"])
        prev = snap["land"]
for q in [2, 3, 4]:
    if land_days[q]:
        print(f"  Q{q}: median day {statistics.median(land_days[q]):.0f}  "
              f"({len(land_days[q])}/{len(all_results)} bought)")

# peaks
print("\n-- peak per-tile counts (max any day, per player) --")
for crop in ["MELON", "STRAWBERRY", "WHEAT", "COW", "SHEEP", "GOOSE"]:
    peaks = []
    for r in all_results:
        peak = max((s["counts"].get(crop,0) for s in r["day_snapshots"]), default=0)
        peaks.append(peak)
    print(f"  {crop:<11} median peak {statistics.median(peaks):.0f}  "
          f"range {min(peaks)}-{max(peaks)}")

# aggregate sells/buys
print("\n-- median totals (across all winners) --")
all_sells = {}
for r in all_results:
    for k, v in r["sells"].items():
        all_sells.setdefault(k, []).append(v)
for k, vs in sorted(all_sells.items(), key=lambda kv: -statistics.median(kv[1])):
    print(f"  SELL {k:<12} median {statistics.median(vs):>5.0f}")

print()
buy_kinds = {}
for r in all_results:
    for k, v in r["buys"].items():
        buy_kinds.setdefault(k, []).append(v)
for k, vs in sorted(buy_kinds.items(), key=lambda kv: -statistics.median(kv[1])):
    print(f"  {k:<25} median {statistics.median(vs):>5.0f}")

hires_list = [r["hires"] for r in all_results]
print(f"\n  HIRES median {statistics.median(hires_list):.0f}  range {min(hires_list)}-{max(hires_list)}")
