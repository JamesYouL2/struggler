# The whole hand planner: what plans, and what only prices

2026-09-20. The maintainer's framing: the hand planner should do the
headline, the hold, the space slot, maximising our events, minimising
theirs, and scoring timing. This note says, component by component, what
the bot does today, which of those six are *planned* and which are
*priced*, and what a planner over all six would have to be.

The short version: **exactly one thing in this bot plans over a whole
hand, and it optimises survival, not value.** Everything on the value side
is a per-card price computed at the moment of one decision, with pairwise
guards where two prices would otherwise fight. That is not a criticism of
the prices -- they are good, and most of this year's measured gains are in
them -- but it is the reason the six items above do not add up to a plan.

## What the turn actually asks

A turn hands you 8 or 9 cards and gives you 6 or 7 action rounds plus one
headline. Every card must go somewhere:

| slot | how many | notes |
| --- | --- | --- |
| headline | exactly 1 | resolves before any action round; the opponent's may resolve first |
| action round: event | 0..R | ours fires for us; theirs fires for them even when we play it for Ops |
| action round: Ops | 0..R | placement, coup, realign -- an opponent card fires their event anyway |
| action round: space | 0..1 (2 with box 2) | consumes a whole action round and the card |
| UN Intervention pairing | 0..1 | needs an opponent card; its Ops then come clean |
| held past the turn | hand size - R | a scoring card can never be held |
| forced scoring | as the engine demands | holding scoring cards >= rounds left forces the play |

So the turn is an **assignment problem with real constraints**: one
headline, R rounds, at most one space attempt, UN pairs with exactly one
opponent card, and holds are whatever is left over. The six items the
maintainer lists are not six features -- they are six *slots in one
assignment*, and three of them (space, UN, hold) are all ways of disposing
of the same scarce thing: an opponent card we would rather not fire.

## What exists today, slot by slot

| item | what the bot does | planned or priced? |
| --- | --- | --- |
| **Headline** | `_score_card_play` returns `event_value - 0.5 x ops_value` (a half-round charge for the round it costs); `DefconPlanner.headline_pick_risk` prices the DEFCON risk, including that theirs may resolve first and drop DEFCON -- estimated from the Ops distribution of the unseen pool, ties to the US | **priced**, per card |
| **Hold** | `value_as_held` = `hold_value` for a normal card, `LOSS` for a scoring card (holding one loses the game). No option value for the flexibility itself | **priced**, per card |
| **Space** | `space_card` picks the opponent card whose Ops-plus-event is worst among those the Space Race accepts; only that card is valued as a space play (`value = max(value, space_value(...))`). The box premiums are weights (`space_ability_2/4/6/8`), and `attempts_allowed` / `space_ok` handle the second attempt | **priced**, with a one-card pre-selection |
| **Our events** | `event_value` resolves the event on a public sandbox rather than estimating it; `card_play_value` takes the best legal mode | **priced**, exactly |
| **Their events** | three separate mechanisms: UN Intervention (`un_card` = their worst event in our hand), the space slot (`space_card`), and simply eating the event when we play their card for Ops (priced in `card_play_value`). `_non_firing_value` makes sure a card is only as bad as its best *non-firing* mode | **priced**, three rules |
| **Scoring timing** | `scoring_card_value` resolves the scoring card in the sandbox (exact, since tiers are discontinuous and a near miss pays nothing), plus `+2 x action_round` to prefer later in the turn; the urgency masses (`scoring_hand`, `scoring_rival`, `scoring_final`) shape every country's value by *when* its region will next score | **priced**, plus one nudge |

## The one thing that plans: the survival DP

`DefconPlanner` searches the whole hand: which card in which mode in which
round, over the rounds remaining, against the opponent's chance of dropping
DEFCON and of attacking our hand. It returns P(we are forced into a play
that loses the game). It is a real plan -- it knows that playing the safe
card now leaves the lethal one for a round when DEFCON is lower.

It optimises **survival only**. Its objective is a probability of losing,
not VP. So the bot has a whole-hand planner for the thing that almost never
happens and per-card prices for the thing that happens every round:

- corners are **rare and fatal**: 7 of 256 seat-games ever reach "every
  line loses", and all 7 lost to DEFCON 1
  ([instrument](2026-09-19-last-exit-instrument.md));
- everything else -- which card headlines, which is held, which is spaced,
  when the scoring card goes -- is decided one card at a time.

## Where the seams show

The tell that this is an assignment problem being solved by per-card prices
is the set of pairwise guards already in the code:

- `space_card` **skips `un_card`** -- an explicit one-line guard so the same
  opponent card is not both spaced and UN-paired. Two rules, one hack,
  and nothing generalises it to a third.
- Only `space_card` is valued as a space play at all, so the space slot is
  pre-assigned by a greedy rule before any comparison happens.
- `+2 x action_round` on a scoring card is a timing preference expressed as
  a constant, not a plan about which round is best.
- Five Year Plan gets `value -= max(0, len(hand) - 3)` to prefer the late
  hand -- a hand-shape heuristic in a per-card price.

None of these is wrong. Together they are a planner written as a pile of
tie-breaks, and they cannot express the trades that matter: *space the
Soviet card I cannot answer, or hold it and eat a smaller event next turn?*
*Headline the scoring card to deny their headline, or keep it for round 6
when Europe is mine?*

## What changed in the last two days

Three things, all of which make a value-side planner cheaper than it was
when the audit descoped one:

1. **The planner's leaf cost.** `opponent_event` was 1.68M calls of enum
   machinery a ranking; the worst position fell 3.40 s -> 2.22 s
   ([note](2026-09-19-planner-hot-spot.md)).
2. **The sandbox budget.** 60% of all planner nodes were spent inside
   simulated events at the full 20,000-state budget; the worst decision
   fell 530k nodes -> 131k with identical games
   ([note](2026-09-20-the-stall-is-the-drain.md)).
3. **The potential is affordable.** The linear weights price a placement's
   expected-payout change at 2.45 ms against the DP's 75.6 ms, exact for a
   one-member move ([note](2026-09-19-bisect-v0.2.1.md) and
   `tests/test_potential_delta.py`). Wired into every delta it costs 0.40 s
   a ranking, which is still too much for a search -- but it is 30x closer
   than the number that descoped it.

And one thing that has NOT changed: **the hand canonicalisation is still
unbuilt.** Collapsing interchangeable safe cards takes the survival search
from 25,122 distinct states to 7,317 (0.29x). Any whole-hand value search
would multiply that saving, because it explores the same shape.

## What a real planner would be

**One objective over one turn**, maximising

    sum over cards of value(card, slot) - P(loss) x game_value

subject to the constraints in the table above: one headline, R rounds, at
most one space attempt, UN pairs with one opponent card, holds are the
remainder, a scoring card is never held.

Two tractable shapes, and they are not exclusive:

**(a) Separable prices, exact constraints.** Keep today's per-card prices
-- they are the thing this project has spent the year calibrating -- and
solve the *assignment* exactly instead of by tie-break. Every (card, slot)
pair gets a price; a min-cost matching picks the allocation. This is the
audit's step 4 and the v3 plan's step 6. It buys: no double allocation,
space and UN and hold decided together, and the headline chosen knowing
what the rest of the hand needs. It does not buy: sequencing effects,
because the prices are computed against today's board.

**(b) Forks for the orderings that matter.** Sequencing *is* the other half:
playing the Ops card first changes the board the event then fires on. A few
candidate orderings simulated two or three plies deep, scored by the value
function, is the v3 plan's step 7. It is expensive, and it is where the
canonicalisation and the sandbox budget pay for themselves.

**Start with (a).** It is bounded work with a clear oracle -- the allocation
it produces can be compared against today's choices on the corpus, and the
cases where they differ are exactly the trades the tie-breaks cannot
express. It also makes (b) cheaper by shrinking what has to be searched.

## What to measure, and what not to expect

The instrument says the survival side is nearly solved, so **do not justify
this by corners.** Justify it by the tail: a third of USSR seat-games touch
0.25 whole-hand risk without ever closing out, and that is where a better
allocation of the same cards should show up. Run
`scripts/measure_last_exit.py` before and after and watch the tail mass at
0.25, not the corner count -- 7 in 256 is too small a sample to move
visibly.

And the honest prior: the last three measured wins were a turn curve
(+0.039), a deleted term (+0.031) and a set of safety fixes (+0.043). None
of them was a search. A planner has to beat that bar, and the anchored arm
goes **before** the merge.

## Open questions for the maintainer

1. **Is the hold worth option value?** `value_as_held` prices a held card at
   what it will be worth next turn and nothing for the flexibility. A
   planner that allocates holds needs to know whether "keep a 4-Op card for
   a turn I cannot predict" is worth a premium, and no measurement here
   answers it.
2. **How aggressive should the space slot be?** Today it is "the worst
   opponent card, if the Space Race accepts it". The box premiums are
   guesses (`space_ability_*`, all `guess/underdetermined` in the ledger).
   An arm over those four weights would tell us whether the slot is being
   spent on the right card before a planner starts allocating it.
3. **Scoring timing: is `+2 x action_round` the whole policy?** It says
   "later is better" with no model of what later buys. The masses already
   know when each region next scores; the timing rule does not use them.

## The maintainer's rulings (2026-09-20)

**1. The space slot can be two, and the second one opens mid-turn.**
`attempts_allowed` already states the rule: a second attempt when our marker
is at box 2 or beyond **and theirs is not** (6.4.4), and the planner grants
it the moment the search reaches box 2, exactly as the engine would.

This is not a static constraint on the assignment. The second slot is
*created* by the first attempt succeeding, and an attempt is a die roll, so
the number of space slots in a turn is **stochastic and endogenous**: it
depends on an action the plan itself chose and on how the roll went. A pure
matching (shape (a) above) cannot express that -- it assumes the slots are
known before the allocation. Two ways out, and they want measuring rather
than arguing:

- solve the matching twice, once per slot count, and weight by P(the first
  attempt advances the box) -- cheap, and exact if nothing else in the turn
  depends on the roll;
- or treat the first space attempt as a chance node and let shape (b)'s
  forks carry it, which is what the survival DP already does.

The exclusivity clause matters strategically too: the slot is worth more
when they are below box 2, because taking it denies them the same doubling.
Nothing in the value function sees that today.

**2. Build it alongside `DefconPlanner`, then try to delete `DefconPlanner`.**
Agreed as the shape, and the note's job is to say what deletion would
require, because the two planners are not the same search:

| | survival DP (today) | the assignment planner |
| --- | --- | --- |
| objective | P(forced into a losing play) | VP value minus P(loss) x game |
| runs when | **only when the hand holds a hazard** | every turn |
| cost | median **0 nodes** a decision, p95 2,188 | every hand must be allocated |

The survival DP is cheap because of one line -- `if not any(hazardous(c,
hand) for c in hand): return 0.` -- and that early exit is why the median
decision searches nothing at all. **A value objective has no such exit.**
Every hand needs an allocation, so unifying the two moves the cost from the
5% of hands that are dangerous to 100% of hands. That is the number to
measure before committing to deletion, not after.

What the unified planner must also carry, or deletion loses real behaviour:
the opponent's DEFCON drop and hand-attack probabilities, the trap states
(Quagmire, Bear Trap), the China card, and the escapes that are not plays --
Space, the UN pairing, and the scoring-discard cases (Five Year Plan, Ask
Not). Those are the survival DP's whole content, and each is a constraint or
a slot in the assignment anyway. So subsumption is the right end state; the
order is: build it, prove it reproduces the DP's risks on the corpus, then
delete.

**3. A hold does deserve option value.** `value_as_held` currently prices a
held card at what it will be worth next turn and nothing for the
flexibility. It gets a term. No measurement here says what it should be, so
it arrives as a weight at 0 with an arm over a small grid -- the same shape
as `vp_swing`, which is how that one was finally settled.

**4. The space slot's policy stands** -- the worst opponent card the Space
Race accepts. What is still unmeasured is the four box premiums
(`space_ability_2/4/6/8`, every one `guess/underdetermined` in the ledger),
and ruling 1 gives a reason to expect `space_ability_2` in particular to be
mispriced: it is worth a second slot *and* the denial of theirs.

**5. Scoring timing comes from the turn lookahead, not a constant.**
`+2 x action_round` goes. The planner already knows how many rounds remain
and what each card would do in each of them, so "when does this scoring card
go" becomes an ordinary slot assignment -- with the constraint the engine
already enforces (a scoring card cannot be held past the turn) and the
masses that already know when each region next scores. This is the clearest
case of a per-card nudge that a plan makes unnecessary.

### The order this implies

1. Hold option value as a weight, with a grid arm. Independent of the
   planner, and it is an input the planner needs priced.
2. The hand canonicalisation (25,122 -> 7,317 states). It pays for itself in
   the survival DP now and again in the assignment search later.
3. The assignment planner behind a weight, alongside the DP, scoring timing
   included from the start (ruling 5) and the space slot count handled by
   the two-solve approximation (ruling 1).
4. Only then: does it reproduce the DP's risks? If yes, delete the DP and
   measure the cost change on the 95% of hands that never searched before.
