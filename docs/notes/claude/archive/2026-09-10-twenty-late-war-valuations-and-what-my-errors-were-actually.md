# Twenty Late War valuations, and what my errors were actually made of

Scoring my own estimates against the maintainer's, on the fourteen cards
where a comparable number exists: **7 within the 0.75 tolerance, 5
overpriced by an Op or more, 2 underpriced by an Op or more.** The split
is not noise, it is two clean groups:

| Overpriced | Mine | Expert | | Underpriced | Mine | Expert |
| --- | ---: | ---: | --- | --- | ---: | ---: |
| Glasnost (base) | 4.0 | 1.0 | | Aldrich Ames Remix | 3.5 | 6.5 |
| The Iron Lady | 3.0 | 0.5 | | Tear Down This Wall | 4.0 | 5.0 |
| Ortega | 2.5 | 0.5 | | | | |
| LADC (base) | 2.5 | 0.0 | | | | |
| An Evil Empire (base) | 2.5 | 1.5 | | | | |

**Every card I overpriced is conditional, and I priced each at its best
case.** Glasnost's bonus taken as its base, An Evil Empire's Flower Power
case as its base, Ortega's free Coup without its DEFCON cost, Latin
American Debt Crisis assuming a country flips, The Iron Lady's Socialist
Governments cancellation as though it usually matters. **Both cards I
underpriced are unconditional with a large realised swing.** So the error
is not a level bias to correct; it is that I collapse a distribution to
its best case and compress the top of the range.

That has a direct consequence for the bot, and it is not the same
mistake. The bot also has exactly one number per card, so it must collapse
conditionals too -- but it collapses them by *simulating the actual
board*, which is the right way and is strictly better than my guess. The
places it fails are where the condition is not on the board it can see:
Flower Power being active, John Paul II having been played, whether the
US will be forced to play Socialist Governments for Ops, and above all
**win probability**, which it does not represent at all.
