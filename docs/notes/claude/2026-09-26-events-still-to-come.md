# Events still to come: discount the country an event is aimed at

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
| 110 | AWACS Sale to Saudis | Mid | Saudi Arabia 1.00 |

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

## The readings

(Filled in at read time.)
