# Expert strategy sources: Sankt and Ziemowit

Strategy from the strongest known Twilight Struggle players, recorded so
the value function can be calibrated against something other than this
bot's own games. The mirror gate cannot see a mistake both sides make, and
`models/expert_valuations.json` covers ~30 rows on the opening board only,
so an outside reference is load-bearing.

**Who these people are.** Ziemowit Pazderski is ranked #1 in the
International Twilight Struggle Rankings and is the most decorated player
of the game. Kris "Sankt" Wei is the strongest of the Chinese school, whose
style is named after him.

**The order to weigh sources in**, as stated by this repo's maintainer, who
is a top 20 to top 50 player worldwide and writes as *Lastchancexi* on
Reddit:

1. Sankt and Ziemowit, who are stronger than the maintainer.
2. The maintainer, whose valuations are what
   `models/expert_valuations.json` records and what the value function is
   fitted to.
3. `twilightstrategy.com`, the Western canon. The maintainer is
   "definitely stronger" than its author, so it is a reference and not an
   authority.
4. The author of this repo's LLM bot prompt, weakest of the four.

The practical rule: when the bot disagrees with the maintainer, the bot is
wrong. When the maintainer disagrees with `twilightstrategy.com`, prefer
the maintainer. When Sankt or Ziemowit disagree with the maintainer, raise
it rather than silently picking a side -- the three disagreements at the
end of this file are exactly that case.

**Provenance, which matters for how much weight to give this.** The only
source that could be retrieved is a third-party compilation: a 2017 blog
post collecting Sankt's forum posts and adding replay analysis, which also
quotes one ranking of Ziemowit's. It is **not** written by either player.
BoardGameGeek refuses automated fetches (HTTP 403) and `twilight-league.com`
no longer resolves in DNS, so the primary threads and the "Z vs Sankt"
series could not be read. Treat everything below as reported speech at one
remove, and quote it to the user before fitting a weight to it.

Sources, and what is behind each:

| Source | State | Holds |
| --- | --- | --- |
| [Collected Musings of Sankt & co.](https://maninmotiongoingnowhere.wordpress.com/2017/02/14/twilight-struggle-the-collected-musings-of-sankt/) | retrieved | everything below |
| [BGG: Sankt style?](https://boardgamegeek.com/thread/1630208/sankt-style) | HTTP 403 | the primary thread |
| [BGG: Ziemowit vs Sankt](https://boardgamegeek.com/thread/1968746/ziemowit-vs-sankt) | HTTP 403 | 2018 commented game |
| [BGG: ABCs for TS, Z for Ziemowit](https://boardgamegeek.com/thread/2802164/rtsl-abcs-for-ts-a-z-z-for-ziemowit) | HTTP 403 | Ziemowit entry |
| twilight-league.com "Z vs Sankt, The Road So Far" 1 and 2, "RTSL: ABCs for TS" | DNS fails | indexed by search, unreachable |

Ziemowit reportedly also teaches through a YouTube channel of his own play,
which is the obvious next source and needs a human to watch it.

## The two schools, which is the headline disagreement

The compilation frames Sankt's approach against the Western canon
(`twilightstrategy.com`):

- **Western:** play for map position and win at final scoring; use the
  Space Race sparingly.
- **Chinese (Sankt):** take short-term points and push the Space Race as
  far as it will go. "Space is the 7th region due to its scoring
  potential."

This bears directly on `FINAL_SCORING_ODDS` and the scoring horizon. This
bot measured 24.5% of its own games reaching final scoring and already
suspects that is generous for expert play. A school that plays explicitly
for early points and space would push it lower still.

## Numbers that are directly usable as calibration targets

**Expected VP per Battleground, by region** (credited in the compilation to
a calculation by "Aragorn", not to Sankt):

| Region | Value per Battleground |
| --- | --- |
| Europe | 3rd Battleground 6-10 VP; the 4th only 2 VP |
| Asia | ~5 VP |
| Middle East | a little under Asia |
| Latin America | ~5 VP, "obviously more volatile" |
| Africa | ~4 VP, "by far the most volatile" |

This is the shape `battleground` times the region's scoring weight is
trying to produce, from an independent source, and it is strongly
non-linear in a way the current additive per-country function is not: the
third Europe Battleground is worth three to five times the fourth. That is
the domination-margin effect the `margin_*` terms were added for, and it is
a target to fit them against.

**Space Race.** Reaching the first two scoring spaces before the opponent
is a 6 VP swing; the third scoring space alone is another 4 VP. Caution:
do not enter the Mid War holding a 2-1 space lead, because One Small Step
lets the opponent jump you.

**France** is "generally worth 6 VPs each time Europe is scored", the
single most valuable country to spread into. Thailand is next best
individually and is cheap to control. Egypt is a cheap Battleground with
access to another and blocks the USSR route into Algeria.

## Card handling

**Always event (your own):** Grain Sales to Soviets, Aldrich Ames Remix,
Captured Nazi Scientist. Nazi Scientist because the card is only worth 1 Op
otherwise.

**Never event (your own):** Formosan Resolution, COMECON, and "most
surprisingly" NORAD.

**Space these:** Decolonization on Turn 1, because Blockade will almost
certainly cut your hand at some point. Containment and Nuclear Subs, rather
than playing the event. Vietnam Revolts, "powerful early but very weak
afterward". The opponent's War cards, with Korean War the main exception:
Sankt will often let Korean War fire if the opponent already has military
operations and an influence lead in South Korea.

The discard-a-held-card ability is "by far the most important ability with
this rabid spacing style, especially as the USSR".

**Coups.** Couping 2-stability non-Battlegrounds is a highly inefficient
use of Ops, and you can still place 1 influence there even after a
successful coup.

## Openings

Both players key the opening to the hand, which this bot's `OPENING_BOOK`
cannot do.

**US, holding Marshall Plan as the headline:** depart from the traditional
3 West Germany / 2 Italy / 1 Greece and Turkey. Use 3 West Germany, 2
Italy, 2 France, then spend Marshall into those three plus Greece or Spain,
Turkey, UK and Canada.

**US, no Marshall.** Sankt strongly prefers 4 West Germany / 4 Italy / 2
Iran when holding any of Nasser, Europe Scoring, Middle East Scoring (if
headlined), Suez Crisis or Arab-Israeli War. He prefers 4/3/3 only with
Socialist Governments, or Red Scare/Purge if headlining it.

**Empty West Germany** is for one specific hand only (Blockade, Truman,
Nasser, Vietnam Revolts, Decolonization, COMECON, Fidel, Romanian
Abdication) and even then put 1 influence in West Germany and 3 into
France.

**USSR Turn 1.** Prefer couping Italy over Iran, because Italy is a
potential 6 VP swing every time Europe scores; coup it when there is at
least a 2/3 chance of securing the country. Against a Marshall headline
that opens France, a 4-Ops coup is about 50/50 to secure Italy. Sankt
rarely coups Iran on AR1 without the De-cards, because Thailand and the
cheap Southeast Asian countries are critical for long-term domination and
the USSR needs events for them. An alternative is a 2-Ops spread into
Afghanistan and Israel, forcing the US on two fronts.

**Non-Battleground placements worth making:** 1 influence in Malaysia for
access; 1 in Costa Rica early, so you can get back into Panama.

## Headline priority, Turn 1 US

Sankt: Marshall Plan > Containment (when it gains 5+ Ops, or is needed
against Blockade) > Middle East Scoring = Red Scare/Purge > Captured Nazi
Scientist > Containment (when it gains under 5 Ops).

Ziemowit, as of August 2016: Middle East Scoring = Red Scare/Purge =
Containment (on the same condition) > Marshall Plan > Containment at 3-4
Ops > Defectors > Captured Nazi Scientist.

They disagree on Marshall Plan: first for Sankt, fourth for Ziemowit. Worth
knowing before treating either ordering as ground truth.

**USSR Turn 3, which card to hold:** Five Year Plan > UN Intervention (if
you do not already hold a 4-Ops US event) > a strong 4-Ops US event, such
as Marshall Plan with much of Western Europe still open, or NATO if you are
losing the European Battlegrounds > Indo-Pakistani War > Duck and Cover,
the strongest US Turn 3 headline > Defectors > other US events.

## What the retrieved source does not cover

Recorded so nobody later attributes an opinion to Sankt that he was never
quoted as holding. The compilation says **nothing** about: the China Card
(beyond one replay using it for an Italy coup), DEFCON management, the
required Military Operations, realignment as a strategy against couping,
when to score a region, the Mid War or Late War beyond Turn 3, hand size,
or the 20 VP threshold. Its coverage is Turn 1 to Turn 3, and it is mostly
about the US and USSR openings.

## Where this agrees and disagrees with what we already believe

The maintainer's own valuations are the reference this repo fits to
(`models/expert_valuations.json`, and the principles table in
`docs/CLAUDE_NOTES.md`). These outside notes do not override them. Where
they differ, ask.

**Agreements, which raise confidence:**

- Grain Sales and Aldrich Ames are always evented. Already a stated
  principle here and still not implemented; Sankt adds Captured Nazi
  Scientist to that list.
- France is a top-value country. The bot currently ranks France *below*
  Egypt, Pakistan and Iraq for a US placement, an inversion the expert
  check already flags. Two independent sources now say the bot is wrong.
- Thailand and the cheap Southeast Asian countries matter for long-run
  domination, which is what the access and margin terms exist to capture.
- The opening should be chosen from the hand. Both players do this; the
  book cannot, and this is already plan step 4.

**Disagreements to put to the maintainer:**

- **The opening.** The maintainer prefers 3 West Germany / 3 France / 2
  Italy / Iran to 2, with 4/4/2 as "old school". Sankt strongly prefers
  4/4/2 on a wide class of hands and reserves the split lines for
  Socialist Governments or Red Scare. The maintainer's own exposure table
  in `CLAUDE_NOTES.md` also found 4/4/2 safest. Worth resolving before the
  book is rewritten.
- **Space Race weight.** The Chinese school treats space as a seventh
  scoring region and spaces aggressively, including cards this bot would
  play. If that is right, `space_value` and the space slot are
  substantially underweighted.
- **NORAD is never evented.** The maintainer prices NORAD at about 1 Op
  and the bot at 0. Sankt's claim is about play, not value, but a card you
  never event is worth less than one you sometimes do.

## How to use this file

1. Do not fit a weight to a number here without checking it against the
   maintainer first. This is reported speech from a third-party
   compilation, and one of its two named experts is quoted only once.
2. The regional Battleground table and the Space Race swings are the two
   items concrete enough to become fixture rows. They belong in
   `models/expert_valuations.json` with an explicit note that their
   provenance is this file, not the maintainer.
3. The gaps above are the reason to reach the unreachable sources. Someone
   with a browser should pull the two BoardGameGeek threads and Ziemowit's
   YouTube channel; the Mid War, Late War, China Card and Military
   Operations advice is exactly what this bot most needs and exactly what
   the retrieved source lacks.
