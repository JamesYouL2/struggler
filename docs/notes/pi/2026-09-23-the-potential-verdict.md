# The potential verdict: +0.021 [-0.000, +0.042], and the rule says stop

Run 35790097695 (`potential-verdict-{base,on}`), block 72000-73023
against `bc5ef93`, paired, **1023 shared seeds** (one lost -- see the
shard note below). `on` carries `potential: 1.0, potential_refresh: 1.0`;
the decision rule was in the arm's own `context` before dispatch.

| arm | vs `bc5ef93` | one-sided 95% | seats (US / USSR) |
| --- | ---: | --- | --- |
| `potential-verdict-base` | 0.544 | [0.527, 0.561] | 0.618 / 0.470 |
| `potential-verdict-on` | 0.565 | [0.548, 0.582] | 0.644 / 0.486 |

| `on` − `base` (paired) | one-sided 95% | shared seeds |
| --- | --- | ---: |
| **+0.021** | **[-0.000, +0.042]** | 1023 |

## The rule, and the branch it fires

Quoted as registered: *"paired lower bound above 0 means the term earns
its place and the refresh approximation is the next question; at or
below 0 means it does not, at a sample size that can say so."*

**The lower bound is at or below 0 -- the term does not earn its
place.** `potential` and `potential_refresh` stay at 0; the ledger
records it; nothing in play changes. Step 5 of the VP rebuild plan is
closed by this, and with it the plan: the country layer shipped (steps
1-4), the sandbox gap closed first (15caae4), and the term's 1024-seed
verdict has now been read.

The temptation, written down so it can be refused in writing: the point
estimate is +0.021 -- *identical* to the 512-seed reading (run
35531902621: +0.021 [-0.009, +0.052]) -- and the interval's lower edge is
a rounding away from zero. This is exactly the shape of the
fit-vs-`bc5ef93` case on 2026-09-21, where -0.001 was held as a stop. A
line that moves when the gap is smallest is not a line (the 2026-09-21
handoff, item 7).

## What this does not settle

- **A second block could clear it.** The fit's own precedent: +0.023
  [-0.001, +0.047] on block 64000 was held back and block 68000 cleared
  at +0.054 [+0.031, +0.078]. But that is a NEW pre-registered question
  on a fresh block, not a re-read of this one -- and the rule here says
  stop, so it is the maintainer's call whether to ask it at all.
- **The term and its `potential_refresh` round tables are one bundle**
  (stated in the arm): nothing here separates a refresh-on-drift
  schedule from the term itself, and the finishing note's drift
  suggestion rides on the term earning its place first.
- **The region layer stands where it stood.** `region_potential` stays
  (removing it under the fitted weights costs 0.067); `potential` on top
  of it is measured not-worth-turning-on at its one shipped setting.

## The shard that lost a seed

`potential-verdict-on [6/8] w2` failed inside `run-shard` after playing
127 of its 128 seeds. The `if: always()` upload preserved the partial
report -- the known audit-F4 shape: a partial upload with nothing in the
report saying so -- and the collect pooled 1023 shared seeds, which is
what the pairing above reads. The failing step's own output came back
**empty through every log fetch tried** (job log and `--log-failed`), so
the cause is recorded as *unrecovered* rather than guessed. What the
tooling owes itself later: a report that says `127/128` where it now
says nothing, so a shortened block is visible in the table instead of
only in the seed column.
