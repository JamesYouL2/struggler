# The planner's hot spot: two predicates, not the search

2026-09-19. The v3 plan flagged a T9 headline position that ranks in about
25 s and said to profile it before building step 6, since step 6 runs
through the same machinery. Profiled, and the cost is not where the plan
assumed.

## What the profile said

The worst position in the recaptured corpus (record 293, T9 USSR action
round, 8 cards) ranked in 3.40 s. By self time:

| | calls | self |
| --- | ---: | ---: |
| `opponent_event` | 1,678,782 | 0.90 s |
| `enum.__call__` / `_missing_` | 4,192,034 | 1.11 s |
| `hazardous` | 1,319,188 | 0.43 s |
| `Side.opponent` | 1,967,266 | 0.25 s |

**A third of the ranking was enum machinery inside one predicate.**
`opponent_event` read `CARDS[cid].side.value == self.side.opponent.value`,
so every one of 1.68 million calls walked a property with a branch and two
`.value` lookups. Nothing about the search was wrong; the leaf was.

## What changed

Three memoisations and one precomputation, all exact:

1. **`opponent_event` is a set lookup.** The opponent's events are a fact
   about the deck and our seat, so the set is built once per planner.
2. **`self.other`** replaces `self.side.opponent` in the inner loops.
3. **`hazardous` is memoised** per (card, hand). It was recomputed for every
   card at every node.
4. **`_next` and `_after_hand_attack` are memoised.** `solve` already was,
   and these two sit between `solve` and itself: the same state re-did the
   DEFCON-drop split and the hand-attack maximum on every path that reached
   it -- 235k and 453k calls against 74k distinct solves. The
   `hand`-minus-one-card tuples the hand-attack maximum rebuilt 3.6 million
   times are cached with them.

## Measured (local, idle box)

| | before | after |
| --- | ---: | ---: |
| record 293 | 3.40 s | **2.22 s** |
| the five worst positions | 5.47 s | **4.07 s** |
| all 401 corpus positions | 19.0 s | **16.5 s** |
| mean per ranking | 47.3 ms | **41.2 ms** |
| max | 3.49 s | **2.18 s** |

**Exactness is not argued, it is tested.** The parity corpus pins the
planner's risks in the order they were asked, so a change that moved any of
them fails `test_parity_corpus.py`. The whole suite passes (992), which is
what makes these safe: they are caches over pure functions of the state
already in the key.

## What is left, and the bigger win

The search itself is now the cost, and most of its state space is the same
position under a different name. A card nobody can be hurt by differs only
in its Ops and whether it scores, so which one you play is irrelevant.
Canonicalising the hand that way, measured over the 25 worst positions:

| | today | canonical |
| --- | ---: | ---: |
| distinct states | 25,122 | **7,317** (0.29x) |
| distinct hands | 2,283 | **473** (0.21x) |

That is a 3.4x smaller memo, and it is exact rather than an approximation --
but only if safe cards really are interchangeable, which needs checking
against space eligibility, `payable`, the scoring flag and the Five Year
Plan special case. It is the next thing to build here, with the same corpus
as its oracle.
