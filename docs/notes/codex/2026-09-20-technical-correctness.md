# Technical correctness review: hand-survival boundaries

Date: 2026-09-20.
Reviewed SHA: `316b5af92b75d89f3c51b3dad7f3c3617ae10418`.
Publication base: `394bfdd219becae9645e810aa045ca78043f250f`.
Main advanced during review; the intervening change touches experiment config,
notes, testing guidance, and a registry test, not the reviewed safety code.
Repository: JamesYouL2/struggler, default branch `main`.
Historical baseline tag: `v0.1.0` = `50e5af5bbd32bb9fc3de15ee6a8a8384db8a9db9`.
This is a bounded follow-up correctness review, not a full audit against that tag.

## Assessment

Two live-policy defects reproduce at the reviewed SHA. Both sit at the boundary
between board-changing actions and the hand-survival planner. Neither finding
requires a claim that a different strategic heuristic is stronger. This PR
records the defects and bounded repair tasks; it changes documentation only.

| Priority | Finding | Consequence |
| --- | --- | --- |
| P1 | Latent hazards use unrestricted coup geography | Safety checks can be disabled before a placement creates a legal nuclear-loss target for a restricted event. |
| P2 | Post-event replanning applies the current event again | A safe DEFCON-3 reducer can be priced as certain turn loss, erasing meaningful score differences. |

P1 is about missed loss prevention; P2 is a false positive in risk pricing.
The engine itself is not shown to apply either incorrect rule. The supplied
positions isolate the bot's implementation; prevalence in normal games and
aggregate playing-strength effects have not been measured.

## F1 — card-specific coup restrictions disappear in latent-hazard detection

**Locations:** `src/struggler/bots/strategic/defcon.py`,
`DefconPlanner.latent_hazards`, `coup_threat`, and `_event_risk`;
`src/struggler/bots/strategic/policy.py`, `rank_actions`, `_mode_risk`,
and `_placement_risk`.

`_event_risk` correctly restricts Ortega to Nicaragua's neighbors and Tear
Down This Wall to Europe, with their DEFCON-ignoring free coups. But
`latent_hazards` calls `coup_threat(actor, 2)` without either the country
restriction or `ignore_defcon`. That is a different rules question.

With our influence in Angola, the opponent has a generic legal battleground
coup at DEFCON 2. Neither restricted event can use Angola. Consequently the
held card is safe now but becomes dangerous when we enter an eligible target.
`latent_hazards` returns an empty list, so `rank_actions` sets `_planner` back
to None for placement decisions. `_mode_risk` also uses that list as its guard
for event-board resimulation. `_placement_risk` cannot repair a guard that
prevents it from being called with a planner at all.

### Reproduction

From the repository root, after `uv sync --frozen --extra test`:

```bash
PYTHONPATH=tests uv run python - <<'PYCODE'
from test_defcon_planner import setup_hand, planner
from struggler.engine import Side, Action, DecisionKind as K
from struggler.bots.strategic import StrategicPlayer

cases = [
    ('Ortega_Elected_in_Nicaragua', Side.US, 'Cuba', 'Nicaragua'),
    ('Tear_Down_This_Wall', Side.USSR, 'Italy', 'Austria'),
]
for card, side, target, access in cases:
    e = setup_hand([card], side=side, rounds=1, defcon=2, space_used=1)
    for country in e.board.influence:
        e.board.influence[country] = {'US': 0, 'USSR': 0}
    e.board.influence['Angola'][side.value] = 1
    e.board.influence[access][side.value] = 1
    assert target in e.board.neighbors(access)
    before = planner(e, side)
    print(card, before.event_risk(card), before.latent_hazards(before.hand))
    e._push(side, K.PLACE_INFLUENCE,
            (Action(K.PLACE_INFLUENCE, {'country': target}),),
            {'ops_remaining': 1, 'phasing_player': side.value})
    bot = StrategicPlayer()
    bot.rank_actions(e.observe(side))
    print('planner enabled:', bot._planner is not None)
    e.step(e.legal_actions()[0])
    print('risk after placement:', planner(e, side).event_risk(card))
PYCODE
```

Observed for both cards: event risk before `0.0`; latent hazards `[]`;
placement planner enabled `False`; event risk after placement `1.0`.
These are constructed atomic placement fixtures with valid adjacent access,
not complete replayed games. They demonstrate the missing safety path, not
that the policy selects this placement over a particular alternative.

### Smallest repair and acceptance criteria

Factor the borrowed-coup target restrictions and DEFCON exception into one
shared query used by both event risk and latent-hazard detection. Do not copy
the special cases into a second list that can drift again. Keep the existing
Nuclear Subs and Cuban Missile Crisis checks.

Add regressions for both cards with an unrelated legal target already on the
board. Require that the restricted card is recognized as latent, the ranking
keeps its placement planner, and creating its first eligible battleground
raises the continuation risk. Pair each with an outside-geography placement
that does not raise risk. Preserve the existing CIA/Fidel regression and
cover the event-board resimulation guard as well as single-point placements.

## F2 — the event is transitioned twice when replanning its resulting board

**Locations:** `policy.py`, `StrategicPlayer._mode_risk` and `_after_event`;
`defcon.py`, `DefconPlanner.transition` and `_event_risk`.

`_after_event(obs, cid)` fires and resolves the event, then returns an
observation with the resulting influence and DEFCON. `_mode_risk` constructs
a planner from that observation and calls `risk(cid, mode)` again. That call
starts another transition for the event whose effects have already happened.
A reducer at DEFCON 3 is therefore evaluated as a reducer starting at DEFCON 2.

The resimulation only runs if the remaining hand contains a latent hazard.
This makes the defect position-dependent: making CIA Created safe for lack
of a target can paradoxically make Duck and Cover appear more dangerous.

### Reproduction

```bash
PYTHONPATH=tests uv run python - <<'PYCODE'
from test_defcon_planner import setup_hand
from struggler.engine import Side
from struggler.bots.strategic import StrategicPlayer
from struggler.bots.strategic.defcon import SurvivalPrior

for latent in (True, False):
    e = setup_hand(['Duck_and_Cover', 'CIA_Created'], rounds=1,
                   defcon=3, space_used=1)
    e.board.influence['Cuba']['USSR'] = 0 if latent else 2
    e.push_full_card_play(Side.USSR, 'Duck_and_Cover')
    bot = StrategicPlayer(survival_prior=SurvivalPrior(
        opponent_hand_attack=0, opponent_lowers_defcon=0))
    obs = e.observe(Side.USSR)
    ranked = bot.rank_actions(obs)
    print('latent:', latent)
    for key, action in ranked:
        print(action.payload, bot.action_risk(obs, action), key)
    event = next(a for _, a in ranked if a.payload['mode'] == 'event')
    e.step(event)
    print('engine after:', e.defcon, e.is_terminal)
PYCODE
```

Observed: with latent CIA, both event and Ops modes report `(immediate=0,
turn_loss=1)` and both receive score `-230.9839223075649` (the game's priced
loss). Without latent CIA, both report `(0, 0)`. In both cases the real event
leaves DEFCON 2 and the engine nonterminal. There is only one round left,
so CIA can be held; no future forced play explains the claimed loss.

The false certainty is in the priced turn-risk component. The first safety
key component remains zero; this is not a claim that immediate-loss ordering
itself marks the action certain defeat.

### Smallest repair and acceptance criteria

Give post-event continuation an explicit contract: consume the current card
and round exactly once and start from the effects already resolved. Preserve
remaining hand, attempts, China availability, trap/effect state, and DEFCON
consistently. Do not simply rerun the event against its resulting observation.
If instead retaining the pre-event transition and substituting board state,
prove that stateful effects are still counted once; resetting DEFCON alone
would be an incomplete general fix.

Add the one-round Duck/CIA regression above through `rank_actions`, for event
and opponent-event Ops modes. Check that each has zero turn-loss risk with
future priors disabled and retains its distinct ordinary score. Preserve
Fidel creating a lethal target, and add a stateful-event case to guard the
continuation contract. Confirm the real engine outcome independently of the
planner's own predicted risk.

## Earlier findings: status at this SHA

- The previous immediate-event risk double charge is **fixed** in
  `safety_key`: it subtracts immediate risk before charging residual risk.
  The sandbox terminal-ownership path also prevents charging a probabilistic
  ending again in `event_value`. Relevant strategic regressions pass. This
  differs from F2, which repeats the state transition during replanning.
- Ortega/Tear Down **direct event risk** already has the geographic restriction.
  F1 is the remaining omission in latent-hazard detection and its callers;
  do not describe the whole event-risk implementation as missing geography.
- The remote `fix/hand-safety-v3` tip
  `65677cf85ba88174cbc2164fa62838d803cf5039` is an ancestor of reviewed main.
  These reproductions therefore include that work rather than requesting
  that its already merged fixes be implemented again.

## Validation and coverage

Executed at the reviewed SHA:

- Both inline reproductions above, including controls and real engine steps.
- `uv run pytest -q tests/test_defcon_planner.py`: **68 passed**.
- `uv run pytest -q tests/test_strategic.py -k 'risk or summit or ending' tests/test_engine_defcon_chains.py`:
  **5 passed, 89 deselected** (the selector applies to both files).
- `uv run pytest -q tests/test_engine_defcon_chains.py`: **19 passed**.
- Documentation whitespace and index-link checks before publication.

Existing tests passing while the reproductions fail the intended contract is
the coverage gap. No implementation changes, corpus recapture, strength
experiments, or workflow dispatch were performed. The full local suite was
not run; normal push/PR CI supplies full-suite verification for the docs branch.

Scope excludes a full card/rules survey, hidden-information audit, performance
review, and rebuild calibration. Existing documented engine simplifications
in `docs/LIMITATIONS.md` were not reclassified as newly discovered bugs.

## Recommended implementation sequence

1. Repair and regress F1's shared restricted-coup query.
2. Repair and regress F2's post-event continuation contract separately.
3. Run existing survival, strategic-risk, engine-chain, and full-suite gates.
   Keep any later strength evaluation separate from these correctness proofs.

Do not block these bounded fixes on the full VP rebuild or joint hand allocator.
