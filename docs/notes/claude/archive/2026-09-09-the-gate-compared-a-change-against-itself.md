# 2026-09-09 — The gate compared a change against itself

`gate.sh` snapshotted the baseline's `strategic.py` and `evaluator.py`, and
`load_module` bound that sibling evaluator while the baseline loaded. The very
next change was to `public_cards.py`, which is not either of those, so the
baseline imported the *candidate's* table. Both sides played the same bot.
The gate returned:

    full-vs-base: 32 seeds, score 0.500, signed VP 0.0
    full-vs-held: 64 seeds, score 0.500, signed VP 0.0
    pooled score 0.500 +/- 0.000 over 96 seeds
    ACCEPTED

A standard error of exactly zero over 96 seeds is the tell. Proven directly:
the baseline's `final_scoring_odds` and the candidate's resolved to the same
module object.

Two fixes. The snapshot is now the revision's whole `struggler/bots` package
(`git archive`), and `load_module` resolves every `struggler.bots.*` import to
it through a `sys.meta_path` finder installed only while the baseline loads.
A finder rather than pre-executing the files, because the snapshot's modules
import each other and no execution order is right in general. `struggler.engine`
is deliberately not snapshotted: it is the shared arbiter both sides are
measured under. A baseline that imports lazily inside a function, after the
load returns, still gets the candidate's module; nothing here fixes that.

And the acceptance rules now warn when every game is a dead heat, since that
is either a change that cannot affect play or a comparison that is not
comparing anything. It cannot fail: `ec99a5f` was a proven behaviour-neutral
refactor and gated at exactly 0.500 legitimately.

The lesson generalises past this instance. Codex flagged incomplete revision
isolation as an open item after the `evaluator.py` fix, and the answer was
"other imported modules come from the candidate environment" -- true, filed,
and then it bit within the hour. A known gap in a measurement tool is a
liability, not a footnote.
