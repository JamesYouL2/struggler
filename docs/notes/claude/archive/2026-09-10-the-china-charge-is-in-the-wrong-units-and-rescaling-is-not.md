# The China charge is in the wrong units, and rescaling is not a no-op

The maintainer, on the claim that scaling the board terms changes nothing:
"rescaling does matter because of VP cards (like OPEC / Arms Race)."

Measured on seed 4002 at turn 4, scaling `w.battleground` and `w.control`
by 0.5, 1, 2 and 4, OPEC's value stays at exactly −2.000 times the one-Op
value at every scale, so *that* ratio is preserved. But the one-Op value
itself goes 45.02 → 83.77 → 161.25 → 316.21, which is **sub-linear**:
1.86x, 1.92x, 1.96x for successive doublings. So the system is not
scale-free, it merely converges to scale-free as the board terms grow.
Something absolute is anchoring it, and the maintainer is right that the
absolute level is a real parameter -- the earlier note claiming otherwise
was wrong, and is corrected in place above.

Chasing the anchors turned up a bare one. **The China Card charge is
subtracted from `card_play_value`, which is in raw board units where one
Op is worth 83.77 on this board.** The constant is 5.0. That is **0.06
Ops**, where the intent was 5.

And the write-up made it worse rather than better. The code it replaced
was `value -= 4`, which claimed nothing. It was renamed `CHINA_HOLD_OPS`,
documented "in Ops", given a test asserting `>= 4.0` as "the 2-VP-swing
floor", and committed with a message saying it implemented the
maintainer's figure. **Shape 6 (a number on the wrong scale) and shape 8
(a test that encodes the defect as the contract), in the same change, in a
commit whose whole subject was scale discipline.**

It is renamed `CHINA_HOLD_RAW` and left at 5.0 rather than multiplied by
thirty, because the naive correction is worse than the bug: 5 Ops
converted honestly is about 187 raw against a 4-Ops card worth 149, so
China would never be played at all. The maintainer's 5 Ops is what
*holding* the card is worth, and playing it hands that to the opponent
rather than destroying it, so the charge is some function of both, not the
hold value. That needs their number and a gate. The test now pins the
discrepancy so closing it has to be deliberate.

**The open question this leaves**, and it is bigger than China: how many
other bare constants are added to or subtracted from board-unit values?
`value -= max(0, len(obs.hand)-3)` for Five Year Plan is the next one, and
it is at least documented as a tie-break. A sweep is warranted.
