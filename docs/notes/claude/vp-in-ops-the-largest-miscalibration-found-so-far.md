# VP in Ops (the largest miscalibration found so far)

The flat `vp` weight of 3.0 raw priced a VP at 0.14 Ops on the opening
board and 0.08-0.23 Ops in the Mid War. The expert's rule: 1 Op = 2 VP in
the Early War (a VP is 0.5 Op), 1 Op = 1 VP in the Mid War, 2 Ops = 1 VP
in the Late War: Ops are worth most while the board is empty, VP most
when few turns remain to convert Ops. `StrategicPlayer.vp_value(obs)` =
era rate x `ops_value(obs, 1)`, so VP and Ops stay on one scale as the
board's Ops value moves (`vp_early` 0.5, `vp_mid` 1.0, `vp_late` 2.0; a
per-turn table is the refinement if tuning wants it). Used by the event
sandbox, scoring cards, wars, the space race, Yuri and Samantha, the
neural correction and the MCTS leaf. A reentrancy guard prices a VP at a
flat 20 raw per Op while the one-Op value is itself being computed
(coups and placements can price VP). The expert first stated the rule
inverted (2 Ops per VP early); the opening fixture (Olympic Games 0.3,
Korean War -1) showed ~0.5 and the corrected rule agrees. Opening fixture
unchanged at 25 misses; corpus regenerated (506 positions) as an
intentional semantic change.
