# The first annotated positions: 2 of 6 agree

The maintainer marked the first five positions of the annotated suite
(docs/EXPERT_ASKS.md, "The other thing") on 2026-09-26.

The five came from `scripts/position_pack.py`'s Part B selector, run on
the current parity corpus: the closest calls the shipped bot makes in its
own self-play, where the top two options are within 0.5%. Position 1's
answer was about the CARD, not the coup target, so its card-play decision
was captured too, by replaying seed 4002. That makes six entries in
`tests/fixtures/positions/annotated-01.json`, and
`tests/test_annotated_positions.py` asks the current bot each one.

| id | position | bot | maintainer | agrees |
| --- | --- | --- | --- | :---: |
| p1-card | seed 4002 T7 AR1, USSR card play | The China Card (+0.27 Ops over How I Learned) | **How I Learned to Stop Worrying** | no |
| p1-coup | the same, coup target (4 Ops) | Angola 45.28 vs Nigeria 45.19 | **Nigeria** (with How I Learned) | no |
| p2-coup | seed 4002 T9 AR1, USSR coups, holds South America Scoring | Brazil | any of Brazil, Venezuela, Argentina ("realignment dynamics make it unclear") | yes |
| p3-place | seed 4003 T1 AR6, US last Op | Vietnam = Laos/Cambodia, France 0.5 Op behind | **France**: Europe Scoring is still out, so go Europe unless Laos is needed for domination. "Definitely not Vietnam due to Vietnam Revolts" | no |
| p4-coup | seed 4003 T5 AR1, USSR coups after ABM Treaty | Angola 91.70 vs Zaire 91.36 | "Good move", but **prefer Zaire**, so Portuguese Empire Crumbles and South African Unrest are not made "free" | no (close) |
| p5-place | seed 4003 T7 AR1, US 2 Ops from Missile Envy | Venezuela vs Brazil | Brazil fine | yes |

p5 records Venezuela as accepted pending confirmation. The maintainer
wrote "Brazil/argentina fine", but Argentina is USSR-controlled (0-2) and
not among the bot's options.

## What each miss is missing (hypotheses, not yet traced)

1. **The China Card's value when held** (p1-card). The bot spends it on
   an Africa coup, which wastes the Asia bonus and passes the card
   face-down, when a 2-Op card does the same job. It rated the difference
   at 0.27 Ops. EXPERT_ASKS item 7 already has the maintainer's China
   Card answers, so the first check is whether the bot prices them.
2. **Opponent events aimed at a country** (p3). Vietnam Revolts, still in
   the draw pile, puts 2 USSR Influence into Vietnam. A US point there is
   exposed, and nothing in `country_value` knows. The same shape covers
   any card with a fixed target: Decolonization, Junta, Brush War, and so
   on.
3. **Own-hand event overlap** (p4). The USSR holds Portuguese Empire
   Crumbles, which reaches Angola anyway. Couping Angola spends Ops on
   what the card will do for free, where Zaire adds coverage. The bot
   prices its hand card by card and never asks where its own events will
   land.
4. **Africa** (p5, the maintainer's question "what is Africa doing?").
   The USSR held Africa Scoring, and one more USSR Battleground (Nigeria
   or Angola, both empty) gave it domination. The US bot rated Nigeria
   only 0.16 Ops behind Venezuela. It cannot see the USSR hand, but
   `p_opponent_holds` exists; whether it was high here, and whether the
   domination swing is priced at that probability, is the check. The
   maintainer also noted the US should dump Cultural Revolution as soon
   as possible while it does not hold the China Card. p5's own card was a
   forced Missile Envy play, so that point is for an earlier round.

The maintainer's side question, "why is AWACS in the USSR hand at T7?",
found an ENGINE DEFECT. AWACS Sale to Saudis (#110) is a Late War card,
but `cards.json` had it in MID_WAR, so it was shuffled in at turn 4. I
first answered that the engine was right, having checked only that the
card moved as the data said. Fixed in PR #67, gated by a test pinning all
110 printed periods. These positions were captured on the wrong deck, and
p1's USSR hand would not hold AWACS on the right one. The maintainer's
answers are about the board and the other cards, so they stand, but the
fixture positions should be recaptured once #67 merges.

## What this instrument is worth, now measured

Six positions, one answer each, found four misses. At least three are
distinct missing ideas that no weight A/B could have found, because they
are not weights. That is the case the ask made for the suite. More
positions from the same selector will repeat near-ties like p2, so the
next pack should also include decisions where the bot's choice is
confident but plausibly wrong (for example, card plays that spend the
China Card), not only close calls.
