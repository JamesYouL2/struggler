# The phantom beats the correct China Card, and that is the finding

Three readings of "the China Card in the opponent's reply budget", all
against the same shipped bot (reply model 3: the Ops of the unseen
non-scoring cards):

| variant | what the reply budget adds | reading |
| --- | --- | --- |
| phantom (`experiment/china-phantom`) | the China Card, **always** -- ours, theirs, face up or down | gate 0.557 [0.507, 0.606] rotated books; 0.555 [0.506, 0.603] iran/austria |
| model 5 | the China Card only when the opponent holds it **face up** | pooled 0.475 [0.455, 0.494] (gate 0.482 +/-0.017; 256-seed experiment 0.471, REJECTED) |
| model 4 | max(their face-up China Card, best card of an `opponent_hand_size` draw) | pooled 0.479 [0.449, 0.509] (gate 0.475 +/-0.024; experiment 0.482) |

Pooled is inverse-variance over the gate and the experiment. Sources:
`2026-09-13-the-china-phantom-lives-in-the-reply-budget.md`,
`2026-09-13-reply-budget-models.md`, the phantom gate notes.

The rule-correct version is about 2.5 points worse than shipping nothing;
the rule-incorrect one is about 5.5 points better. `phantom_trace.py` put
all of the phantom's decision changes in `_reply_budgets`, so this is not a
side effect somewhere else. Something about the reply budget is wrong, and
the phantom happens to correct it.

## Hypotheses, each with the reading that would separate it

1. **Budgets are too small in general.** A 4 added to every pool raises
   every weighted budget; the China Card is incidental. Model 5 adds it in
   a minority of positions and model 4 replaces the average with a maximum
   -- both *should* raise budgets too, which argues against this, unless the
   size of the shift is what matters. Separates with: model 3 plus a
   constant 4-Op card always (the phantom, as a named model) against model 3
   plus a constant 3-Op card.
2. **"Face up" is the wrong condition.** When we play the China Card it
   passes to the opponent face down and is theirs for the rest of the game.
   The reply search prices the next action round, but what the reply is
   *protecting against* pays at the next scoring, by which time a face-down
   China Card usually is face up. Model 5 drops exactly that case. Separates
   with: the China Card whenever the opponent owns it, face up or down.
3. **Holding it ourselves should raise their budget.** Implausible as a
   rule, but the phantom's gain is concentrated wherever model 5 differs
   from it, and when we hold the China Card is the largest such set.
   Separates with the same pair as 2: if "owns it, either face" recovers the
   phantom, 3 is not needed.
4. **The reply model is mis-specified and a larger budget compensates.**
   Codex's Q1/Q2/F5 (unreachable replies, the doubled retake cost, replies
   after the last move) and M1 (delta missing other countries' access) all
   distort the same discount. A budget error could be offsetting one of
   them. Separates with: re-running the phantom and model 5 on top of
   `experiment/reply-fixes` once it is gated.

## Not decided

Proposed, not dispatched. The cheapest decisive pair is hypothesis 2's --
the China Card whenever the opponent owns it, against the phantom, both
256 seeds -- and it is worth running after the reply fixes land, since 4
would change what both mean.
