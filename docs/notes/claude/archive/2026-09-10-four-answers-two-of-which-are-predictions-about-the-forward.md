# Four answers, two of which are predictions about the forward search

**The Battleground table, closed.** Egypt −1.5 (was −2) and Cuba −1.0
(was −1.5, and possibly −0.5, since adjacency is worth about +1 and
partly offsets Fidel and Ortega). The 2-3 VP spread bounds the **region
means** -- 2.67, inside it -- not the whole map, so the per-country
figures are free to run wider. Europe and Thailand tied at 6.0 is fine.
And the 4.0 floor is "probably a touch low": it gives 0.81 VP per Op
where Europe and South America sit exactly on the fitted 1.00, so about
5.0 would put ordinary ground on the same line.

**Coup size is hand-planner work.** The bot may be choosing the right
target and the wrong amount -- one Op where two or three buys the chance
of the bigger result -- and the maintainer's instruction is not to fix it
on its own. Filed against the planner with China's play charge and the
safe windows.

**OAS into Chile: "empty battleground, zero access. One ply look ahead
makes this obvious."** That is a prediction about code written tonight,
and a free test of it: the forward search should reach the maintainer's
answer on Decision 8 without being told. If it does not, the search is
weaker than the argument for it.

**Region readiness: "when you've been behind and then get to even, or
you've been even and have gone ahead."** Which is a *trajectory*
condition, not a state one -- it compares the region now against the
region earlier, and nothing in the bot remembers earlier. That explains
why `EXPERT_ASKS` item 3 has resisted an answer for so long: every
attempt has looked for a rule about the present board. The real home is
the hand planner; one ply should help.

**And the 2x risk premium has two candidate explanations**, per the
maintainer and astra: nested terms double-counting, or the 20th VP
mattering most -- the auto-victory discontinuity. The second is
testable and links the two halves of the unchaining plan: **if the
premium is really the VP discontinuity in disguise, then giving
`vp_value` its convexity should make the premium unnecessary**, and
`game_value` at its honest arithmetic value should then survive the gate
it failed twice. That is a sharp prediction and worth running as the
test of step 2.
