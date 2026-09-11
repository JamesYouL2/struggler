# Improving DEFCON is worth about an Op, and the bot prices it at zero

The maintainer, unprompted: *acting immediately after a DEFCON
improvement in the Mid to Late War is worth an Op, because of the free
Battleground Coup it unlocks.* Their own judgement is that it does not
need a parameter -- it is a constant, not a term.

They are describing rule 6.3.4 from the other side. DEFCON 4 forbids Coups
in Europe, 3 also Asia, 2 also the Middle East, so improving DEFCON
**re-opens a region to Coups**, and the side that improved it acts first.
The value is the tempo of a Coup the opponent could not have made a moment
earlier.

The bot cannot see any of this. The event sandbox values an event by the
influence it moves and the VP it awards; DEFCON is neither, so an event
whose effect is "improve DEFCON one level" prices at exactly 0 -- the
flag-only blindness again, in a case nobody had listed as flag-only.
`defcon` does reach `country_value`, but only to gate Coup prohibitions
and the `wipe` term, which ships at 0.

Cards this under-prices, all of them by roughly the same Op: Glasnost,
Salt Negotiations (two levels), Summit's raise branch, Warsaw Pact's
partner NATO, and every Coup the bot declines to make in a region it has
just unlocked. It is a small constant and a wide one.

Worth adding to the flag-only list in `docs/EXPERT_ASKS.md` item 4 rather
than treating as its own item: same cause, same fix.

**Still unresolved, and the arithmetic does not close.** If the DEFCON
improvement alone is worth ~1 Op, and Glasnost's whole base is 1.0, then
its 2 VP to the USSR is worth about nothing -- against a stated Late War
scale of 2 Ops per VP, which would put those 2 VP at ~4 Ops on their own.
Three readings and I cannot pick between them from here: granted VP
converts differently from bought VP; or the DEFCON improvement is a real
*cost* to the USSR that cancels the VP; or the 2-Ops-per-VP rule is a
buying price rather than a holding value. `vp_late` is 2.0 and every Late
War VP event is priced through it, so this is worth one sentence from the
maintainer.
