# The Middle East cannot be overprotected, and Asia cannot be wiped

Asked which non-war cards can erase a whole country's Influence, here is
the complete list the engine implements (`whole=True`, or a named
`remove_all_influence`):

| Card | Period | Wipes | Where |
| --- | --- | --- | --- |
| Truman Doctrine | Early | USSR | one *uncontrolled* Europe country |
| Warsaw Pact Formed | Early | US | 4 Eastern Europe countries |
| Blockade | Early | US | West Germany, unless the US discards 3+ Ops |
| Nasser | Early | US | Egypt — half, rounded up |
| De Gaulle Leads France | Early | US | France — 2, not a wipe |
| **Muslim Revolution** | **Mid** | **US** | **2 of Sudan, Iran, Iraq, Egypt, Libya, Saudi Arabia, Syria, Jordan** |
| Sadat Expels Soviets | Mid | USSR | Egypt |
| Marine Barracks Bombing | Late | US | Lebanon, plus 2 elsewhere in the Middle East |
| Iranian Hostage Crisis | Late | US | Iran |
| The Iron Lady | Late | USSR | UK |
| Ortega Elected in Nicaragua | Late | US | Nicaragua |

Two things fall out, and both are larger than the Egypt note that prompted
the question.

**Muslim Revolution reaches five of the six Middle East Battlegrounds.**
Libya, Egypt, Iraq, Iran and Saudi Arabia are all on its list; only
**Israel** is not. It is a 4-Ops USSR card that is *not* removed after
firing, so it returns at every reshuffle. For the US the conclusion is
categorical rather than per-country: **there is no such thing as
overprotecting a Middle East Battleground other than Israel**, because the
Influence can be removed entire without the USSR spending an Op on the
board.

**Correction, and the same mistake for the third time.** I concluded from
this that AWACS Sale to Saudis, which cancels Muslim Revolution, must be
worth well more than a 3-Ops US card. The maintainer: Muslim Revolution's
event is very strong on the board but "the marginal value of it over Ops
is only 1" — it is a 4-Ops card, so playing it as an event beats simply
spending the four Ops by about one. Cancelling it is therefore worth
around half an Op, and AWACS matters mainly as a way to defuse Muslim
Revolution as a hand trap in the Late War. **A card is worth its event
minus its own printed Ops, and a denial card is worth the opponent's
margin, not the event's board effect.** Third recurrence of shape 6, "a
number on the wrong scale", and the same error as Warsaw Pact Formed.

Israel is not the safe harbour the Muslim Revolution list makes it look,
either. **Arab-Israeli War targets Israel specifically**, is not removed
after firing, and a won war does not wipe: `core.py:2157` **seizes**,
moving the defender's Influence to the attacker, so it is a 2-for-1 swing
rather than a removal. Camp David is the only thing that blocks it. The
maintainer's own ranking puts Israel seventh of eleven and Egypt third —
Israel's worth to the US is access to Lebanon, Egypt and Libya, not the
Battleground itself.

**Asia has no wipe card at all.** Nothing in the list above touches Asia,
in any period. Every Asian Battleground can be lost only to a Coup, a
Realignment, or the two war cards. That is the exact inverse of the Middle
East, and it is a reason to prefer Asian Battlegrounds at equal VP that
neither the region table nor the country table above expresses.

The asymmetry within the list is worth noting too: of the eleven cards,
**eight wipe US Influence and three wipe USSR Influence**. Overprotection
is a US problem far more than a USSR one.

Adjacent to the class, and the reason the question was framed as
"overprotection": **Shuttle Diplomacy** (Mid, US, not removed after
firing) drops one USSR-controlled Battleground from the next Middle East
or Asia scoring. It removes nothing from the board, but it makes the
marginal Battleground worthless at exactly the moment it would have been
counted.
