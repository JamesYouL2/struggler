# Aldrich Ames is already right; Five Year Plan's whole risk is unpriced

Two cards the maintainer flagged, and they come out opposite ways.

**Aldrich Ames Remix is free when it is the last card, and the bot knows
it.** `own_hand = [c for c in obs.hand if c != cid]` excludes the card
being played, so pricing it with one card in hand leaves an empty hand,
`best` falls to 0 and the loss is 0. The engine agrees: `_aldrich_ames`
returns early on an empty US hand. Nothing to fix -- worth recording
precisely because the instinct was to go and fix it.

**Five Year Plan is the opposite: its entire risk is explicitly
unpriced.** From `event_value`:

```
# The victim loses a uniformly random card. Five Year Plan's
# "a US event fires" rider is not priced.
```

The bot charges only the expected loss of a random card. But the rider is
the whole card -- the maintainer: "really safe in early war, pretty safe
in mid war, and **death in late war**" -- and that era dependence comes
entirely from how bad the US event is when it fires. Pricing only the card
loss removes exactly the term that varies. The `DefconPlanner` does model
it (`_hazard` averages over the US cards in hand) but only for terminal
risk, so a Five Year Plan that fires a merely *expensive* US event is
still free to the value function.

The nudge beside it is wrong in a second way:

```
if cid == 'Five_Year_Plan' and obs.side is Side.USSR:
    value -= max(0, len(obs.hand)-3)
```

Another bare constant in board units (about 0.01 Ops per card), and keyed
on the wrong variable. The maintainer: Five Year Plan "loves discarding
negative / even scoring cards / 1-Op cards", so what matters is the
*quality* of the hand and the fraction of it that is US-associated, not
how many cards are in it. The expected loss at line 1620 already accounts
for hand size. The bot computes the per-card hold values three lines
earlier and then throws them away for a card count.
