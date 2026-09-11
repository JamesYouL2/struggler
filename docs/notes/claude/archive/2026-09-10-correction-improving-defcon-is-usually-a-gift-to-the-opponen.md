# Correction: improving DEFCON is usually a gift to the *opponent*

I recorded "acting immediately after a DEFCON improvement is worth an Op"
and treated it as a benefit to the side that improves it. The sign is
usually wrong, and the maintainer's Glasnost explanation is why.

The mechanism is not the regional restriction I assumed (8.1.5 geography,
which never covered Africa anyway). It is that **at DEFCON 2 any
Battleground Coup ends the game**, so improving to DEFCON 3 makes
Battleground Coups safe again *everywhere*. The value goes to whoever
acts next -- and after your own action round, that is your opponent about
80% of the time.

So Glasnost's base finally adds up: 2 VP to the USSR, worth roughly 4 Ops
at the Late War rate, **minus** handing the US a free Battleground Coup
worth about the same. Base 1.0. The arithmetic that would not close was
missing a cost, not a discount on the VP, and `vp_late` at 2.0 is fine.

Two consequences.

**The bot has this backwards twice over.** It prices a DEFCON improvement
at 0 (the sandbox measures influence and VP), and my proposed fix would
have added a *positive* constant for the improver. The correct treatment
is a transfer: mostly negative for the side that improves DEFCON, positive
for the side that moves next.

**It is the same shape as Military Ops.** Both are turn-order effects that
the position evaluator cannot see because they are not on the board, and
both are worth about a card. That is now two, which suggests looking for
the rest rather than patching each.

Also from the maintainer, and it belongs in the Battleground table: **a
free Battleground Coup in the Mid to Late War is worth almost 2 VP by
itself**, and the proposal is to value Battleground Coups as equal to an
Africa Battleground (Angola, Zaire, Nigeria). Noting a tension to resolve
with them: the Sankt-derived table puts an Africa Battleground at ~4 VP,
so "a Coup is worth almost 2 VP" and "value a Coup as an Africa
Battleground" differ by about a factor of two unless the second means the
marginal rather than the total.
