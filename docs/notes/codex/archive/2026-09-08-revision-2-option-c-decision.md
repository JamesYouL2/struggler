# 2026-09-08 — Revision 2 / Option C decision

**Yes to Option C as a bounded measurement stage.** Defer Rust while
establishing a corrected reference and measuring inexpensive Python
improvements. This is not a commitment to complete a large array-Python
rewrite before Rust can be considered.

Suggested order:

1. Capture the corrected parity corpus AND fresh baseline timings/profiles.
   Include explicit DEFCON risk outputs and planner inputs: the listed
   evaluator outputs and rank safety keys alone do not cover the planner's
   public operations. Include truncation cases and learned-prior context.
2. Try the smaller predicate-hoisting/memoisation change first, then measure
   it independently. Current `DefconPlanner` already caches `solve` and
   `_event_risk` with `lru_cache`; do not assume another cache eliminates
   millions of expensive computations. Measure cache hits, misses and
   wrapper/key-construction cost. Keep hazard-at-DEFCON-2 semantics and
   replacement multiplicity intact.
3. Index the evaluator incrementally, with parity and whole-workload timing
   after each meaningful slice. If conversion or Python indexing overhead
   erases the gain, stop rather than completing a rewrite solely because
   it was called a prerequisite. A Rust kernel can receive arrays while
   the original dict-based Python evaluator remains the reference.
4. Choose among keeping the Python improvements, a batched Rust kernel,
   parallel search, or a broader native rollout implementation. Deep MCTS
   does not logically require porting the entire engine; that remains an
   option to justify with measurements and a concrete latency target.

The draft's corpus -> indexing -> memoisation order is workable, but
measuring only after both optimizations loses attribution. Prefer the
cheaper memoisation experiment first unless the fresh profiles favor an
equally small indexing change. No predicted speedup is approved here.

Revision 2 still contains stale, contradictory sections: its later
prerequisite list puts the corpus last; its signatures still say u8 despite
the int16 layout; its call list still describes static hazard masks and a
DEFCON native solve despite the newer scope exclusion; and its risk table
still rounds rankings despite trace/ranking parity without rounding above.
Treat the Option C section as the proposed current scope, and consolidate
these leftovers before treating the whole document as an implementation
contract. The evaluator-plus-planner Amdahl row also computes to about
5.2x at s=20 and 6.0x at s=50 for p=.85, rather than 4.9x/5.9x.

Validation: read revision 2 at HEAD `371d592` and confirmed the existing
DEFCON caches in source. The cited MCTS fix commits are present in history;
this decision does not constitute a fresh implementation audit of them.
