# 2026-09-09 — One scoring implementation, and the overrides the bot could not see

Three copies of region scoring existed: `Board.score_region` (fused, fast, no
overrides), `Board.region_tier` plus `Board.region_bonus_vp` (the parts the
engine assembled a score out of), and `evaluator.region_vp` (index space, for
the bot). Only the engine's copy knew about the per-scoring overrides, so with
Formosan Resolution or Shuttle Diplomacy in force the bot and the engine
disagreed about what a region was worth -- and the bot then chose on its own
number and was paid on the engine's.

`score_region` now takes `extra_battlegrounds`/`ignored` and is the only
implementation the engine has; `_score_region_net` adds which events are in
force and the Europe Control victory, and nothing else. `region_bonus_vp` is
deleted. `Board.scoring_overrides` derives the pair as a pure query, and
`Engine._scoring_overrides` keeps only the consumption, which is the part that
is not a query. The bot mirrors the derivation in index space
(`evaluator.scoring_overrides`) and reads the flags from
`observation.game_effects`.

Two things this made me get wrong first, both caught by measurement rather
than by reading:

**Deriving the overrides at `prepare` would have been wrong.** They read
control, and every trial placement moves control. Taking Taiwan is what turns
Formosan Resolution on, so the placement that does it has to see the promotion
in its own delta. They are derived per call; the empty case costs a `bool`
test, so the hot loop does not pay a set lookup for a card that is not in
play.

**Crediting a one-shot in both regions it could apply to is not a rounding
error.** My first version applied Shuttle Diplomacy to the Middle East *and*
Asia, because either could score next. Against the parity corpus one position
moved 5 VP in Asia and 1 in the Middle East from the same single discount -- a
6 VP phantom, five times the 1 VP gap I was fixing. Dropping a Battleground
can cost a whole tier, so "apply it twice, it is only a small overcount" was
never true. It is now spent once, on the region whose scoring is nearer
(`_shuttle_region`), ties to the Middle East. Pricing the actual play of a
scoring card is unaffected: that runs the real engine in the sandbox, which
applies and consumes the effect for real.

The event sandbox reads the flags from the *sandbox* engine after the event
fires, not from the observation. That is the whole reason an event whose only
effect is setting a flag now prices at anything: Shuttle Diplomacy went from
0.0 to -1.3 for a USSR seat on a corpus position (a US event, so a USSR player
handing it over is paying for it).

71 of 464 corpus positions had one of these in force. The corpus was
regenerated; the differences are Middle East and Asia region scores, Shuttle
Diplomacy's own value, and the two events that move influence there (Voice of
America, ABM Treaty) re-scoring those regions under the discount.

**The engine now records that Final Scoring ran** (`Engine.final_scoring_ran`,
serialized only once true, so earlier recorded states compare equal).
`scripts/game_endings.py` counted `reason == 'final_vp'`, which misses a game
that reached Final Scoring and ended partway through it at `vp` or
`europe_control`, and misses draws, which carry no reason at all. Constructed
one of each to check the flag catches them. This matters because that script
produces the calibration table, and it was undercounting the numerator.

The golden replay `full_game_ops_only.json` gained exactly one line, checked
by diffing every checkpoint before rewriting rather than by regenerating the
file: 618 checkpoints, one added key, nothing changed or removed.
