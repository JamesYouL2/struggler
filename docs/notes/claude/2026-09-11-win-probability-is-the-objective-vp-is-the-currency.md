# Win probability is the objective; VP is the currency

The maintainer asked, mid-way through denominating the value function in
VP: "What about win probability? What calculates what? Does VP value
calculate win probability or is it denominated by win probability?" Then,
before the answer landed, supplied the better formulation themselves.

## The answer: denominated by

Win probability is the only terminal quantity. VP is a state variable,
not a utility. The chain runs

    board + hand + turn  ->  expected VP  ->  P(win)

and the value of an action is `dP(win)`. So a VP is worth `dP/dVP` -- a
**rate**, and a state-dependent one, not a constant.

But VP stays the working currency, because the value function is a sum of
terms and **VP adds while probability does not**. Sum in VP; carry
`dP/dVP` in the exchange rate. That rate is precisely what `per_vp(turn)`
stands in for, which means the turn curve is an estimate of something
real rather than a free parameter.

## The maintainer's formulation, which is stronger

> Win probability should be based solely on VP difference, board value,
> hand value, and deck value... but board value, hand value and deck value
> are all denominated in VP?

This is a **sufficient-statistic** claim: the position matters only
through one scalar.

    v_eff  = vp_track + board_vp + hand_vp + deck_vp
    P(win) = F(v_eff, spread)

It is better than framing the objective on the VP track, because it makes
"behind" mean *behind in effective VP*. A side at -5 on the track with a
dominant board is not behind and should not be gambling. The track alone
cannot express that.

## Three things it requires

**1. Board and deck double count if they are added.** The remaining
scoring cards are not a separate pile of VP; they are *how board value is
paid out*. And the code already knows this: `_urgency_for` sums
`scoring_discount ** turns` over `scoring_schedule(obs, card)`, which
reads deck state, and `country_value` multiplies importance by that
urgency. So the composition is **board x schedule**, not board + deck.
A separate "VP remaining in the deck" addend counts the same VP twice.

The same discipline binds `hand_vp`: a hand's Ops *become* board, so hand
value has to be marginal over what the board already promises. Every term
in the sum is a delta over the ones before it. That is a rule to hold, not
something that falls out of the definitions.

What does belong as a genuine addend is event VP -- cards that award VP
directly rather than through a region scoring. That is not board-mediated.

**2. Deck value's real job is the denominator.** Two positions with
identical `v_eff` have very different win probabilities if one has 20 VP
of scoring still to come and the other has 5. The deck sets the
**spread**, and that is where it earns its place.

Which is the payoff: under `P(win) = F(v_eff / s)`, the marginal value of
a VP at par is `1 / (4s)`. So

    per_vp(turn)  =  1 / spread(turn)
    vp_swing      =  spread(turn 1) / spread(turn 10)

`vp_swing` is not a taste parameter. It is a ratio of standard deviations,
computable from `public_cards.py`, which already owns the scoring schedule
and the reshuffle estimate. The turn curve is the proxy to use until the
deck-aware spread exists.

Note the model predicts a **hyperbolic** rise, not an exponential one: as
the scoring opportunities remaining fall roughly linearly, `1/s`
accelerates late. Bounded below by final scoring, which keeps `s(10)` off
zero.

**3. It pins the board weight scale, and that is the biggest
consequence.** Today the absolute scale of the board weights is arbitrary
and provably cancels -- `Q/O = (1-r)(S/O) - 40er`. Denominate board value
in VP and the scale stops being free: "controlling Iran is worth 1.2 VP"
becomes a falsifiable claim, checkable against what positions actually
score in self-play. That converts most of the 28 weights in
`StrategicWeights` from tuned parameters into measured ones.

It also demotes `AUTO_VICTORY_VP` from a chosen constant to the location
of an absorbing barrier, which is a rule.

## What this says about curvature, and the hazard in it

A linear-in-VP objective is **risk-neutral everywhere**, which is what the
bot has today. Under `P(win) = F(v_eff / s)` the objective is curved:
convex when behind (a coin flip is worth taking), concave when ahead. That
is the maintainer's "swingyness/aggression, pushing/defending 20 VP hard",
and it arrives free -- no aggression parameter.

It is also the best available explanation for the ending-turn statistic:
8.00 against a human field's 6.81, Late War reached in 70% against 48%.
Pressing for the 20 VP track is a variance trade, and a risk-neutral
evaluator is indifferent to variance by construction. The bot cannot press
because nothing in the objective pays for it.

**The hazard:** risk-seeking when behind is, concretely, taking DEFCON
shots -- which is what the maintainer comment in `stakes.py` already asks
for. But the nuclear rate is 15.6% against a human 5.4-11.7% band and the
gate vetoes at 25%. Curvature pushes toward the veto, and that is likely
to bind before strength does.

## State of the machinery

`value_of_win_probability` and `clipped_win_probability` exist in
`stakes.py` and have **no caller in `src/`** -- only `tests/test_stakes.py`.
There is no win-probability estimator in the bot. They are a calibration
hook with nothing hooked to them, and the map is linear (`(2p-1) * 20`),
which is a chord through the real curve: correct at par, correct near the
0.90 ceiling by construction, wrong in between.

## Order of work

1. Ship the 2x turn curve. First-order term of the right thing, gate-ready.
2. Log a per-turn VP trace (games record only final `turn`/`vp`/`winner`
   today) and measure `spread(t)`. No behaviour change.
3. Gate the measured exponent against 2x.
4. Then curvature in `v_eff`, gated separately. Biggest blast radius, and
   the change that should move the ending-turn number.

## Separating the two variables (maintainer, same exchange)

> Board value / hand value / deck value should all be calculated at VP
> value at zero VP diff. And we can separate these two variables? ... We
> probably do need to separate these two values.

Yes. The split is

    position_vp = board_vp + hand_vp + deck_vp     # at par. pure.
    P(win)      = F(vp_diff, position_vp, spread)  # all score-dependence

and there are three reasons, the third of which is not obtainable any
other way.

**It kills a circularity this repo has already paid for.** `v_eff =
vp_diff + board_vp(v_eff)` is implicit and self-referential, and the
codebase carries the same shape today: the `coup -> vp_value -> ops_value
-> coup` cycle, documented in `tests/test_order_independence.py`. Breaking
it the naive way -- pricing a VP off the placement spend -- was tried at
`a12d2af` and **the gate rejected it at 0.434 with 13 nuclear losses**,
because `game_value` is the VP price times the track, so cheapening a VP
cheapened losing the game. The fix that survived was to fix the price up
front. Computing position value at par is that fix made principled rather
than operational: the VP denomination reads turn and deck, never score.

**The nonlinearity belongs to the outcome map, not the position.** The
objection to "at par" is that a board really is worth less at +19, where
Europe Control is worth 1 VP because it simply wins. True, but that is `F`
saturating, not the board changing. A board is worth what it is worth in
VP; how much that VP matters is a property of where the track stands. All
track-dependence in `F` and only in `F` buys the saturation for free and
keeps `position_vp` a pure function -- which is also what makes it
comparable across games and turns, and therefore measurable at all.

**They have different error properties, and summing early destroys
that.** `vp_diff` is observed exactly, with zero error. `position_vp` is a
model estimate with large error. Separated, the estimate can be validated
on its own (does a position estimated at +3 actually score +3? -- the
per-turn VP trace now recorded in `benchmark.play_game` is what answers
this), and a shrinkage can be fitted:

    F(vp_diff + lambda * position_vp, spread),  lambda <= 1

One parameter, well posed, fittable from self-play, and invisible if the
two are pre-summed. `lambda = 1` is the current implicit assumption and
nobody has tested it. This is also the answer to whether the split
collapses back into a single sum: only if `lambda` is 1.

**Blast radius.** `vp_value` is already score-independent -- it reads only
`obs.turn`. The leak is `game_value = GAME_SWING_VP * vp_value`, which
folds the track in, and every `priced()` sentinel bound depends on it.
Those are what would move into `F`, and the `a12d2af` result says to gate
that rather than refactor it confidently.

## Threats, and what the logit form already buys (maintainer, same exchange)

> Logit function is probably best for vp value based on diff. And there
> are so many ways you should threaten to win the game, so ideally board
> value is really denominated in individual vp diffs to get to win
> probability, but holy hell that's going to be so hard to calibrate. And
> obviously specific cards in hand that get you to 20 vp are amazing.

### The logit retires machinery rather than adding it

`LOSS`, `Certain`, `priced()` and `GAME_SWING_VP`-as-a-clamp exist
*because* a linear-in-VP objective cannot express saturation, so every
terminal outcome needs a hand-placed bound and every value term needs to
know not to do arithmetic on one. Under `F` the saturation is the
function. Most of the sentinel layer stops being necessary rather than
merely becoming correct.

### The card case is already handled; the board case is not

Both card paths sandbox the play and detect the ending:

- `scoring_card_value` resolves the card and returns `-LOSS`/`LOSS` when
  `engine.is_terminal`, so a scoring card crossing +20 is priced at the
  game rather than at its VP.
- `_resolve_sandbox` does the same for events, including the
  probabilistic case: a die face that ends the game is worth its share of
  `game_value`, not its share of a sentinel (the Summit fix).

**The board is the gap.** A board promising +15 VP to a side standing at
+13 is worth *winning*, and board value is linear in VP with no reference
to the distance to the barrier.

And the maintainer's own separation closes it for nothing: with all
score-dependence inside `F`, `position_vp` beyond the barrier is
automatically worthless because `F` saturates. What would otherwise be a
barrier check in seven board terms falls out of the architecture.

### Threat multiplicity is one parameter, not a threat model

Two effects that look alike and are not:

**Variance.** More ways to score widens the outcome distribution, so `s`
rises. Automatic once `s` is a position quantity rather than a turn
constant, and it correctly makes variance good when behind and bad when
ahead.

**Option value.** The real threats effect, and separate: the opponent
cannot defend everything, so the realized outcome sits closer to the *max*
of the threats than to their mean.

What makes the second tractable is that **the shape of `E[max]` is a
constant of mathematics, not a tunable**. For `n` roughly exchangeable
threats,

    E[max] - mean  ~  sigma * a(n)
    a(n) = 0, 0.56, 0.85, 1.03, 1.16   for n = 1..5

(the expected maximum of `n` standard normals: `1/sqrt(pi)`,
`3/(2 sqrt(pi))`, ...). So the fit is **one scale**, `position_vp + kappa
* sigma * a(n)`.

`n` is nearly free: `region_margin` already computes the distance to the
next scoring tier for all seven regions on every decision, and a live
threat is a region where a plausible Ops investment crosses a tier.

**Caveat, stated rather than corrected:** `a(n)` assumes independent
threats, and Twilight Struggle threats are correlated -- they compete for
the same Ops and the same cards -- so the true premium is smaller. `kappa`
would absorb correlation and opponent defensive scarcity together and
would therefore not be interpretable as either. A fitted fudge with a
principled shape, not a measurement.
