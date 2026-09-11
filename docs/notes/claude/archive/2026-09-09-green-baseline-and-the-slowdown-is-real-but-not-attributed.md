# 2026-09-09 (overnight) — Green baseline, and the slowdown is real but not attributed

Work done unsupervised, following Codex's revised sequence. Nothing was
committed and no weights changed.

### Baseline restored

`5a2f3bb` regenerated the parity corpus (427 records, captured clean at
`c15a603`, no dirty paths). The suite at that revision: **588 passed, 3
skipped, 0 failed**, including `test_parity_corpus.py`. The single expected
red test recorded in earlier sessions is therefore closed; treat a parity
failure from here on as a real one.

Housekeeping worth knowing: four leftover watcher shells from an earlier
session were deadlocked, each polling `ps` for a pattern that its own
command line contained, so each was waiting for itself. They had been idle
25 minutes on a quiet machine. If a background wait never fires, check
whether its own command line matches its own predicate.

### The bot really did get slower, normalised for game length

The obvious confound first, and it is dead: **games are not running
longer.** Mean end turn is flat at 8.4 across every gate from `b18b7a9` to
`ec48dfa`. Game seconds do scale hard with how far a game goes (median 3.6 s
at end-turn 3, 28.8 s at end-turn 10, over 4,636 games), so per-turn cost is
the number to compare, not per-game.

Seconds per turn of play, in git commit order, one row per gate:

| Period | s/turn |
| --- | ---: |
| `b18b7a9` .. `1a03954` (Sept 8, before the corpus commit) | 1.07 - 2.21 |
| `2a3f12c`, dice averaging's first landing, later reverted | 2.73 |
| `8ba89db` .. `ec48dfa` (Sept 8 evening onward), 24 gates | 2.80 - 4.42 |
| `df29bf8`, measured under load 17 | 10.17 |

So roughly **1.9x on per-turn cost**, it never came back down, and the step
sits at the `8ba89db` / `6ec71d4` / `4e67bf0` cluster. The natural
experiment inside it: dice averaging spiked its first landing to 2.73
against neighbours at 1.07-1.90, was reverted, and every gate after it
re-landed in `4e67bf0` is at or above 2.80.

**This is suggestive, not attribution.** Every row is a separate gate run
under uncontrolled machine load, which is exactly the confound this file
keeps warning about. Codex's controlled experiment -- the same positions,
the same machine, revisions compared back to back -- is still the thing that
would settle it. What this does establish is that the question is worth the
experiment, and that "the games just got longer" is not the answer.

### Frozen positions: two hot paths, not one

Four corpus positions, three unprofiled repetitions each, fresh player per
repetition (a warm player carries per-decision caches and would time the
second call), on a quiet machine at `5a2f3bb`:

| Position | Decision | Options | Min elapsed |
| --- | --- | ---: | ---: |
| Opening placement, T1 AR1 US | `place_influence` | 38 | 0.007 s |
| Scoring-card choice, T1 AR1 US | `action_round_play` | 7 | 0.034 s |
| Ordinary mid-war hand, T5 AR1 USSR | `action_round_play` | 9 | 0.191 s |
| Hazardous late hand, T7 AR1 US (whole-hand risk 0.469) | `action_round_play` | 8 | 0.336 s |

Elapsed and CPU agree to the millisecond, so none of this is waiting on
anything. A decision costs **48x more late than at the opening**, which is
why per-turn cost is the right unit and why a hazardous hand is the
workload to optimise.

The profiles say the cost is in two different places depending on which:

- **Ordinary mid-war hand:** `event_value` is 0.340 s of 0.486 s profiled,
  about 70 %.
- **Hazardous late hand:** `action_risk` into `defcon.risk` is 0.410 s of
  0.612 s, about 67 %, and `event_value` is not the story at all.

That refines Codex's single-game profile, which showed `action_risk` ~49 s,
`delta` ~37 s and `ops_value` ~31 s as overlapping cumulative paths: they
overlap because they are the same two paths sampled over positions of both
kinds. **Optimising either one alone wins about half the workload.** It also
gives the slowdown a plausible mechanism, since both suspected commits
(`6ec71d4` pricing VP in Ops, `4e67bf0` averaging the sandbox dice) add work
inside event valuation, which is the dominant path in ordinary hands.

Harness: `frozen_bench.py` in the session scratchpad, selection deterministic
by corpus order so the same four positions return on every run. It is not
committed; it should be, next to `profile_baseline.py`, if this becomes the
standard measurement.

### The bot declines free Coups: six event branches decided by option order

`score()`'s `EVENT_CHOICE` arm has twelve per-event rules and two
choice-shaped ones (`choice in CARDS`, `choice == 'boycott'`), and then
`return 0.0` (`strategic.py:1898`). Anything with no rule scores 0.0 on
every branch, and `sorted(..., reverse=True)` is stable, so the **first
option offered wins**. The notes recorded this as the Warsaw Pact
branch-selection defect. It is much wider than one card.

Reproduced directly against the engine, not inferred from reading:

| Event | Options | Bot picks | All tied at 0.0 |
| --- | ---: | --- | --- |
| Tear Down This Wall | none / coup / realign | **none** | yes |
| Junta | none / coup / realign | **none** | yes |
| Ortega Elected in Nicaragua | none / coup | **none** | yes |
| Warsaw Pact Formed | remove / add | remove | yes |
| Chernobyl | six regions | EUROPE | yes |
| South African Unrest | south_africa_only / and_adjacent | south_africa_only | yes |

The first three are the serious ones: `push_free_coup_or_realign` puts
`"none"` first in the option tuple, so **the bot declines the free
Coup or Realignment that is the entire point of those three cards, every
time.** This is not a cautious refusal -- the DEFCON planner is not
consulted on this decision at all, and the engine has already filtered the
options to legal ones. It is a tie broken by tuple order.

Chernobyl always blocks Europe and South African Unrest always takes the
smaller option, both unconditionally.

Two reasons this went unseen. It is **invisible to the gate by
construction**: both sides are strategic, both decline, so the games are
symmetric and score 0.500, the same blind spot as a rules change. And the
expert table prices whole cards on the opening board, where none of these
six can fire.

The fix is not new machinery. A free Coup/Realignment type choice is
already valuable to this bot in other decision kinds, so route it through
the existing coup and realignment valuation instead of returning 0.0;
Chernobyl's region choice is the region score it already computes. What it
must not become is a per-branch sandbox simulation, which would land in
the middle of the hottest path (event valuation is ~70 % of an ordinary
mid-war decision, above), so the speed finding and this one pull against
each other and should be designed together.

Reproduction: resolve the event on a fresh `Engine.new_game(seed=7)`, take
the pushed `EVENT_CHOICE`, and compare `rank_actions` keys. Probe kept in
the session scratchpad; it belongs in `tests/` as a regression that asserts
no `EVENT_CHOICE` presents an all-tied ranking.

### Two of Codex's open items are already closed

Checked rather than assumed, since both were on the "what still applies"
list:

- **`_event_helper` stale weights: fixed.** `strategic.py:1014` rebuilds the
  helper whenever `helper.weights is not self.weights`, with a comment
  naming the training case. The finding is stale.
- **Silent sandbox fallback: addressed.** `_event_value_uncached`
  distinguishes `SandboxUnsupported` (debug, expected) from any other
  exception (warning, recorded in `sandbox_failures` where a caller can see
  the value is an estimate). Landed as `b5466cc`.
