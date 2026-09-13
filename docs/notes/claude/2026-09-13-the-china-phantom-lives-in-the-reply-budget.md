# The China phantom's five points live in the reply budget

`bc5ef93` stopped counting the China Card as an unseen card (it is face up,
and counts toward nobody's hand size). Putting it back -- the "phantom" --
gated five points better against main: 0.557 [0.507, 0.606] with rotated
books, 0.555 [0.506, 0.603] on iran/austria. The question was which of the
five places that read `card_state(obs, c) == 'unseen'` carries that.

## What was measured

`scripts/phantom_trace.py` ranks every one of the 401 parity-corpus positions
with the shipped bot, then again with the phantom restored -- everywhere, and
in each consumer alone (it patches `card_state` by caller name). It counts
decisions that change. It does not play games and is not a strength
measurement.

| phantom restored in | top action changed | order changed | agrees with "all" |
| --- | ---: | ---: | ---: |
| every consumer | 9 | 80 | - |
| `_reply_budgets` | 9 | 80 | 9/9 |
| `_unseen_holds` | 0 | 0 | 0/9 |
| `_hand_attack_value` | 0 | 0 | 0/9 |
| `_hand_upgrade_value` | 0 | 0 | 0/9 |
| `_ops_modifier_value` | 0 | 0 | 0/9 |

The whole effect is the reply budget. The other four consumers see a pool one
card larger (median 27 against 28) and rank nothing differently. The nine
top-action changes are 5 `place_influence` and 4 `ops_type` -- both decisions
the forward search's reply discount prices. The event values the phantom
moves most often (Grain Sales 39 positions, Missile Envy 19, Containment 19)
move without changing a choice.

## What it means for the reply model

The phantom put a 4-Op card into every reply budget: the opponent was assumed
able to answer with the China Card whoever held it, face up or face down. The
restored strength is therefore a statement about the reply budget being too
small without it, not about the China Card as such -- and the phantom is the
wrong way to fix that, because it credits the opponent with our own card.

The maintainer's two candidates, measured separately
(`experiment/reply-budget-models`, `tests/test_reply_budgets.py`):

- **model 5** -- model 3's pool, plus the China Card only when the opponent
  holds it face up. The phantom, restricted to where it is true.
- **model 4** -- the budget is the maximum of the opponent's known cards (their
  face-up China Card) and the best card in a hand of `opponent_hand_size`
  drawn from the unseen pool, scoring cards drawn as zeros. A reply is made
  with their best card, not an average one.

If model 5 recovers the phantom's points, the card was the whole story. If
only model 4 does, the phantom was standing in for "budgets are maxima", and
the China Card was the largest card that happened to be in the pool.

## What this does not say

Nothing about strength. Decision changes on a fixed corpus attribute the
phantom to a code path; the gates are what say whether any of it is worth
points.
