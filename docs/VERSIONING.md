# Versioning the bot

Baselines are git tags, `vMAJOR.MINOR.PATCH`. The gate compares a
candidate against the previous commit *and* against the oldest tag still
believed sound, because a series of individually-neutral changes can
drift the bot downward without any one of them failing a gate. One
baseline cannot see that; two can.

## What the numbers mean here

A bot is not a library, so the usual "breaking API change" reading needs
saying explicitly. There is a real compatibility surface --
`StrategicWeights.load`, and `benchmark.load_module`, which has to be able
to run an older `bots/` package against today's engine.

- **MAJOR** -- a saved model or an older baseline no longer loads. The
  weights schema loses or renames a field, or the package layout moves
  (`strategic.py` becoming `strategic/` was one of these; `gate.sh`
  refuses a pre-split base for exactly this reason).
- **MINOR** -- playing behaviour changes and a gate accepted it. Adding a
  weight with a default is MINOR: old models still load.
- **PATCH** -- behaviour is unchanged. Tests, docs, refactors, perf, and
  anything gated off by default.

"A gate accepted it" is weaker than it sounds and the tag does not claim
otherwise: acceptance means *not a measurable regression*. A MINOR bump
records that the behaviour moved and nothing caught it getting worse, not
that the bot improved.

## The tags

| Tag | Commit | What it is |
| --- | --- | --- |
| `v0.1.0` | `3c31254` | The flat-40 state: the last revision the maintainer ruled on directly ("a flat 40 is what the maintainer wants"), and the last before any forward-search work. Verified to still run as a gate baseline against today's engine. |
| `v0.2.0` | see `git tag` | The forward search on (`reply_model=3`), gated at `01de83f` as a dead heat on strength and carried by the poke rate falling 6.27 -> 0.08 a seat a game. Plus the named opening books, which are a no-op at the default. |

Still `0.x`: the bot's strength against a human has never been measured,
and every gate so far has returned a dead heat. There is no basis for a
1.0.

## Moving the older baseline

Raise the older tag only when the change between it and HEAD is one you
would defend without the gate's help -- a fixed defect, a rule the engine
was getting wrong, a term the maintainer has priced. Not on a dead heat,
which is most of them: a dead heat is the evidence that the old baseline
is still a fair reference, not that it is obsolete.

Check the candidate still runs before tagging it. An older `bots/`
package is loaded against *today's* engine, and that has broken before --
a baseline once died on `TypeError: a certain outcome is an ordering
flag`, which reads as a gate failure rather than an incompatible
baseline. `scripts/gate.sh` reports a baseline crash separately for this
reason.
