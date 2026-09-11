# The Battleground table, answered as structure rather than numbers

The maintainer declined to give per-region constants and gave the rules
that generate them instead, which is better and is directly
implementable.

**Europe Control is 40 VP.** Today it is `null` in `rules.json` and a bare
`1_000.0` in `greedy._scoring_card_favorability`. Forty is the whole VP
track, which is what an automatic victory is worth, and it puts Europe on
the same scale as everything else instead of a magic number.

**What a marginal Battleground is worth, by what it swings:**

- **Domination hinges on a one-Battleground differential.** 3 against 2,
  or 2 against 1: the tier turns on being strictly ahead, not on a
  threshold. So the Battleground that takes you from level or behind to
  ahead is the whole tier, and the next one is worth almost nothing.
- **Control only matters when you are one away**, because Control needs
  *every* Battleground in the region (`board.region_tier`:
  `side_bg == total_bg`). Central America at 2 of 3, Africa at 4 of 5.
- **Presence matters only if you hold no Battleground.**
- **Ignore country count everywhere except Asia.** That is a deletion:
  `margin_country` (0.05) can go to zero outside Asia, which is one fewer
  tuned weight and serves the audit.

**The sharp prediction, and the test case.** Because Control needs all
Battlegrounds and Domination needs only strictly more, the *second to
last* Battleground in a region buys nothing -- it neither creates
Domination (already held) nor reaches Control. In the six-Battleground
regions that is the fifth, so **the 5th Battleground in Asia and the
Middle East are the worst on the map at turn 4**. That follows from the
engine's own tier rule, and it is exactly the non-linearity an additive
per-country value function cannot represent.

It is also a free check on the bot: rank every Battleground on a turn-4
board and see whether the fifth Asia and Middle East ones come last. They
almost certainly do not, since `battleground` is a flat tier weight times
a regional scoring weight.

**Calibration positions offered:** turn 1 and turn 4 Mid War with all
scoring cards still in the deck. That is the fixture the current
opening-board table cannot be -- see the context-scaling rule -- and it is
what the `margin_*` weights should be fitted against.
