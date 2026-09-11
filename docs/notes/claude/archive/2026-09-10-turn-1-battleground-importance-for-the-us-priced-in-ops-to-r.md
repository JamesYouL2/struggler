# Turn-1 Battleground importance for the US, priced in Ops-to-reach

The maintainer's proposal was Egypt / Pakistan / France at the top, on
wipe and adjacency, with Malaysia-for-Thailand as roughly the fourth place
Ops go. Three of those four are *second-hop* Battlegrounds, so the honest
comparison is total Ops from the setup, which the board file settles.

The US controls exactly two countries at setup: **UK** (5 Influence,
stability 5) and **Australia** (4, stability 4). Everything reachable on
turn 1 follows from those two plus the countries the US already occupies:

| Line | Ops to control | Battlegrounds bought |
| --- | ---: | --- |
| UK → **France** | 3 | 1 |
| Iran (1) → **Pakistan** (2) | 3 | 2 (Iran is itself a Battleground) |
| Australia → Malaysia (2) → **Thailand** (2) | 4 | 1, but Thailand counts twice in Southeast Asia Scoring |
| Israel (3) → **Egypt** (2) | 5 | 2 |

Overlaying the wipe exposure from the section above changes the order:

- **France, 3 Ops.** One Early War card takes 2 back (De Gaulle) and
  nothing in the Mid or Late War touches it. Five adjacencies — UK, West
  Germany, Spain/Portugal, Italy, Algeria — the most of any reachable
  Battleground. And it is the only one of the four that carries Europe's
  forced-defensive-spend multiplier. First, clearly.
- **Iran → Pakistan, 3 Ops for two Battlegrounds.** Cheapest by a
  distance, and the most perishable: Iran is the single most exposed
  country the US holds (Muslim Revolution standing, Iranian Hostage
  Crisis, Iran-Iraq War), and Pakistan carries the Indo-Pakistani discount
  that never lifts.
- **Thailand, 4 Ops.** Zero wipe exposure — Asia has no card in the class
  — and the USSR cannot reach Malaysia or Thailand at all on turn 1; its
  entire turn-1 Asian reach is the two Koreas. The only ways to lose it are
  a Coup (stability 2, so cheap) and Brush War.
- **Egypt, 5 Ops.** The most expensive to reach and the most exposed
  Battleground on the map: Nasser, Muslim Revolution and Sadat all name
  it, and Sadat *hands it to the US for free*.

So: **France, then the Iran-Pakistan line, then Thailand, then Egypt** —
Egypt last, because its wipe exposure is a reason to spend turn-1 Ops
elsewhere, not there. You pay three Ops for Israel before Egypt is even
reachable, to buy the one country the USSR can be evicted from later at
the cost of a 1-Ops US card.

**This is not a disagreement with the maintainer — it is a disagreement
with the bot, and the maintainer already recorded the answer.**
`models/expert_valuations.json` ranks US opening placement **France,
Pakistan, Egypt, Iraq, …**, which matches the derivation above on all
three. The bot's order is **Egypt > Pakistan > Iraq > France**, and it is
one of the five recorded US placement inversions in the expert fixture.

That inversion has a shape: the bot puts both Muslim Revolution targets
(Egypt, Iraq) above France, and France last of the four. **Both
structural terms the maintainer described today would move it the right
way** — Europe's forced defensive spend raises France, and wipe exposure
lowers Egypt and Iraq. Two independently-motivated terms predicting the
same five recorded misses is the strongest evidence so far that they are
real terms and not just good commentary, and it makes the US placement
inversions a cheap way to test them before spending a gate.

Thailand is not in the fixture because it is not a legal turn-1
placement — it is second-hop, behind Malaysia — so its third place here
is an addition to the recorded ranking rather than a check against it.

What this reasoning cannot see, and the maintainer can: contest
probability. It prices Ops-to-reach and card exposure, both of which are
in the data files, and assumes nothing about how hard each is to hold
against a USSR that wants it. Asia's freedom from wipe cards is partly
offset by how cheaply the USSR reaches it once Decolonization and
Afghanistan are out.
