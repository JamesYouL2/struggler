# Win probability on held-out games: the logistic beats the bot, and the MCTS leaf is five times too steep

The maintainer's question (2026-09-27): does a logistic fit predict game
outcomes better than the current bot, and what does clipping at
[0.05, 0.95] or [0.10, 0.90] do? That is offline prediction and needs no
MCTS: record positions from self-play, fit on some games, score on games
the fit never saw.

**Run:** `winprob.yml` run 36344337350, seeds 160000-161499 (1500 games,
StrategicPlayer self-play at HEAD 6e47bfd), 24746 rows (one per turn
start per seat, labelled with the engine's winner). The split is by seed:
seed % 5 in {0,1,2} is train, 3 is validation (picks L2), 4 is test.
**Every number below is on the 300 test games (5102 rows).** A local
600-game run (seeds 160000-160599, 120 test games) read the same to two
decimals on every row.

| model | log loss | Brier | clip [.05,.95] | clip [.10,.90] | share outside [.05,.95] |
|---|---|---|---|---|---|
| constant | 0.6931 | 0.2480 | 0.6931 | 0.6931 | 0.0% |
| **leaf as-is** (`MCTSPlayer.leaf_return`) | **1.0382** | 0.2411 | 0.7385 | 0.6783 | **54.5%** |
| vp | 0.6365 | 0.2213 | 0.6365 | 0.6365 | 0.0% |
| leaf calibrated | 0.5716 | 0.1932 | 0.5720 | 0.5723 | 3.6% |
| leaf calibrated x turn | 0.5696 | 0.1926 | 0.5701 | 0.5708 | 4.4% |
| 09-10 shape (vp + board_vp*turn/10) | 0.5485 | 0.1849 | 0.5489 | 0.5512 | 5.9% |
| **logistic** | **0.5150** | **0.1711** | 0.5154 | 0.5195 | 9.0% |

Logistic minus the best bot reading (leaf calibrated x turn), test log
loss, bootstrap paired by game: **-0.0546 [-0.0710, -0.0380] (90%)**.

## What it says

**1. The logistic predicts better than any reading of the current bot.**
The interval excludes zero by a wide margin. It is calibrated end to end:
rows it puts at 0.95-1.00 won 97.0% (predicted 97.6%), rows at 0.00-0.05
won 2.1%. Its features are banked VP, VP x turn, board_vp, board_vp x turn,
turn, seat, DEFCON, space-race lead, China, scoring cards and ops in hand,
and the two tails past +/-12 VP. The weights are in the run's `report.json`.
The largest standardised weights are board_vp x turn (1.11), VP (0.53), VP
x turn (0.46) and seat (0.36, US).

**2. The MCTS leaf as it stands does worse than predicting 50% every
time.** It scores a log loss of 1.04 against the constant's 0.69, and 54.5% of its
predictions fall outside [.05, .95]. Rows it puts at 0.99 won 78.6%; rows
at 0.008 won 19.0%. The value underneath is informative: calibrated with
one slope it reaches 0.572. So the fault is the scale, not the signal.
`(1 + tanh(x/100)) / 2` is `sigmoid(x/50)`. The fitted slope is 1.341 per
standard deviation of `leaf_raw` (sd about 337), which is about
`sigmoid(x/250)`, or **`tanh(x/500)`**. **The leaf is about five times too
steep.** A saturated leaf compresses the difference between a good and a
bad line near +/-1, which is one candidate explanation for the MCTS
arms' vetoes (docs/notes/claude/2026-09-27-mcts-horizons-timed.md). This
is a hypothesis for a search arm, not a finding about playing strength.

**3. Clipping is a bandage for the leaf and a small cost for the
calibrated models.** For the leaf as-is it removes most of the damage
(1.04 -> 0.74 at [.05,.95], 0.68 at [.10,.90]), and even then it barely
beats the constant. For the logistic, [.05,.95] costs 0.0004 and
[.10,.90] costs 0.0045: in self-play, rows beyond 0.95 really do win
about 97%. The maintainer's 0.75-0.90 ceiling is a claim about strong
human play ("you cannot force a win"). Bot-vs-bot outcomes cannot test
it, and this reading neither supports nor refutes it. [.05,.95] is nearly
free as a safety margin.

## What it does not say

- Nothing about playing strength. A better predictor of *self-play*
  outcomes is not yet a better search leaf; that takes an MCTS arm
  (the obvious one: leaf temperature 500 instead of 100).
- The labels are this bot's games. A value fitted to them encodes this
  bot's mistakes (docs/notes/codex/2026-09-27-linear-value-learning.md).
- One row per turn start per seat. Mid-turn positions, which is where a
  leaf is actually read, are not sampled.

## Reproduce

    gh workflow run winprob.yml -f seeds=160000-161499 -f block=50

The rows, report and table are artifacts of run 36344337350 (they expire
after 30 days). Local copies are in `logs/winprob/ci-36344337350/`.

## The search arm (dispatched 2026-09-27)

`mcts-leaf500` against `mcts-leaf100`. Both are the guarded h1 AR1 search
(96 simulations, safe root, leaf risk, confidence 2), and they differ only
in `leaf_scale` (`MCTSPlayer(leaf_scale=...)`,
`STRUGGLER_MCTS_LEAF_SCALE`). Both play HEAD's strategic bot on the fresh
block 152000-152511 and are paired by seed. The rule, written before the
number, is in `.github/experiments.json`. Read the paired difference with
a one-sided 95% interval:

- lower bound above 0: 500 becomes the MCTS default;
- upper bound below 0: the fit's calibration does not transfer to search;
- the interval covers 0: no measured effect at 512 games.

Either way, the arm is vetoed if the searching side's DEFCON-1 losses are
more than 1.5 times `mcts-leaf100`'s.
