# A country's value is three terms, and a wipe destroys only one of them

The maintainer, on Egypt: "Egypt with Nasser/Sadat only has adjacency and
urgency value."

That is the resolution of the whole per-country thread, and it says the
adjustment table is the wrong *shape* rather than the wrong size. A flat
"Egypt −2 VP" reduces everything about the country in proportion. What
actually happens is that one of three components goes to zero and the
other two are untouched:

| Component | What it is | Wipe exposure does |
| --- | --- | --- |
| **Durable holding** | the Battleground's own tier value, kept over time | **destroyed** -- you cannot keep what a 1-Op card removes |
| **Adjacency** | the reach it gives: Egypt opens Libya, Sudan, Israel | **untouched** |
| **Urgency** | holding it *at the moment the region scores* | **untouched** -- a wipe before scoring costs nothing you had banked |

So Egypt is not a Battleground worth 2 VP. It is a Battleground worth ~0
to *invest* in and its ordinary value to *hold at a scoring*, which are
different decisions the bot currently cannot separate.

**And the bot already has all three as separate terms** -- `country_value`
for the holding, `access` for adjacency, and the region/urgency terms for
scoring. So the implementation is to discount the holding component by
exposure, not to subtract VP from the total. That is strictly easier than
the flat table and strictly more correct.

**Why Egypt specifically.** Mapping every cheap eviction onto the
Battlegrounds it reaches:

| Country | Against the US | Against the USSR |
| --- | --- | --- |
| **Egypt** | **Nasser (1)**, Muslim Revolution (4) | **Sadat (1)** |
| Iran | Iran-Iraq (2), Iranian Hostage (3), Muslim Rev (4) | Iran-Iraq (2) |
| Iraq | Iran-Iraq (2), Muslim Revolution (4) | Iran-Iraq (2) |
| India, Pakistan | Indo-Pakistani (2) | Indo-Pakistani (2) |
| West Germany | Blockade (1) | -- |
| UK | -- | The Iron Lady (3) |

**Egypt is the only Battleground on the map with a one-Op eviction
available against both sides.** Five are two-sided, and the other four are
two-Op. That is the whole explanation for why it alone loses its holding
value rather than merely being discounted -- and it is arithmetic from the
card list, not a judgement anyone had to supply.

It also explains the spread question from the section above. The
per-country spread (4.0 VP) being larger than the per-region spread (2.67)
is not an inconsistency: they measure different things, and the per-country
figure is large precisely because a handful of countries lose an entire
component of their value rather than a fraction of all of them.
