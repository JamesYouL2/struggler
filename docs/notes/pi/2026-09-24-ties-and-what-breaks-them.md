# Ties, and what breaks them

Every ranking here is a sort over floats, and where two options price
equal something still has to be picked. This catalogue says what breaks
each tie today -- by rule or by accident -- because the 2026-09-23
assignment-planner defect was exactly this class: a tie broken by an
accident (dict key order) in the worst possible direction. Written
2026-09-24 at the maintainer's ask.

## The hierarchy, for every option ranking

`rank_actions` sorts `((safety_key, action) ...)` by key
`(certain, _plan_pref) + rest`, `reverse=True`. Python's sort is
STABLE, so the resolution order is:

1. **`safety_key[0]`** -- the certain-defeat sentinel. Deliberate:
   certain loss is refused outright, whatever is on the table.
2. **`_plan_pref`** -- the hand planner's preference for this slot.
   Constant 0 whenever the planner is off (it is: `hand_assignment` 0),
   so at the shipped config this rung is inert and the ordering is
   unchanged -- the parity corpus pins that.
3. **`safety_key[1:]`** -- the residual-risk-in-score blend and the
   score itself.
4. **`decision.options` order** -- the stable sort's residue. This is
   `legal_actions()` enumeration, i.e. the ENGINE's offered order: the
   universal last-resort tie-break for every card pick, play mode,
   headline, event choice and coup target. Accidental by default: it is
   deterministic, but it is not a rule of the bot's, and what it means
   is "whatever the engine listed first".

## The planner's own ties -- the defect, still unremedied

`hand_planner.solve` orders cards by `sorted(..., key=c.key)` and its
`offer` keeps the FIRST strict maximum (`candidate > top_value`). So a
tied DP resolves to the earliest card in **key order** -- alphabetical
card id. With flat per-round prices the DP is indifferent and the key
decides: the planner "plays its hand in alphabetical order", which is
what the -0.240 mostly was
([the diagnosis](../claude/2026-09-23-the-planner-plays-its-hand-in-alphabetical-order.md)).
Inert at `hand_assignment` 0; the ordering fix
(`fix/hand-planner-lead`, leads only on strict preferences) read -0.061
and was not merged. A second site in the same family:
`max(plans, key=lambda wp: wp.probability)` (policy, the assignment
pick) takes the first plan in enumeration order on a tie.

## Deliberate tie-breaks -- rules that exist because of an incident

- **`Terrain.neighbors` sorted by country id.** Not tidiness: a set's
  iteration order follows `PYTHONHASHSEED`, which "once moved a sum by
  one ulp and reordered a tied placement" (the comment says so). Sum
  order is load-bearing for float ties, and this is the fix.
- **The reply answer keeps the retake on a tie.** `_after_reply` prices
  the retake first and a Coup replaces it only by `coup < best`, strict:
  equal harm keeps the retake.
- **Headline ordering: more Ops, ties US first** (`defcon.py`'s
  comparison, stated in its docstring).
- **Shuttle Diplomacy's region pick** breaks on `region_urgency`
  (`evaluator.region_urgency`, "the Shuttle Diplomacy tiebreak").
- **The space candidate is the worst card.** Before this rule two cards
  at equal space value "collapsed to the same space value and the tie
  broke on hand order" -- fixed deliberately (Decolonization -75 ahead
  of Fidel -23).

## Accidental ties -- the risk list

- **Engine option order** as the universal residue (above). Safe for
  determinism; arbitrary in meaning.
- **Hand-attack and discard choices** (`gains.sort(reverse=True)`,
  "the worst cards go first"; Ask Not's upgrades; Grain Sales'
  better-of-2-Ops-and-the-shown-card): ties fall to the caller's
  enumeration.
- **Influence and coup-target allocation** (`gains.sort(reverse=ours)`):
  ties to input order.
- **Event choice**: "unhandled event branches tie-break to the first
  legal option" -- a documented default (STRATEGIC_AI's Limits).
- **The one-ulp tie**: the same logical comparison can tie or not
  depending on summation order. Everything under `evaluator` sums in a
  fixed order for this reason; a term added with a different grouping
  can turn a tie into a win or back (`docs/notes/claude/`'s float-
  regrouping entries and evaluator's own header).

## What this costs when a tie is wrong

1. The planner's alphabetical order -- a quarter of a game (run
   35814771005's -0.240, mostly this).
2. **A tie flood hangs the bot**: zeroing a discriminating family makes
   positions that differed only in that term tie exactly, and whatever
   breaks ties then explores far more -- the `access: 0.0` ablation sat
   on one game for four hours (the stall detector's origin story).
3. The `PYTHONHASHSEED` reordering -- a tie that moved with the
   interpreter.

## What pins the current behaviour

**The parity corpus freezes every accidental ordering above**: it
reproduces rankings exactly, tie order included. So any deliberate
tie-break change is a behaviour change like any other -- corpus
recapture plus a gate -- and the corpus is also why none of these can
drift silently. The one tie NOT pinned anywhere is the planner's key
order at `hand_assignment > 0`: no corpus record exercises the planner
(it sits at 0), and `tests/test_hand_planner.py`'s cases have clear
winners -- the alphabetical residue survives any test whose positions
do not tie.
