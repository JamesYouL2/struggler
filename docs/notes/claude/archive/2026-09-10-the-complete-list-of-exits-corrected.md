# The complete list of exits, corrected

The maintainer, on the claim that a 1-Op card has no way out: "there is
Ask Not / Containment / Brezhnev? Anything else I'm missing?" -- and the
previous section was indeed incomplete. Three exits work regardless of a
card's Ops, and two modifiers move a card across the threshold.

**Exits that ignore Ops entirely:**

| Exit | Who | Reach |
| --- | --- | --- |
| **UN Intervention** | either side, holding it | Play the opponent's card for its Ops and the event does not fire. The clean exit, at any Ops value. Cannot be used on itself (`cid != un_intervention_id`). |
| **Ask Not What Your Country Can Do For You** | **US only** | Discard any number of hand cards and redraw. The event benefits the US whoever plays it, so the USSR playing it for Ops hands the US the discard -- it is not an exit the USSR can buy. |
| **Space Race box 6** (Eagle/Bear Has Landed) | its sole holder | Discards the **Held Card** before the next deal -- one card, once a turn, and only the card carried between turns, not anything in hand. Much narrower than "discard a held card" suggests. |

**Involuntary, but they do clear a trap:** Terrorism, Five Year Plan,
Grain Sales, Aldrich Ames and Missile Envy all remove cards from a hand
without playing them. An opponent attacking your hand may take the 1-Op
card you could not get rid of, which is a real reason the hand-attack
terms should not be priced as pure harm.

**Exits that need 2+ Ops, and so are closed to a 1-Op card:** the space
race (boxes 1-4 need 2, rising to 4), the Quagmire / Bear Trap discard
(`>= 2`), and the Blockade / Latin American Debt Crisis payment (`>= 3`).

**And the threshold moves.** Exits test the *modified* Ops (FAQ 7.4), so:

- **Containment** (+1 to all US Operations) and **Brezhnev Doctrine** (+1
  to all USSR) lift a 1-Op card to 2 and **open every exit** for a turn.
  That makes them defensive cards as well as offensive ones, which is not
  how either is usually described.
- **Red Scare/Purge** (−1 to the opponent, **minimum 1**) pushes a 2-Op
  card down to 1 and **closes them all**. The minimum means it cannot
  strand anything below 1, so its trapping power is exactly the 2-Op
  cards.

So the corrected statement is not "a 1-Op card cannot be shed" but: **a
1-Op card can only be shed by UN Intervention, by Ask Not if you are the
US, or by luck** -- and Containment or Brezhnev can lift it out of the
trap for a turn. Fourteen cards sit at 1 Op; Lone Gunman and CIA Created
are on the safe-window list and are two of the three the planner scores
at 0.00 risk.

One consequence for the planner, which already models `payable` at 2+:
**it should also model UN Intervention and Ask Not as exits**, or it will
keep reporting a trapped hand that a held UN Intervention makes safe.
