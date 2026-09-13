# The Blockade recursion is a chain of fresh helpers, and the guard cannot see it

Answers question 4c of `2026-09-13-handoff-for-codex.md`: where the Blockade
`RecursionError` actually is. Found overnight 2026-09-12 with the self-play
tracer (`scripts/selfplay_trace.py`), after one correction to the tracer
itself. Nothing is fixed here.

## How often

Strategic self-play, seeds 9000-9191, one seat per seed
(`2026-09-12-selfplay-lengths-and-sandbox-stacks.md`):

| revision | Blockade fallbacks | games | ABM Treaty fallbacks | games |
| --- | ---: | ---: | ---: | ---: |
| `f492dc3` | 69 | 17 of 191 | 0 | 0 |
| `ac27de8` (HEAD bots) | 85 | 24 of 192 | 5 | 2 |

Every one is the same shape. Each is a decision priced by the generic
estimate instead of the simulation, logged at WARNING and otherwise silent.

## The loop

The first overnight run kept only `traceback.extract_tb`, which holds the
frames from the `except` clause down to the raise: 17 frames of a stack that
was 1000 deep. The loop was entirely above the catch, so that run pointed at
`defcon.py` -- where the last frame happened to be when the limit hit -- and
was wrong. `47c9d01` keeps the live stack above as well. Rerun on seed 9003
(`logs/trace-9003/`, gitignored), the stack is 973 frames above the catch and
17-28 below, and these frames each repeat about 65 times:

    event_value                  policy.py:1757
    _event_value_uncached        policy.py:1779
    _public_event_value          policy.py:1630
    _resolve_sandbox             policy.py:1669   helper.choose_action(...)
    choose_action / rank_actions policy.py:612, 668
    safety_key -> score          policy.py:823, 2416
    _score_event_choice          policy.py:2796   -hold_value(choice): the US discard
    hold_value                   policy.py:1925
    card_play_value              policy.py:2319
    value_as_ops                 policy.py:2264   cid != self.un_card(obs)
    un_card                      policy.py:2334   event_value of every opponent card in hand
    -> event_value ...

In words: Blockade's sandbox pushes the US discard choice. The helper that
plays it prices each discard as `-hold_value(card)`. `hold_value` goes
through `value_as_ops`, which asks `un_card` which opponent card UN
Intervention is being kept for, and `un_card` answers by calling
`event_value` on every opponent card in the hand -- which opens another
sandbox, whose helper prices its own choices the same way.

It needs UN Intervention in the hand being priced: `un_card` returns before
the loop otherwise. That is why it fires in 1 game in 8 rather than every
time Blockade is evaluated, and why a plain game on seeds 4000/4001 showed
none.

## Why the guard does not stop it

`event_value` has a re-entry guard: a card already in `_events_in_progress`
gets the shallow Ops estimate instead of a second simulation. It exists for
exactly this -- "Ask Not prices the hand, which holds Five Year Plan, which
prices the hand, which holds Ask Not".

But the set is per player (`policy.py:648`), and the sandbox does not run on
this player. `_event_helper` (`policy.py:1503`) builds a new
`StrategicPlayer`, which builds its own helper when it prices an event, and
so on. Every level of the chain is a different object with an empty guard,
so no level can see that Blockade is already being simulated two levels up.
The guard is correct for recursion within one player and blind to recursion
across the helper chain, which is the only kind the sandbox produces.

## What this corrects

- `2026-09-13-handoff-for-codex.md` section 4c, which said the recursion
  could not be reproduced and retracted a die-roll-fork theory. The fork
  theory was wrong; so was "not reproducible" -- it needs UN Intervention in
  hand.
- The comment on the Latin American Debt Crisis branch (`policy.py`), which
  said Blockade "survives only because it is one choice deep". It does not
  survive. Debt Crisis was the same loop hit on every evaluation; Blockade and
  ABM Treaty hit it whenever the hand holds UN Intervention. Debt Crisis was
  fixed by never simulating it, which removed one entry point and left the
  loop.

## The fix, proposed and not applied

Share the guard across the chain: the helper takes the parent's
`_events_in_progress` set rather than starting its own, so the inner
`event_value(Blockade)` sees the outer one and gets the shallow estimate --
the guard's documented behaviour, applied where it was always meant to apply.
That is one line in `_event_helper`, and it would also let the Debt Crisis
special case be re-examined rather than stand as a workaround.

It changes decisions -- every position that currently falls back to the
estimate would get a simulation with a shallow inner price instead -- so it
needs a corpus delta measured before re-capture and a gate. It was not
applied tonight because the gate ladder and the ablations running on CI are
measuring the current bot.

**And it wants a test, by the repo's rule.** This is the second time the same
loop has shipped (Debt Crisis, then Blockade/ABM Treaty), and both times the
only symptom was a WARNING line and a generic estimate. The test to write:
build a hand with UN Intervention and an opponent Blockade, evaluate
Blockade, and assert `sandbox_failures` is empty -- which fails today.
