# 2026-09-09 — Two claims I got wrong before measuring them

Both were the same mistake: reasoning about impact from the shape of the
code instead of checking whether the thing was live and how much it was
worth.

**Warsaw Pact Formed.** The event sandbox drives an `EVENT_CHOICE` by asking
the helper policy, which scores both branches at exactly 0.0 and so
tie-breaks on option order. On the opening board it takes `remove` (all US
Influence from four Eastern European countries) where the US has none, and
the card prices at 0.00 -- while `add` places five USSR Influence in Eastern
Europe. I reported that as a large mispricing and the top priority. The
user's valuation is 0.5 Ops: the points go where the USSR already holds or
soon will, and playing it hands the US NATO. Against `tolerance_ops` of 0.75
the bot's 0.00 is inside calibration. `models/expert_valuations.json` now
records it. The branch-selection defect is real and still unfixed; what was
wrong was the evidence I offered for it, which was board movement rather
than value.

**The Coup prohibitions.** `wipe_risk` and `coup_targets` gated on DEFCON
alone, so they priced USSR Coups that NATO, the US/Japan pact and The
Reformer forbid. I described that as the bot over-defending Europe for the
rest of the game. It does not: `wipe` ships at 0.0, "off until calibrated",
so the term never runs. The fix is right and worth having -- calibrating a
term that is systematically wrong across a whole region fits the weight to
the wrong quantity, and this is what would give NATO a value -- but it
changes no game today, and I said it would.

The check that would have caught both takes a minute: for a card value, look
it up in `models/expert_valuations.json` against `tolerance_ops`; for a term,
look at whether its weight is non-zero.

### What did land

`Board.coup_prohibited` and `Board.nato_protects` are the derivation;
`Engine._usable_coup_realign_target` keeps the defender's Influence, DEFCON,
and which events are in force, and the NATO logic exists once rather than
twice. `evaluator.coup_forbidden` mirrors it in index space,
`strategic.coup_bans` reads the flags off the observation, and the event
sandbox reads them off the sandbox engine so an event that turns one on is
worth the risk it removes. Derived per call, because NATO's shield follows
US Control and a trial placement moves control.

`test_coup_forbidden_matches_the_engine_under_every_prohibition` walks every
country under all 32 flag combinations against `Board.coup_prohibited`, and
asserts each prohibition fired at least once rather than trusting that a
board happened to exercise it.

Two things the tests found that reading did not. West Germany cannot be
wiped at all -- stability 4 holding 4 needs roll + Ops >= 12, and the maximum
is 10 -- so the obvious country to write the NATO test around is the one
country in Europe where the term is silent. And under NATO the risk that
remains is divided over fewer targets, so lifting the shield on one country
with De Gaulle does not return it to its unshielded value; it lands harder
than it did before.
