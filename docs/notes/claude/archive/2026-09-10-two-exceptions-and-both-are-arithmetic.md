# Two exceptions, and both are arithmetic

The maintainer: "Thailand and Europe have to be the only differences,
because of math? That 20 VP minimum jump is real."

Checked, and yes -- exactly two, and neither is a matter of judgement.

**Thailand is the only Battleground scored by two cards.** Seven
countries lie in Southeast Asia and are counted by both Asia Scoring and
Southeast Asia Scoring: Burma, Laos/Cambodia, Thailand, Vietnam,
Malaysia, Indonesia, Philippines. **Thailand is the only Battleground
among them.** Every other country on the map is scored once. That is why
it is the single per-country exception the bot's own numbers already
show -- 0.176 against 0.117 for the rest of Asia -- and it needs no
expert input, because it falls out of the country table.

**Europe is the only region whose Control is a win condition rather than
a VP award**, and the size of it is not a constant:

| VP (US view) | Europe Control to the US |
| ---: | ---: |
| −15 | 35 VP |
| −5 | 25 VP |
| **0** | **20 VP** |
| +5 | 15 VP |
| +15 | 5 VP |

**It is worth `20 - vp`: the distance to auto-victory.** Twenty at par,
which is the "20 VP minimum jump", and more when behind. It is also a
genuine discontinuity -- Europe Domination is 7 VP and Control is 20 at
par, a cliff between adjacent tiers that no smooth function of Ops can
represent.

**And it is the same expression the game-swing work arrived at
independently.** `game_value` should be `20 - vp` upward and `20 + vp`
downward rather than a flat 40; Europe Control's value *is* that upward
swing, because it realises it in one step. Two unrelated threads landing
on one formula.

That also resolves three numbers that looked like they were fighting:

- **40** is the whole track, and is only right from −20.
- **20** is the value at par, and is the honest default.
- **~15**, the maintainer's 1.67x of the fitted curve, is what it is
  worth to *chase* -- the realised value discounted by the odds of
  getting there.

**So the region model reduces to one parameter and two rule-derived
exceptions.** Value proportional to the Ops a region absorbs; Thailand
counted twice because two cards score it; Europe Control priced at the
distance to victory. That replaces six free constants with something
fitted to eighteen points and two facts about the rulebook, and it is a
far better starting shape than tuning six weights against a gate that
needs 96 seeds to see six points.
