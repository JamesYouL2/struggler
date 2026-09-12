# The reshuffle is where the information is

The maintainer, on the turn-3 scoring-card question: "there's three types
of scoring cards... you know a huge portion of your opponent's hand the
turn after the reshuffle. Actually using it is another thing... but that's
huge."

Measured, and it is.

## Mandate #4 was being misread

`card_state` classified every card not ours, not played and not removed as
`'unseen'`, with the docstring "draw pile or the opponent's hand --
deliberately indistinguishable, **mandate #4**".

That is not what the mandate says. It constrains what `observe()` may
*expose* -- the opponent's card **identities**, and the identity of undrawn
cards -- and in the same breath records that **their hand count is
public**. `Observation` already carries `opponent_hand_size`,
`draw_pile_size`, the full `discard_pile` and `removed_cards`.

So the engine was already handing the bot every input needed to compute a
posterior over the opponent's hand, and the bot was declining to, on the
grounds that the engine would not compute it for them. Inferring a
distribution from public counts is not peeking; it is the thing a strong
player does at the table, and the mandate's design deliberately permits it.

## What is implemented now

Pure functions of one observation, in `public_cards.py`:

    unseen_cards(obs)         every card in their hand or the pile
    unseen_split(obs)         (their hand size, draw pile size)
    p_opponent_holds(obs, c)  the uniform posterior over that pool

Two invariants make the accounting trustworthy, both tested: the pool is
exactly `their hand + draw pile`, and the probabilities sum to their hand
size.

It also removed a phantom. The China Card is face up in front of its owner
and counts toward nobody's hand size, but `card_state` had no case for it,
so it sat in the unseen pool for the whole game, inflating it by one and
mispricing every probability drawn from it.

## The measurement: knowledge peaks *before* the reshuffle

Over captured turn-1 to turn-4 positions:

| turn | unseen pool | their hand | draw pile | P(they hold it) |
| ---: | ---: | ---: | ---: | ---: |
| 1 | 26.9 | 4.9 | 22.0 | 17.6% |
| 2 | 13.6 | 4.9 | 8.7 | **34.6%** |
| 3 | 20.6 | 4.9 | 15.7 | 22.9% |
| 4 | 54.7 | 5.7 | 49.0 | 10.2% |

It doubles from turn 1 to turn 2 as the pile drains, the turn-3 reshuffle
halves it back, and the Mid War influx at turn 4 -- 49 cards -- craters it.
The maintainer's instinct that the reshuffle is the moment is right; the
correction is that the *approach* is rich and the reshuffle destroys it.

## And the turn-3 hand is a mixture, which the uniform model cannot express

The engine deals the pile to empty before reshuffling -- confirmed, every
reshuffle in four games logs `discards back into a draw pile of 0`, and
`_draw_card` only reshuffles when `draw_pile` is empty. `_deal_to_limit`
alternates USSR/US, so the remnant splits about evenly between the hands.

Measured draw pile at the last decision of each turn: **22.0 / 8.8 / 15.0**.
The remnant entering turn 3 is 8.8 cards, not the ~5 the earlier reshuffle
note's arithmetic predicted -- so of the ~14 cards dealt on turn 3, about
**8.8 come from the known remnant and 5.2 from the reshuffle**. The remnant
is the majority of the deal.

**And the remnant half is not a probability at all -- it is certainty.**
The maintainer: "half the opponent's hand is 100% on t3, because you will
have drawn the cards your opponent doesn't."

That is the whole point and it is what a uniform posterior can never
express. The remnant is a *known set* and it is dealt entirely into the two
hands. You see your own share. So the remnant cards you did not receive are
in their hand, full stop -- no estimate involved. The 50% figure above was
my error: it priced the split as if it stayed uncertain after the deal,
when seeing your own cards determines the complement.

| source | cards | P(they hold it) |
| --- | ---: | ---: |
| remnant you did not draw | ~4.4 | **100%** |
| dealt from the reshuffle | ~2.6 | ~12% |
| what the bot computes today | -- | 22.9% for all of it |

So about half their turn-3 hand is *known exactly* and the rest is known
worse than at turn 1, and the bot assigns one middling number to both.
(Modulo one card of slack: at the end of turn 2 they still hold about one
card, so the remnant set is known up to that single ambiguity.)

This is simply what deck tracking is. Trackers in card games record who
played what precisely so the complement becomes deducible, and every input
is public.

The remnant cards are also the loaded ones: a card still in the pile after
two turns is one nobody drew, and for a scoring card that means one that
has not scored. Worse for the current model, a scoring card in the remnant
is dealt on turn 3 and **must** be played that turn, because scoring cards
cannot be held -- so its true "scores this turn" probability is near 1, not
22.9%.

## The same mechanism makes early scoring cards worth more

The maintainer again: a scoring card that does not appear in turns 1-2
scores about **one time fewer across the whole game** than one that does.
The reason is the reshuffle's position in the cycle:

| first appears | path | scorings |
| --- | --- | ---: |
| turn 1-2 | played -> discard -> **reshuffled at T3** -> drawn again T3-T9 -> discard -> reshuffled ~T9 -> played | **3** |
| turn 3, from the remnant | dealt T3 -> played T3 -> discard -> next reshuffle is ~T9 -> played | **2** |

The early card re-enters the deck *at* the turn-3 reshuffle and has the
whole Mid War to come back. The remnant card burns its first play
immediately *after* that reshuffle, so it waits for the second one.

`scoring_schedule` returns `(0, reshuffle)` for every live scoring card
alike, so the bot prices both at two scorings. It is systematically low on
the ones already seen -- which is the opposite of the intuition that an
unplayed scoring card is the dangerous one.

### The forward-looking half of that, which *is* a defect

Most of the asymmetry above is historical -- the early card has already
banked a scoring, and a past scoring changes no future decision. But one
part of it is live, and the code cannot express it.

From turn 2, a scoring card **in our hand** is played this turn, recycles
at the turn-3 reshuffle, comes back in the Mid War, and recycles again at
the second reshuffle: **three** future scorings. One sitting in the remnant
is dealt at turn 3, played then, and comes back only at the second
reshuffle: **two**.

`scoring_schedule` returns at most two entries for anything:

    schedule = (0,) if once else (0, reshuffle)

So it never prices a third cycle, and the measured bucket masses say a
third cycle is real -- cycle 3 carries a full 1.0 of expected scorings at
turn 1.

Size, honestly: with `scoring_discount` at 0.8 the missing term is
`0.8 ** 8` against `1 + 0.8 ** 2`, about a **9% understatement of turn-1
urgency**. It shrinks to nothing under a steeper discount (0.6% at 0.55),
so it interacts directly with the discount experiment now queued, and
should be measured after it rather than before.

The direction is the interesting part: it understates *early* board value,
in a model that already measures early board value as much the highest.
Fixing it widens the turn-1 premium rather than narrowing it.

## What the sharp version needs, and why it is not done here

One fact carried across the reshuffle: *which cards were in the pile when
it emptied*. That set is computable at the end of turn 2 by elimination
(unseen = remnant + the ~1 card they still hold), and everything else
follows -- including the certainty above, which needs only that set and
our own deal.

But it is **memory**, and this bot is a per-decision pure evaluator over a
snapshot whose only persistent state is caches invalidated every decision.
Shape 1 in `bug-shapes.md` -- a cached value keyed on less state than it
reads -- has recurred seven times, more than any other. A deck tracker is
exactly that shape: state that must be keyed on the reshuffle history and
invalidated on nothing else.

So it wants its own gate and its own invariant test, and it should wait
until the uniform version has shown it pays. The uniform version is a
strict improvement on a phantom-inflated pool and is testable today.
