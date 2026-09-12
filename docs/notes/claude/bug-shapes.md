# The bugs this repo actually gets
### 1. A cached value keyed on less state than it reads (seven times)

`7cb9fbe` two evaluator memos ignoring neighbouring influence; `9d9890f`
valuing only the countries an event touched; the rollout cache not syncing
the board; MCTS leaves inheriting the last ranking's context; the
`_event_basis` surviving across decisions; and tonight the VP price, where
`coup -> vp_value -> ops_value -> coup` made one Op worth 28.43 or 27.78
depending only on which arm of the ranking asked first.

The seventh was the forward search: `_after_reply` moved the board and
then called `delta`, which prices against per-decision caches keyed on the
board as synced. Not a stale number but an inverted *sign* -- the term
written to discourage poking encouraged it, and the minimum-poke rate sat
at 13 a game instead of falling to 0.25. Written hours after this list
was. Gated by `tests/test_base_cache_discipline.py`.

**The practice: an order-independence property test.** Every one of these
is the same assertion -- *evaluating the same position twice, in different
orders, gives the same numbers*. That is a property test over the corpus
positions and it is cheap. The pure-function extraction into `evaluator.py`
was the right structural move and did not stop instance six, because the
cycle was in the stateful wrapper. **Nothing may be memoised until this
test exists**, and the planner memoisation is next in the queue.

### 2. A sentinel used as a number (four times)

`LOSS = -1e6` means "certain defeat", and it has escaped into arithmetic
through `ops_value`, `_resolve_sandbox`, `hold_value`, and dice averaging
(`0.4167 * LOSS`). Each time the fix was another clamp.

**The practice: make it unrepresentable.** A separate type -- `Certain`
versus a float price -- so the type checker refuses the mean of a hand
containing defeat. Codex proposed this independently. Clamps are a fourth
patch on a design that invites the mistake.

### 3. The measurement comparing something against itself (seven times)

`871b170` snapshotting two files instead of the package; the gate running
against a dirty working tree; counting the opponent's nuclear losses as
the candidate's; drawing unplayed seeds from the wrong sample; and tonight
the package loader, where a baseline would have bound the candidate's
submodules.

**The practice: negative controls.** A test for an isolation mechanism is
worthless unless it fails when the mechanism is removed. Tonight's first
attempt at one passed either way, and only checking that revealed I was
testing the wrong half. Also worth keeping: the "standard error of exactly
zero" alarm, which is a cheap tell that two things are identical when they
should not be.

The sixth is the parity corpus, and it is the quietest of them. A record
stores the weights it was captured with and the test rebuilds them as
`StrategicWeights(**rec['weights'])` -- so a weight added *after* capture
is absent from the record and filled from the current default. The oracle
then takes two of its inputs from the code it exists to check. It sat
harmlessly for as long as the new weights' defaults did not move, and
surfaced the day `reply_model` went from 0 to 3: 525 records "failed"
against behaviour they had never recorded. Backfilled at the values in
force at capture (`reply_model=0`, the search not yet existing), which
restores the oracle without re-running anything, and gated by
`test_every_record_pins_every_weight` -- every field of the dataclass
must appear in every record.

The seventh is the same package loader as the fifth, from the other side,
and it is the worst of them because nothing failed. `load_module` rooted
its finder at `os.path.dirname(path)`, which stopped being the bots
directory the day the strategic bot became a package (`136a8c6`): the gate
passes `<base>/strategic/policy.py`, so the finder looked for
`struggler.bots.greedy` inside `<base>/strategic/` and missed -- and missed
its own package too. It resolved **nothing**. From 2026-09-10 every gate
ran a baseline made of its own `policy.py` and the candidate's evaluator,
defcon, public_cards, greedy and rollout, so a change confined to any of
those was compared against itself and could only come back a dead heat.
The fifth's test passed throughout, because it puts its entry file at the
snapshot root and production never does.

It surfaced only because `c0ccd95` moved nine functions out of `greedy.py`
into `rules_math.py`, which turned the silent miss into an ImportError two
seconds into a gate. Gated by
`test_a_baseline_inside_a_package_still_shadows_the_bots_root`, which
reconstructs the production layout -- entry file one level down, a name
present in the snapshot's `greedy.py` and absent from the candidate's --
and fails with the rooting reverted. **The lesson is about the negative
control above, not about paths: the fifth's gate was a real negative
control and still missed this, because it controlled the wrong layout.**

### 4. Two implementations of one rule, drifting (four times)

`cddb7a0` three copies of region scoring, only one of which knew about the
scoring overrides; two Ops estimates, one for card choice and one for the
Ops-type branch; and the invariant checker, where the copy in the property
tests was silently the weaker.

**The practice: derive, then prove equality exhaustively.**
`test_coup_forbidden_matches_the_engine_under_every_prohibition` walks all
32 flag combinations against the engine's own answer, and asserts each
prohibition fired at least once. That is the pattern to copy whenever the
bot mirrors an engine rule.

The fourth: `Decision.public()` hides an option list that names cards, and
decided "names cards" as `"card" in option.payload` -- the rule written a
second time, as a key name. Blockade asks the US to discard a 3+ Ops card
and keys its options `choice`, so the qualifying part of the US hand went
into the shared history both players are handed. Found by
`tests/test_history_privacy.py`, which asks the rules' question instead:
every card id in the shared history must already have been revealed by an
event the history carries. The filter now matches option *values* against
the card ids, which cannot be forgotten when a new decision spells its key
differently.

### 5. A silent fallback hiding a defect (twice, and it paid off once)

`event_value` caught every exception and substituted a plausible estimate,
so a programming error read as an approximation. `b5466cc` made unexpected
failures a warning and recorded them. **That fix caught tonight's bug**:
the Military Ops sandbox credit read a variable that is an evaluator index
rather than a `Side`, and every sandboxed event fell back silently until
the warning said otherwise.

**The practice: distinguish "unsupported" from "broken" at the type level**
and never let the second be quiet.

### 6. A number on the wrong scale (four times)

VP priced at 0.14 Ops; the event estimate at 0.02-0.06 Ops; the DEFCON
prior at seven times its measured rate; Military Ops at an eighth of a VP.
Each was a hand-set constant sitting next to quantities on a different
scale.

**The practice: units in the name, and one conversion point.** Every
weight should say what it multiplies. `military` is now a multiplier on a
VP, not a raw number, and reads that way.

### 7. Timing measured under uncontrolled conditions (three times)

"Never time anything while a gate runs" was already in this file, and I
did it anyway, twice tonight: a 3x slowdown that was contention, and a
3.7x speedup that was two runs at different revisions.

**The practice: both arms in one process, interleaved, same inputs.**
Anything else is two anecdotes.

### 8. A test that encodes the defect as the contract (twice)

`test_mutation_can_be_restricted_to_named_weights` asserted that *every*
weight changes under a default mutation, which is exactly the bug -- the
disabled terms were being switched on. The parity test that expected a
`vp` ending partway through Final Scoring preserved a rules defect the
same way.

**The practice: assert intent, not observed output.** When a test is
written to pin current behaviour rather than desired behaviour, say so in
its name or docstring so the next reader knows it is a characterisation
test and not a specification.

### 9. A process check that matches the process doing the checking (four times)

`pgrep -f <pattern>` matches against full command lines, and the asking
process has one. All four were the same bug wearing different clothes:

- `pkill -f 'openings US=france'` killed the shell that ran it, because
  that shell's own command line contained the pattern.
- `pgrep -f 'gate.sh'` reported a gate running when none was, for the
  same reason.
- Six `until ! pgrep -f 'pytest -q'` wait-loops span for hours after the
  suite finished: the loop's own `eval` string contains `pytest -q`, so
  the condition could never become false. They were found only because
  the maintainer asked why ten tasks were running.
- A guard written *to prevent* this -- `pgrep -f '[g]ate.sh'`, bracketed
  -- still matched, because the same compound command also contained
  `bash -n scripts/gate.sh` in plain text. The bracket protects the
  pattern from itself; it does nothing about the rest of your own
  command line.

**The practice: never ask `pgrep` whether something is running.** The
bracket trick is not a fix, it is a narrower version of the same bug, and
it fails the moment the command line grows. Enumerate `/proc`, exclude
your own PID *and every ancestor*, and match on the actual executable
plus argv -- `scripts/gate_running.py` is the worked version. If a shell
one-liner is genuinely required, `flock` on a lock file answers "is it
running" without pattern-matching anything.
