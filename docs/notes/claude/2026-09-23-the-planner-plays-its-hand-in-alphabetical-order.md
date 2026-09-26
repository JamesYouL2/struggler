# The assignment planner plays its hand in alphabetical order

Run 35814771005 read `hand-assignment-on` minus `hand-assignment-base` at
**-0.240 [-0.262, -0.218]** over 1152 paired seeds (0.309 against 0.549,
signed VP -10.86 against -1.77, USSR-seat nuclear losses 40 against 26).
The pre-registered rule says the gate stays shut, and it does. This note
is about *why*, because a quarter of a game is not what a weaker allocation
idea costs. The last three improvements here that shipped measured
+0.03 to +0.04. A loss of 0.24 is the size of a defect.

It is a defect, and the reason is simple: **the plan decides which cards to
play this turn, but not when to play each one. `_plan_pref` then reads an
order out of it anyway.**

## The mechanism

`hand_prices` gives every ordinary card the same price in every round:
`play=(play,) * rounds`. Only a scoring card's price varies by round,
through ruling 5's `gain`. So for the non-scoring cards the DP's objective
does not depend on which round a card lands in. Every ordering of the
chosen set scores the same total. `solve_hand` breaks the tie in
`offer(...)` on strict `>`, walking `ordered`, which is sorted by card key.
The first card that reaches the maximum wins slot 0. That card is the
alphabetically first one, unless float regrouping in `price + rest` picks
some other card by an ulp.

`_plan_pref` then takes `assignment.rounds[0]` as the card to play NOW, and
the ranking puts it above every option that is not a certain defeat. In
practice the policy's "best card now" becomes "the alphabetically first
card of the set it means to play this turn".

A toy hand against the branch's solver shows it directly (headline
excluded):

    prices  A_weak 0.5, B_ok 2.0, M_mid 3.0, Z_best 9.0   (flat over 4 rounds)
    rounds  A_weak, B_ok, M_mid, Z_best

So the weakest card goes first and the best card goes last.

## In played games

`diag.py` (full source at the end) plays
the planner-on bot against the shipped bot on seeds 4000-4003 and
instruments every action-round decision:

| | count | share |
| --- | ---: | ---: |
| action-round decisions | 207 | |
| lead changed the scorer's own top pick | 168 | 81% |
| promoted card = alphabetically first of the plan's round units | 152 | 73% |
| mean price rank of the promoted card (0 = best in hand) | 1.53 of 4.6 | |

Typical overrides, from the logs:

    turn 1 AR2 US:   played De_Stalinization (price 9.81)  instead of Red_Scare_Purge (102.52)
    turn 1 AR2 USSR: played Containment (9.67)             instead of Socialist_Governments (78.70)
    turn 2 AR1 US:   played Arab_Israeli_War (9.23)        instead of US_Japan_Mutual_Defense_Pact (47.72)

I did not break down the remaining quarter, where the promoted card was
not the alphabetically first. The likely causes are the units whose price
does vary: a scoring card that ruling 5 times, or a space or UN unit. That
is a guess, not a count. These four games carry no opening book and are
unpaired, so they measure the mechanism, not strength.

The scale is not the problem. The prices in the table match the scorer's
(`test_hand_planner_wiring` pins that). The lead is a lexicographic key,
so no scale was ever involved.

## A second, smaller defect: the China Card is invisible

`hand_prices` iterates `obs.hand`, and the China Card is not in it. So the
plan never assigns China to a round, and whenever the scorer's top pick is
a China play, the lead overrides it with a hand card. Seed 4001, USSR,
turn 1: the scorer wanted China in AR2 through AR6, and the planner overrode
it every time.

## The same tie decides which cards are held (found while fixing)

Reading the plan as a set (fix 1 below, as first written) is not enough.
On a smoke run of that version, seed 4000 still overrode the scorer in
32 of 62 action rounds: it held NORAD, the scorer's top pick, and played
Duck and Cover. The price table shows why. At `hold_option` 0 **an
ordinary card's hold price is exactly its play price**. `hold_value` reads
the same `card_play_value` that `play_price` does:

    turn 1 AR1 US, rounds_left 6        play      hold
       COMECON                          26.42     26.42
       Duck_and_Cover                   40.34     40.34
       NORAD                            40.34     40.34
       Europe_Scoring                    0.00   -415.18   (never held)

So every partition of the ordinary cards into "played" and "held" has the
same total, and the partition is the solver's by-key tie-break too. Early
slots fill alphabetically, so the leftover card is the alphabetically last.
Apart from its hard constraints (scoring cards, the space and UN units,
the round count), the objective is flat. The only real content is the
headline choice (headline price against play price) and those units.

**What shipped on `fix/hand-planner-lead`:** the lead acts only on a
STRICT preference, tested by re-solving with the candidate forced
(`_plan_lead`). A held card is demoted only if forcing it into a round
lowers the plan's value. A headline leads only if forcing it reaches the
plan's value. A one-ulp tolerance keeps float regrouping from counting as
a preference. The China Card is exempt. Where every ordinary card ties,
nothing is demoted and the ranking is exactly the shipped one;
`test_a_tie_between_playing_and_holding_is_not_a_preference` pins that.

That makes the re-run arm (`hand-lead-on`) a narrow reading. It measures
the planner's strict preferences, mostly the headline and the space and
UN units, not whole-hand allocation. For the allocation to say anything
about holds, a hold has to be priced differently from a play: a real
next-turn price (the card's value on a later board, the risk of
carrying it, a discard or an event lost), not the same number twice.
That is the modelling question the hold-option grid tried to answer with
a premium, and it read nothing above 0.

## Readings, 2026-09-23: both fixed variants lose, and the rule says stop

Block 80000-81023 (held 90000-90127), paired, against `bc5ef93`. Both
runs were stopped by the halfway check (the `paired` fix, PR #45, doing its job).
Neither result is below -0.10, so under the pre-registered rule each is a
verdict, not a defect to chase. Each upper bound is below 0, so **the gate
stays shut** for both.

| arm | run | paired diff vs `hand-lead-base` | seeds | US seat | USSR seat | nuked (US/USSR) |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| `hand-lead-base` | both | -- | 640 | 0.628 | 0.509 | 11/7 |
| `hand-lead-on` (strict lead) | 35844260343 | **-0.061 [-0.090, -0.032]** | 639 | 0.586 | 0.427 | 8/26 |
| `hand-worst-on` (hold the worst) | 35845098170 | **-0.088 [-0.117, -0.060]** | 637 | 0.536 | 0.425 | 23/22 |

- **The base arm read identically in both runs** (0.568 [0.547, 0.589],
  the same seats and nuclear counts), as it must at weight 0. The two
  on-arms are therefore comparable: holding the worst cards by default is
  about 3 points worse than acting only on strict preferences, and both
  are worse than no planner.
- **The loss is mostly the USSR seat** (0.509 down to about 0.43), and
  nuclear losses rise: USSR from 7 to 26 under the strict lead, and both
  seats under hold-worst. *Hypothesis, not measured:* `pref` sorts
  above the risk/score blend in `rank_actions`' key (only `certain` is
  above it). Demoting a card therefore promotes the next non-demoted card
  even when that card carries more DEFCON risk. A lead that only reorders
  within an equal-risk band would test this.
- **The planner arms are slow.** One strict-lead shard and two hold-worst
  shards stalled, each on a single game that ran past the 1200 s stall floor
  (for example seed 80638 USSR). No base shard stalled. `_plan_lead`
  re-solves the DP once per held card (and `hold_worst` adds one per
  candidate), on every ranked decision. The pooled readings lose 1 and 3
  seeds to this; that is what audit F2 warns about, and here it is too
  small to matter.
- **Not settled:** whether a planner with a real hold price (not play ==
  hold) could win. Everything measured so far on this line has been the
  lead's tie-breaks, not whole-hand allocation.

## The headline-only planner, and a correction from the maintainer (in flight)

After both whole-turn variants lost, the maintainer asked whether the
headline alone helps: `headline_only` (on `fix/hand-planner-headline-only`)
lets the plan lead the headline and nothing else.

Its first dispatch (35857931995) was cancelled before any reading. In
smoke games it **headlined opponent cards** (Cambridge Five and
Arab-Israeli War as the US). The maintainer's correction: a headline fires
the event, so the card that loses least should be a strong event of your
own, and you should almost never headline the opponent's cards. The price
table showed two causes:

- The table's headline price was the scorer's `event - 0.5 x Ops value`,
  and the plan also charges the headlined card its whole play. Ops were
  counted 1.5 times, which favours low-Ops cards.
- **The bot values its own events far below their Ops.** East European
  Unrest's event is worth 11 against 63 for its 3 Ops (turn 1, seed 4000),
  so "event minus Ops" is strongly negative for almost every own card, and
  a 2-Ops opponent card whose event fires anyway looked cheapest. Charging
  the Ops once does not fix this (Cambridge Five -42 against East European
  Unrest -52).

Fixed in the table only (`51c9224`): an opponent's card is never a headline
candidate, and the headline price is the event alone. The re-run,
**35858542880**, read (block 80000-81023 + held 90000-90127, paired, both
waves played because the halfway check was not decisive):

| arm | score | paired diff vs `hand-lead-base` | seeds | US seat | USSR seat | nuked (US/USSR) |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| `hand-lead-base` | 0.548 [0.532, 0.564] | -- | 1152 | 0.614 | 0.481 | 19/25 |
| `hand-headline-on` | 0.543 [0.527, 0.559] | **-0.005 [-0.023, +0.014]** | 1148 | 0.614 | 0.472 | 13/55 |

**Under the pre-registered rule, the gate stays shut.** The lower bound is
at or below 0. Changing only the headline is worth nothing measurable, and
the interval rules out a gain above about 1.4 points. Four seeds were
lost to two slow planner shards.

What the average hides: **USSR-seat nuclear losses more than double, 25 to
55**, while the score barely moves. The planner's headline lead sorts above
the risk/score blend and below only `certain` (a certain defeat). So a
headline that raises the chance of nuclear war without making it certain
can still lead. This is the same shape as the USSR nuclear rise in both
whole-turn variants. *Hypothesis, not measured:* a lead that only reorders
cards within one DEFCON-risk band would close it. With four planner
variants now below or level with the shipped bot, it is not worth
another run unless holding a card gets its own price. The event-price question became its own experiment:
[event strength](2026-09-23-event-scale.md).

**The cancel did not stop the run.** Cancelling killed wave 1, but
`interim` and `run2` were `if: always()`. `interim` ran on the empty
artifacts, failed open, and launched all of wave 2, and eight shards played
for twenty minutes until a second cancel. It was the second time: pi's
2026-09-22 hold-option "orphan" had the same shape. Both jobs are now
`!cancelled()`, gated by `test_a_cancel_never_launches_wave_two`.

## What would fix it

This part is design, and it has not been measured. The branch is pi's, and
the call is the maintainer's.

1. **Stop reading an order the objective does not contain.** (As first
   written, this said to use the plan as a set. That is not enough: see the
   section above. What shipped acts only on strict preferences.) Use the plan
   as a set, not a sequence. Demote cards the plan holds, and let the
   existing scorer choose among the cards it means to play this turn:
   `pref = 1 if card not in assignment.holds else 0`. Keep a slot-specific
   lead only where the price actually varies by round (a scoring card's
   ruling-5 timing, the space and UN units).
2. **Or make the order real.** Price each card per round (for example,
   what the current board gives now against a decay for later), so the
   DP's argmax for slot 0 means something. That costs more and is a
   modelling question in its own right.
3. **Either way, give the China Card a unit** (or exempt China plays
   from the lead) so the lead cannot veto it.
4. **Gate the shape.** Test that permuting card keys (renaming) does not
   change which card the lead promotes on a hand with distinct prices. The
   existing wiring test uses a hand where this cannot show.

Once (1) is in, the arm is worth re-running as it stands. The reading
above is of the tie-break, not of whole-hand allocation, so it says
nothing either way about the allocation hypothesis. The tail read in
`docs/notes/pi/2026-09-23-assignment-planner-tail-reads.md` (USSR 6/32
to 3/32 at 0.25) was also taken under this defect and should not be
quoted.

## The near-tie band: the rule, written before the number (2026-09-25)

Both measured failures share one mechanism, stated as a hypothesis above
twice: `pref` sorted above the whole risk/score blend, so demoting a card
promoted the next one whatever it cost, and USSR-seat nuclear losses
rose with every variant. The maintainer's 2026-09-25 shape closes exactly
that: **"consider only doing planner if strategic bot's normal decision
is tied or close to tied."**

Built on `exp/planner-near-tie` (the strict-preference lead of `935872b`,
ported onto main, plus `_plan_band`): the plan's strict preferences
reorder only the card plays whose safety key matches the best one's
`certain` and risk slots and whose score is within `hand_assignment` Ops
(at this turn's `ops_value`) of it. Outside the band the scorer's order
stands. A band holding fewer than two options asks the planner nothing,
which should also end the planner arms' stalls. At 0 the planner is not
consulted and the parity corpus is unchanged.

Arms, on a fresh block, anchor `bc5ef93`, paired: `planner-band-base`
(0), `planner-band-01` (0.1 Op), `planner-band-05` (0.5 Op),
`planner-band-10` (1 Op). Seeds `132000-133023` + held `133500-133627`,
reserve `133700-133827` (two full spare shards an arm).

THE RULE, not moved after the number:

1. Each band arm's paired difference against `planner-band-base`: lower
   bound above 0 means that band beats the shipped bot.
2. Exactly one beats it: that width goes to a change gate. More than one:
   the highest point estimate (the widths are an ordered scale), with the
   runner-up's reading recorded.
3. **Veto:** an arm whose bot DEFCON-1 losses (both seats summed) exceed
   the base's by more than half is not nominated, whatever its score.
   That is the failure every earlier planner variant showed.
4. None beats it: an arm whose upper bound is below 0 costs, and the
   planner stays off. If all cover 0, the tie-break is not measurable at
   this sample, and the planner line waits for a real hold price
   (EXPERT_ASKS 6a: timing an event, or sitting out a negative card past
   the reshuffle, with `vp_swing` as the per-turn decline).

What it cannot settle: whole-hand allocation. Play and hold are still
priced the same, so the plan's only strict preferences are the headline
and the space and UN units. This reads the plan as a tie-breaker, which
is all it can honestly be until a hold has its own price.

## The near-tie band: the reading (run 36225640116, 2026-09-26)

1152 paired seeds per arm, all four complete. The interim failed open,
correctly: base lost one wave-1 game (575 of 576), so every arm played
wave 2 and its spares. Five shards were partial, and the spare shards
backfilled every lost core seed (listed in `pooled.json` as `dropped` /
`backfilled`). This is the first full run on the 64-seed, spare-shard
pooling. The final bar is 1.678.

| arm | paired diff vs base | bot nuked (US + USSR) | USSR seat |
| --- | ---: | ---: | ---: |
| `planner-band-base` (0) | 0.546 [0.530, 0.562] (level) | 22 + 32 = 54 | 0.499 |
| `planner-band-01` (0.1 Op) | **-0.008 [-0.019, +0.003]** | 55 | 0.484 |
| `planner-band-05` (0.5 Op) | **-0.009 [-0.027, +0.010]** | 44 | 0.475 |
| `planner-band-10` (1 Op) | **+0.004 [-0.016, +0.024]** | 51 | 0.503 |

**By the rule, branch 4.** No lower bound is above 0, so nothing is
nominated. The veto has nothing to catch. All three cover 0, so the
tie-break is not measurable at this sample, **`hand_assignment` stays 0**,
and the planner line waits for a real hold price (EXPERT_ASKS 6a).

What it does settle: **the band closed the nuclear failure.** Every
earlier variant raised USSR-seat nuclear losses (7 -> 26, 25 -> 55). Inside
the band they are flat or lower (44-55 against 54), and the losses of
-0.061 and -0.240 are gone: the worst band reads -0.009. So the override
itself was what cost. As a tie-breaker the plan is harmless, and at
+/-0.02 it is not measurably useful. The first dispatch (36219501188) died
on every on-arm shard: arithmetic on a certain-win sentinel in
`_plan_band`, fixed, with a regression test.

## The exact-tie arm: the rule, written before the number (2026-09-26)

The maintainer asked for the band as a pure tie-breaker. `hand_assignment`
1e-9 makes the band hold only options whose scores tie to about 1e-9 Op.
Those are the choices engine order decides today: 17.5% of real
card-play choices in the live remeasurement. This needs no code change,
and the base arm's shards are cached, so only `planner-band-tie` plays.
Timed on 221 identical card-play positions, the band costs +1% per
card-play decision at 0.1 Op and nothing at 0; an exact-tie band sits
below that.

THE RULE, not moved after the number: read `planner-band-tie` paired
against `planner-band-base`.

1. **Ship** (through the change gate) if the paired interval covers 0 or
   lies above it, AND the bot's DEFCON-1 losses (both seats summed) do not
   exceed the base's by more than half.
2. **Stay at 0** if the upper bound is below 0, or if the nuclear veto
   fires.

Why the bar is "not measurably worse" rather than a gain: a tie-break
replaces an arbitrary pick (the engine's listing order), so a principled
preference in its place needs only to do no measurable harm. That is a
convention, and a ship under (1) is not a measured improvement. The
nearest measured band (0.1 Op) leaned -0.008 [-0.019, +0.003].

## Reproduction

    git worktree add ../planner origin/feat/hand-planner-assignment
    cd ../planner && PYTHONPATH=src ../struggler/.venv/bin/python diag.py 4000

`diag.py` subclasses `StrategicPlayer`, overrides `rank_actions`, and
compares the ranked head against the `safety_key` maximum (the shipped
order) on every `ACTION_ROUND_PLAY` where a plan exists.

```python
"""Instrument the planner's lead in played games: does the card it promotes
match the scorer's own top pick, and is it just the alphabetical-first of the
cards the plan intends to play this turn?"""
import collections, sys
from struggler.bots.strategic import StrategicPlayer, StrategicWeights
from struggler.bots.strategic import policy as P
from struggler.engine import Engine, Side, DecisionKind as K
from struggler.runner import play_game

stats = collections.Counter()
examples = []

class Probe(StrategicPlayer):
    def rank_actions(self, obs):
        ranked = super().rank_actions(obs)
        d = obs.pending_decision
        if d is None or d.kind is not K.ACTION_ROUND_PLAY or self._hand_plan is None:
            return ranked
        plan = max(self._hand_plan, key=lambda wp: wp.probability).assignment
        if not plan.rounds:
            return ranked
        want = plan.rounds[0][1]
        played = [u[1] for u in plan.rounds]
        # the scorer's own pick: rank by safety_key alone (the shipped order)
        own = max(((self.safety_key(obs, a), a) for a in d.options), key=lambda p: p[0])[1]
        chosen = ranked[0][1].payload.get('card')
        prices = {c.key: c.play[0] for c in self.hand_prices(obs)}
        stats['decisions'] += 1
        stats['lead_changed_pick'] += own.payload.get('card') != chosen
        stats['want_is_alpha_first_of_played'] += want == sorted(played)[0]
        order = sorted(prices, key=prices.get, reverse=True)
        if want in order:
            stats['want_price_rank_sum'] += order.index(want)
            stats['hand_size_sum'] += len(order)
        if len(examples) < 6 and own.payload.get('card') != chosen:
            examples.append((obs.turn, obs.action_round, obs.side.value, chosen, own.payload.get('card'),
                             round(prices.get(chosen, float('nan')), 2), round(prices.get(own.payload.get('card'), float('nan')), 2)))
        return ranked

seed = int(sys.argv[1])
engine = Engine.new_game(seed=seed) if hasattr(Engine, 'new_game') else Engine(seed=seed)
on = Probe(StrategicWeights(hand_assignment=1.0))
off = StrategicPlayer(StrategicWeights())
side_on = Side.US if seed % 2 == 0 else Side.USSR
winner = play_game(engine, {side_on: on, side_on.opponent: off})
print('seed', seed, 'planner side', side_on.value, 'winner', winner and winner.value, 'turn', engine.turn)
print(dict(stats))
if stats['hand_size_sum']:
    print('mean price rank of promoted card (0=best):', stats['want_price_rank_sum'] / stats['decisions'],
          'of mean hand', stats['hand_size_sum'] / stats['decisions'])
for e in examples: print('turn %s AR%s %s: played %s (price %s) instead of %s (price %s)' % (e[0], e[1], e[2], e[3], e[5], e[4], e[6]))
```
