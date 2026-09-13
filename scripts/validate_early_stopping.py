#!/usr/bin/env python
"""Shadow-validate the gate's early stopping against completed gates.

`scripts/gate.sh` stops a run once the seeds still unplayed cannot change
the acceptance verdict (`benchmark._decided`). That is a prediction, and a
prediction needs checking: docs/notes/codex/ asks for the two kinds of
disagreement (a stop that accepts what the full run rejects, and the
reverse), the games saved, and a comparison against simply playing a fixed
number of games.

This replays the decision offline over gates that ran to completion, so it
costs no games. Three things it measures:

1. **Fidelity.** For each completed gate, replay `_decided` incrementally
   and compare the verdict it would have stopped on with the full run's.
   Arrival order matters -- the pool is `imap_unordered`, so games come back
   in completion order -- so each gate is replayed over many shuffles as
   well as the job order.
2. **Saving.** Games not played, as a fraction. Wall time is close to
   proportional: games are independent and the pool stays full until the
   stop.
3. **The fixed-N alternative.** Judge on the first N games and stop
   unconditionally. Simpler, and if its disagreement rate is no worse at a
   comparable saving, the predictive machinery is not earning its keep.

Near-boundary behaviour is what actually matters, and the completed gates
are all comfortable accepts, so `--synthetic` resamples them into gates
whose true score is tilted across 0.500 -- rejections included -- and
reports both disagreements as a function of distance from the boundary.
Both designs are measured on the same gates and the same arrival orders,
because both are judged on a subset and both therefore inherit the same
widening of the confidence interval.

    python scripts/validate_early_stopping.py --shuffles 60 --synthetic 600

Measured 2026-09-09 over the 8 completed gates (all accepts) and 600
resampled ones. Predictive stopping saves 10.2% of games and beats a fixed
160 in every bucket, decisively where it matters: at a true margin of
0.03-0.06 below the line it accepts 9.7% of gates it should reject, against
26.4% for the fixed design. So it earns its keep -- but it is not free, and
that residual false-accept rate is the optimism inherent to stopping when
the data looks decisive, not a defect in the code. Raising `min_games`
trades it back roughly one for one (176 games: 2.0% false accepts, 4.2%
saved), which is why the floor stays where it is: a stopped ACCEPT near the
boundary is simply weaker evidence than a completed one, and a gate that
lands within 0.06 of 0.500 is worth finishing.
"""
from __future__ import annotations

import argparse
import collections
import json
import random
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from struggler.bots.benchmark import (ACCEPTANCE, _decided, acceptance,
                                      seed_scores, summarize)

BASE, HELD = "full-vs-base.json", "full-vs-held.json"


def completed_gates(root: Path, held_seeds: int = 64):
    """Gates whose held-out sample ran to completion. A gate that stopped
    early has no full-run verdict to check against -- that is the evidence
    the stop threw away, and the reason this cannot be done after the fact
    on every gate."""
    for d in sorted(root.glob("gate-*")):
        base, held = d / BASE, d / HELD
        if not (base.exists() and held.exists()):
            continue
        b, h = json.loads(base.read_text()), json.loads(held.read_text())
        if len(h.get("games", [])) < held_seeds * 2:
            continue
        yield d.name, b["games"], h["games"]


def full_verdict(base_games, held_games) -> bool:
    ok, _ = acceptance([("base", dict(summary=summarize(base_games, 0), games=base_games)),
                        ("held", dict(summary=summarize(held_games, 0), games=held_games))])
    return ok


def job_order(base_games, held_games):
    """The order `benchmark.main` submits: base and held seeds interleaved by
    `zip_longest`, both seats of a seed adjacent."""
    by_seed = collections.defaultdict(list)
    for g in base_games:
        by_seed[(0, g["seed"])].append(g)
    for g in held_games:
        by_seed[(1, g["seed"])].append(g)
    base_seeds = sorted({g["seed"] for g in base_games})
    held_seeds = sorted({g["seed"] for g in held_games})
    order = []
    for i in range(max(len(base_seeds), len(held_seeds))):
        if i < len(base_seeds):
            order.append((0, base_seeds[i]))
        if i < len(held_seeds):
            order.append((1, held_seeds[i]))
    return [g for key in order for g in by_seed[key]]


def replay(arrival, sample_of, planned):
    """Where `_decided` would have stopped, or None if it never did."""
    seen = []
    for game in arrival:
        seen.append(game)
        if _decided(seen, sample_of, planned):
            return len(seen)
    return None


def stopped_verdict(arrival, stop, sample_of) -> bool:
    played = arrival[:stop]
    base = [g for g in played if sample_of.get(g["seed"]) == 0]
    held = [g for g in played if sample_of.get(g["seed"]) == 1]
    return full_verdict(base, held)


def check_gate(name, base_games, held_games, shuffles, rng):
    sample_of = {g["seed"]: 0 for g in base_games} | {g["seed"]: 1 for g in held_games}
    planned = collections.Counter(
        [0] * len({g["seed"] for g in base_games}) + [1] * len({g["seed"] for g in held_games}))
    total = len(base_games) + len(held_games)
    truth = full_verdict(base_games, held_games)
    scores = seed_scores(base_games + held_games)
    margin = statistics.fmean(scores.values()) - 0.5

    orders = [job_order(base_games, held_games)]
    pooled = base_games + held_games
    for _ in range(shuffles):
        shuffled = list(pooled)
        rng.shuffle(shuffled)
        orders.append(shuffled)

    stops, disagree = [], 0
    for arrival in orders:
        stop = replay(arrival, sample_of, planned)
        if stop is None:
            stops.append(total)
            continue
        stops.append(stop)
        if stopped_verdict(arrival, stop, sample_of) != truth:
            disagree += 1
    return dict(gate=name, total=total, truth=truth, margin=margin,
                mean_stop=statistics.fmean(stops), min_stop=min(stops), max_stop=max(stops),
                disagree=disagree, orders=len(orders))


def fixed_n(base_games, held_games, n, shuffles, rng):
    """The alternative: play the first `n` games, whatever they say."""
    sample_of = {g["seed"]: 0 for g in base_games} | {g["seed"]: 1 for g in held_games}
    truth = full_verdict(base_games, held_games)
    pooled = base_games + held_games
    if n >= len(pooled):
        return 0, len(pooled)
    disagree = 0
    orders = [job_order(base_games, held_games)]
    for _ in range(shuffles):
        shuffled = list(pooled)
        rng.shuffle(shuffled)
        orders.append(shuffled)
    for arrival in orders:
        played = arrival[:n]
        base = [g for g in played if sample_of.get(g["seed"]) == 0]
        held = [g for g in played if sample_of.get(g["seed"]) == 1]
        if not base or not held:
            disagree += 1  # cannot even be judged: two samples are required
            continue
        if full_verdict(base, held) != truth:
            disagree += 1
    return disagree, len(orders)


def synthetic_gates(gates, count, rng, base_seeds=32, held_seeds=64):
    """Gates resampled from the recorded per-seed results.

    The completed gates are almost all comfortably accepted, so they say
    little about the boundary -- and none of them is a rejection, so on real
    data only one of the two disagreements can even occur. Resampling seeds
    with replacement produces gates across the whole range, rejections
    included, and the recorded seeds are the only honest source of what a
    seed's result looks like."""
    pool = []
    for _, base_games, held_games in gates:
        by_seed = collections.defaultdict(list)
        for g in base_games + held_games:
            by_seed[g["seed"]].append(g)
        pool.extend(rows for rows in by_seed.values() if len(rows) == 2)
    # Resampling uniformly gives gates clustered near the pool's own mean,
    # which leaves the clear rejections -- the ones a gate most needs to get
    # right -- untested. Each synthetic gate draws a tilt and weights seeds
    # by exp(tilt * score), which slides the true score across the range
    # while every seed remains a real recorded result.
    scored = [(rows, statistics.fmean(r["result"] for r in rows)) for rows in pool]
    for _ in range(count):
        tilt = rng.uniform(-14, 14)
        weights = [pow(2.718281828, tilt * (score - 0.5)) for _, score in scored]
        base, held = [], []
        for index, want, into in ((0, base_seeds, base), (1, held_seeds, held)):
            picked = rng.choices(scored, weights=weights, k=want)
            for i, (rows, _) in enumerate(picked):
                for g in rows:
                    clone = dict(g)
                    clone["seed"] = 4000 + i if index == 0 else 5000 + i
                    into.append(clone)
        yield base, held


def sweep(gates, count, shuffles, rng, fixed=None):
    """Disagreement as a function of how close the gate is to the boundary.

    `fixed`, when given, measures the fixed-N design over the same gates and
    the same arrival orders -- the only fair way to compare them, since both
    are judged on a subset and both therefore inherit the same widening of
    the confidence interval."""
    buckets: dict[str, list] = collections.defaultdict(list)
    fixed_buckets: dict[str, list] = collections.defaultdict(list)
    for base_games, held_games in synthetic_gates(gates, count, rng):
        sample_of = ({g["seed"]: 0 for g in base_games}
                     | {g["seed"]: 1 for g in held_games})
        planned = collections.Counter(
            [0] * len({g["seed"] for g in base_games})
            + [1] * len({g["seed"] for g in held_games}))
        truth = full_verdict(base_games, held_games)
        scores = seed_scores(base_games + held_games)
        margin = abs(statistics.fmean(scores.values()) - 0.5)
        key = ("<0.01" if margin < 0.01 else "0.01-0.03" if margin < 0.03
               else "0.03-0.06" if margin < 0.06 else "0.06-0.10" if margin < 0.10
               else ">=0.10")
        pooled = base_games + held_games
        for _ in range(shuffles):
            arrival = list(pooled)
            rng.shuffle(arrival)
            stop = replay(arrival, sample_of, planned)
            if stop is None:
                buckets[key].append((False, len(pooled), truth, truth))
                continue
            got = stopped_verdict(arrival, stop, sample_of)
            buckets[key].append((got != truth, stop, truth, got))
            if fixed and fixed < len(pooled):
                played = arrival[:fixed]
                if any(sample_of.get(g["seed"]) == 0 for g in played) and \
                        any(sample_of.get(g["seed"]) == 1 for g in played):
                    got_f = stopped_verdict(arrival, fixed, sample_of)
                    fixed_buckets[key].append((got_f != truth, fixed, truth, got_f))
    return buckets, fixed_buckets


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--logs", default="logs/game-check")
    p.add_argument("--shuffles", type=int, default=100,
                   help="random arrival orders per gate, on top of the job order")
    p.add_argument("--fixed", type=int, default=160, help="the fixed-N design to compare against")
    p.add_argument("--synthetic", type=int, default=0,
                   help="resample this many gates to sweep the acceptance boundary")
    p.add_argument("--seed", type=int, default=0)
    args = p.parse_args(argv)

    rng = random.Random(args.seed)
    gates = list(completed_gates(Path(args.logs)))
    if not gates:
        print("no completed gates found", file=sys.stderr)
        return 1

    print(f"{len(gates)} completed gates, {args.shuffles} shuffled arrival orders each "
          f"(min_games={ACCEPTANCE['min_games']})\n")
    print(f"{'gate':<16}{'verdict':>9}{'margin':>9}{'games':>7}{'mean stop':>11}"
          f"{'range':>12}{'disagree':>10}")
    rows, fixed_bad, fixed_orders = [], 0, 0
    for name, base_games, held_games in gates:
        row = check_gate(name, base_games, held_games, args.shuffles, rng)
        rows.append(row)
        span = f"{row['min_stop']}-{row['max_stop']}"
        print(f"{row['gate']:<16}{'ACCEPT' if row['truth'] else 'REJECT':>9}"
              f"{row['margin']:>+9.3f}{row['total']:>7}{row['mean_stop']:>11.1f}"
              f"{span:>12}{row['disagree']:>7}/{row['orders']}")
        bad, n = fixed_n(base_games, held_games, args.fixed, args.shuffles, rng)
        fixed_bad += bad
        fixed_orders += n

    saved = 1 - statistics.fmean(r["mean_stop"] for r in rows) / statistics.fmean(
        r["total"] for r in rows)
    total_disagree = sum(r["disagree"] for r in rows)
    total_orders = sum(r["orders"] for r in rows)
    print(f"\npredictive stopping: {total_disagree}/{total_orders} verdicts disagree with the "
          f"full run, {saved:.1%} of games saved")
    print(f"fixed {args.fixed} games:  {fixed_bad}/{fixed_orders} disagree, "
          f"{1 - args.fixed / statistics.fmean(r['total'] for r in rows):.1%} saved")

    if args.synthetic:
        print(f"\n{args.synthetic} gates resampled from the recorded seeds, by distance "
              f"from the boundary:")
        print(f"{'|margin|':<12}{'gates':>8}{'stop':>7}"
              f"{'predictive: f.rej':>19}{'f.acc':>8}"
              f"{'fixed ' + str(args.fixed) + ': f.rej':>19}{'f.acc':>8}")
        buckets, fixed_buckets = sweep(gates, args.synthetic,
                                       max(1, args.shuffles // 10), rng, fixed=args.fixed)
        for key in ("<0.01", "0.01-0.03", "0.03-0.06", "0.06-0.10", ">=0.10"):
            rows_b = buckets.get(key)
            if not rows_b:
                continue

            def rates(rows):
                if not rows:
                    return None, None
                fr = sum(1 for bad, _, truth, _ in rows if bad and truth) / len(rows)
                fa = sum(1 for bad, _, truth, _ in rows if bad and not truth) / len(rows)
                return fr, fa

            fr, fa = rates(rows_b)
            ffr, ffa = rates(fixed_buckets.get(key, []))
            fixed_cols = ("       n/a     n/a" if ffr is None
                          else f"{ffr:>18.1%}{ffa:>8.1%}")
            print(f"{key:<12}{len(rows_b):>8}"
                  f"{statistics.fmean(s for _, s, _, _ in rows_b):>7.0f}"
                  f"{fr:>18.1%}{fa:>8.1%}{fixed_cols}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
