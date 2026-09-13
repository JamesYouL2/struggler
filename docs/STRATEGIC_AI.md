# Strategic AI

`strategic` is a local tactical AI with a linear evaluation function and an
optional evolutionary training pipeline. It needs no API key, GPU, or ML
framework. Its default weights are handcrafted; `models/strategic-v1.json`
is a small training-run checkpoint, not a large-scale pretrained model.

## Play

```sh
python src/main.py --us strategic --ussr greedy --seed 1 --no-game-log
python src/main.py --us human --ussr strategic

# Load a trained checkpoint (applies to every strategic seat).
STRUGGLER_STRATEGIC_MODEL=models/strategic-v1.json \
  python src/main.py --us strategic --ussr greedy --seed 1
```

The same player works through the existing physical-board and replay/resume
interfaces. It has no private conversation or RNG state to restore.

```python
from struggler.bots.strategic import StrategicPlayer, StrategicWeights

bot = StrategicPlayer(StrategicWeights.load("models/strategic-v1.json"))
action = bot.choose_action(observation, history)
```

## How it plays

- A country is worth what its region will still score. Its importance is
  multiplied by the sum, over the scoring cards that count it, of
  `scoring_discount` (0.8) to the power of the turns until each expected
  scoring, from the static period schedule and where each card is now
  (`bots/public_cards.scoring_schedule`): a live card scores this cycle
  and again after the reshuffle (about 1.6), a discarded one only after
  the reshuffle (0.6), a Mid War card from turn 4 (0.5 on turn 1);
  Southeast Asia Scoring once. Holding the card multiplies this cycle's
  term by `scoring_hand` (1.2): we pick the moment. So a battleground in
  an unscored Early War region is worth about 2.5x one in a region just
  scored, and Mid War battlegrounds grow in value as turn 4 approaches.
  The same schedule drives the checkpoint benchmark's projection.
- The schedule stops at the end of the game, and every region is scored once
  more there, at its measured odds of the game getting that far
  (`public_cards.FINAL_SCORING_ODDS`, times `scoring_final`). Neither used to
  be true: a reshuffle two turns off on turn 9 predicted a scoring on turn 11,
  and the end-of-game scoring was missing, so the weight came out flat on
  every turn of the game. Final scoring is not a certainty to put in its
  place. The provisional prior now uses the
  [BPA 2026 round-4 results](https://twstourney.wordpress.com/2026-round-4/):
  six of 27 games reached final scoring, divided by the number reaching
  each turn. Only six reached turn 10, all scoring finally; the resulting
  1.0 is a small-sample observation, not a guarantee. This selected cohort
  includes different bids and held-card losses, and needs broader validation.
  `scripts/game_endings.py` remains a bot-report diagnostic, not the source
  of this table. It used to filter on the end reason `final_vp`, which
  missed draws and the VP/Europe wins that land partway through the
  engine's final-scoring procedure; the engine now records
  `Engine.final_scoring_ran` and serializes it, the benchmark writes it per
  game as `final_scoring`, and the script counts that (falling back to the
  old filter for reports written before the flag existed).
- The opening setup is a book, not a search (`OPENING_BOOK`): USSR
  East Germany +1, Poland +4, Austria +1 (4/4 keeps control through East
  European Unrest; Austria reaches Italy and West Germany); US West
  Germany 4, Italy 3, then the +2 handicap to Iran and West Germany
  (5 holds against Socialist Governments). The influence search decides
  only if the book's country is somehow unavailable. Before the book the
  value function put 3 in Czechoslovakia, a non-battleground.
- Ops are priced by their best use on this board (`ops_value`): a greedy
  influence plan (so the value is concave in Ops: the fourth point buys
  less than the first) or the best coup, whichever is larger. The Ops-type
  choice prices its influence branch with that same greedy plan. It used to
  take the best single country's value per Op and multiply by the Ops, which
  assumes every point goes to one country at the first point's rate: on one
  test position that read 188 where the plan reads 119, so a card could be
  picked on one estimate and spent on the strength of another. Events,
  Ops and VP are then on one scale, where a battleground control is 19
  and a VP is `vp` (3). A flat 2 per Op had made Nuclear Test Ban's 3 VP
  (9) beat its 4 Ops (8) on turn 1; now 4 Ops on the opening board are
  worth 44-58, and the VP weight is the knob to calibrate against that.
- Every event the idle sandbox can run is simulated (`PUBLIC_EVENTS` is
  everything but the `HIDDEN_INFO_EVENTS`, which need hands or the deck,
  and the Ops-modifier cards, which are priced directly: Containment and
  Brezhnev Doctrine as the marginal Op on every other Ops card in the
  beneficiary's hand, Red Scare/Purge as the expected marginal Op lost over
  the victim's hand drawn from the unseen cards, the China card included;
  about 5-7 Ops at a turn-1 headline): the helper policy plays each choice the
  event raises, chance takes its middle roll, and an event the sandbox
  cannot drive falls back to the 0.8 x Ops estimate. Before this only 23
  events were simulated, and De-Stalinization was priced at 4.8, below its
  Ops. Flag-only events (NATO, Warsaw Pact, NORAD, Nuclear Subs, Quagmire,
  Bear Trap) move no influence and so value 0; that is a known gap.
- The two flag events that change *scoring* rather than influence are
  priced, because region scoring takes the same per-scoring overrides the
  engine applies. `Board.scoring_overrides` derives them -- Formosan
  Resolution promoting a US-held Taiwan to a Battleground in Asia, Shuttle
  Diplomacy dropping one USSR-held Battleground from the Middle East or
  Asia -- and `evaluator.scoring_overrides` mirrors it in index space. The
  bot reads which are in force from `observation.game_effects`
  (`strategic.scoring_flags`), and the event sandbox reads them from the
  sandbox engine after the event fires, which is what makes an event whose
  only effect is turning one on worth something. Overrides are derived per
  call rather than frozen at `prepare`, because they read control: taking
  Taiwan is what switches Formosan Resolution on, and the placement that
  does it has to see that. Shuttle Diplomacy is one-shot across two
  regions, so a whole-board value spends it once, on the region whose
  scoring is nearer (`_shuttle_region`); see docs/LIMITATIONS.md.
- Access is the battlegrounds a stake lets its side reach (`_access`),
  each worth its control value over its stability: full weight when this
  holding alone reaches one, `access_redundant` when another holding
  already does (insurance, one more direction to contest from). Chains --
  a battleground two steps away through a country not yet held -- counted
  too until 2026-09-12, weighted `access_chain`; ablated alone over 128
  seeds it was not measurably worse (0.491 +/-0.063), while being 92% of
  the traversal `access` can do, so it was removed. Reach into a
  battleground the opponent can
  already place in is a race they may win first, worth `access_contested`
  (0.25) of exclusive reach. Nothing for ground held. Getting to
  battlegrounds first is most of what a non-battleground is for, and it is
  why De-Stalinization prices so high.
- Region margin (`margin_presence`, `margin_battleground`, `margin_country`,
  `region_margin`): the exact region score pays nothing until a tier flips,
  so partial credit is added on the country-importance scale: progress
  toward a first controlled country where a side has none (presence, "the
  whole game" in the Middle East: the USSR's Iraq), and each battleground
  and country of margin toward or past domination, capped at two, times
  the domination-minus-presence gap in presence units. Fitted to
  `models/expert_valuations.json` (31 -> 26 misses; Iraq first for the
  USSR).
- First mover (`first_mover`): presence in a battleground the opponent has
  none in but could reach is tempo, whoever fills an empty country first
  makes the other pay to contest it, worth `first_mover` x importance /
  stability (a 4-stability contest is the least valuable Op on the board).
- Wipe risk (`wipe`, `wipe_backed`, `wipe_risk`, `coup_targets`): **deleted
  2026-09-13.** The chance a 3- or 4-Ops coup removes every point held, times
  a stake that depended on backing. It shipped at `wipe = 0`, "off until
  calibrated", and was never calibrated; the retention it approximated is now
  measured directly (`scripts/measure_access_conversion.py`). The parity
  corpus reproduced unchanged without it, which is the proof it moved no
  decision. `evaluator.coup_forbidden`, which kept it from pricing a Coup the
  rules forbid (NATO, the US/Japan pact, The Reformer), stays, with its test
  against `Board.coup_prohibited`; nothing in the value function reads it
  now, and the `bans` argument still threaded through `country_value` is
  unused until a term needs it again. `progress_curve` (pinned at 1.0, so the
  progress term was already linear) and the retired `ops` weight went in the
  same change.
- One space slot a turn (`space_card`): among the opponent's cards the
  Space Race accepts, the one whose Ops-plus-event is worst is the space
  candidate, and only it is valued as a space play when choosing a card.
  Decolonization (-75) is spaced ahead of Fidel (-23); before, both
  collapsed to the same space value and the tie broke on hand order.
- Country importance is battleground or not (`battleground`, `control`=0):
  a plain country is worth nothing of its own, since its control only moves
  the domination tally the region score computes exactly; what it is for is
  reach, priced by the access and first-mover terms. The Southeast Asia
  tier and the realignment-leverage term were removed in Sept 2026: the
  scoring weights and access express both.
- Coups and realignments are priced on the same board change as placing
  influence (`delta`), as the expectation over their dice -- six rolls for
  a coup, thirty-six for a realignment -- and nothing on top. A coup on a
  2-stability country gives up a point of margin to the roll, and that is
  already in the rolls. A `coup_discount` of 0.9 multiplied both until
  2026-09-13: a placement preference, not a rule, and the maintainer's reading
  was that it did not make sense. Military Ops are still credited to a coup.
- VP per Op is the quantity the influence search maximises (`influence`
  returns gain per Op spent, including the doubled cost under enemy
  control), so 1- and 2-stability countries, which reach control for the
  fewest Ops, are automatically the best value while their scoring card
  is live; nothing extra encodes that.
- Searches affordable multi-point investments into each candidate country,
  accounting for the end of doubled placement costs when enemy control breaks.
- Enumerates all six coup rolls and all 36 realignment roll pairs. These are
  exact expectations of its local board evaluator, not a simulation at an
  average roll. Prices military-operations deficits and avoids directly fatal
  coups, including Cuban Missile Crisis.
- Evaluates selected deterministic public-board events using the engine's
  event implementation, resolving influence choices for each beneficiary.
  Handles friendly versus enemy card allegiance when comparing ops, events,
  and spacing, and detects selected dangerous DEFCON cards.
- Handles event influence removal/placement, war targets, scoring cards,
  discards, and selected event choices such as Blockade and Wargames.
  Scoring cards go through `StrategicPlayer.scoring_card_value`, which
  resolves the region in the idle sandbox rather than estimating it, because
  the tiers are discontinuous and a near-miss is worth nothing. Ask Not's
  discard choice prices a scoring card as the exact negation of that: dump
  the regions that would score against us, keep the ones that would not.
- **Prices risk rather than ranking it, and prices it once.** `safety_key`
  refuses certain defeat outright, then folds the *residual* turn-loss risk
  into the score as `(1-residual)*score - residual*game_value`, where
  `game_value` is the whole VP
  track (`GAME_SWING_VP` = 40) at this turn's price per VP -- about 8 cards
  on turn 2, 22 on turn 6, 43 on turn 9, so a 10% risk costs one to four
  cards. It used to be a separate key element *ahead* of the score, which
  made safety lexicographic: a risk of 1e-8 lost to a risk of 0 whatever
  was on the table, and nothing could ever be bought with risk at any
  price. That is the likeliest reason this bot lost to DEFCON 1 38x to 82x
  less often than a human tournament field. `LOSS` stays the sentinel for a
  *certain* outcome; a probabilistic one is worth the game and no more.
  `action_risk` exposes both numbers, since the key no longer does.
  Decisions whose score is not in raw board units (`EVENT_CHOICE`'s
  per-card rules) keep risk as a prior key element, because blending an
  ad-hoc scale with `game_value` would swamp it.

  The residual is what is left of the turn-loss risk once the event's own
  share of it is removed: `(risk - immediate) / (1 - immediate)`. It has to
  be, because `score` already owns the immediate share -- `event_value`
  prices a firing event as `(1-r)*result - r*game_value` -- while
  `DefconPlanner.transition` returns `r + (1-r)*future`, so `risk`
  *contains* that same `r`. Charging `risk` here billed `r` twice and, for a
  sandboxed event, three times. Summit at DEFCON 2 keyed at -974.51 against
  an honest -485.57: an implied loss chance of 0.79 where the dice give
  0.4167, a worse price than losing the game outright. With one owner per
  layer the two compose exactly, since `(1-f)*score - f*game_value` is the
  full expectation when `score` is already unconditional. Only
  `ACTION_ROUND_PLAY` needs a guard -- the mode is not chosen there and
  `risk` mins over the modes on offer, so `immediate` is capped at `risk`
  lest a Lone Gunman that could still be spaced be refused as certain.
  The affected cards are the ones whose `event_risk` is strictly between 0
  and 1: Summit, Grain Sales (USSR), Missile Envy, Five Year Plan, and Star
  Wars when the discard pile's best card is itself fractional. Everything
  else returns 0 or 1 and takes the sentinel path.
- The sandbox averages a die over its faces, so a game-ending face is one
  outcome of an average and carries `game_value`, not the sentinel: Summit
  at DEFCON 2 priced at 0.4167 * LOSS, which is 15/36 of a number chosen to
  be unreachable. It is now -0.40 games. An event that ends the game
  without a die still returns the sentinel. Having priced that ending, the
  sandbox *owns* it: `event_value` skips its own `event_risk` charge for
  any event whose simulation reached a terminal state on a die branch,
  which is the third of Summit's three counts.
- **A value term never carries the sentinel.** `LOSS` is an ordering flag
  that only `safety_key` reads, chosen to be unreachable so the test for it
  can be exact. It is not a price, so nothing that averages, mins or maxes
  card values may carry it out -- the mean of a hand containing -1e6 is not
  a number. `hold_value` clamps both its branches to `game_value` and
  `event_value` clamps its result before any risk arithmetic, so the
  invariant is: `event_value` returns either exactly `LOSS` or a price
  bounded by the game, and nothing in between
  (`test_the_certain_defeat_sentinel_never_leaves_a_value_term` sweeps every
  card for it). This has shipped three times -- through `ops_value` (a
  winning coup), `_resolve_sandbox` (one die face), and `hold_value` (a card
  the side cannot play, which priced Ask Not at 742x the whole game and put
  Aldrich Ames past the sentinel, where it was refused as certain defeat).
- Plays for the kill, not only against its own defeat. Nuclear war costs
  the *phasing* player the game (8.1.3) -- whoever played the card, not
  whoever is spending the Operations. So when an opponent's event hands us
  Ops on their own Action Round (Lone Gunman, CIA Created, Grain Sales, ABM
  Treaty pulled by Missile Envy), couping a Battleground at DEFCON 2 wins
  outright, and `StrategicPlayer._is_phasing` is what both `score` and
  `coup_survival_risk` ask. The Summit, Olympic Games and How I Learned
  choice branches use the same distinction. What the bot does *not* do is
  manufacture the situation: it takes the kill when the opponent hands it
  over, but nothing in the policy steers toward a DEFCON 2 where the
  opponent is holding one of those cards.
- Values a hand card *inside* a hand term with a deliberately shallow rule
  (`_shallow_event_value`): the flat estimate for anything that could
  recurse, the full value for everything else. The hand terms are mutually
  recursive by nature -- Ask Not prices the hand, which holds Five Year
  Plan, which prices the hand -- and a cycle breaker that caches whichever
  card it reached first makes the answer depend on the order legal actions
  happen to be enumerated in. It did: reversing the options moved Ask Not by
  170 raw units. An event the engine says cannot occur here is worth nothing
  (`_event_eligible`), asked of `EVENTS[...].eligible` rather than
  reimplemented.
- Prices the hidden-information cards from what a card in a hand is worth
  (`hold_value`: a scoring card scores its region, anything else is played,
  so an opponent event carries its harm and a card you would rather not
  hold is *negative*). Ask Not is the sum of the chosen upgrades over our
  hand, capped at the Action Rounds left (`_hand_upgrade_value`); Five Year
  Plan and Terrorism are a random hold lost, Aldrich Ames Remix the largest,
  Grain Sales the better of 2 Ops and the shown card, Missile Envy the
  opponent's best card swapped for a 2, Star Wars the best US or neutral
  event in the discard pile, CIA Created and Lone Gunman one Op
  (`_hand_attack_value`, `HAND_ATTACK_EVENTS`). Our own hand is exact; the
  opponent's is unseen (mandate #4), so those terms use an Ops-only proxy
  over the unseen cards (`_unseen_holds`) and the hand size we can see. A
  discard from a hand whose cards all have negative hold value is a gain to
  the victim -- the end-of-turn Five Year Plan dumping a scoring card -- and
  it falls out of the arithmetic. Two expert calibrations sit on top: a
  card *discarded* outright (not swapped, as Missile Envy does) costs its
  holder `CARD_DENIAL_OPS` (1.5) Ops beyond the card, unless it was a card
  they wanted gone; and a card lost from a hand larger than the rounds
  left costs only its excess over the card its holder would have held
  anyway. The beneficiary's seat is then scaled by `HAND_ATTACK_REALISED`
  (0.5) -- calibrated against the expert's Grain Sales 4 and Missile Envy
  3, which the raw sums overshot by exactly that factor, and against the
  gate, which rejected them at face value; the victim's seat measured even
  on its own and is not discounted. Salt Negotiations is the best hold in the discard pile, Our Man In
  Tehran five draws' worth of what the US would rather not see. The generic
  estimate that remains for anything else is `0.8 * ops_value(card.ops)` --
  on the same Ops scale as every other term, after a long spell at a raw
  `weights.ops` that priced everything on it near zero.
- The follow-up decisions those events raise are priced by the same
  quantities, because a term that promises the best choice is worthless if
  the choice then falls to option order: Grain Sales takes the shown card
  only when its hold plus what the USSR loses beats 2 Ops (a Soviet event's
  harm is in the hold, so those go back); Star Wars picks the best event in
  the pile, or none; Missile Envy's giver hands over the tied card worth
  least; Aldrich Ames discards the US card worth most to the US. The first
  two used to fall through to the generic card-choice rule, which scored a
  card at *minus* its Ops -- so Star Wars fetched the weakest card in the
  pile, and the gate rejected the terms for it.

All decisions use only `Observation`; history is currently ignored. The event
sandbox is constructed from public fields with an independent fixed RNG and
empty unknown hands/deck. Every event that does not depend on hidden cards
is simulated there (`PUBLIC_EVENTS`). The live engine, its private decision stack,
its RNG state, and the opponent's hidden cards are never copied or inspected.
The actual action always comes from the offered legal options.

## Where the evaluation lives

The terms above are pure functions in `bots/strategic/evaluator.py`. Each one is a
function of its arguments alone: no `self`, no `Observation`, no `RULES`
lookup, no memo, so the same arguments always give the same float.
`StrategicPlayer` keeps the policy -- which observation is in play, what to
search, how to rank -- and calls them.

Two pieces of data carry what the terms need.

- **`Terrain`** is the map: adjacency, stability, battlegrounds, regions and
  the rules constants derived from them. It never changes, so it is built
  once per process. Countries are indices into `data/countries.json` order,
  and neighbours are sorted by name so that a sum cannot change with
  `PYTHONHASHSEED`.
- **`Position`** is one board's influence plus the vectors the terms would
  otherwise recompute constantly: control per country, reachability per side,
  and the neighbour counts reachability needs. `Position.place` keeps all
  three correct after one country changes, in time proportional to that
  country's neighbours.

Scoring urgency is the third input, passed as a vector. It depends on the
observation and never on the board, so `prepare` computes it once per
decision instead of memoising it country by country mid-search.

The scoring overrides are the fourth, and they are *not* a vector: they read
control, so `region_vp` takes them per call as index sets, and
`board_value` takes a region-keyed map of them. `None` and an empty map mean
what an unmodified board means, which is why every caller that does not know
about Formosan Resolution or Shuttle Diplomacy is unaffected.

**The one rule.** `StrategicPlayer.board` and `StrategicPlayer._position`
describe the same position, and every write goes through `_set_influence` or
`_add_influence` (or through `prepare`, which reloads both). A write straight
into `board.influence` leaves the snapshot describing a board that no longer
exists. `STRUGGLER_CHECK_SNAPSHOT=1`, or setting `strategic.CHECK_SNAPSHOT`,
makes every `delta` inside a ranking rebuild the snapshot from the board and
compare; two tests use it to pin the write sites, in `test_strategic.py` and
`test_rollout.py`. Outside a ranking `delta` re-reads the board itself, so the
diagnostic entry points (`country_value`, `region_score`, `region_margin`,
`value`) stay correct for callers that write to the board directly.

**Reusing a basis.** Every whitelisted event at one decision starts from the
same board, so the sandbox values that board once and re-values only what the
event moved. What it moved is not the set of countries whose influence
changed: `country_value` reads out to `evaluator.VALUE_RADIUS` hops, because
`access` walks a neighbour's neighbours and then asks whether *those* are
reachable. The radius lives beside the terms that set it, and
`test_value_dependents_covers_every_country_a_change_can_move` moves one
country and checks that nothing outside the claimed set moved with it.

**One scoring implementation.** The engine no longer has its own: region
scoring is `Board.score_region`, with the per-scoring overrides from
`Board.scoring_overrides`, and `Engine._score_region_net` adds only the two
things that are the engine's business -- which events are in force, and the
Europe Control automatic victory, which has no VP for either implementation
to return. `Board.region_bonus_vp` is gone with it; it existed to let the
engine assemble a score out of parts `score_region` already assembles.
`evaluator.region_vp` remains a second implementation, in index space and on
purpose, and `test_region_vp_matches_the_engine_under_every_scoring_override`
holds it to the first over every combination of overrides. `region_tier` is a
third partial one, kept because callers want the tier itself; a corpus test
pins it to `score_region` too.

This structure exists because the evaluator twice shipped a memo keyed on
less state than the terms actually read. `_access` reads influence two hops
out but was memoised on `(board, cid, side)`, so a trial placement in a
neighbour left it stale, and the same position scored differently depending
on what had been evaluated first: 39 of 598 corpus rankings changed when the
memo was bypassed. A function that owns no state cannot do that.

## Evaluate and train

Evaluation plays both seats on every seed, with events enabled. Identical seeds
pair the initial shuffle; later dice consumption can diverge with the policies.
The report includes per-game records, scores by side, and a standard error
computed over seed pairs. A draw counts as half a point.

```sh
python -m struggler.bots.train evaluate --pairs 20 --seed 1000 \
  --model models/strategic-v1.json --report evaluation.json
python -m struggler.bots.train evaluate --opponent random --pairs 20 --seed 1000
python -m struggler.bots.train evaluate --opponent strategic --pairs 20 --seed 1000

python -m struggler.bots.train train --seed 200 --pairs 8 \
  --generations 4 --population 4 --workers 8 \
  --fields scoring_discount,scoring_hand --output my-model.json
python -m struggler.bots.train evaluate --opponent strategic --pairs 16 \
  --seed 4000 --model my-model.json --workers 8
```

Training mutates the positive evaluation weights using seeded log-normal
noise and selects by terminal game score, evaluating the incumbent and each
mutation on the same paired seeds. The opponent is a frozen **anchor**: by
default the initial weights playing as the strategic bot, so every
generation's score means the same thing and the search cannot drift toward
a moving target. `--anchor greedy` keeps the older, weaker opponent; since
the DEFCON survival planner the strategic bot scores 1.00 against greedy on
a 16-seed baseline, so greedy no longer discriminates between candidates.
`--fields` restricts mutation to named weights (for example the two
scoring-card urgencies). Ties retain the incumbent. Each generation saves
its checkpoint and a trace with the selected weights. `--model` can
initialize a new run from an existing checkpoint; it does not restore an
earlier optimizer RNG.

Cost is `2 * pairs * population * generations` complete games, spread over
`--workers` processes. Use evaluation seeds outside the entire training
range (`seed` through `seed + pairs * generations - 1`). Increasing training
volume does not guarantee improved performance against people or unseen
policies. Compare checkpoints against several opponents before adopting
them. The `strategic` evaluation opponent uses handcrafted defaults unless
`--rival` names a checkpoint.

## Measured results

The supplied policy won **34 of 40 games (85%)** against `GreedyPlayer` on
held-out seeds 1000–1019, each played from both seats, with events enabled:

| Seat | Wins | Games |
| --- | ---: | ---: |
| US | 14 | 20 |
| USSR | 20 | 20 |

The paired-seed standard error is about 5.3 percentage points; this is a small
benchmark against one relatively weak opponent. Full game outcomes are in
[`models/strategic-default-evaluation.json`](../models/strategic-default-evaluation.json).
The greedy baseline includes the Europe-control scoring crash fix supplied
with this change.

The included checkpoint was produced with `--seed 200 --pairs 4
--generations 2 --population 3` (48 games). Neither generation found a strict
improvement, so it **retains the handcrafted weights**; its training trace is
stored in the checkpoint. Therefore the benchmark above also describes the
checkpoint's identical policy. This run validates the training pipeline; it
does not demonstrate that learning improved playing strength.

Validation: 392 tests passed, 3 skipped, including tactical regressions,
observation non-mutation, deterministic paired games, and model serialization.

## Hand survival

`bots/strategic/defcon.py`'s `DefconPlanner` is the tactical guard in front of every
VP score. `StrategicPlayer.safety_key` ranks each legal option by a tuple:
certain immediate defeat first, then -- for scores in raw board units -- the
residual turn-loss risk priced *into* that score rather than ranked ahead of
it (the middle element is a constant there; it still carries the risk for the
ad-hoc scales). So a card play, play mode, headline, event choice, or trap
discard that leaves the hand unable to survive the turn is charged what that
costs, and certain defeat loses to any option that is not, regardless of
country value.

The planner is a memoised search over the observation only, never hidden
state: the state is (hand, rounds left, DEFCON, Space Race box and
attempts, China Card, trapped). Each of our rounds tries every card and
mode the engine would offer (Ops, event, Space Race, UN Intervention),
firing an opponent card's event on Ops exactly as the engine does. Between
our rounds a chance node applies `SurvivalPrior`:

- `opponent_lowers_defcon` (flat default 0.75) while DEFCON is above 2;
- `opponent_hand_attack` (flat default 0.10) that an Aldrich Ames,
  Terrorism, Grain Sales, or Missile Envy removes one of our safe cards,
  chosen adversarially so a plan with no spare safe card is charged for it;
- `unknown_chain_loss` and `replacement_hazard` for cards the search
  cannot see (Five Year Plan's random target from the US side, Missile
  Envy, Ask Not's replacements).

Those two probabilities are learned, not hand-set, when a checkpoint is
configured. `bots/opponent_model.py`'s `OpponentModel` is a two-head
network (one tanh hidden layer, sigmoid outputs, standard library only)
over public `Observation` features: turn, round, rounds left, DEFCON, hand
sizes, the unseen-card share, each side's military-ops deficit, whether
the opponent is trapped or Red-Scared, Iranian Hostage Crisis, and the
public status (hand / unseen / discard / removed / not yet in the deck) of
each attack card. Its labels are real: replaying a recorded game, each
headline or action-round pick becomes a row labelled with whether a card
held then was gone from the hand at that side's next pick (removals by the
side's own decisions do not count) and whether DEFCON fell on an
opponent-attributed step in between. Whole games stay in one of the
train/validation/test splits. Train it from the checked-in logs and use
it with `STRUGGLER_OPPONENT_MODEL`:

```sh
python -m struggler.bots.opponent_model --logs 'logs/game-check/*.json' \
  --output models/opponent-model-v1.json
STRUGGLER_OPPONENT_MODEL=models/opponent-model-v1.json \
  python src/main.py --us strategic --ussr strategic --seed 1
```

`DefconPlanner` swaps the two flat prior values for the model's
predictions per observation (`StrategicPlayer(opponent_model=...)`, also
accepted by `EventValuePlayer`); the report next to the checkpoint gives
log-loss and Brier score per head against the base-rate predictor and a
calibration table on held-out games. The flat defaults remain the
fallback without a checkpoint. A model trained on bot-vs-bot logs learns
those bots' habits, so retrain it when the bots change. In particular the
checked-in checkpoint's hand-attack head is a base rate below 1% because
these bots almost never event Grain Sales, Aldrich Ames, or Terrorism;
strong humans always event the first two and event Terrorism whenever
behind or holding Iranian Hostage Crisis
([DEFCON_STRATEGY.md](DEFCON_STRATEGY.md#hand-discard-effects-traps-and-modifiers)).
Against humans prefer the flat prior, or a model trained on human logs.

Two decisions outside the card play itself are also priced. A
battleground coup (`coup_survival_risk`, used for the Ops-type choice and
the coup target) is evaluated by the hand's survival at the lowered DEFCON
with our influence added to the target, because a won coup hands the
opponent's CIA Created or Lone Gunman a place to coup back; a non-
battleground coup costs nothing. A headline pick (`headline_pick_risk`)
weighs the chance the opponent's higher-Ops headline resolves first and
lowers DEFCON before ours fires, so a 1-Ops suicide card is not a "safe"
headline at DEFCON 3. Our own revealed, still-pending headline
(`Observation.headline_pending`) is a forced event ahead of the action
rounds in every evaluation made during the opponent's headline.

Card-specific transitions cover DEFCON raisers, Ask Not, Aldrich Ames,
Five Year Plan, Salt Negotiations' retrieval, Blockade and Latin American
Debt Crisis (pay a 3+ Ops card with no event, or refuse), and self-trapping
with Quagmire/Bear Trap, after which each round discards a 2+ Ops card
without an event and rolls 1-4 to escape. `discard_risk` prices a mid-play
discard (Blockade's choice, a trap step) with the current round already
spent; `event_risk` prices a single event firing now, including the
opponent-granted coups of CIA Created, Lone Gunman, Grain Sales, Tear Down
This Wall, and Ortega. A hand with no hazardous card short-circuits to zero
risk; a search over `max_states` states falls back to a conservative count
of safe cards versus rounds and is reported in the diagnostic log.

The strategy behind these rules is [DEFCON_STRATEGY.md](DEFCON_STRATEGY.md);
`tests/test_defcon_planner.py` pins each transition and the seed 2400
(headline), 2401 (Blockade), and 2402 (coup target) regressions from
`logs/game-check`; all four of the 2400-2403 strategic-vs-strategic games
that ended in nuclear war now end on VP or final scoring.

## Limits

This is a bounded tactical policy, not full-game minimax, MCTS, or deep RL.
Influence search invests in one country at a time and uses average value per
operation; it does not search every allocation across multiple countries.
Operations-type evaluation estimates future placements from current
reachability; the engine's offered actions remain authoritative for each
actual placement. Its regional evaluator approximates special scoring modifiers,
although scoring-card and Wargames decisions use the engine's scoring code.

Events that need hidden cards (`HIDDEN_INFO_EVENTS`) use rough
allegiance/ops-based estimates, events whose only effect is a flag value 0,
and unhandled event branches tie-break to the first legal option. Long-term event
flags are only partially valued. Hand survival is a bounded search with
fixed priors: it does not track which attack cards the opponent actually
holds, model the opponent's regional play, or value the board damage a
refused Blockade costs against the risk it avoids. Its safety heuristics
are not a guarantee against every nuclear loss. Strength against the supplied baselines is evidence of an improvement,
not evidence of expert human-level play.

## Experimental MCTS prototype

`mcts` searches at an ordinary action-round card pick when its own hand
contains a scoring card; other decisions use the strategic policy. It is
opt-in and does not change the `strategic` default.

```sh
STRUGGLER_MCTS_SIMULATIONS=24 \
  python src/main.py --us mcts --ussr strategic --seed 3003 --no-game-log \
  --log-level INFO --log-file mcts.log
# Optional soft wall-time limit, checked between complete simulations:
STRUGGLER_MCTS_SIMULATIONS=100 STRUGGLER_MCTS_SECONDS=1 \
  python src/main.py --us mcts --ussr strategic --seed 3003
```

`MCTSPlayer(seed=0, simulations=24, max_steps=256, time_limit=None)` runs
UCT over our card-play macros, with strategic opponent responses. A macro
is a card with either strategic continuation or an instruction to invest
in one reachable, uncontrolled BG in a region we hold scoring for. It
considers the top three survival-safe cards, additional safe scoring cards,
and up to two BG targets per non-scoring card. Targeted continuations prefer
Ops, influence, then that country until controlled; every atomic action
must still be legal and tie the best strategic survival ranking. The same
continuation is used when executing a selected macro in the real game.
Events and the opponent's moves resolve through the strategic policy.

Each simulation samples the unknown hand and deck from public inventory
counts, with its own RNG, and advances to turn end (including military-Ops
penalties), terminal game state, or the atomic-step cap. The engine is
constructed from `Observation` at a card boundary, never cloned from the
live game. Tree nodes are keyed by our observation, excluding decision IDs;
no opponent-hand or deck identities enter that key. Each actor's rollout
policy receives only its own observation. This is a small information-set
UCT prototype against a fixed opponent policy, not full adversarial ISMCTS.
Hidden-card sampling is uniform and does not condition on behavioral history.

The leaf return is explicitly **banked VP plus remaining board potential**:
`weights.vp * signed_engine_vp + strategic.value(board, side)`, transformed
with `tanh(value / 100)` and clipped to ±0.99. Actual terminal wins/losses
return ±1, draws 0. Regional board potential is a heuristic for future
scoring, not a replacement for points already scored. A regression holds
the final board identical while changing scoring order and checks that the
banked-VP difference changes the search return.

### Rollout policy

Below the root every decision -- our own micro-decisions after a card
pick, and the whole of the opponent's play -- is answered by
`bots.rollout.RolloutPolicy`, a `StrategicPlayer` subclass that trades
foresight it does not need for speed. The sampled sandbox holds every
card, so a suicide inside a rollout costs that simulation the loss the
tree can see; what the full policy spends most of its time on buys little
there. Profiling a 24-simulation search at seed 3003 T1 AR1 put 91% of
the time in the rollout policy's rankings: Ops-type 43%, card picks 29%,
coup targets 12%, influence points 8%. The cheap policy keeps the parent's
scores and changes four things:

- **Immediate-only survival guard.** `ImmediatePlanner` is the DEFCON
  planner with no lookahead: a card is refused when firing it *now* loses
  (an opponent DEFCON reducer at DEFCON 2 with no space escape), and coup
  risk is the certain loss only. The probabilistic whole-hand search runs
  only at the root, where the real decision is made.
- **One plan per card play.** Scoring an Ops-type option already finds the
  best country for it; the winning type's target is remembered and served
  at the following coup or realignment decision without re-ranking. The
  first influence-point decision plans the whole spend (each country's
  best point count committed at once, then re-planned for the remainder)
  and later points are served from that plan while they stay legal.
- **Rankings cached by information key** for the life of one search, so
  the root moves' own micro-decisions, repeated by every simulation, are
  ranked once. Hit counts (`hits`, `misses`, `served`) are on the policy.
- **Cheaper plumbing**, shared by the full policy: boards share the static
  adjacency map, enum members hash by identity, region starting scores are
  memoised per ranking, sandboxes copy effect state without `deepcopy`,
  and one helper policy plays every simulated event's placements.

The root still uses the full `StrategicPlayer`, and the macro chosen by the
search is executed in the real game through the same cheap continuation
that the rollouts used, so the executed play is the one that was searched.

Measured on the same position (CPU seconds, 24 simulations): 1.9 s before,
1.13 s with the rollout policy, 0.8 s with the plumbing changes. Root move
values changed with the policy switch (the rollouts play differently), and
were identical across the plumbing changes.

`last_search` and INFO logs report simulations, node count, elapsed seconds,
truncated simulations, and each root macro's visits and mean return. Fixed
simulation counts are reproducible for a given bot seed and observation;
time-limited results depend on machine speed. Very small budgets can leave
some root macros unexplored. The time limit is soft: one simulation can
overrun it. Search trees are discarded after each card decision.

Scope: standard events-enabled games, including optional cards when their
presence can be inferred from the inventory. Unsupported/inconsistent
inventories or ambiguous extra-round cursors fall back to strategic with an
INFO message. Mid-event and headline search, Ops-only simulations, learned
rollout policies, opponent search, and general multi-country allocation are
not implemented. A bounded rollout can stop before scoring; the diagnostic
`truncated` count exposes this. Passing tactical regressions establishes
correct plumbing, not an improvement in tournament strength.

Initial validation: 465 tests passed, 3 skipped. A seed-3003 game with US
`mcts` at 24 simulations against USSR `strategic` completed with a USSR win.
The 12 searched card decisions took a median 5.00 seconds and maximum 11.43
seconds on this workspace (other validation work ran concurrently); none
of the rollouts hit the step cap. The US selected Pakistan investment
macros on turn 1 AR3 and AR4 and scored Asia at -5 on AR5. This is a smoke
measurement, not a paired comparison or evidence of a strength gain.

### Profile-guided speed improvements

Strategic evaluation now caches country values (including event sandboxes)
and map access terms for one decision, reuses region membership, and skips
regional rescoring when a hypothetical influence change leaves control
unchanged. Realignment evaluates each distinct dice margin once while
retaining the original summation order. Influence observations copy both
mapping levels directly; their integer leaves need no recursive deepcopy.
MCTS information keys freeze public fields directly instead of deep-copying
a dataclass and encoding JSON. Simulation count, safety policy, rollout
horizon, and VP-inclusive returns are unchanged.

Three alternating before/after runs on saved seed-3003 positions measured:

| Workload | Before (median) | After (median) | Speedup |
| --- | ---: | ---: | ---: |
| Rank 150 strategic decisions | 0.900 s | 0.627 s | 1.44x |
| First US card pick, 24 MCTS simulations | 4.472 s | 2.772 s | 1.61x |

All legal-action rankings and root MCTS move values matched exactly across
these comparisons. These are local microbenchmarks, not a full-game timing
or playing-strength claim. Measurements are saved in
`logs/game-check/mcts-speed-comparison.json` (gitignored evidence).

**Profiling the workload the gate actually runs**, rather than saved
positions, found the two largest costs outside the evaluator entirely.

- `Board.serialize` deep-copied the influence mapping. Influence is exactly
  `dict[str, dict[str, int]]`, so a nested comprehension is what
  `copy.deepcopy` produces and 15x cheaper. The event sandbox forks engines
  by serializing them and forks again per die face, so this ran 1278 times
  a game. `Observation` had already been fixed this way; `serialize` had
  not.
- The event basis valued all 85 countries, then 10 regions, then 10
  margins, through the diagnostic entry points -- each of which builds a
  `Position` for the board it is handed. That is 105 full snapshot rebuilds
  of one unchanging board, quadratic in the map for a walk that is linear.
  Those entry points now take an optional snapshot, and the basis builds
  one.

Both are behaviour-neutral, and the parity corpus is the oracle that says
so. Eight full benchmark games (seeds 4000-4003, both seats, three
repetitions, no MCTS), run in both orders to cancel the drift that makes
whichever revision goes first look better:

| Order | Baseline | Candidate | Speedup |
| --- | ---: | ---: | ---: |
| Baseline first | 65.39 s | 61.57 s | 1.06x |
| Candidate first | 66.65 s | 57.70 s | 1.16x |
| Position-matched, first slot | 65.39 s | 57.70 s | 1.13x |
| Position-matched, second slot | 66.65 s | 61.57 s | 1.08x |

About 1.1x. The profile implied nearer 1.2x, and the gap is the profiler:
`cProfile` charges per-call overhead, so it overstates a function called
678,000 times. Read a profile for *where* the time goes and a stopwatch for
*how much*.

**The gate stops when the answer is in.** Both samples now run in one worker
pool (`--seeds` with `--held-seeds`), so the slowest game's tail is paid
once rather than once per sample, and the seeds alternate between the two
groups so a run that stops early has played some of each. With `--decide`,
after each finished seed the gate asks whether the seeds still unplayed
could change the verdict: the unplayed ones are resampled from the played
ones, and it stops when the verdict survived every draw but 1%. Resampling
covers nuclear losses as well as scores, because stopping early can only
*miss* a failure, and the games not played are exactly the ones that might
have carried the second loss. `GATE_DECIDE=0` plays everything.

Each unplayed seed is drawn from its own sample, never from the two pooled.
The samples exist because the tuning seeds are the ones a change was
selected on, so they score better by construction; letting one stand in for
an unplayed held-out seed would make the rule optimistic in exactly the way
the split guards against. The gate exhausts the smaller tuning range first,
so every seed unplayed at the decision point is a held-out one, which is
what makes the distinction bite rather than a formality. `draw_unplayed` is
separate from `stable_verdict` so a test can check that property directly
instead of inferring it from a verdict.

What this is: curtailment, predicting the full run's verdict, rather than a
test spending its own error budget early -- which is why it never makes a
rejection more likely, only an acceptance sooner. Its blind spot is the
bootstrap's: resampling cannot produce a seed score it has not seen, so a
sample with no spread predicts no spread with false certainty, and a run of
identical dead heats is exactly that. The evidence floor is the bound on it.

The rule cannot fire before the 150-game evidence floor, which is what
bounds the saving: replaying the 14 gate reports under `logs/game-check`
seed by seed, it saves 17.3% of the full games and changes no verdict. The
floor is doing most of the work here -- at a floor of 100 the saving is 31%
but one of the 14 verdicts flips, which is why the floor stays where it is.
Deterministic curtailment (stop only when no possible remaining result
could change the verdict) is exact but saves just 6%, because one seed can
swing the mean a long way.

**A rules change to the engine is not gateable for strength.** Only
`src/struggler/bots` is snapshotted; the engine is shared on purpose, as the
arbiter both sides are measured under. So a commit that touches no bot file
puts byte-identical players on both sides of every game and returns exactly
0.500 -- not because the change is neutral, but because both sides play
under the same new rules, which makes a rules fix symmetric by construction.
`gate.sh` now says so up front when the diff touches no bot file, because
"ACCEPTED, 0.500" is otherwise easy to read as evidence. Such a run is a
crash-and-nuclear-loss smoke test; the rules tests are what validate the
change.

The verdict arithmetic itself now lives in `benchmark.verdict`, which
`acceptance` reports and `stable_verdict` asks about a resampled future, so
a rule cannot mean one thing when the gate reports it and another when the
gate stops early on it. `acceptance` asserts the two agree.

For the weight-by-weight removal candidates, policy/leaf distinction, and
proposed ablations, see [Strategic simplification audit](STRATEGIC_SIMPLIFICATION.md).
