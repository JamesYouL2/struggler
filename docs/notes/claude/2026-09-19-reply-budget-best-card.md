# The reply budget: the opponent answers with their best card

2026-09-19. The maintainer: "v0.2.1 has to do with the reply budget being
too low. Either set it to 4 total, or have the weighted average be some
kind of maximum reply."

## Why it fits

- **The shipped model (3) is not a maximum.** It weights each budget 0-4
  by how often a SINGLE unseen card has that many Ops. The non-scoring deck
  is 14 one-Op, 40 two-Op, 36 three-Op and 12 four-Op cards, so the
  average budget is about 2.45 Ops, with 12% weight on a 4-Op answer.
- **The opponent chooses their best card.** A seven-card hand holds a 3+
  card about 99% of the time and a 4-Op card about 59% of the time.
- **The phantom matches the drift.** The China "phantom", a 4-Op card in
  every reply budget, was removed by `bc5ef93` on 2026-09-12. Restoring it
  read +0.055, all of it in `_reply_budgets`
  ([the trace](2026-09-13-the-china-phantom-lives-in-the-reply-budget.md)).
  v0.2.0 and v0.2.1 have the phantom; `07d553a` and later do not. The
  1024-seed drift canary puts the bot behind exactly v0.2.0 and v0.2.1 and
  ahead of `07d553a` onward
  ([the drift note](2026-09-18-drift-located-at-v0.2.1-v0.2.3.md)).
- **The earlier "max" test was confounded.** A max model was tried on
  2026-09-13 (model 4 of `experiment/reply-budget-models`) and read 0.479,
  but that was before the reply-model fixes, which the phantom note flags
  as a confound.

## What was built (`exp/reply-budget-max`, from the revert branch, fit off)

`reply_model = 4`: the exact hypergeometric distribution of the maximum
printed Ops among `opponent_hand_size` cards drawn from the unseen pool,
scoring cards as 0 (`_best_card_budgets`). It uses public information
only, and is cached once per decision, reset with `_reply_budget_pool`.

Tests (`tests/test_reply_budget.py`):

- the budgets form a distribution;
- a one-card hand reproduces the pool's own Ops mix exactly;
- the budget grows with hand size and is above the shipped model's at 7.

Footprint: across 120 placement positions from the corpus, the top action
changes in 2 (model 4) or 3 (`reply_ops` 4) against model 3. That is the
same order as the phantom's 9 in 401, so 1024 seeds are needed.

## Arms (1024 seeds, 34000-35023, anchored from the start)

| arm | weights | anchor | paired against |
| --- | --- | --- | --- |
| `rb-base-vs-v0.2.1` | defaults | v0.2.1 | -- |
| `rb-ops4-vs-v0.2.1` | reply_model 1, reply_ops 4 | v0.2.1 | base |
| `rb-max-vs-v0.2.1` | reply_model 4 | v0.2.1 | base |
| the same three `-vs-07d553a` | | 07d553a | base |

Success means the gap to v0.2.1 closes (paired gain, and the score toward
or past 0.500) without losing ground against 07d553a.

## Results (run 35457740325): neither closes the gap

| arm | score | one-sided 95% | paired vs base |
| --- | ---: | --- | --- |
| `rb-base-vs-v0.2.1` | 0.485 | [0.468, 0.502] | -- |
| `rb-ops4-vs-v0.2.1` | 0.465 | [0.449, 0.481] | -0.020 [-0.037, -0.003] |
| `rb-max-vs-v0.2.1` | 0.491 | [0.475, 0.507] | +0.006 [-0.012, +0.023] |
| `rb-base-vs-07d553a` | 0.499 | [0.482, 0.516] | -- |
| `rb-ops4-vs-07d553a` | 0.486 | [0.469, 0.503] | -0.012 [-0.030, +0.005] |
| `rb-max-vs-07d553a` | 0.475 | [0.458, 0.492] | **-0.024 [-0.042, -0.006]** |

- **A flat budget of 4 is worse** against v0.2.1, measurably, and leans
  worse against 07d553a. It over-fears the reply.
- **The best-card maximum is a wash against v0.2.1 and loses to
  07d553a.** It would not have passed the anchored check, so it is not
  adopted.
- The shipped model (one random unseen card) stays. The v0.2.1 gap is
  not the reply budget's size. On this fresh block the base reads 0.485
  against v0.2.1, inside the drift canary's 0.470-0.474 at PR #4's code.
  The next candidate is bisecting v0.2.1..07d553a itself.
