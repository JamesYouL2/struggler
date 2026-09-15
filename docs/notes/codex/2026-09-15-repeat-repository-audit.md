# Repeat repository audit — 2026-09-15

## Revision and scope

- Reviewed default branch `main` at `bfaa229e91e36fe69b5b3fd32f266cca52789352`, fetched and confirmed with `git ls-remote --symref origin HEAD`.
- Previous reviewed revision: `51e4ca44318e22898bfc0a4684659535342bbea9`, from the September 13 strategic-math audit.
- Historical baseline: annotated tag `v0.1.0`, peeled to `3c3125431f2979171101cbda07e95f69b65b5ddd`.
- Isolated detached worktree; existing checkouts and their uncommitted notes preserved.
- Focused repeat audit: recent changes, previous findings, strategic board potential and replies, observation changes, MCTS sampling/returns, benchmark completion, harvest validation, and CI configuration. Read AGENTS.md, CLAUDE.md and relevant architecture, strategy, testing, limitation, and handoff notes.
- This is not an exhaustive review of all cards, the native port, every script, or live LLM adapters. No implementation edits, paid API calls, strength tournaments, or remote publication.

## Assessment

The previously reported main-policy accounting and reply-boundary defects have implementations and regression coverage on main. The remaining new confirmed defect is in the optional MCTS bot: nonterminal leaf returns still depend on the policy's previous ranking context when banked VP is nonzero. Fix this before drawing conclusions from MCTS strength comparisons. No new P1 defect in the default strategic policy or rules engine was verified in this review.

## A1 — P2: MCTS prices banked VP using the previous node's context

**Locations:** `src/struggler/bots/mcts.py:191–202` (`leaf_return`), `src/struggler/bots/strategic/policy.py:964–1003` (`evaluate`), and `policy.py:1265–1289` (`vp_value`).

`leaf_return` first calls `self.policy.evaluate(obs)`. That method correctly prepares the leaf's context for board potential, then restores the previous board, urgency, Ops caches, and `_vp_price` in its `finally` block. The following `self.policy.vp_value(obs)` consequently returns the **restored previous ranking's VP price**. Passing the leaf observation does not override the memo or resync the restored board.

Reachable production path: `choose_action` → `moves` → `ranked` → `policy.rank_actions`, followed by simulated moves and `leaf_return`. Rankings of newly expanded nodes leave different VP prices on that shared policy. Thus a leaf's banked score is converted using an unrelated node; on a fresh player the call can instead calculate against its initial board. This is a context/caching defect, independent of whether the VP valuation model is strategically good.

**Reproduced without modifying implementation:** use `tests/test_mcts.py::scoring_position`, set `leaf.vp = 1`, and evaluate that identical leaf after different prior rankings:

| Prior ranking | US leaf return | VP price used |
| --- | ---: | ---: |
| None; fresh MCTS player | -0.18133235535519102 | 6.0 |
| The leaf's original turn-4 position | -0.13029506591442544 | 11.232 |
| Turn 9, US Mexico 10, USSR Cuba 0 | -0.15150946045298594 | 9.0675 |

The correctly prepared leaf-context calculation returns `-0.13029506591442544`. A second probe changing only the prior ranking's turn from 4 to 9 returned `-0.13029506591442544` versus `-0.09100749161095387` for US, and `0.0969346667088183` versus `0.05739684577034884` for USSR. The leaf itself did not change.

The existing `test_leaf_value_does_not_depend_on_what_was_ranked_before` uses a fixture with **zero banked VP**, making the stale-price contribution exactly zero. The banked-VP tests establish the sign of that term but do not test its independence from prior rankings.

**Smallest useful correction:** evaluate board potential and banked VP together inside one leaf-local prepared context, before restoring the caller. Use the same cold-cache VP-price initialization as ordinary rankings. Merely clearing `_vp_price` after `evaluate` is insufficient: the board, urgency, and Ops caches have already been restored too.

**Acceptance criteria:** identical nonterminal leaves with nonzero positive and negative VP must have identical returns after fresh, same-position, unrelated-board, different-turn, and opposite-seat rankings. Verify both seats, terminal ±1/draw 0 behavior, and preservation of the caller's board/context. Extend the existing regression rather than add another zero-VP-only test. No broad MCTS rewrite is needed.

### Reproduction

Run from the reviewed checkout:

```sh
uv run python - <<'PY'
import sys
sys.path.insert(0, 'tests')
from test_mcts import scoring_position
from struggler.bots.mcts import MCTSPlayer
from struggler.engine import Side

leaf = scoring_position()
leaf.vp = 1
for label in ('fresh', 'same', 'different'):
    bot = MCTSPlayer()
    if label != 'fresh':
        prior = scoring_position()
        if label == 'different':
            prior.turn = 9
            prior.board.influence['Mexico']['US'] = 10
            prior.board.influence['Cuba']['USSR'] = 0
        bot.policy.rank_actions(prior.observe(Side.US))
    print(label, bot.leaf_return(leaf, Side.US),
          bot.policy.vp_value(leaf.observe(Side.US)))
PY
```

## Previous findings rechecked

| Finding from prior audits | Status at reviewed revision |
| --- | --- |
| M1: influence deltas omit neighboring access changes | Fixed in `73c0d57`: affected neighbors included; before/after, warm-cache and placement-order tests in `test_board_potential.py`. |
| M2: regional potential uses inconsistent urgency | Fixed via `28495f6`, merged in `930dfdc`: shared `region_potential`, Asia uses its own scoring urgency, event sandbox and whole-board paths agree. |
| F2: redundant access aggregate decreases with extra routes | Fixed in `4df6ade`: symmetric shares of a geometric aggregate replace `k * decay**(1-k)`. This corrects the accounting; it does not validate independent-route probabilities. |
| Q1/Q2/F5: reply reach, changing placement cost, final-game horizon | Fixes merged in `553cd14`: reach/Chernobyl checks, pointwise Ops cost, and shared engine turn-order helpers. Tests cover nine turn-order cases. This remains a bounded reply approximation, not full counterplay search. |
| F4 follow-up: a stall labels a completed sample stalled | Fixed in `e4360c1`: per-sample unfinished games determine the stamp, and acceptance tolerates old stamps with explicitly empty unfinished lists. |
| F6: Our Man in Tehran choice is blind | Fixed in `c5d36e8`: US-only `examined_cards`, private-card-aware keep/discard scorer and prompt; rollout information key includes examined cards. Physical mode remains a documented no-op. |
| F8: harvest validation can certify almost no evidence | Fixed in `8716d5c`: finite-number parsing, full held-out coverage, per-row tolerance, and refusal to overwrite reference valuations. Strict thresholds are policy choices, not proof of generalization. |
| F1/F3/F7: scoring collector, complete-pair accounting, observation/payload mutation | Already fixed at the previous reviewed SHA; relevant existing regression coverage retained. No new regression identified in the reviewed changes. |

## Strategic judgments and remaining hypotheses

- The September 14 notes describe reply ablations and a planned retention/value rebuild. An experiment branch or proposed formula is not a main-branch implementation. This audit makes no claim that those experiments are accepted or improve strength.
- Conversion probability, retention probability, and temporal discount remain different quantities. A coherent shared potential fixes internal accounting; it does not establish calibration against human play.
- Coup replies, hand planning, and deeper search remain strength hypotheses. They are not substitutes for fixing the reproduced MCTS leaf-context error, nor mandatory correctness requirements for the default tactical policy.
- The current parity corpus is useful for behavioral exactness, but replaying recorded weights does not establish current-default strength. The CI workflow does run the complete suite on main and pull requests.

## Validation

- Full local suite: `uv run --extra test pytest -q` — **851 passed, 4 skipped, 2 xfailed, 1 failed**, 251.55 seconds as reported by pytest. Output: `logs/audit-20260915-pytest.log`.
- The sole failure is `tests/test_process_checks.py::test_a_monitoring_loop_is_not_a_gate`, a `FileNotFoundError` reading `/proc/221/cmdline` before the matching assertion. This reproduces the earlier workspace PID-namespace limitation. An independent probe returned `os.getpid() == 8`, while `/proc/self/status` reported PID 7195 and namespace PIDs `7195 8`; a live subprocess had PID 9 with no `/proc/9/cmdline` entry. This is not a newly verified engine/bot failure, and the local suite is not described as wholly green.
- GitHub's **tests** workflow completed successfully on the exact reviewed SHA: [run 34916631188](https://github.com/JamesYouL2/struggler/actions/runs/34916631188). This is separate matching-SHA CI evidence, not a replacement description of the local result.
- The full local run passed the existing board-potential, reply-lookahead, Tehran, harvest, benchmark-stall, MCTS, replay, and parity regressions. A1 escaped the existing MCTS context test because it uses zero banked VP.
- Standalone A1 reproductions and the correctly prepared leaf-context comparison ran against this worktree and produced the numbers above, including both-seat checks. No source code or test expectations were changed.
- `git diff --check` passed for the documentation update. Only this note and the Codex index are changed.

## Development priority after discussion

The maintainer selected the [value-function rebuild](value-function-rebuild/README.md) as the next development priority and asked to set MCTS work aside. A1 remains recorded as an audit finding; it is not the active work queue. Preserve the resolved findings' regressions during the rebuild, and distinguish experimental strength evidence from accounting correctness.

## Publication

Prepared for a documentation-only pull request on a separate branch from `main` at `bfaa229e91e36fe69b5b3fd32f266cca52789352`, the same revision that was audited and tested. The pull request also includes the rebuild README and notes-index update. No implementation changes are included.
