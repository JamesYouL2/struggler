# Per-country adjustments, and the class of card that makes overprotection useless

The maintainer's per-country notes, calibrated at **start of turn 4** like
the region table above. These are adjustments to the per-Battleground
value, not replacements for it.

| Country | Adjustment | Because |
| --- | --- | --- |
| Thailand | **up**, to ~6 VP + the Asia Battleground | Southeast Asia Scoring counts it twice. The biggest non-Europe country on the map at start of turn 4 |
| India, Pakistan | −1 VP each | Indo-Pakistani War in the deck |
| South Korea | −1 VP | Korean War in the deck |
| Egypt | −2 VP | Sadat Expels Soviets in the deck. Muslim Revolution also bites |
| Israel | −1 VP | Arab-Israeli War in the deck |
| Iran | −1 VP each | Iranian Hostage Crisis, Iran-Iraq War |
| every South American country | **+1 VP** | Realignment is far swingier there |
| 1-stability African Battlegrounds | discount to **1/4 – 1/3** | Less stable than the 2-stability ones and jammable by a 4-Ops play. Still better value per Op, just not by the ratio the stability numbers imply |

**Every one of these is conditional on the card still being live**, which
makes the whole table implementable: `public_cards.card_state` already
distinguishes `removed` / `discard` / `future` / `unseen` without breaking
mandate #4. The discount is simply not applied once the card is `removed`.

And the removal flags decide whether a discount ever lifts:

| Card | Removed after firing | So the discount |
| --- | --- | --- |
| Korean War | yes | lifts permanently once it fires |
| Sadat Expels Soviets | yes | lifts, for its half of Egypt |
| Iranian Hostage Crisis, Iran-Iraq War | yes | lift |
| **Arab-Israeli War** | **no** | never lifts (except via Camp David, which blocks it) |
| **Indo-Pakistani War** | **no** | never lifts |
| **Muslim Revolution** | **no** | never lifts (except via AWACS, which cancels it) |

So Israel, India, Pakistan and the Middle East carry a *standing* discount,
while South Korea and Iran carry one that expires. The bot currently
applies neither.
