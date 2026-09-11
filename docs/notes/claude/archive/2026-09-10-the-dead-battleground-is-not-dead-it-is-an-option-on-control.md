# The dead Battleground is not dead: it is an option on Control

Refining the previous section with the maintainer. Every Battleground I
called "dead" -- the one that creates no Domination because you already
hold it -- turns out to be **exactly one away from Control**, because
Control needs the whole region. So its value is not zero:

    dead BG  =  insurance on the Domination you hold  +  P(Control) x Control VP
                (~0.5 VP)

| Region | Control VP | Dead BG | Away from Control |
| --- | ---: | ---: | ---: |
| Europe | **40** | 4th | 1 |
| Asia | 9 | 5th | 1 |
| Middle East | 7 | 5th | 1 |
| Africa | 6 | 4th | 1 |
| South America | 6 | none | - |
| Central America | 5 | none | - |

With Europe Control at 40 this is not a small correction. **Europe's 4th
Battleground is worth several times Asia's 5th** on the option term
alone, though both look identical to a tier-based value function. The
maintainer's ~2.5 VP figure is the ordinary case; Europe is the exception
and the whole reason Control VP has to scale it.

Which sharpens the earlier claim rather than overturning it. The 5th
Battleground in Asia and the Middle East really are the worst on the map,
but the reason is not that they buy nothing -- it is that their Control
prize (9 and 7) is small against the difficulty of holding *all six*
Battlegrounds. Europe's dead Battleground has the same shape and a
40-point prize.

**Two quantities the margin term needs, neither of which it has:**

1. **Tier fragility.** Domination at a +1 differential dies to one swing;
   with no Battlegrounds left for the opponent it cannot. The maintainer's
   South America case: at 2 against 1 you dominate, but the free
   Battleground means the opponent can reach 2-2, so the third is
   insurance rather than progress. Cheap to compute -- it is just how many
   Battlegrounds the opponent can still take.
2. **Distance to Control, priced by that region's Control VP.** Currently
   nothing distinguishes being one Battleground from Control in Europe
   from being one away in Africa.

And Central America and South America are the flattest regions precisely
because three and four Battlegrounds leave no room for a middle one:
every Battleground taken from the Domination point onward changes a tier.
