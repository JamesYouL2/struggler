# Wipe exposure is a variance term, not a discount — and turn 1 is not turn 4

Two corrections that fit together. The maintainer: "turn 1 is obviously
super different than turn 4", and "on turn 4, France by a mile;
Iraq/Pakistan/Iran/Egypt are only important **because of** wipes."

The second reads at first like the opposite of the discount table, and it
is not. The two statements are about different terms:

- **The marginal Influence point** in a wipeable country is worth little,
  because a card can remove the whole stack without the opponent spending
  an Op on the board. That is the discount, and it is what "you cannot
  overprotect the Middle East" means.
- **Whether you hold the country at scoring time** is worth as much as
  ever, and in a wipeable country that outcome is decided by which card
  turns up rather than by who spent Ops. That is what makes Iraq,
  Pakistan, Iran and Egypt *important* at turn 4 with every scoring card
  still in the deck: they are where the VP actually moves.

So wipe exposure lowers the value of the marginal point while leaving —
arguably raising — the value of the tier swing the country participates
in. **Those are different terms in the region-margin function and the bot
conflates them into one.** It has no notion of variance at all, which is
why it cannot express either half.

On the periods: the Ops-to-reach ordering in the previous section is a
turn-1 instrument and says nothing about turn 4, where the setup is long
gone and the Mid War region weights have risen from 0.51 to 1.64. France
leads both, and at turn 4 "by a mile" — which is what Europe Control at
40 plus forced defensive spend predicts. The rest of the turn-1 order does
not carry over.
