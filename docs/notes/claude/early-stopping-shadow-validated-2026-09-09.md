# Early stopping, shadow-validated (2026-09-09)

Codex asked for the gate's early stopping to be checked against completed
gates rather than trusted, and compared with simply playing a fixed number
of games (docs/notes/codex/). `scripts/validate_early_stopping.py` does
it offline, so it costs no games; rerun it as gates accumulate.

Only 8 of the 16 recorded gates can serve as references. The other 8
stopped early, and what they stopped is exactly the evidence needed to
check them -- worth knowing before assuming a validation like this can be
done retrospectively at any time.

Over those 8 (all accepts) plus 600 gates resampled from their seeds with
the true score tilted across the line:

| |margin| | predictive f.rej | f.acc | fixed 160 f.rej | f.acc |
| --- | ---: | ---: | ---: | ---: |
| <0.01 | 0.0% | 0.0% | 1.7% | 0.0% |
| 0.01-0.03 | 3.5% | 0.0% | 7.9% | 0.0% |
| 0.03-0.06 | 0.0% | **9.7%** | 0.7% | **26.4%** |
| 0.06-0.10 | 0.0% | 4.8% | 0.0% | 6.1% |
| >=0.10 | 0.0% | 0.0% | 0.0% | 0.0% |

Predictive stopping saves 10.2% of games against the fixed design's 16.7%,
and is better in every bucket -- so the answer to Codex's "retain it only
if its measured tradeoff is better" is yes, keep it.

The finding that matters more is the column both share. Stopping early
accepts gates it should reject, at up to 9.7%, concentrated where the true
score sits 0.03-0.10 below the line. That is not a bug: fewer seeds means a
wider one-sided interval, the rule accepts when the upper bound reaches
0.500, and a run stops when its data happens to look decisive. Raising
`min_games` buys it back about one for one (176 games: 2.0% false accepts
for 4.2% saved), which is not a trade worth making blind.

So the floor stays at 150 and the honest consequence is recorded instead:
**a stopped ACCEPT is weaker evidence than a completed one**, and a gate
landing within 0.06 of 0.500 is worth rerunning with `GATE_DECIDE=0`.
Every gate this session that mattered was inside that band.

The nuclear-loss rule started as "any is a blocker" and was wrong. It
rejected the scoring-horizon commit on one loss, and the recorded gate
games say that is variance: 3 candidate losses in 4226 games, 0.071%, across
three separate commits, two of which landed. At that rate a 192-game gate
sees one about one time in eight, so demanding zero would have rejected a
change in eight on noise, which is the failure the strength rule was written
to avoid. Two is now a fail; one warns and names the seat and seed to replay.

Recounted 2026-09-09, after `4f01bc7` fixed the attribution: the earlier
figure of 4 in 1920 included one game the *opponent* lost to DEFCON 1, and
the recorded corpus has since more than doubled. The rate came down rather
than up, which matters for Codex's proposal to drop the cap entirely
(docs/notes/codex/): a FAIL at two fires by chance in under 1% of gates,
so the tripwire is close to free.
Replay it: seed 4014 USSR turn 9 was a real lost position, the planner
having correctly flagged every remaining play as a certain loss several
action rounds earlier, with two US DEFCON-lowering cards stuck in a hand of
two at DEFCON 2.

A seed counts once, not once per seat: both seats play the same deal from
the same shuffle, so counting them separately understates the spread and
makes noise look like a result.

The held-out range (5000-5063 by default) exists because selecting change
after change on 4000-4031 is how a bot overfits its own benchmark. It
earned its place immediately: the event-basis fix scored 0.469 on the
tuning seeds and 0.555 held out.

The rest of the gate is diagnostics to read, not rules: the turn-1
event-value table (`python -m struggler.bots.benchmark --table`, read by
eye against your own judgement), the expert valuation diff (`--expert
models/expert_valuations.json`: the expert's prices in US Ops on the
opening board, the bot's values converted on its own Ops scale, misses
over 0.5 Ops flagged, ordering constraints checked, unpriced rows listed
as a to-do), and the turn-3 checkpoint. The expert check is deliberately
not a rule: it is a handful of hand-priced rows whose miss count moves by
one or two on changes that are otherwise clearly fine. One structural
change per branch. When a check fails, bisect, do not tune.

The Rust plan is `docs/RUST_PORT_PLAN.md`.

```sh
# narrate a game: plays, events, influence moves, coups, DEFCON, scoring
STRUGGLER_OPPONENT_MODEL=models/opponent-model-v1.json \
  python src/main.py --us strategic --ussr strategic --seed 3003 \
  --log-level INFO --log-file game.log
# WARNING level prints only nuclear risk; DEBUG adds every action and the planner's numbers
# 16-seed paired A/B of a weight change against a rival checkpoint (8 workers, ~3 min)
python -m struggler.bots.train evaluate --opponent strategic --pairs 16 --seed 4000 \
  --rival rival.json --workers 8
```

`logs/game-check/` holds the evidence games (gitignored): `*-after-fix`,
`*-learned-priors`, `3003-*`, and the A/B reports. The baseline that every
change is measured against is seeds 4000-4015, both seatings.
