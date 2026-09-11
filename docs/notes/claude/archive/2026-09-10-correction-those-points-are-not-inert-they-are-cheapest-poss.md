# Correction: those points are not inert, they are cheapest-possible breaks

The section above is wrong in its central claim and the conclusion it
drew from it. It said the bot's top-ranked placements were "inert" points
that "flip no control". **They all flip control**, and checking takes one
line:

| Country | US | SU | Stability | Control now | After +1 USSR |
| --- | ---: | ---: | ---: | --- | --- |
| Thailand | 21 | 19 | 2 | US | **nobody** |
| Pakistan | 9 | 7 | 2 | US | **nobody** |
| India | 3 | 0 | 3 | US | **nobody** |
| Japan | 4 | 0 | 4 | US | **nobody** |
| Cuba | 3 | 0 | 3 | US | **nobody** |

"One point into Japan where the USSR needs eight" was the error: eight is
what *control* costs, one is what *breaking* costs. The bot is finding
the cheapest break available, every time, and ranking it first. That is
locally correct, and `_investment` returning one point is correct too --
the rate is concave because the first point does all the work. The
proposed `>` to `>=` fix is a no-op and was reverted; the rate is never
flat.

**And the real economics are exact, which is better than the story it
replaces.** Placing into an opponent-*controlled* country costs 2 Ops per
point. Once broken, nobody controls it, so *restoring* costs 1 Op per
point. Break Japan for 2 Ops and the US puts it back for 1.

> **A break that does not also take control loses the exchange two to
> one.**

That is the maintainer's "you have to spend all your Ops, because
otherwise you make it too easy for the opponent", as arithmetic rather
than as judgement, and it is why the defender wins break wars. It also
explains the stability-2 concentration: those are the countries where
both sides can keep re-breaking cheaply, so the 2:1 exchange runs over
and over and forty points accumulate.

**The fix is unchanged and now better motivated.** No discount term is
needed and none would be principled -- the bot's valuation of the break
is right, and what it is missing is the reply. One ply of
opponent-response makes the 2:1 exchange visible, and "commit or stay
out" falls out of it: a break big enough that restoring costs the
opponent more than it cost you is exactly a break that survives one ply.
