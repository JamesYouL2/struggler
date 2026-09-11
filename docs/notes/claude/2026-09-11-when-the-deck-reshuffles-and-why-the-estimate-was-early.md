# When the deck reshuffles, and why the estimate was early

The maintainer asked whether there was an easy way to look at reshuffle
timing. There was, and it found a calibration bias worth a behaviour
change.

## The arithmetic: turn 3 is forced

No assumptions, no removal rate, nothing to tune:

```
35 Early War cards enter at turn 1
T1: deal 16 (both hands to 8)   -> pile 19, play 14
T2: deal 14                     -> pile  5, play 14, discard 28
T3: deal needs 14, pile has 5   -> RESHUFFLE, unavoidable
```

Observed in 15 of 15 games that reached turn 3; the sixteenth ended on
turn 2.

## The second one turns on about one card

Running the same accounting forward, with a rate of cards leaving the
game entirely:

| cards leaving the cycle per turn | second reshuffle |
| ---: | --- |
| 0 | T9 |
| 1, 2, 3 | T7 |

At zero removals the pile after the turn-7 deal is **1**. One card of
slack across the whole mid war, which is why turn 7 versus turn 9 is a
knife edge rather than a tendency, and why turn 8 -- the Late War influx
of 21 arriving just as the pile empties -- is possible but narrow.

**Never three.** The model gives two under every removal rate, and 16
games gave 23 reshuffles, which only decomposes as seven games with two
and nine with one. The maintainer said they had never seen three and did
not think it possible; the arithmetic agrees.

## Transfers are not removals, and that was my error

The model above says "any removals -> T7", but the games mostly gave T9.
The reason is that the two cards which actually drain the draw pile do
not remove anything from the game.

| effect | draw pile | recycled pool | when |
| --- | --- | --- | --- |
| **Ask Not** (US, 3 Ops, Mid War): discard any number, draw that many | −N | unchanged | mid-turn |
| **Our Man in Tehran** (US, 2 Ops, Mid War): top 5 off the pile, kept ones back, the rest to *discard* | −N | unchanged | mid-turn |
| remove-on-event | — | −1 | at play |

These two are the only events that pull from the draw pile outside the
deal, they are both Mid War and both US. Our Man in Tehran's code is
explicit that discarded cards go to `discard_pile` and not
`removed_cards` -- "permanent exile and nothing reshuffles it" -- so the
pool survives and only the draw pile shrinks.

So the timing is: **T3 forced; T9 by default; T7 or mid-turn when one of
those two drains the pile.** The maintainer's "generally turn 3 and turn
7" is what a game with those cards played looks like; the bot's 15-to-1
split toward T9 says the bot rarely plays them, which is a separate
question about whether it values them correctly.

## The bias, and the fix

`turns_to_reshuffle` divided today's pile by the draw rate:

```python
per_turn = max(1, 2 * hand_limit(obs.turn) - 2)
return max(1, -(-obs.draw_pile_size // per_turn))
```

That assumes a fixed pool. The deck is not one: **46 Mid War cards join
at turn 4 and 21 Late War at turn 8**, roughly doubling it and then
adding half again. Measured against where reshuffles actually landed, the
estimate was right at turns 1-2 and 8 and early through the entire mid
war.

It matters because `scoring_schedule` returns `(0, reshuffle)` discounted
by `TURN_DISCOUNT ** t`. Predicting turn 7.5 when the reshuffle lands at
turn 9 under-discounts the second scoring by about 1.4x, so the bot
over-valued every scoring card in hand through the part of the game where
most scoring happens.

Walked forward turn by turn with the influx added:

| asked at turn | before | after | actual |
| ---: | ---: | ---: | ---: |
| 1 | 3 ✓ | 3 ✓ | 3 |
| 3 | 4.5 ✗ | 7.3 | 9 |
| 5 | 7.5 ✗ | **8.7 ✓** | 9 |
| 6 | 7.8 ✗ | **9.0 ✓** | 9 |
| 7 | 8.2 | **9.0 ✓** | 9 |
| 8 | 9.2 ✓ | **9.0 ✓** | 9 |
| 9 | 12.9 | 11, past the horizon | none |

The residual bias at turns 3-4 is the transfer effect above, and is
deliberately not modelled: Ask Not and Our Man in Tehran are two cards in
one hidden hand, and pricing them would be guessing at it (mandate #4).

The estimator now also returns a value past the horizon when the pile
outlasts the game. `scoring_schedule` already filtered that case -- the
maintainer's "if reshuffle is past T10 it means there is no reshuffle and
everything should hit 0" was already true -- but the old estimator could
never produce it, so the branch was dead.

**This is a behaviour change and needs a gate.** It makes scoring cards
less attractive through the mid war, which could go either way on
strength.
