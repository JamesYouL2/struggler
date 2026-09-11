# Would a full Rust port give ten times, and is numpy a correctness tool?

Two questions from the maintainer, after they ruled out the Rust port as
a speed project ("way too much code to change; only do it if correctness
guarantees are super important and it doesn't slow you down, because
tuning is easier in Python for humans").

## The arithmetic: 10x needs ~90% of the workload, not the evaluator

Amdahl on the full-game profile in `docs/RUST_PORT_PLAN.md` (DEFCON
planner ~60% cumulative, evaluator ~25%, enum attribute access ~12%):

| ported | what that covers | s=20 | s=50 | s→∞ |
| ---: | --- | ---: | ---: | ---: |
| 25% | evaluator only (the planned Option A) | 1.3x | 1.3x | 1.3x |
| 60% | DEFCON planner only | 2.3x | 2.4x | 2.5x |
| 85% | evaluator + planner | 5.2x | 6.0x | 6.7x |
| 90% | + half the engine glue | 6.9x | 8.5x | 10.0x |
| 97% | + engine core and enums | 12.7x | 20.2x | 33.3x |

Solving for 10x: an infinitely fast kernel still needs **p = 0.90**; a
realistic 20x kernel needs **p = 0.947**.

**So yes, 10x is plausible — and only for engine + planner + evaluator +
policy, about 10,000 lines.** The currently planned evaluator port caps
at **1.33x** on full games, which is the gate's workload. It was never
going to make the gate faster, and I recommended it as a route to the
ten-minute gate before reading the plan's own budget. That was wrong.

A partial port is worse than it looks, too: the bot calls the engine
constantly inside event sandboxes, so a Rust bot over a Python engine
pays FFI on the hottest path. The split has to be all-or-nothing at the
engine boundary.

## What it would cost, and the one argument that changes

The maintainer's objection is that tuning is easier in Python. Half of
that survives scrutiny and half does not:

- **Tuning constants would not get harder.** The surface is 28 floats in
  `StrategicWeights`, already loaded from JSON. A Rust build reads the
  same file; tuning stays a file edit, not a recompile.
- **Changing the value function's *shape* would.** Adding a term,
  changing what `delta` prices, trying a new forward search — that
  becomes a compile cycle instead of an edit.

Which decides it: **the shape is still moving.** On 2026-09-11 alone it
moved four times (the forward search turned on, Five Year Plan's rider
priced, opening books added, and the break-commitment question is still
open). A port now freezes a design that is not settled.

**The trigger to revisit: a month in which only constants change.**

## The cheaper lever, and why the obvious reading of it is wrong

The planner is ~60% of a full game and nobody has optimised it — but
that 60% is *cumulative*. Profiling twelve hazardous late rankings gives
exclusive time:

| module | exclusive |
| --- | ---: |
| `evaluator.py` | 40.1% |
| `policy.py` | 24.1% |
| `defcon.py` | **5.9%** |

So "optimise the planner" means **cut the evaluator calls the planner
makes**, not make `defcon.py` faster. `delta` is 47% cumulative at 1746
calls per ranking.

### And a caution about reading profiles at all

The profile's top entry was `card_state` at 332k calls, all of them
`_reply_budgets` rebuilding the same unseen-card pool on every call — a
pool that cannot change within a ranking, and a defect introduced the
same day by the forward search. cProfile attributed 11% to it.

Caching it per decision, measured interleaved in one process: **1.03x**.

Not 11%. cProfile charges per-call overhead, so it systematically
overstates functions with huge call counts and cheap bodies. **A
profile's top-N is an attribution, not a speedup forecast**, and the
next optimisation should be measured the same way before it is believed.
The cache stays — it is correct and free — but it is not the lever.

## numpy / numba for correctness: no, and they would cost some

Asked whether array libraries would help correctness rather than speed.

**They would not, and numpy adds hazards this codebase is specifically
prone to:**

- **Views alias.** A numpy slice shares storage, so mutating one array
  silently changes another. The commonest defect here is a cached value
  keyed on less state than it reads — seven times — and views are a new
  way to produce exactly that.
- **Integer overflow is silent.** `int64` wraps rather than raising, and
  Python ints do not.
- **Negative indices wrap instead of erroring**, so an off-by-one reads
  the wrong country rather than failing.
- **Broadcasting does something rather than erroring** when shapes are
  merely compatible instead of correct.

numba adds nothing at all here: it is a JIT, and `njit` in nopython mode
removes error checking rather than adding it.

### What would help, and it is already half-installed

The real index-confusion risk is that `Position` uses parallel lists
indexed by country index `i` and side index `s`, both plain `int`.
Swapping them is silent. `typing.NewType` makes that a type error, and
**the type checker just adopted (`ty`) enforces it** — the same tool
that catches `CardSide is Side.US`. That is the correctness win, for
about twenty lines of annotation and no new dependency.
