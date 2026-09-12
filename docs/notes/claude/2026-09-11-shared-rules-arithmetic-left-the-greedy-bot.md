# Shared rules arithmetic left the greedy bot

`greedy.py` held nine functions that four other things imported. The
maintainer's instruction, on seeing that: "do move it out."

## The hazard, which is not tidiness

`benchmark.py` runs `GreedyPlayer` as a comparison baseline (`--bot
greedy`, `--opponent greedy`), and `train.py` trains against it. So a
change made to one of those helpers *for the strategic bot* would have
moved the baseline the strategic bot is measured against, in the same
commit, silently.

That was not hypothetical. It surfaced while pricing the Space Race
ability boxes: the natural fix was to make `_space_race_expected_vp`
return something for boxes 2, 4 and 6, and that function is greedy's. The
fix went into `StrategicPlayer._space_expected_vp` instead, which was the
right call for a second reason -- what an ability is *worth* is a policy's
opinion, and the shared helper should report only what the rules award.

## What moved, and the line it was cut on

Into `src/struggler/bots/rules_math.py`, renamed to public names because
the leading underscore had stopped being true years ago:

`sync_board`, `in_bonus_region`, `bonus_ops`,
`coup_roll_modifier_estimate`, `coup_risks_defcon`, `realignment_bonus`,
`realignment_modifier`, `effective_ops_estimate`, `space_race_expected_vp`

`_expected_coup_gain` stayed. It takes a `GreedyWeights` and calls
`board_value`, so it is that bot's opinion rather than a rule. **The line
is whether the function has an opinion**: pure functions of public
observation state move; anything taking weights does not.

`greedy.py` went from 495 lines to 413 and still re-exports the names, so
nothing that imported them from there breaks.

## The trap

Four of the nine share a name with an `Engine` method:
`_bonus_ops`, `_in_bonus_region`, `_realignment_bonus` and
`_realignment_modifier` all exist in `engine/core.py` as well, because the
bots deliberately *mirror* engine internals rather than call into them --
a bot may only read what a seat can see (mandate #4), and
`realignment_bonus`'s docstring has said so all along.

A repo-wide rename of `_realignment_bonus` would have renamed
`Engine._realignment_bonus` and its four call sites in `core.py`, plus
`tests/test_engine_realignment.py`, which asserts on the engine method.
The rewrite was scoped to `bots/` plus the three test modules that import
the *bot* versions, and afterwards every surviving `_name` reference was
checked to be an engine method. `tests/test_events.py` and
`tests/test_engine_realignment.py` were correctly left untouched.

This is shape 4 in `bug-shapes.md` -- two implementations of one rule --
in its benign form: the duplication is deliberate, documented, and now
lives somewhere that says so in its module docstring rather than inside a
baseline bot.

## Verification

A pure move should change nothing, and the parity corpus is the oracle
that says so. It could not be run directly: the Space Race ability
weights are in the same working tree, they are a real behaviour change,
and they add four fields that `test_every_record_pins_every_weight`
rejects.

So the corpus was run with the four ability weights forced to `0.0`, which
makes `_space_expected_vp` numerically identical to the old path. Passing
there isolates the move from the change sharing its working tree.

Lint was held to its pre-refactor count: the move orphaned two imports in
`greedy.py` (`Subregion`, `effective_ops`), and removing them returned
ruff to exactly 13 findings across the four touched files.
