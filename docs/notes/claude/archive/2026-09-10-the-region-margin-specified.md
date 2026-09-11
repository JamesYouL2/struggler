# The region margin, specified

Enough has now arrived to write this as a function rather than tune it.
Collecting the maintainer's rules into one place, in the order the value
accrues as you take a region.

**1. Presence is a tier, and one Battleground denies Control.** The first
country in a region buys Presence. The first *Battleground* additionally
makes the opponent's Control impossible outright, because Control needs
`side_bg == total_bg` -- there is no partial version. In Europe that is
denying an automatic victory, so the first Europe Battleground carries a
denial term worth a share of 40 VP whatever else it does. Nothing in the
current function represents denial at all.

**2. Linear up to Domination.** Between Presence and the Domination
differential the value is roughly linear in Battlegrounds -- this part
the existing `progress` and `margin_battleground` terms already
approximate, and it is the part they get least wrong.

**3. The differential is the tier.** Domination turns on `side_bg >
opp_bg`, so the Battleground that takes you from level or behind to ahead
is worth the whole tier and the next is worth much less. A threshold
model gets this wrong in both directions.

**4. Equality is worth something on its own.** Being level on
Battlegrounds *blocks* the opponent's Domination. That is a real
defensive value with no term today: the bot sees no difference between
being level and being one behind, when one denies a tier and the other
concedes it.

**5. Insurance, once ahead.** A +1 differential dies to one swing; it
stops dying when the opponent has no Battlegrounds left to take. The
South America 2-against-1 case: the third Battleground is insurance, not
progress.

**6. The last Battleground is an option on Control**, priced by that
region's Control VP -- 40 in Europe against 9 in Asia and 6 in Africa.

So the shape is: `denial + linear progress + tier step at the
differential + insurance + option on Control`, with Control VP scaling
the last and the first. Six regions, one function, and it replaces
`margin_presence`, `margin_battleground`, `margin_country` (which goes to
zero outside Asia) and part of `progress`.

That is four tuned weights becoming one structured function with two
constants -- the insurance rate and the Control option rate -- which is
the kind of collapse the weights audit was supposed to find and could
not, because the structure had to come from outside.
