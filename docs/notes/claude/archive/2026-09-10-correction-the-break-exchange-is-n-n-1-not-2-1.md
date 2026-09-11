# Correction: the break exchange is n : n-1, not 2:1

The 2:1 figure recorded above is true only of the *minimum* break, and
stating it as the general rule got the maintainer's own advice backwards.

The doubled rate for placing into an opponent-controlled country stops
the moment control breaks -- which the **first** point does. Every point
after is single rate. So the 2x toll is paid once. Measured through the
engine against a defended stability-2 country (US 2, SU 0):

| Ops spent | points bought | end state | repair Ops | ratio |
| ---: | ---: | --- | ---: | --- |
| 2 | 1 | US 2 SU 1 | 1 | 2:1 |
| 3 | 2 | US 2 SU 2 | 2 | 3:2 |
| 4 | 3 | US 2 SU 3 | 3 | **4:3** |
| 5 | 4 | US 2 SU 4 | taken | -- |

**Breaking with n Ops costs the defender n-1 to repair.** The penalty is
one Op whatever the size, so the relative loss shrinks the more you
commit. A four-Op break is 4:3, near enough fair, and the maintainer
calls it "the effective way of breaking, and the best way to break
control in stability 2 countries with no overprotection."

So "spend all your Ops" is not a warning that partial breaks get undone
-- they all get undone at these sizes. It is that **the rate improves
with commitment**, because the toll is fixed and the gain is not. My
earlier framing had the mechanism wrong while happening to reach the
same advice.

Two riders, both the maintainer's. Five Ops takes the country but only
to *bare* control, which a single point breaks again -- security needs a
sixth. And over-protection is a Mid and Late War move: on turns 1-4
neither side can spare the Op.

`tests/test_ops_wars.py` pins all of it through the engine rather than
through `points * influence_cost`, which is exactly the arithmetic the
first version of that module got wrong.

**And this is the case for the forward search rather than against it.**
The maintainer: "the weighted look ahead should handle most of this for
free." It should -- a one-ply reply prices a 3-point break against the
3-Op answer it actually invites, where a fixed discount would have to
encode the whole n : n-1 table by hand.
