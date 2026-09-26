# Ties measured, and the unhandled events

> **Correction (2026-09-25): the counts below are inflated; do not quote
> them.** `scripts/measure_ties.py` patches `rank_actions` on the class,
> and the event helpers that price each option are StrategicPlayers too,
> so it records the SIMULATED event decisions alongside the live ones --
> one headline ranking recorded seven EVENT_INFLUENCE rankings with no
> action applied. Its `STAT` also carries over between games on a
> worker, and some events listed as unpriced (Independent Reds, Junta,
> Ortega, Tear Down This Wall) do have scorers. See the Codex audit
> 2026-09-25, F3. The live-only instrument replaces this measurement.
>
> **Remeasured live (2026-09-25, `fix/event-measurement`, seeds
> 42000-42001, 2 games):** 41 live EVENT_CHOICEs, of which **6 unpriced**
> (South African Unrest 3, Warsaw Pact 2, Chernobyl 1) -- about 3 blind
> picks a game, not 66 -- plus 3 priced-but-all-equal (Our Man in Tehran 2,
> Independent Reds 1) and 5 top ties. The three unpriced events are exactly
> the ones the maintainer answered on 2026-09-25 (EXPERT_ASKS 5: price by
> board value before and after). Card plays are the live tie: 40 of 228
> real ACTION_ROUND_PLAY choices (17.5%) had tied tops, which is where the
> planner's near-tie band acts. War targets: 2 of 7 all-equal, which the
> maintainer calls inconsequential. Two games: rates, not verdicts.
> `logs/event-measurement/ties-42000.json`.

The companion measurement to [the ties catalogue](2026-09-24-ties-and-what-breaks-them.md):
which tie actually fires, how often, and how many event choices the bot
makes with no opinion at all. `scripts/measure_ties.py` wraps
`rank_actions`, re-derives each option's sort key, and records how the
top was separated. Sample: **4 self-play games** (seeds 42000-42003,
shipped weights, events on) -- ~7,800 rankings, so the per-kind rates
are stable-looking but the POSITIONS are few; treat the percentages as
rates, not verdicts.

## Where ties fire (4 games)

| decision kind | rankings | mean options | **decided by engine order** |
| --- | ---: | ---: | ---: |
| `WAR_TARGET` | 91 | 23.2 | **37 (40.7%)** |
| `ACTION_ROUND_PLAY` | 506 | 5.2 | **84 (16.6%)** |
| `EVENT_CHOICE` | 2183 | 3.8 | **273 (12.5%)** |
| `COUP_TARGET` | 189 | 9.6 | **20 (10.6%)** |
| `HEADLINE_PLAY` | 78 | 8.6 | 1 (1.3%) |
| `PLAY_MODE` | 509 | 2.7 | 4 (0.8%) |
| `EVENT_INFLUENCE` / `PLACE_INFLUENCE` / `REALIGNMENT_TARGET` / `OPS_TYPE` / `EVENT_OPS_ORDER` | 7543 | -- | **0** |

Reading it:

- **The continuous terms never fully tie.** Influence placement (41.7
  options!), realignments and event placements all separate by the key:
  the value function is discriminating exactly where it is summed over
  boards. Ties live where the options are DISCRETE and few-valued: a war
  target list, a hand of cards, a coup target set.
- **`WAR_TARGET` is the worst offender** (2 in 5): a war's target country
  is picked by `legal_actions()` order whenever the targets price equal
  -- plausibly often, since a war's value is mostly "do I win it", which
  many targets share.
- **Card picks tie one time in six** (`ACTION_ROUND_PLAY`): same-ops
  cards with no live event price the same. This is the family the
  planner's alphabetical defect lives in; at `hand_assignment > 0`
  `_plan_pref` would arbitrate some of them (it shows 0 everywhere here,
  as documented -- it is inert at the shipped weight).
- `plan_pref` decided **zero** rankings, as expected at weight 0.

## The unhandled EVENT_CHOICEs (273 all-tied in 4 games)

When EVERY option ties, the policy has no opinion: `_score_event_choice`
returns `None` (0.0) for each and the first legal option wins. By event:

| event | all-tied picks in 4 games |
| --- | ---: |
| `Che` | 80 |
| `South_African_Unrest` | 72 |
| `Independent_Reds` | 36 |
| `Chernobyl` | 28 |
| `Warsaw_Pact_Formed` | 22 |
| `Olympic_Games` | 20 |
| `Our_Man_In_Tehran` (no examined card) | 6 |
| `Latin_American_Debt_Crisis_double` | 1 |

The code-side inventory (28 routed choice branches vs the priced ones)
names the rest that this sample never reached: `Junta`,
`Ortega_Elected_in_Nicaragua`, `Tear_Down_This_Wall`,
`Cambridge_Five_query`, `Cuban_Missile_Crisis_defuse`,
`Missile_Envy_physical_pick`. **About eleven branches are unpriced**,
plus two anomalies this run exposed:

1. **`Independent_Reds` HAS a priced branch** (`choice in
   self.board.countries`) yet all 36 picks tied -- the branch did not
   fire for the offered choices or prices them all equal. Worth a look
   before it is filed as "priced".
2. **`Our_Man_In_Tehran` is priced only with `examined_cards`**; without
   a shown card its choice falls through (6 picks here).

Separate category, from STRATEGIC_AI's Limits: the six flag-only events
(NATO, Warsaw Pact, NORAD, Nuclear Subs, Quagmire, Bear Trap) that "move
no influence and so value 0" -- a known gap, not a tie.

## Measuring the impact, next

What this run already bounds: ~66 arbitrary picks a game (265 in 4), of
which a war target and a card pick are among the most consequential.
What it does NOT say is what those picks cost. The instrument for that:

**`scripts/measure_event_gaps.py`** (proposed): for each unpriced event,
take the positions where it fired in play, resolve every offered choice
both ways on the public sandbox, and report the VP spread the policy
cannot see -- `mean(best_choice - first_option)` is exactly the cost of
picking blind. A spread near zero says the tie is harmless (many will
be: `Chernobyl`'s region ban may barely matter); a spread of VP says
the first-option rule is leaving points on the table every time. The
same instrument prices the flag-only six: fire the flag on a sandbox
board and read the delta the 0.0 hides.

## What this does not settle

Four games. The rates are per-ranking and the rankings within one game
share its positions; a 40.7% war-target tie rate could move either way
on more games. And a tie is not automatically a mistake -- it says the
model has no preference, which is sometimes true and fine. The impact
instrument is what separates harmless ties from expensive ones.
