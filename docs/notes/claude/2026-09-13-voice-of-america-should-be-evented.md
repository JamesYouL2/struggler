# The Voice of America should be evented almost always

The maintainer, 2026-09-13, after reading game logs: **the US should event
The Voice of America basically always -- about 95% of the time** -- and they
are concerned the bot does not.

The card: US, 2 Ops, "Remove 4 non-US Influence from non-Europe countries
(no more than 2 per country)". Four points of USSR influence for a 2-Op
card, at any turn, anywhere outside Europe -- which is why spending it for
Operations is almost never right.

## What the strategic bot does, measured

Pooled over 91 benchmark reports on disk (`logs/**/*.json`, every
`card_modes` counter; the gate, drift and ablation runs of 2026-09-11 to
2026-09-13):

| the US played The Voice of America | plays |
| --- | ---: |
| as its headline (the event fires) | 4287 |
| for its event in an action round | 1739 |
| for Operations | 5 |
| on the Space Race | 0 |

That is **99.9% event** (1739 of 1744 action-round plays, 99.7%, and every
headline). Only two reports fall under 95%, each by a single Ops play:
0.92 (11 of 12, `coup-discount-1` held-out sample) and 0.95 (18 of 19, the
iran/austria gate against 9b90ef0).

So in the reports this repo keeps, the concern does not reproduce -- which
means it is somewhere these counters do not look. Candidates, not yet
checked:

1. **The LLM bot.** `logs/` also holds LLM games, and `card_modes` is only
   recorded by `benchmark.play` for the strategic, greedy and MCTS bots. The
   maintainer's logs may be LLM games; `analyze-llm-game` is the tool.
2. **Holding it.** A card kept past the end of a turn is not a play and is
   not counted. A US hand that sits on Voice of America turn after turn
   would look like 100% here.
3. **The USSR's side of it.** When the USSR holds Voice of America it fires
   the US event whatever it does, except on the Space Race: the counters show
   the USSR spaced it 2777 times, used it for Ops 1079 and paired it with UN
   Intervention 184. Spacing it is correct play for the USSR; how often the
   US gets the event from a USSR hand is a different number from how often
   the US events its own copy.
4. **Timing.** "Always event" can hide "event it at the wrong time": a
   headline whose four points land where nothing can be scored.

## What would settle it

Which logs the maintainer read. With that, the check is a replay of those
decisions, not a new measurement. If the rule should be enforced rather than
observed, the place is `models/expert_valuations.json` (a valuation that puts
the event far above 2 Ops) plus a behaviour test over positions where the US
holds it -- not a special case in the policy.
