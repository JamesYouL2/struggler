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

## What would fix it

This part is design, and it has not been measured. The branch is pi's, and
the call is the maintainer's.

1. **Stop reading an order the objective does not contain.** Use the plan
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
