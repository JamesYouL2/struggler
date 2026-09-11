# 2026-09-09 — Preferred architecture for an 8-core personal laptop

The user endorsed this practical direction:

> Exact engine -> lightweight hand sampling -> selective tactical search
> -> fast handcrafted or small learned value.

Keep the engine authoritative for legality and chance. Sample hidden hands
consistently with public information, and give each simulated player only
information available to that seat. Spend search on consequential card
choices, scoring timing and a few competing investment plans; use cheap
continuations for routine atomic placements.

The recommended progression is:

1. Finish the deterministic evaluator: correct event values, scoring
   horizons and state synchronization before optimizing measured hot paths.
2. Improve search candidates and remove redundant branches before simply
   increasing simulation count.
3. Parallelize independent games first. Start around 4-6 workers and measure
   throughput and thermal throttling; eight busy workers need not be fastest
   on a laptop. Run timing benchmarks separately from training workloads.
4. Test a small CPU-friendly learned value model before learning a policy.
   Collect outcome-labeled self-play positions, with varied opponents, and
   compare prediction quality against the handcrafted evaluator on held-out
   games. Split data by whole game and seed, not individual positions.
5. Integrate the learned value only if it improves search at equal wall
   time. Compare heuristic search and learned-value search directly; retain
   the handcrafted evaluator as a baseline and diagnostic tool.

Defer full belief-state CFR, large neural networks, learning from scratch,
and sophisticated learned hand beliefs. Student of Games and ReBeL are
architectural references, not proposed laptop training recipes. Strategic
can supply initial competence and training opponents without defining every
future rollout and leaf value.

This is a preferred experimental direction, not a demonstrated strength
gain or a hardware performance guarantee. Game-generation throughput,
held-out results and equal-time playing strength decide whether learning
earns a place. The eight-core constraint changes the scale and order of
experiments; it does not require abandoning selective search.
