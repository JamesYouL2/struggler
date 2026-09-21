# Don't revert to v0.2.1: it is not the simpler bot

2026-09-21. Asked directly, and worth recording because the premise is
reasonable and wrong, and because it will be asked again the next time a
period nets to zero.

The reasoning that leads here is sound as far as it goes:
[109 commits after v0.2.1 the bot plays v0.2.1 to a draw](2026-09-20-since-v0.2.1.md)
(0.505 [0.489, 0.521], 1024 seeds). If two versions are level in strength,
take the simpler one. The step that fails is the last one: **v0.2.1 is not
simpler.** It is smaller.

## The two numbers point opposite ways

| | v0.2.1 | HEAD | |
| --- | ---: | ---: | --- |
| `bots/strategic/` | 3,983 lines | **6,599** | +66% |
| weights declared | 28 | 27 | |
| weights *live* (non-zero) | 26 | **24** | |
| **board-value weights live** | **19** | **10** | **-47%** |

The codebase grew by two thirds while the model it implements nearly
halved. Those are not in tension; they are the shape of the whole year's
work. What grew is *apparatus*, and apparatus has no free parameters in
it.

"Board-value" here means a weight that enters what a position is worth --
`country_value`, `access`, the region terms -- as opposed to a policy or
search knob. The membership is listed below so the boundary can be argued
with rather than taken on trust.

- **v0.2.1 (19):** `control`, `battleground`, `progress`, `reserve`,
  `first_mover`, `margin_presence`, `margin_battleground`, `margin_country`,
  `margin_live`, `access`, `access_redundant`, `access_chain`,
  `access_contested`, `region`, `vp_early`, `vp_mid`, `vp_late`,
  `progress_curve`, `ops`. (`wipe` and `wipe_backed` were declared at 0.)
- **HEAD (10):** `control`, `battleground`, `progress`, `reserve`,
  `access`, `access_decay`, `region`, `vp_base`, `vp_swing`,
  `europe_control_vp`. (`country_vp_scale`, `europe_curve` and
  `access_chain` are declared at 0.)

## What was actually deleted, and what was added

Fourteen weights are gone since v0.2.1:

    access_contested  access_redundant  first_mover  margin_battleground
    margin_country    margin_live       margin_presence  ops
    progress_curve    vp_early          vp_late      vp_mid
    wipe              wipe_backed

Nearly every one went because an arm said it was inert or wrong, not
because someone tidied. The four `margin_*` weights went on a measurement;
`progress_curve` was pinned at 1.0 (which is the identity) and then
removed; `first_mover` read 0.513 [0.475, 0.550] ablated, the highest of
its batch; `vp_early/mid/late` collapsed into `vp_base` and `vp_swing`.

Thirteen were added -- but count what kind:

- **Board value (6):** `vp_base`, `vp_swing` (replacing three),
  `access_decay`, `europe_control_vp`, and `country_vp_scale` /
  `europe_curve`, both shipped at 0.
- **Policy and search (7):** `space_ability_2/4/6/8`, `last_window_guard`,
  `reply_coup`, `scoring_rival`.

So the board-value layer took 14 out and put 6 in, two of them off. The
growth is on the policy side and in the machinery.

## Where the 2,616 lines went

| | v0.2.1 | HEAD |
| --- | ---: | ---: |
| `policy.py` | 2,563 | 3,571 |
| `evaluator.py` | 733 | 926 |
| `public_cards.py` | 125 | 396 |
| `defcon.py` | 444 | 532 |
| `forecast.py` | -- | **687** |
| `schedule.py` | -- | **213** |
| `valuation.py` | -- | **138** |

`forecast.py`, `schedule.py` and `valuation.py` did not exist in v0.2.1.
They are the deck's public schedule and the exact scoring potential --
**instruments, not knobs.** `forecast.tier_weights` reproduces the tier DP
to 1e-15; `public_cards` is what lets urgency know when a region will next
score. Reverting deletes the measuring equipment and keeps the guesses.

## Three things a revert would cost

1. **It un-learns fourteen measurements.** Every deleted weight is a
   settled question. Reverting re-adds the region margin -- deleted
   *because* an arm said it was inert -- and the rest with it.
2. **v0.2.1 predates the hand-safety fixes.** Audit F1-F5 and the
   last-safe-window guard landed 2026-09-18; they are correctness defects,
   not tuning, and they were the largest single gain of the period (USSR
   nuclear losses 169 -> 37 of 512). v0.2.1 carries all five.
3. **v0.2.1 predates the instruments that found the regression.** The
   1024-seed drift canary, sharded anchored experiments, the parity corpus
   as it now stands, `test_experiment_registry.py`,
   `test_scale_discipline.py`. The drift being discussed was only ever
   visible because those exist. Reverting to escape a regression by
   deleting the regression detector is the wrong trade at any price.

## What "level" does and does not license

0.505 [0.489, 0.521] means **the two cannot be told apart at 1024 seeds**,
not that they are identical. The interval allows v0.2.1 being up to 0.011
better or 0.021 worse.

That matters for the argument: if simplicity were strongly on v0.2.1's
side, level strength would make a revert a genuine option, and the right
call would be to take the simpler bot and keep the measurement. Simplicity
is not on its side, so the question does not arise. **The revert case rests
entirely on a simplicity claim that the numbers contradict.**

## The legitimate version of the impulse

The instinct -- this thing has too many parts, cut it back -- is right, and
it already has a home: the deletion queue in
[the margin note](2026-09-19-delete-the-region-margin.md) and step 4 of
[the VP rebuild plan](2026-09-20-finishing-the-vp-rebuild.md).

Step 4 deletes `battleground` and `control` and the un-fitted half of
`country_value` -- taking the board-value layer from **10 live weights to
8** and removing a whole parallel implementation of the same four terms.
That is a real simplification, it is gated on a measurement rather than a
preference, and it keeps every instrument that proves it is safe.

**Simplify forward, not backward.** Each deletion is cheaper than the last
because the apparatus that prices it is already built -- which is the
return on those 2,616 lines.
