# What to price, in order of what it unblocks

The ten things the maintainer can supply that the bot cannot derive, work
out from games, or read off the board. Ranked by leverage, not by size.

The case for doing this at all, in one measurement: the Military
Operations change was the first gate in this project's history whose
lower bound cleared 0.500, a ten-point gain. The expert fixture called it
**neutral** -- 23 misses against 24 -- because the fixture is thirty rows
on the *opening board* and the Military Operations requirement is worth
least on turn 1 and most in the turns that decide games. A fixture that
cannot see the change it is judging will call anything neutral. Fixing
that is items 1 and 2.

Current coverage, playable cards only:

| Period | Cards | Priced | Unpriced |
| --- | ---: | ---: | ---: |
| Early War | 35 | 27 | 8 |
| Mid War | 45 | 33 | 12 |
| **Late War** | **22** | **4** | **18** |

Games end on turn 8.4 on average and half reach turn 10, so the period
with no coverage at all is one the bot plays in most games.

---

## 1. The Late War table: 22 cards, 4 priced

**In progress.** `models/expert_valuations_latewar.json` holds what has
arrived: Aldrich Ames Remix 6.5, The Reformer 3.5 (5 with its bonus),
Pershing II Deployed 2.5, Glasnost 1.0 (5 with its bonus). Seat-own Ops,
matching the Mid War file.

Two things already learned from four cards. **My estimates are biased low
on the strongest cards** -- Aldrich Ames came in at 6.5 against my 3.5 --
which is the shape you would expect from a scale anchored on an opening
board where nothing is that decisive. And **two of the four are
conditional**, base versus bonus, which the fixture format and the bot
both lack any way to express.

The rest of the hole. Format is **seat-own Ops** -- positive is good for
the side holding the card, so a strong USSR event is a positive number
under USSR, matching the Mid War file rather than the US-signed opening
board one. Rough is fine; tolerance is 0.75.

| Ops | Side | Card |
| ---: | --- | --- |
| 4 | US | Soviets Shoot Down KAL-007 |
| 4 | NEUTRAL | Wargames |
| 3 | US | An Evil Empire |
| 3 | US | Chernobyl |
| 3 | USSR | Iranian Hostage Crisis |
| 3 | US | North Sea Oil |
| 3 | US | Tear Down This Wall |
| 3 | US | The Iron Lady |
| 2 | USSR | Iran-Contra Scandal |
| 2 | NEUTRAL | Iran-Iraq War |
| 2 | USSR | Latin American Debt Crisis |
| 2 | USSR | Marine Barracks Bombing |
| 2 | USSR | Ortega Elected in Nicaragua |
| 2 | US | Reagan Bombs Libya |
| 2 | US | Solidarity |
| 2 | US | Star Wars |
| 2 | NEUTRAL | Terrorism |
| 2 | USSR | Yuri and Samantha |

## 2. Expected VP of a Battleground, by region -- ANSWERED as structure

The core term (`battleground` times the region's scoring weight) is fitted
to nothing. The only figures available are third-hand, from the Sankt
compilation, credited to someone else: Europe's 3rd Battleground worth
6-10 VP and its **4th only 2**, Asia ~5, Middle East a little under, Latin
America ~5, Africa ~4.

**Answered**, and as rules rather than constants: Europe Control is 40 VP;
Domination turns on a one-Battleground differential; Control matters only
one away because it needs every Battleground; Presence only if you hold
none; ignore country count outside Asia. See `docs/CLAUDE_NOTES.md`, "The
Battleground table, answered as structure". Outstanding: the turn-1 and
turn-4 Mid War calibration positions the maintainer offered.

## 3. When is a region ready to score?

The bot has an urgency multiplier and a small per-round bonus, and nothing
else. It will play Asia Scoring at minus six with no Asia presence. What
is the actual rule -- presence plus how many Battlegrounds, or dominance
minus how much risk, or "never before turn N unless X"? Any form that can
become a condition.

## 4. Flag-only events, an entire class worth 0

The sandbox values an event by the influence and VP it moves, so an event
whose whole effect is setting a flag prices at exactly zero. Currently
worth nothing to the bot: **NATO, NORAD, Formosan Resolution, Nuclear
Subs, Quagmire, Bear Trap, Warsaw Pact Formed**, and the persistent halves
of others. You have already priced NATO at ~1 Op and NORAD at 1.5. The
remaining five, plus a rule of thumb for "a flag that denies the opponent
a whole line of play", would close the class.

**Add DEFCON improvements to this item.** The maintainer's rule: acting
immediately after improving DEFCON in the Mid to Late War is worth about
an Op, because it re-opens a region to Coups and you move first. The
sandbox measures influence and VP, so it prices that at 0 today. Same
cause as the flags, same fix, and it touches Glasnost, Salt Negotiations,
Summit's raise branch and every Coup declined in a region just unlocked.
They judge it a constant rather than a parameter.

## 5. Event branch choices the bot decides by tuple order

These offer a choice the bot scores at 0 on every branch, so it takes
whichever the engine lists first. Free Coups are fixed; these are not:

- **Chernobyl** -- which region to block. Always picks Europe.
- **Warsaw Pact Formed** -- remove US influence, or add USSR. Always removes.
- **South African Unrest** -- South Africa only, or with adjacent. Always the smaller.
- **Latin American Debt Crisis** -- which countries to halve, and whether to pay.

A one-line rule each is enough.

## 6. Safe windows: which cards must be played before DEFCON falls

The seed 4015 lesson. Lone Gunman is nearly free at DEFCON 3 and loses the
game at DEFCON 2, and the bot has no notion that a card's safe window
closes. Which cards have one, and roughly what it is worth to dump such a
card early rather than hold it? This is the objective the hand planner
needs, and possibly a cheaper standalone term.

## 7. The China Card -- ANSWERED

**Holding it is worth 5 Ops; playing it costs 8**, because the transfer
is the expensive half: you lose the option and hand the same option to
the opponent. And the charge decays with the game -- "whoever has it on
t10 is going to play it 100% of the time, even with a 2 VP swing" -- so
it is a rounds-remaining quantity like `military_credit`, not a
constant.

Outstanding is the implementation, not the number. The bot charges 5.0
*raw board units* at the point of play, which is 0.06 Ops on a measured
board, and the maintainer's conclusion is that when to play China is a
whole-hand planner decision rather than a constant. See
`docs/CLAUDE_NOTES.md`, "The China charge is in the wrong units".

## 8. Military Operations: when to eat the penalty

Now priced at one VP per Op of deficit, discounted over the rounds left,
which gated as the session's one clear gain. What is missing is judgement:
when is it correct to just take the penalty, and should the requirement
change which card you play in the last round of a turn?

## 9. Space Race box abilities

The bot prices a box by its VP times the roll odds, which matches your
"about 2 VP a box, discounted by failure". It prices the box's **ability**
at zero -- and Sankt calls discard-a-held-card the most important ability
for that style. What is each ability worth, especially the discard and the
"play 8 cards" one?

## 10. The 20 remaining Early and Mid War cards

Lower leverage than the Late War table but the same work. Mid War:
AWACS Sale to Saudis, Alliance for Progress, Che, Cuban Missile Crisis,
How I Learned to Stop Worrying, John Paul II Elected Pope, Latin American
Death Squads, Nixon Plays the China Card, One Small Step, Our Man in
Tehran, Panama Canal Returned, Summit. Early War: Truman Doctrine,
COMECON, East European Unrest, Special Relationship, Duck and Cover,
Defectors, Formosan Resolution, UN Intervention.

---

## The other thing, which is not a price

An **annotated position suite**. The mirror gate structurally cannot see a
mistake both sides make -- which is how the bot declined every free Coup
for its entire existence -- and needs about 96 seeds to notice a six-point
swing. Annotated positions are the only instrument that sees either.

This should cost you almost nothing to produce: the positions come from
real games with the legal moves and the bot's own choice already laid out,
and the job is to mark the better move and one line of why. Seed 4015 turn
7 is the first entry. Ask for the pack.
