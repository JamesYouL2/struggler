# Events still to come: discount the country an event is aimed at -- measured, off

The maintainer's rule (2026-09-26): "Vietnam is less valuable than Laos due
to Vietnam Revolts. South Korea less valuable than North Korea, Egypt less
valuable than Libya, etc. Just putting a slight discount here if the card
is live might help a lot." Two conditions came with it: **the list must be
complete**, and **Mid and Late War cards are discounted before they enter
the deck**.

## How it works

1. **Which countries each event moves** is derived from the engine, not
   written by hand. `scripts/probe_event_exposure.py` fires every event
   for its own side on 200 random boards:
   - both sides are on every country, and preconditions are forced when
     the board misses them (John Paul II for Solidarity, and so on);
   - a single war die rolls 6, and every choice is answered at random.

   A country's share for a card is how often it moved in the firings that
   moved anything. `event_exposure.json` holds the result, and
   `tests/test_event_exposure.py` fails if the file is incomplete (every
   event card is present and fired) or stale (the probe no longer
   reproduces it from the engine).
2. **Aimed, not touched.** Summing every share saturated the map. The
   free-Ops and choice events (Marshall Plan, De-Stalinization, Voice of
   America) each brush dozens of countries, and Canada ended up at the
   full discount. A country counts for a card only if it is a fixed
   target (share of at least 0.9), or the card reaches at most three
   countries and this one takes at least 0.4 of it
   (`evaluator.aimed_countries`). The list it selects follows; it is the
   list to check.
3. **When the card fires.** `public_cards.p_event_fires` is P(the card is
   played before the game ends) from public information, using the same
   deck arithmetic as the scoring schedule. A removed card scores 0 and our
   own hand 1. An unseen card is in their hand, or dealt this cycle, or
   dealt after the reshuffle. A **Mid or Late War card not yet in the deck
   counts 1 if it enters before the end**, so it is discounted from turn 1.
4. **The discount.** Each country's importance, for both sides, is
   multiplied by `1 - event_exposure x min(1, sum of share x P(fires))`
   (`evaluator.event_discount`). Both sides, because an exposed country is
   a poor place to invest for whichever side the event helps: it takes
   the country for free.
   `StrategicWeights.event_exposure` ships at **0**. Then nothing is
   computed and the parity corpus is unchanged.

## The list (the aimed-event cut of the probed table)

| # | card | war | aimed at (share) |
| ---: | --- | --- | --- |
| 8 | Fidel | Early | Cuba 1.00 |
| 9 | Vietnam Revolts | Early | Vietnam 1.00 |
| 10 | Blockade | Early | West Germany 1.00 |
| 11 | Korean War | Early | South Korea 1.00 |
| 12 | Romanian Abdication | Early | Romania 1.00 |
| 13 | Arab Israeli War | Early | Israel 1.00 |
| 15 | Nasser | Early | Egypt 1.00 |
| 17 | De Gaulle Leads France | Early | France 1.00 |
| 24 | Indo Pakistani War | Early | India 0.57, Pakistan 0.43 |
| 27 | US Japan Mutual Defense Pact | Early | Japan 1.00 |
| 28 | Suez Crisis | Early | Israel 0.94, France 0.93, UK 0.92 |
| 52 | Portuguese Empire Crumbles | Mid | Angola 1.00, SE African States 1.00 |
| 53 | South African Unrest | Mid | South Africa 1.00, Angola 0.42, Botswana 0.41 |
| 54 | Allende | Mid | Chile 1.00 |
| 55 | Willy Brandt | Mid | West Germany 1.00 |
| 64 | Panama Canal Returned | Mid | Panama 1.00, Venezuela 1.00, Costa Rica 1.00 |
| 65 | Camp David Accords | Mid | Jordan 1.00, Egypt 1.00, Israel 1.00 |
| 68 | John Paul II Elected Pope | Mid | Poland 1.00 |
| 72 | Sadat Expels Soviets | Mid | Egypt 1.00 |
| 82 | Iranian Hostage Crisis | Late | Iran 1.00 |
| 83 | The Iron Lady | Late | Argentina 1.00, UK 1.00 |
| 88 | Marine Barracks Bombing | Late | Lebanon 1.00 |
| 91 | Ortega Elected in Nicaragua | Late | Nicaragua 1.00 |
| 96 | Tear Down This Wall | Late | East Germany 1.00 |
| 101 | Solidarity | Late | Poland 1.00 |
| 102 | Iran Iraq War | Late | Iran 0.55, Iraq 0.45 |
| 110 | AWACS Sale to Saudis | Late | Saudi Arabia 1.00 |

Left out by the cut: every free-Ops or choice event whose reach is wide:
- Decolonization, Marshall Plan, Warsaw Pact, COMECON, East European
  Unrest and Independent Reds;
- Socialist Governments, Truman Doctrine, Colonial Rear Guards, Muslim
  Revolution, Liberation Theology, OAS and Junta;
- Debt Crisis, The Reformer, Pershing II, KAL 007, Brush War, Olympic
  Games, CIA Created, Voice of America, Che, Lone Gunman, ABM Treaty and
  Grain Sales;
- Marine Barracks' Middle East half. Its Lebanon half stays.

In total, 44 events move no influence at all.

## What it does to the annotated positions

Taken from `tests/fixtures/positions/annotated-01.json` (PR #66), by
weight:

| id | 0 (shipped) | 0.1 | 0.25 | 0.5 | 1.0 | maintainer |
| --- | --- | --- | --- | --- | --- | --- |
| p1-coup | Angola | **Nigeria** | **Nigeria** | **Nigeria** | **Nigeria** | Nigeria |
| p4-coup | Angola | **Zaire** | **Zaire** | **Zaire** | **Zaire** | Zaire ("don't make Portuguese and South Africa free") |
| p5-place | Venezuela | **Brazil** | **Brazil** | **Brazil** | **Brazil** | Brazil fine |
| p2-coup | Brazil | Brazil | Brazil | Brazil | Brazil | any |
| p3-place | Vietnam | Laos | Laos | Laos | Laos | France |
| p1-card | China Card | China Card | China Card | China Card | AWACS | How I Learned |

From 0.1 up, agreement goes from 2 of 6 to 4 of 6.

- **p4 is the maintainer's own reason, recovered by the general rule.**
  Angola is aimed at by Portuguese Empire Crumbles and South African
  Unrest. The first note on these positions guessed p4 needed a separate
  "own-hand overlap" idea; it does not.
- **p3 moves off Vietnam but lands on Laos.** The maintainer's France
  ("Europe scoring is still out, go Europe") is a different idea, and
  this term does not reach it.
- **p1-card is the China Card question**, and untouched.

## THE RULE, before the number

Arms against `bc5ef93` (consistent with the other readings in flight),
1024 seeds on the fresh block 147000-148023, reserve 148100-148227, waves
off. `ee-base` is the shipped bot; `ee-01`, `ee-025` and `ee-05` set
`event_exposure` to 0.1, 0.25 and 0.5.

1. Each arm is read paired against `ee-base`. A lower bound above 0
   nominates that weight for a change gate. If several clear, take the
   highest point estimate; the weights are an ordered scale.
2. **Veto:** an arm whose bot DEFCON-1 losses exceed the base's by more
   than half is not nominated.
3. **None clears, and none has an upper bound below 0:** strength does not
   see it at 1024 seeds. The position suite does (3 flips toward the
   maintainer's move at every weight). That calls for the maintainer's
   decision, and ships only through a change gate if they take it.
4. **Any arm with an upper bound below 0:** that weight costs. The term
   stays at 0 at that weight or above, and the note says why.

## The readings (run 36270091127, 2026-09-26)

All four arms are complete at 1024 seeds. Five seeds were lost to the
`bc5ef93` anchor's helper-chain hang and backfilled from the spares.
The run was dispatched before #67 moved AWACS to the Late War, so both
sides of every pair play that one-card-off deck; a paired difference is
unaffected.

| arm | vs bc5ef93 | paired vs `ee-base` | bot DEFCON-1 losses |
| --- | ---: | ---: | ---: |
| `ee-base` (0) | 0.571 [0.554, 0.588] | -- | 48 |
| `ee-01` (0.1) | 0.566 | -0.005 [-0.026, +0.017] | 41 |
| `ee-025` (0.25) | 0.550 | -0.021 [-0.044, +0.001] | 38 |
| `ee-05` (0.5) | 0.514 | **-0.058 [-0.082, -0.035]** | 32 |

**By the rule:**

- **Rule 1: nothing is nominated.** No lower bound is above 0.
- **Rule 4: 0.5 costs.** Its upper bound is below 0, so the term does not
  ship at 0.5 or above.
- **Rule 3: 0.1 and 0.25 cover 0.** 0.25 does so only at its edge. At
  1024 seeds strength does not see them, while the position suite does:
  three of six positions flip to the maintainer's move at any weight from
  0.1. **So this is the maintainer's decision.** `event_exposure` stays 0
  unless they take 0.1, and taking it goes through a change gate.

The shape is monotone: more discount, more loss. The bot's own DEFCON-1
losses fall with the weight, from 48 to 32. That fall is a real change in
play, not noise at this size, and it does not buy strength.

## Why it might cost (hypotheses, not yet tested)

1. **It discounts holding, not just investing.** The maintainer's rule is
   about where to put influence. The implementation discounts a
   country's importance in the whole board value, so an exposed
   battleground the bot already controls counts for less at the next
   scoring, though it scores in full until the event lands. Applied only
   to the placement decision (the `delta` of a trial), with the board value
   left alone, the rule would say what the maintainer said and no more.
2. **Future cards count as certain from turn 1.** `p_event_fires` gives a
   Mid or Late War card 1.0 as soon as it enters before the game ends: the
   scoring schedule's flat convention. That discounts Iran, Poland and
   Nicaragua for the whole Early War, when their events are years off. A
   time discount would weigh a Late War event less on turn 1.
3. **Both sides are discounted alike.** For the side the event helps,
   the country comes free later, but holding it now still counts. The
   symmetric discount charges the beneficiary for a threat that is not
   theirs.

(1) and (2) are each a small code change, and each can be tested on the
annotated positions first, which cost seconds, before an arm. The suite
now reads 4 of 6 with the term on; any variant must keep that.

## Weighing distant events less: the rule, before the number (2026-09-26)

The maintainer chose hypothesis 2 to test first. `StrategicWeights.event_decay`
weighs each route by which a card can first reach a hand by `decay ** turns
from now` (`public_cards.p_event_fires`). A card in a hand now is weighed at
decay^0; pile deal k at decay^(k+1); recycled deals from the reshuffle turn;
a future-war card from its war's entry. So a Late War target on turn 1 weighs
decay^7. 1.0 is the undecayed path, and the parity corpus is exact at it. On
the annotated positions every weight and decay tried (0.25-1.0 x 1.0-0.4)
keeps the 4 of 6: their events are near, and decay strips only the distant
part.

Arms against **`v0.6.0`** (the anchor for new arms since #69), 1024 seeds
on the fresh block 149000-150023, reserve 150100-150227, waves off, each
`compare_to` `ed-base`:

- `ed-base`: `event_exposure` 0;
- `ed-05-d10`: 0.5, undecayed (the reference, remeasured here: -0.058 on
  bc5ef93);
- `ed-05-d07`: 0.5, decay 0.7;
- `ed-05-d04`: 0.5, decay 0.4;
- `ed-025-d07`: 0.25, decay 0.7.

THE RULE, not moved after the number:

1. **Nomination**, as before. A decayed arm whose paired lower bound
   against `ed-base` is above 0 goes to a change gate (the highest
   estimate if several clear). An arm whose bot DEFCON-1 losses exceed the
   base's by more than half is vetoed.
2. **The hypothesis**, read seed by seed across arms, the way the access
   interaction was: `ed-05-d07 - ed-05-d10` and `ed-05-d04 - ed-05-d10`.
   If either interval lies above 0, distance is part of the cost
   (hypothesis 2 supported). If both cover 0, decay does not explain it,
   and hypothesis 1 (discount holding, not just investing) is next.
3. **No nomination, but the cost is recovered** (decayed arms cover 0 while
   `ed-05-d10` is below 0): the term is safe at that setting and still
   flips the positions, which makes it the maintainer's call, as 0.1 was.

## Weighing distant events less: the reading (run 36289814099, 2026-09-27)

All five arms are complete at 1024 seeds against `v0.6.0`, with no stalled
game (the new anchor has no hang).

| arm | vs v0.6.0 | paired vs `ed-base` | bot DEFCON-1 losses |
| --- | ---: | ---: | ---: |
| `ed-base` (0) | 0.512 [0.499, 0.525] | -- | 67 |
| `ed-05-d10` (0.5, undecayed) | 0.469 | **-0.043 [-0.064, -0.022]** | 46 |
| `ed-05-d07` (0.5, decay 0.7) | 0.490 | -0.021 [-0.042, -0.001] | 56 |
| `ed-05-d04` (0.5, decay 0.4) | 0.517 | **+0.005 [-0.016, +0.025]** | 62 |
| `ed-025-d07` (0.25, decay 0.7) | 0.504 | -0.008 [-0.029, +0.014] | 43 |

Read seed by seed against the undecayed arm (1024 seeds, all arms):

- decay 0.7: +0.022 [-0.002, +0.045];
- decay 0.4: **+0.048 [+0.025, +0.070]**.

**By the rule:**

- **Rule 1: no nomination.** No lower bound is above 0.
- **Rule 2: hypothesis 2 is supported.** Decay 0.4's recovery lies above
  0: most of the discount's cost was DISTANT events. The undecayed cost
  also replicated on the new anchor (-0.043 here, -0.058 against
  `bc5ef93`).
- **Rule 3: the cost is recovered at (0.5, decay 0.4).** It is level with
  no discount and still flips three annotated positions to the
  maintainer's move, so it is the maintainer's call. At decay 0.4 a Late
  War target on turn 1 weighs 0.4^7 = 0.002: in effect only events a
  turn or two out count, which is what "if the card is live" meant.

The trend is monotone in decay: stronger decay, better result. The
natural next point is decay 0.2 or lower, which in the limit counts only
cards already in a hand. Whether a near-only discount turns positive is
the open question. Hypothesis 1 (discount investing, not holding) is
still untested and is independent of this one.
