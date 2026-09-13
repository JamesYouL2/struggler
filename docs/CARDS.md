# Cards and the event layer

## Card data policy

The factual data this project needs — each card's Ops value, side
(US/USSR/Neutral), deck (Early/Mid/Late War), and remove-after-event flag
— are facts about the published board game, not any particular expression
of them. They were re-entered independently, with the physical card text
and GMT's published card list as the source of truth, and are stored in
`src/struggler/data/cards.json`. Cite the physical game as the source in
comments and docs.

A reference implementation (`glowsplint/twilight-struggle-py`) exists and
may be consulted for cross-checking only. It carries no license — all
rights reserved by default — so no file or code from it may be copied.
Card mechanics here are designed against mandates #1–#2 (decisions and
actions), never adapted from that project's single-action model.

Each card entry also carries `event_summary`: a short, hand-maintained
paraphrase of what `events.py` actually does mechanically for that card,
used by the LLM bot's prompt, and `null` for a card with no implemented
event. Unlike the other fields, this one is *not* a fact about the physical
game — it is engine-derived documentation of `events.py`'s behavior, kept
in `cards.json` because it belongs with the rest of a card's data. It can
drift from `events.py`; there is no automated sync check (see
[LIMITATIONS.md](LIMITATIONS.md)).

## Difficulty tiers

Events were introduced in increasing order of implementation difficulty,
and the tiers remain a useful taxonomy for reasoning about a card:

1. **Pure state change** — an immediate, unconditional board effect.
2. **Player-choice** — the event enqueues a new decision for a player.
3. **Persistent modifiers** — the event changes future legality or scoring,
   for the rest of the turn or the rest of the game.
4. **Rule-modifying** — the event changes how other rules or cards
   themselves resolve.

A card is not considered done until it has a replay-log regression test
(see [TESTING.md](TESTING.md)).

## Framework

- **Registry.** `src/struggler/engine/events.py` maps a card id → an
  `Event` (`resolve(engine, side)`, plus an `eligible` predicate for
  preconditions). A card *absent* from the registry has no event: with the
  event layer on it is a no-op discard. This is what lets the deck grow
  card-by-card without touching the game loop.
- **Firing paths (mandates #1–#2).** An event fires when its owner (or a
  NEUTRAL card's player) plays it as its event; and — per the core rule —
  when the **opponent's** card is played for Ops, its event *also* fires,
  with the phasing player choosing the order via an `EVENT_OPS_ORDER`
  decision (`event_first`/`ops_first`). Ordering is implemented on the
  decision stack itself: an `EVENT_RESUME` marker is slipped beneath the
  first half's sub-decisions so the second half runs only after they drain.
  Dice inside events are logged `WAR_ROLL` CHANCE decisions, never silent
  `random` calls (mandate #3).
- **Headline firing.** Non-scoring events fire during the headline too.
  Headline resolution is stack-driven: both cards are chosen, their order
  is frozen (higher Ops first, ties US-first) into `_headline_pending`, and
  each card resolves in turn — if its event enqueues sub-decisions those
  drain before the next headline card resolves, the same interrupt order
  the action-round path uses. `serialize()` carries
  `headline_resolving`/`headline_pending`.
- **Player-choice steps.** An event that lets a player distribute influence
  enqueues its own decisions through two generic, fully serializable step
  types: `EVENT_INFLUENCE` (place / remove / remove-all one country at a
  time, for N steps, honouring a per-country cap, a control filter, and an
  "uncontrolled only" filter; it re-pushes itself until N hits 0 or no
  legal target remains) and `EVENT_CHOICE` (a branch, e.g. Warsaw Pact's
  "remove or add", routed by `events.CHOICE_ROUTERS` so the stack stores
  only the event id and the chosen option — never a function). These steps
  live on the same decision stack, so they are hosted correctly inside a
  headline or an opponent's Ops play.
- **China Card bonus.** Playing the China Card for Ops grants its +1 ("all
  Ops used in Asia") for influence (an all-or-nothing invariant in the
  placement step: the 5th point is offered only while nothing has gone
  outside Asia), for coups (+1 Op and +1 military Op against an Asian
  target), and for realignment (one extra roll, offered only while every
  attempt this Ops-spend has targeted Asia — the same all-or-nothing rule,
  in `_maybe_push_realignment_target`).

## Coverage

Every non-scoring card in the deck has an implemented event: 100 registered
in `EVENTS`, plus Defectors via the headline hook and UN Intervention via
its rule-modifier play mode. The trickier ones have a dedicated unit test;
the loop as a whole is covered by a property test and the `events.json`
golden replay.

Remaining work is fidelity, not coverage — see
[LIMITATIONS.md](LIMITATIONS.md).

### Grouped by the primitive each card reuses

**Immediate fixed board/VP/DEFCON/Space effects.** Duck and Cover, Fidel,
Nasser, Romanian Abdication, De Gaulle Leads France, Captured Nazi
Scientist, Nuclear Test Ban, Allende, Portuguese Empire Crumbles, Panama
Canal Returned, Sadat Expels Soviets, John Paul II Elected Pope, Camp David
Accords, Iranian Hostage Crisis, The Iron Lady, An Evil Empire, U-2
Incident, Cultural Revolution, Kitchen Debates, OPEC, Alliance for
Progress, Reagan Bombs Libya, One Small Step (which withholds VP for the
first of its two Space Race steps, scoring only the second), AWACS Sale to
Saudis.

**War family** (attacker chosen, seeded CHANCE roll). Korean War and
Arab-Israeli War have fixed targets; Indo-Pakistani War, Iran-Iraq War and
Brush War let the attacker pick via `WAR_TARGET`. The roll is -1 per
defender-Controlled country adjacent to the target, and the defender's own
superpower space counts as one of those (rule 2.1.5, and see
docs/RULES_SOURCES.md): a US Brush War on Afghanistan or a USSR one on
Mexico is a point harder than the neighbours alone suggest. Military
Operations come from the Event text, not the card's Ops value (8.2.3), and
go to the card's own side even when the opponent played it for Ops
(8.2.4).

**Events that conduct Operations** (`push_event_operations`). CIA Created,
Lone Gunman, ABM Treaty. Glasnost (4 Ops if The Reformer is active) and
Soviets Shoot Down KAL-007 (4 Ops if the US controls South Korea) restrict
those Operations to Influence/Realignment, never Coup.

**Free operations confined to a region** (`push_free_coup_or_realign`,
`push_free_realignment`). Ortega Elected in Nicaragua (a free Coup against
a Nicaragua neighbor), Tear Down This Wall (a free Coup or Realignment in
Europe), Junta (place 2 Influence in a single Americas country, then
optionally a free Coup or Realignment there — the free-op choice is stacked
beneath the placement so it resolves afterwards), Special Relationship (2
VP while the US controls the UK, plus a free Realignment roll if NATO is
also in effect). Because the card itself names the region, these free
attempts ignore 8.1.5's DEFCON-by-region restriction (`_usable_coup_realign_target`'s
`ignore_defcon=True`, per the official FAQ) — Tear Down This Wall still
offers a free Coup/Realignment in Europe even at DEFCON 3 or 4. A
Battleground Coup there still degrades DEFCON as normal; that is a
separate check in `_handle_coup_roll`, untouched by this.

**Forced random discard** (`RANDOM_DISCARD`, a seeded CHANCE decision that
reveals only the drawn card). Five Year Plan (a discarded USSR event
fires), Terrorism (opponent discards, twice after Iranian Hostage Crisis).

**Per-turn coup/realign modifiers.** Nuclear Subs (US Battleground coups
skip the DEFCON degrade — on top of the base rule that only Battleground
coups degrade DEFCON at all), Latin American Death Squads (±1 to Americas coup
rolls), SALT Negotiations (−1 to both sides' coups), Iran-Contra Scandal
(−1 to US realignment via `_realignment_modifier`), Chernobyl (a region
chosen by the US bars USSR Ops influence, via `_chernobyl_blocks`). How I
Learned to Stop Worrying takes the set-DEFCON branch (`set_defcon` plus 5
military Ops).

**The Military Operations track stops at 5** (`_add_military_ops`,
`rules.json` "military_ops_max"), because the printed track has no square
above it and Ops past the top are simply not recorded. Every advance goes
through that method -- coups, the region bonus, How I Learned to Stop
Worrying. It was unbounded, and 19.5% of side-turns in a sample of
benchmark games ended above 5. The end-of-turn requirement is unaffected,
since it only asks whether a side fell short of DEFCON and DEFCON never
exceeds 5; the consequence is Arms Race, which compares the two sides'
positions, and read eight against five as a lead where the board shows a
tie at five.

**Conditional riders paid elsewhere.** U-2 Incident gives the USSR 1 VP and
1 more if UN Intervention is played as an event later that turn
(`turn_effects["u2_incident"]`, paid in the `un_intervention` play branch
beside the We Will Bury You rider that branch already defused). Either side
playing UN Intervention pays it, since the card names none, and the flag
lapses with the turn.

**Persistent game-long triggers** (`game_effects`). Yuri and Samantha (USSR
+1 VP per US coup, in `_handle_coup_roll`), Flower Power (USSR +2 VP per US
war-card play, via `_maybe_flower_power`, cancelled by An Evil Empire).

**Dice contests** (`push_dice_contest` — both roll, higher wins, logged as
`CONTEST_ROLL`). Olympic Games (opponent boycotts, or a +2 contest with
ties rerolled), Summit (regional-domination modifiers, winner takes 2 VP
then adjusts DEFCON; ties are *not* rerolled here), Wargames (only at
DEFCON 2: give the opponent 6 VP and final-score the game).

**Reclaim from the discard pile** (`push_take_from_discard`). SALT
Negotiations (also DEFCON +2) — the player takes one non-scoring card from
the public discard back to hand.

**Revealing or taking cards from the opponent's hand.** The reveal is
sanctioned by the card, so surfacing the involved cards as decision options
is correct, not a leak. Aldrich Ames Remix (USSR discards a chosen US
card), Grain Sales to Soviets (one random USSR card revealed via a CHANCE
step; the US plays it in full — Event or Ops, via
`Engine.push_full_card_play` — or returns it for 2 Ops of its own, and an
empty USSR hand grants the US 2 Ops directly), Ask Not… (discard any own
cards and redraw as many, via `draw_cards_to_hand`; *scoring cards
included* — the illegal act is holding one, not discarding it, and dumping
a scoring card that would score for the opponent is much of the card's
value), The Cambridge Five
(place in a region whose scoring card the US holds; blocked during Late
War).

**Per-turn regional Ops bonus.** Vietnam Revolts generalizes the China
Card's all-in-region +1 into a reusable "bonus region" (`_ops_bonus_region`
/ `_in_bonus_region`): the China Card is `"asia"`, Vietnam Revolts sets a
turn effect giving USSR plays `"se_asia"`.

**Player-choice influence** (`EVENT_INFLUENCE`). COMECON, Marshall Plan,
Decolonization, Suez Crisis, Truman Doctrine, Warsaw Pact Formed (branch),
Socialist Governments, Muslim Revolution, Colonial Rear Guards, Liberation
Theology, The Voice of America, Puppet Governments, OAS Founded, Pershing
II Deployed, The Reformer, Solidarity, Marine Barracks Bombing, Independent
Reds (match-influence branch), East European Unrest and South African
Unrest (which use `push_event_influence`'s per-selection `amount` for the
Late-War 2-per-country removal), De-Stalinization (a relocate flow: remove
up to 4 USSR Influence, then replace it in non-US-controlled countries, max
2 each).

The map is the 84 countries of the standard board. The Chinese Civil War
space belongs to the optional variant in rulebook section 12, which this
engine does not implement; it was in `countries.json` as a plain Asian
country, so it scored (rule 12.1 says it "does not affect any scoring
card") and the US could use it (12.1 forbids that outright). Removed.

**Region Ops bonuses** (`_ops_bonus_region`, `_bonus_ops`). The China Card
earns +1 Op if every Op is spent in Asia; a USSR play under Vietnam Revolts
earns +1 if every Op is spent in South East Asia. A play can carry both --
the USSR's China Card under Vietnam Revolts -- and because South East Asia
is inside Asia, Ops spent entirely there satisfy each condition and earn
both points. That makes the China Card a 6-Ops card, and it is the only way
to reach 6: Containment and Brezhnev cannot add to it, since their ceiling
of 4 applies before these bonuses. The engine used to give China precedence
and drop the other, calling the stack rare and unmodelled; it is a standard
USSR line.

The two lapse independently, so `bonus` is a tuple of region tags and
`non_bonus` the spend that has strayed outside each one. A China Card play
that leaves South East Asia for the rest of Asia forfeits Vietnam Revolts'
point and keeps China's: 5 Ops, not 6 or 4. The same all-or-nothing rule
applies to influence (`_bonus_influence_options`), coups (a South East
Asian target under both earns +2 Ops and +2 military Ops) and realignments
(one extra attempt per intact bonus). A context with no bonus is still
written as `None`/`0`, and `_decode_context` reads the older single-tag
shape, so recorded states and the parity corpus stay comparable across the
change.

**Persistent per-turn modifiers.** Containment, Brezhnev Doctrine, Red
Scare/Purge — consulted via `_effective_ops`, cleared at end of turn. Both
printed bounds apply: Red Scare "to a minimum of 1", Containment and
Brezhnev "to a maximum of 4". Only the floor used to be implemented, so a
4-Ops card under Containment was worth 5. The arithmetic is
`core.effective_ops`, which the bot's `_effective_ops_estimate` calls rather
than copying — it was a copy, and both copies were missing the ceiling. The
"+1 Op if every Op is spent in this region" bonus (the China Card in Asia,
Vietnam Revolts in South East Asia) is not one of these and is not capped by
it: the engine adds it later, at the placement or coup step, so the China
Card under Containment is 4 Ops and 5 in Asia, not 6.

**Persistent game-long legality** (`game_effects`). NATO (eligible only
after Marshall Plan or Warsaw Pact; the USSR may no longer coup, realign,
or Brush War US-controlled Europe, via `Board.nato_protects`), De Gaulle
and Willy Brandt (each lift NATO for one country), US/Japan Mutual Defense
Pact (locks Japan), The Reformer (bars USSR coups in Europe). Enforced in
`_usable_coup_realign_target`, which distinguishes coup from realignment
for The Reformer, and consulted by both target enumerations. Eligibility
flags also gate Arab-Israeli War (Camp David), Socialist Governments (Iron
Lady) and Solidarity (John Paul II).

**Rule-modifiers.** UN Intervention — a `un_intervention` play mode that
spends the held UN Intervention card to use an opponent's event card for
Ops with its event cancelled. The partner card need only be
opponent-associated: the mode is offered "regardless of whether the Event
can occur or not" (FAQ card #32), because spending UN Intervention is also
how the US cancels We Will Bury You, and pairing it with a Soviet event
that happens to be dead is a real line. UN Intervention
itself has no standalone event, so `_play_modes` excludes it from the
`"event"` mode (alongside the China Card) when it is the card being
played directly — it is Ops-only in that case, and the combo only
triggers via the `un_intervention` mode offered on the *other* card.

**Take-and-play from a hand or the discard pile.** Missile Envy
(`missile_envy_take`/`missile_envy_use` — take the opponent's highest-Ops
card, opponent breaks ties; use it for Ops, or its Event when it is neutral
or the taker's own; Missile Envy itself passes to the opponent's hand,
which must spend its next action round playing it for Ops, via
`game_effects["missile_envy_forced"]`), Star Wars (`play_card_from_discard`
— eligible only while the US leads the Space Race; take a non-scoring
discard and fire its event now).

**Free coup with a conditional repeat.** Che (`push_che_coup`/
`begin_che_coup`) — a free USSR coup against a non-Battleground Central
America, South America or Africa target, then a second one against a
different such country if the first removed US Influence, capped at two via
the `che` context on the `COUP_ROLL`.

**Deferred per-turn conditions.** Cuban Missile Crisis (DEFCON→2; a coup by
the flagged side loses the game, checked in `_handle_coup_roll`; the
at-risk side may defuse — Cuba for the USSR, West Germany or Turkey for the
US — offered fresh at the start of each of its action rounds for the rest
of the turn via `Engine._push_cmc_defuse_offer`), We Will Bury You (DEFCON
−1; the USSR's 3 VP are settled in the US Action Round the card named, by
`Engine._settle_we_will_bury_you`, *before* whatever the US plays there —
"USSR gains 3 VP prior to any US VP award" — unless that play is UN
Intervention. If the US had no Action Round left when the card fired there
is no window and no VP at all; the flag lapses at end of turn).

**"Discard a 3+-Ops card or suffer" branch.** The modified Ops value, not
the printed one (FAQ 7.4; see docs/RULES_SOURCES.md). Blockade and Latin
American Debt Crisis, with the US choosing from its own hand the same way
Ask Not… does.

**Scoring-time modifiers and extra rounds** (`_scoring_overrides`,
`_total_action_rounds`/`_side_for_play_index`). Formosan Resolution (Taiwan
scores as an Asian Battleground while the US controls it; nullified once
the US plays the China Card, and unlike Shuttle Diplomacy it *does* apply
to Final Scoring), Shuttle Diplomacy (one USSR-controlled Battleground is
dropped at the next Middle East/Asia scoring, then consumed; "does not
count for Final Scoring at the end of Turn 10", so a copy still in force
when the game ends never takes effect), North Sea Oil (OPEC becomes ineligible game-long; the US plays
one extra action round this turn), Arms Race (scores off the Military
Operations track), Ussuri River Skirmish (take the China Card from the
USSR, or +4 Influence in Asia). `Board.region_tier` and
`Board.score_region` take optional `extra_battlegrounds`/`ignored` sets so
these adjustments are additive and leave every other caller unchanged, and
`Board.scoring_overrides` derives the pair for a region and a set of active
events. `Engine._scoring_overrides` is now only "which events are in force,
and which one this scoring spends" -- Formosan Resolution persists, Shuttle
Diplomacy is consumed by the first Middle East or Asia scoring, whether or
not the USSR held a Battleground for it to drop. The strategic bot reads the
same derivation through `evaluator.scoring_overrides`, so these two are the
only flag events it can price; see docs/STRATEGIC_AI.md.

`Board.coup_prohibited` answers which of these forbid a given attacker a
Coup or Realignment, and `Board.nato_protects` the NATO part alone (Brush
War asks that one too). `Engine._usable_coup_realign_target` keeps only what
is the engine's: the defender holding Influence, DEFCON, and reading which
events are in force out of `game_effects` (`Engine.coup_flags`). The
strategic bot's evaluator mirrors the same query over its own snapshot
(`evaluator.coup_forbidden`, tested against `Board.coup_prohibited`).

**A reactive hook consulted from board mechanics.** NORAD
(`game_effects["norad"]`). An Action Round in which DEFCON *moves* to level
2 arms `turn_effects["norad_pending"]` in `Engine._change_defcon`; the
Influence is placed at the *conclusion* of that round, by
`Engine._push_pending_norad` from the action-round branch of
`_advance_once`. The deferral is load-bearing: placing it the instant
DEFCON moved put it inside the round that caused the move, so a USSR play
that degraded DEFCON with its Event and still had Operations left could
answer the US placement with them. Whether Canada is still US-controlled,
and whether Quagmire has nullified NORAD since, are re-checked at the
placement, not at the arming. A stable DEFCON 2 does not arm it, and
neither does a headline that reaches 2: "it does not apply if DEFCON goes
to 2 during the headline".

**Immediate conditionals.** Nixon Plays the China Card — two exhaustive,
unconditional branches, matching the printed card: if the US already holds
the China Card, +2 VP for the US; otherwise the US takes it, face down and
unusable this turn (card text overriding rule 9.4's face-up default). There
is no discard-to-keep option and no eligibility condition.

**A hidden peek at the draw pile.** Our Man in Tehran. The examined cards
live in `Engine._our_man_queue`/`_our_man_kept` — plain serialized state
(mandate #5) deliberately excluded from `observe()` — while the
`EVENT_CHOICE` decision offered to the US only ever contains
`"keep"`/`"remove"`, never the card identity, so the opponent's observation
cannot infer which card is under consideration even though
`pending_decision` is otherwise shared (mandate #4). Kept cards return to
the draw pile, which is reshuffled through the seeded RNG once all (up to
5) cards are decided.

**A headline-cancellation interaction plus a separate action-round
trigger.** Defectors has no `EVENTS` entry — neither of its two printed
clauses is an ordinary `resolve(engine, side)` event. Headlined by the US,
`_apply_defectors_headline` (called from `_advance_once` once both headline
picks are frozen, since it must act before either headline card resolves)
discards the USSR's headlined card unresolved. Played by the USSR in a
normal action round — Event or Ops, not Space Race —
`_maybe_defectors_action_round` (hooked into `_handle_play_mode` alongside
Flower Power) instead gives the US 1 VP. The USSR headlining it, or the US
playing it in an action round, have no printed effect and are correctly
no-ops.

**A persistent per-player operating lock.** Bear Trap (traps the USSR) and
Quagmire (traps the US), independent of who actually plays the card — the
same way Duck and Cover always favors the US regardless of who plays it.
`Engine._trap_key_for`/`_push_trap_step`, hooked into the action-rounds
branch of `_advance_once`, replace the trapped side's normal
`ACTION_ROUND_PLAY` with a mandatory-when-possible discard of an Ops-2+
card (`QUAGMIRE_DISCARD`) followed by a seeded `QUAGMIRE_ROLL` CHANCE die
that frees the side on a 1–4. With no legal card to discard, that action
round is simply wasted with no roll at all — except that a scoring card in
hand must still be played, since a scoring card may never be held past end
of turn.

## Space Race boxes

Box 2 (a second Space Race attempt per turn), box 4 (see below), box 6 (may
discard the Held Card at end of turn), and box 8 (an extra Action Round) are
implemented. Each is granted only to the first side to reach the box and is
cancelled outright — not transferred — the instant the second side also
reaches it (rule 6.4.4), via `Engine._update_space_race_ability` and the
`game_effects` keys `space_race_double_attempt_holder` /
`space_race_headline_reveal_holder` / `space_race_discard_holder` /
`space_race_extra_round_holder`.

Box 4's sole holder picks their Headline card *second*, after seeing the
opponent's already-committed pick. `_headline_pick_order` reverses the
default USSR-then-US pick order for it, and `_push_headline` surfaces the
opponent's card to the holder as `opponent_headline` in the `HEADLINE_PLAY`
decision's `context`, once the opponent has actually picked. Only the pick
order changes; the frozen resolution order (`_headline_resolution_order`,
higher Ops first) is a separate mechanic and untouched by this.

Physical mode already always asks the bot side first so its pick can be
announced in time for the operator to place it on the real board (see
`docs/BOTS.md`); when the *physical* side holds box 4, that default already
gives them the ability's benefit for free, so no special case is needed.
When the *bot* holds it instead, `_headline_pick_order` overrides that
default the other way: the operator is asked first — and must genuinely
place their real card on the board before the app asks for the bot's pick —
so the bot's choice can actually depend on it.

## Region scoring: Control of Europe is a win, not VP

"Control: Control more countries in the Region than the opponent, and Control
all of the Battleground countries." That is the scoring tier, and it is not
control of every country in the region, which is a stricter thing a side may
never reach. Europe alone has no Control value in `rules.json`, because
Control of Europe is an automatic victory: "If either side Controls Europe,
that side wins when the Europe Scoring card is played." Final Scoring scores
every region as if its card had been played, so it wins there too, ahead of
whatever another region would have scored -- `Engine._finish_game` resolves
Europe first for that reason rather than relying on the order of `Region`.

The engine used to gate that win on control of every Europe country and
otherwise score the Control tier as Domination, with a `VERIFY` comment
against the guess. A US board holding all five Europe Battlegrounds and three
more countries scored 10 VP where it should have ended the game, and the bot,
which had the rule right, priced one captured position's Europe Scoring play
at 126 rather than as the certain win it was.

`Board.score_region` still raises rather than returning a number for that
tier, since there is no number to return; ask `Board.region_tier` instead.
That is why `Engine._score_region_net` checks for Europe Control before it
asks `score_region` for a number at all.
`Board.controls_all_of_europe` is gone: it encoded the wrong condition and is
what the engine was reading.

## Corrected DEFCON-related event behavior

Five Year Plan fires only a discarded US-associated event. Scoring cards are
discarded without scoring; USSR may select Five Year Plan at the scoring
deadline when every other held card is scoring and there are enough remaining
rounds. That guaranteed escape offers only modes that trigger the discard.
Missile Envy immediately resolves a received own/neutral event; an opponent
event is used for Ops without firing. Wargames applies its six-VP concession
and ends from the VP track, without regional final scoring (zero is a draw).
Cuban Missile Crisis cancellation is an interrupt on either player's turn;
see [ARCHITECTURE.md](ARCHITECTURE.md#defcon-responsibility-and-cancellation-interrupts).
The DEFCON regressions cover nested events, headline ownership, physical-hand
transfers, cancellation, and save/resume. Card summaries match these rules.
