# Event strength: is the bot's event price scaled too low?

Written 2026-09-23, before the number. The rule each arm will be read
against is quoted here and in its `context` in `.github/experiments.json`.

## Why

The headline-only planner (`fix/hand-planner-headline-only`) headlined
opponent cards, then low-Ops cards over strong events. The price table
from turn 1 of seed 4000 shows the cause is not the planner. **The bot
values its own events far below their Ops.** East European Unrest's event
is worth 11 to it, and its 3 Ops are worth 63. Red Scare/Purge lost a
headline to CIA Created for the same reason. The shipped bot hides this
by headlining the highest `event - 0.5 x Ops value`. Any rule that trades
an event against the Ops it gives up exposes it.

The maintainer's question: is event strength simply scaled too low?

## What is measured

`event_scale` (1.0 as shipped, `StrategicWeights`) multiplies every
price `event_value` returns, **both sides' events**, before the game cap
and the DEFCON-risk blend. Both signs, because the same sandbox prices both
sides' events: if it undervalues one, it undervalues the other. The
recursion guard's shallow estimate and `_shallow_event_value` (hand terms)
are left alone.

Arms, one dispatch, block 82000-83023 (held 91000-91127), all against
`bc5ef93`:

| arm | `event_scale` | paired to |
| --- | ---: | --- |
| `event-scale-base` | 1.0 | -- |
| `event-scale-15` | 1.5 | `event-scale-base` |
| `event-scale-20` | 2.0 | `event-scale-base` |

## The rule, before the number

For each arm on its own:

- A paired lower bound above 0 means that scale beats 1.0. Gate it against
  `bc5ef93`, then flip the default (a MINOR bump). If both arms clear, the
  larger point estimate goes to the gate.
- At or below 0 means it does not, and 1.0 stays.
- A reading below -0.10 is the size of a defect, not a verdict.
- If 1.5 clears and 2.0 reads higher still, the next grid goes above 2.0.
  If 1.5 clears and 2.0 reads lower, the peak is near 1.5.

Prior: small and uncertain. Scaling both signs raises opponent threats as
much as our own events, so the bot will also spend more to dodge their
events (more space attempts, more UN). The net could go either way.

## Not settled by this

- **Own-only scaling.** If both-signs scaling loses, own events alone is
  the next arm. It is a different hypothesis: that the sandbox misses what
  our events set up, not that it underprices events in general.
- **Per-card prices.** A uniform scale cannot fix a table where some events
  are overpriced. That is `docs/EXPERT_ASKS.md` items 4 and 10.

## Reading

(pending)
