# The rule that explains the whole exercise

The maintainer: **context-dependence scales with the turn.** Early War
values are the least context-specific, Mid War in between, Late War the
most, because more turns played means more state a value can hang on.

That is why `models/expert_valuations.json` -- thirty constants on the
opening board -- works as a fixture at all, and why the Late War table
will never be a list of constants. Of the twenty Late War entries now
recorded, **eight are schedules or formulas rather than numbers**. It
also predicts the Military Ops result: a term that pays in the Late War
was invisible to an Early War fixture, and the games saw it.

The design consequence is bigger than the fixture. A single number per
card is the right shape for the Early War and the wrong shape for the
Late War, and the bot uses one shape throughout.
