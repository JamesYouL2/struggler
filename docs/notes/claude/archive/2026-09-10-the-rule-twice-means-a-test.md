# The rule: twice means a test

The maintainer, after the stale-base inversion: "if you make a mistake
more than once, gate that with a test. That's just a good rule."

Adopted, and written into `CLAUDE.md` above the list of recurring
defects, because that list is the argument for it. Eight shapes are
recorded there; six recurred. The ones that stopped recurring are the
ones with a test beside them -- the sentinel escapes stopped after
`Certain` refused arithmetic, the scale errors stopped after
`test_scale_discipline.py`, the stale evaluator memos stopped after the
terms were made pure.

The stale-base inversion is the seventh occurrence of "a cached value
keyed on less state than it reads", and it was written by the same hand
that had documented the other six a few hours earlier. Which is the
whole case: knowing the rule is not the same as being unable to break
it. `tests/test_base_cache_discipline.py` now reconstructs the defect --
stubs `_invalidate_base` to a no-op, runs a real ranking, and requires
the checker to object.

Worth noting what made it catchable at all. The guard rests on
`Position.digest`, which was built earlier tonight for a *performance*
reason, measured as not worth it, and kept only because it made "the
board has not moved" checkable rather than merely commented. That is
exactly the use it was kept for, three hours later.

One thing the episode says about testing more generally: every unit test
of `_after_reply` asked what a value *was*, and the bug was in the
*sign of a difference*. `test_the_forward_search_discounts_a_break_rather
_than_rewarding_it` asserts the direction instead, and would have caught
it where none of the value tests could.
