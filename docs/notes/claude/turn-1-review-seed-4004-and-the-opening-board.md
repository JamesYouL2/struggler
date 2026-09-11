# Turn-1 review (seed 4004, and the opening board)

`logs/game-check/*.t1*.json` and the scratch table of every Early War
event's value on the opening board found, and fixed, in
`bots/strategic.py`: De-Stalinization played for Ops (not simulated: 23 of
101 events were), Nuclear Test Ban's 3 VP over 4 Ops (Ops priced flat at
2), Fidel spaced ahead of Decolonization (both collapsed to the space
value; one space slot now goes to the worst card), Five Year Plan carrying
a 25% "loss" at DEFCON 5 (chain risk now gated on DEFCON 2), and stakes in
already-reachable Eastern Europe earning access. New strategic vs the
previous strategic: 0.84, +11 VP mean, on seeds 4000-4015 both seatings
(`logs/game-check/strategic-new-vs-old-4000-4015.json`;
`python -m struggler.bots.benchmark --bot strategic --opponent strategic@<old strategic.py>`).

The VP weight against the new Ops scale: 3 / 6 / 10 score 0.81 / 0.88 /
0.88 against the previous strategic bot, and 6 and 10 score 0.45 and 0.50
against the current default (3) in mirror matches on the same seeds
(`logs/game-check/vp-*`). No signal at 32 games; the default stays 3.

### The VP-unit value function: tried, reverted, worth retrying

Commit 2d72916 (reverted by 3f3baad) put every weight in VP: a country =
its tier's VP per scoring x the region's expected remaining scorings; a
stake = control value x conversion ** (Ops still needed); reach = a share
of the option it opens, priced by its cost; the exact region score scaled
the same way; Red Scare/Containment = rounds x marginal Op value; CIA
Created = what the granted Op buys. The turn-1 table then read the way a
strong player reads it (Nasser = two USSR Ops, Nuclear Test Ban 3 against
a 4-Ops card's 12-16, COMECON free, Vietnam Revolts up for Thailand
reach). It lost anyway: 0.31 against its parent (ab50946), 0.125 after
three follow-ups (headline = event - half its action-round use, military
credit 0.5, every future scoring cycle counted), 0.20 with the cycles
off; seven weight ablations at the turn-3 checkpoint (tiers x3/x5/x8,
discount 0.6, region 0.4, access/reserve down) all trailed by 3-6 total.
The turn-3 battleground map showed it ceding Middle East and Asia while
taking Africa and South America. The unmeasured suspects are the stake
form (conversion odds vs the linear fraction), the reserve (0.16 VP vs
0.6 VP a point), and the region score's ten-times larger share. Evidence:
`logs/game-check/vpunits*`. The form is right; the calibration needs the
checkpoint benchmark one structural change at a time, not all at once.

UN Intervention is kept for the opponent's card in hand whose event hurts
most (`un_card`): that card's Ops are valued clean, the space slot skips
it, and UN alone is worth the harm it cancels. Measured neutral against
its parent (0.41 with a De-Stalinization relocation plan, 0.44 for the
plan alone, so the pairing itself is within noise); kept because it is
the stated principle (UN + Marshall Plan is four clean Ops).

Still wrong on that board, by human judgement: Marshall Plan at 13.6 (one
Op) is far too low, COMECON at 5.4 slightly high. Both are the same gap:
a stake is valued by its fraction of the way to control, not by its odds
of converting to control by scoring time and what that control would do
to domination. Flag events value 0. The VP weight (3) has not been
recalibrated to the new Ops scale.
