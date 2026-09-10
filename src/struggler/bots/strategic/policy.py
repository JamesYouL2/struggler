"""Observation-only tactical policy with trainable linear evaluation weights.

Searches local influence investments and enumerates combat dice. Selected
public-information events are evaluated using an isolated engine; unknown
hands and the real engine RNG are never consulted. This is a bounded tactical
AI, not full-game minimax or a pretrained neural network.
"""
from __future__ import annotations

import itertools
import json
import logging
import math
import os
from dataclasses import asdict, dataclass, fields, replace
from pathlib import Path
from typing import Sequence

from struggler.engine import Action, DecisionKind as K, Engine, Observation, Region, Side
from struggler.engine.board import Board
from struggler.engine.types import Subregion
from struggler.engine.cards import load_cards
from struggler.engine.core import SANDBOX_LOG
from struggler.engine.events import EVENTS
from struggler.bots.strategic import evaluator as ev
from struggler.bots.strategic.public_cards import (card_state, final_scoring_odds, scoring_cards_for,
                                         scoring_schedule)
from struggler.engine.player import Event
from struggler.bots.strategic.defcon import DefconPlanner, SurvivalPrior, ASK, US_PAYABLE_DISCARDS

log = logging.getLogger('struggler.bots.strategic')
RISK_WARNING = 0.5  # accepted turn-loss risk at or above this is logged at WARNING
# Every write to `self.board.influence` has to go through `_set_influence`, or
# the snapshot's control and reachability vectors stop describing the board.
# Setting STRUGGLER_CHECK_SNAPSHOT=1 rebuilds the snapshot on every `delta`
# and compares; `test_strategic.py` and `test_rollout.py` use it to pin the
# write sites, and both were checked to fail when one is broken.
CHECK_SNAPSHOT = os.environ.get('STRUGGLER_CHECK_SNAPSHOT') == '1'
from struggler.bots.greedy import (
    _coup_risks_defcon, _coup_roll_modifier_estimate, _effective_ops_estimate,
    _bonus_ops, _in_bonus_region, _realignment_bonus, _realignment_modifier,
    _space_race_expected_vp, _sync_board,
)

CARDS = load_cards()
LOSS = -1_000_000.0
# What winning or losing the game is worth, in VP: the whole track, -20 to
# +20. `LOSS` stays the sentinel for a *certain* outcome, which no amount of
# board value should buy; this is the finite figure a *probabilistic* one is
# worth, so that risk can be traded against value instead of ranking ahead
# of it at any price. The expert's number.
GAME_SWING_VP = 40.0
# Decisions whose `score` is in raw board units, and can therefore be blended
# with `game_value`. The rest (EVENT_CHOICE's per-card rules, say) are on
# their own ad-hoc scales and keep risk as a separate, prior key.
_RAW_SCORE_KINDS = (K.ACTION_ROUND_PLAY, K.HEADLINE_PLAY, K.PLAY_MODE,
                    K.COUP_TARGET, K.OPS_TYPE)


def coup_bans(game_effects) -> ev.Prohibitions:
    """Which persistent Coup prohibitions are in force, from public board
    state -- NATO, the US/Japan pact and The Reformer, with De Gaulle and
    Willy Brandt lifting NATO's shield on their own country.

    Without these the value function priced a wipe risk on US-Controlled
    Europe that the USSR is not allowed to attempt, so the bot defended
    against a move the rules forbid, and thinned the risk it spread over its
    real targets by counting unreal ones. It is also what gives NATO and the
    pact a value: what they are worth is the risk they remove, which is a
    number the bot already computes."""
    return ev.Prohibitions(*(bool(game_effects.get(name)) for name in
                             ('nato', 'us_japan_pact', 'reformer',
                              'degaulle_france', 'willy_brandt')))


def scoring_flags(game_effects) -> tuple[bool, bool]:
    """Which per-scoring board adjustments are in force, as (Formosan
    Resolution, Shuttle Diplomacy). Both are public board state, so a bot
    reads them from the observation rather than inferring them.

    Shuttle Diplomacy is one-shot and spent by whichever of the Middle East
    and Asia scores first; the value function does not know which that will
    be, so it credits the discount in both. See docs/LIMITATIONS.md."""
    return (bool(game_effects.get('formosan_resolution')),
            bool(game_effects.get('shuttle_diplomacy')))


class SandboxUnsupported(RuntimeError):
    """The event sandbox knowingly gave up on an event.

    Raised only where giving up is the designed outcome, so that everything
    else reaching `event_value`'s fallback is a defect and is logged as one.
    Catching every exception and substituting an estimate hid a real bug for
    as long as it existed: the two dice-contest events could never resolve,
    and their crude estimate was reported as a simulated value."""

# Opening book: the setup placements in order, per stage. The USSR's 6 in
# Eastern Europe and the US's 7 in Western Europe keep control through
# East European Unrest / Socialist Governments and take the access points
# strong players take; the US +2 handicap goes to Iran, then West Germany.
OPENING_BOOK = {
    ('USSR', 'EASTERN_EUROPE'): ('East_Germany', 'Poland', 'Poland', 'Poland', 'Poland', 'Austria'),
    ('US', 'WESTERN_EUROPE'): ('West_Germany',) * 4 + ('Italy',) * 3,
    ('US', None): ('Iran', 'West_Germany'),
}


def _copy_state(value):
    """Copy the plain JSON-like effect state (dicts, lists, tuples of
    scalars) without deepcopy's generic bookkeeping; sandboxes are built
    by the thousand per search."""
    if isinstance(value, dict):
        return {k: _copy_state(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_copy_state(v) for v in value]
    if isinstance(value, tuple):
        return tuple(_copy_state(v) for v in value)
    return value
# Only deterministic, public-board events whose follow-ups are influence
# decisions. Do not add hand/deck events here without a belief-state model.
# Events whose resolution depends on hidden cards (hands, the draw pile):
# the idle sandbox has none, so they keep an explicit estimate. Every
# other event is simulated in the sandbox, with the helper policy playing
# every choice it raises and chance taking its middle outcome.
HIDDEN_INFO_EVENTS = frozenset('''Five_Year_Plan Grain_Sales_to_Soviets Missile_Envy
Aldrich_Ames_Remix Terrorism Ask_Not_What_Your_Country_Can_Do_For_You Star_Wars
Our_Man_In_Tehran CIA_Created Lone_Gunman Salt_Negotiations The_China_Card'''.split())
# Duration effects priced by the marginal Ops they add to or take from the hands they touch.
OPS_MODIFIER_EVENTS = ('Containment', 'Brezhnev_Doctrine', 'Red_Scare_Purge')
# Hidden-information cards whose value is nonetheless derivable from what a
# card in a hand is worth (`hold_value`): priced by `_hand_attack_value`
# rather than the generic estimate.
# An opponent's card discarded outright -- not swapped, as Missile Envy does
# -- is worth this many Ops beyond the card itself: a card fewer to play
# with, so a card more likely held or wasted. The expert's figure.
CARD_DENIAL_OPS = 1.5
# What the beneficiary of a hand attack actually realises of "my gain plus
# their loss". Calibrated, not derived: with the sums taken at face value
# Grain Sales priced at 8.2 Ops-equivalents and Missile Envy at 6.0 against
# the expert's 4 and 3, and the terms were rejected by the gate (0.428); at
# half they price at 4.1 and 3.0 and a 32-seed run scored 0.539. The victim's
# seat is not discounted -- it measured even on its own -- so what is
# cheaper is spending your round on the attack, not suffering it.
HAND_ATTACK_REALISED = 0.5
HAND_ATTACK_EVENTS = frozenset(('Five_Year_Plan', 'Terrorism', 'Aldrich_Ames_Remix',
                                'Grain_Sales_to_Soviets', 'Star_Wars', 'CIA_Created',
                                'Lone_Gunman', 'Missile_Envy', 'Salt_Negotiations',
                                'Our_Man_In_Tehran'))
# For the docs and tests: what the sandbox is asked to simulate. Every name
# above must be a real card id -- `Our_Man_in_Tehran` (lowercase i) matched
# nothing, so the card stayed in PUBLIC_EVENTS and was simulated in a sandbox
# whose draw pile is empty. It returned 0.0 and recorded no failure, which
# reads as a supported value rather than an artifact.
PUBLIC_EVENTS = frozenset(c.id for c in CARDS.values()
                          if not c.scoring and c.id not in HIDDEN_INFO_EVENTS
                          and c.id not in OPS_MODIFIER_EVENTS)


@dataclass(frozen=True)
class StrategicWeights:
    # Country importance: a battleground is worth `battleground` (times
    # what its region will still score); a plain country a quarter to a
    # third of that. Per Op, a battleground is its tier over its stability
    # (1.25 at stability 4, 1.67 at 3); the expert puts a 1-stability
    # non-battleground between those, so `control` 1.5. Its control also
    # moves the domination tally, which the region score and margin carry,
    # and gives reach, priced by the access terms below.
    control: float = 1.5
    battleground: float = 5.0
    progress: float = 2.8
    # A flat reserve per spare point past control, up to two. Slated for
    # removal once the wipe term below is on: removing it with wipe at 0 lost the gate outright (0.328 against
    # the previous commit, one nuclear loss), so spare points matter.
    reserve: float = 0.35
    # Wipe risk: the chance the opponent's coup (3 or 4 Ops, where DEFCON
    # allows a coup in that region, one coup a turn shared over their
    # targets) removes every point we hold. What that costs depends on
    # backing. Unbacked (no neighbour holds our influence, no superpower
    # adjacency) and the couper can get there first, a wipe flips the
    # battleground: we lose our position and they take the country, so the
    # stake is both. Backed, they still have to flip it to control on their
    # side: the stake is our position, `wipe_backed` of it. `wipe` scales
    # the flip. Off until calibrated (docs/CLAUDE_NOTES.md plan step 2).
    wipe: float = 0.0
    wipe_backed: float = 0.0
    # First mover: presence in a battleground the opponent has none in but
    # could reach. Whoever fills an empty country first makes the other pay
    # to contest it; the bonus is that tempo, times importance.
    first_mover: float = 0.6
    # Region margin: the exact region score pays nothing until a tier flips,
    # so being one battleground short of domination looks like being three
    # short, and a first controlled country in a region where we have none
    # (presence, 3 VP in the Early War regions: "presence versus no presence
    # is the whole game") is worth nothing until it is finished. Partial
    # credit, in VP like the region score: progress toward presence times
    # the presence VP; each battleground and each country of margin toward
    # (or past) domination times the domination-minus-presence gap, capped
    # at two of each. On the country-importance scale (a battleground's
    # control value in the region), not the region score's VP scale:
    # margin_presence 1 makes a finished first presence worth one
    # battleground control.
    # Presence credit counts only where the region is live (its scoring
    # weight at least `margin_live`: scores this cycle), so the bot does
    # not scatter footholds toward presence in regions that will not score
    # for turns (presence 3.0 everywhere lost 0.375 against its base).
    # Battleground margin is stepwise linear: progress toward an
    # uncontrolled battleground counts toward the margin at the linear
    # rate, control is the step, over-protection is the `reserve`.
    margin_presence: float = 1.0
    margin_battleground: float = 0.25
    margin_country: float = 0.05
    margin_live: float = 1.0
    access: float = 1.5
    access_redundant: float = 0.35
    access_chain: float = 0.4
    # Reach into a battleground the opponent can already place in is a race
    # they may win first (Israel -> Egypt for the USSR, with the US already
    # next door): worth this fraction of exclusive reach.
    access_contested: float = 0.25
    region: float = 1.3
    # A VP in Ops, by era: Ops are worth most while the board is empty and
    # VP most when few turns are left to convert Ops into anything, so the
    # expert's rule is 1 Op = 2 VP in the Early War (a VP is 0.5 Op), 1 Op
    # = 1 VP in the Mid War, 2 Ops = 1 VP in the Late War. The Early rate
    # agrees with the opening-board fixture (Olympic Games 0.3, Korean War
    # -1). A per-turn table is the natural refinement once tuning wants
    # it. The old flat `vp` of 3.0 raw priced a VP at 0.08-0.23 Ops
    # everywhere, several times under on every scoring, war and VP-event
    # decision, and by 10-25x in the Late War.
    vp_early: float = 0.5
    vp_mid: float = 1.0
    vp_late: float = 2.0
    # Military Operations, priced in VP like everything else. Rule 6.3.5 is
    # exact and there is nothing to estimate: at the end of the turn a side
    # whose Military Ops are below the DEFCON level hands the *difference*
    # to its opponent as VP, so one Op of deficit closed is worth exactly
    # one VP. This weight is the multiplier on that, and 1.0 is the
    # principled default; it exists to tune, not to define.
    #
    # It was 2.0 raw against a VP worth 14 raw on turn 1 and ~75 in the Mid
    # War, so the requirement was priced at 3% to 14% of its real value and
    # the bot had almost no reason to cover it. This is the third weight
    # found flat against the Ops scale, after `vp` and `ops`; see the
    # comment on vp_early.
    military: float = 1.0
    # Retired: the estimate fallback it scaled now prices through
    # `ops_value`, like every other Ops term. Kept so saved weights and the
    # parity corpus's recorded weights still load; `mutate` will perturb it
    # to no effect.
    ops: float = 2.0
    # A country is worth what its region will still score: the sum over its
    # scoring cards' expected future plays of scoring_discount ** (turns
    # away), from the static period schedule and where each card is now
    # (bots/public_cards.scoring_schedule). Control in a region that scores
    # this cycle and again after the reshuffle is worth about 1.6; in one
    # just scored, 0.6; in a Mid War region on turn 1, 0.5. Holding the
    # card ourselves multiplies this cycle's term by scoring_hand: we pick
    # the moment.
    scoring_hand: float = 1.2
    scoring_discount: float = 0.8
    # What the end-of-game scoring of every region is worth, times its
    # measured odds of happening (public_cards.FINAL_SCORING_ODDS). 0 restores
    # the old behaviour, which priced the last turns as if the game ran for
    # ever and then stopped without scoring.
    scoring_final: float = 1.0
    # progress_curve is the exponent on (margin/stability). It stays linear:
    # progress_curve=2 scored 0.33 +/- 0.09 against this shape (see
    # docs/STRATEGIC_AI.md); option value needs lookahead, not a curve.
    progress_curve: float = 1.0
    # A coup or realignment is priced on the same board change as placing
    # influence, then discounted: it is the less Ops-efficient route to the
    # same result (a coup on a 2-stability country loses a point of margin
    # to the roll), and it is random where placement is certain.
    coup_discount: float = 0.9

    def __post_init__(self):
        if any(not math.isfinite(v) or v < 0 for v in asdict(self).values()):
            raise ValueError('weights must be finite and nonnegative')

    @classmethod
    def load(cls, path: str | Path) -> StrategicWeights:
        data = json.loads(Path(path).read_text())
        if data.get('version') != 1:
            raise ValueError('unsupported strategic model version')
        known = {f.name for f in fields(cls)}
        weights = {k: v for k, v in data['weights'].items() if k in known}
        retired = sorted(set(data['weights']) - known)
        if retired:
            log.info('strategic weights %s: ignoring retired fields %s', path, retired)
        return cls(**weights)

    def save(self, path: str | Path, **metadata) -> None:
        Path(path).write_text(json.dumps(dict(version=1, weights=asdict(self), metadata=metadata), indent=2) + '\n')


# Weights the trainer must not perturb unless asked for by name. `mutate`
# steps a *zero* weight with `abs(gauss(0, scale))` rather than
# multiplicatively -- otherwise zero would be an absorbing state -- so
# leaving a deliberately-disabled term in the default set switches it on:
# a default run turned `wipe` from 0.0 to 0.27. Every `train` run to date
# therefore searched a space that enables an uncalibrated term, and with
# `wipe` non-zero `_value_dependents` widens to the whole board, so those
# runs were also much slower than they looked.
#
#   wipe, wipe_backed  off until calibrated (CLAUDE_NOTES plan step 2)
#   progress_curve     pinned at its neutral 1.0; convex lost 0.33
#   ops                retired, read nowhere in executable code
#
# `--fields` still names any of them explicitly, which is how a deliberate
# ablation turns one on.
UNTUNED_WEIGHTS = ('wipe', 'wipe_backed', 'progress_curve', 'ops')
TUNABLE_WEIGHTS = tuple(f.name for f in fields(StrategicWeights)
                        if f.name not in UNTUNED_WEIGHTS)


class StrategicPlayer:
    def __init__(self, weights: StrategicWeights | None = None, *, survival_prior: SurvivalPrior | None = None,
                 opponent_model=None):
        self.weights = weights or StrategicWeights()
        self.board = Board()
        # The static map, and the snapshot of `self.board` that every
        # evaluation term reads instead of re-deriving control and
        # reachability from the influence dictionaries.
        self._terrain = ev.terrain()
        self._position = ev.Position(self._terrain)
        # Events whose value is the crude estimate rather than a simulation,
        # and why. Read it before trusting an event value.
        self.sandbox_failures: dict[str, str] = {}
        self._events: dict[str, float] = {}
        self.survival_prior = survival_prior or SurvivalPrior()
        # Optional bots.opponent_model.OpponentModel: learned hand-attack and
        # DEFCON-drop probabilities replace the flat survival_prior values.
        self.opponent_model = opponent_model
        self._planner = None
        self._event_basis = None
        self._base_regions = None
        self._base_margins = None
        self._obs = None
        # Per-country scoring weight for `self._obs`, in terrain order, or
        # None for a bare evaluation with no observation behind it.
        self._urgency = None
        # (Formosan Resolution, Shuttle Diplomacy) as of `self._obs`.
        self._scoring_flags = (False, False)
        # The Coup prohibitions as of `self._obs`.
        self._coup_bans = ev.NO_PROHIBITIONS

    def choose_action(self, observation: Observation, history: Sequence[Event]) -> Action:
        ranked = self.rank_actions(observation)
        self._log_choice(observation, observation.pending_decision, ranked)
        return ranked[0][1]

    def rank_actions(self, observation: Observation):
        """Prepare this observation and rank legal actions, without choice logging."""
        decision = observation.pending_decision
        if decision is None or not decision.options:
            raise ValueError('StrategicPlayer requires a pending decision with legal options')
        self.prepare(observation)
        self._events = {}
        # The event sandbox's basis (every country's and region's value on
        # the current board) is keyed on influence alone; the scoring
        # weights it was computed with belong to the previous decision's
        # turn and hand, so it must not survive into this one (the parity
        # corpus caught a headline's basis pricing action round 1's events).
        self._event_basis = None
        self._base_regions = {}
        self._base_margins = {}
        self._ops_values = {}
        # One VP's price, fixed once per decision. `military_credit` needs it
        # inside `coup`, which `ops_value` calls, which `vp_value` calls --
        # a cycle whose answer otherwise depended on which arm was evaluated
        # first (ops_value(1) came out 28.43 or 27.78 by order alone). Fixing
        # it at the start of the ranking, always from a cold cache, makes it
        # a property of the position rather than of the traversal.
        self._vp_price = None
        self._unseen_hold_values = {}
        self._events_in_progress = set()
        # Set by `_resolve_sandbox` when it prices a probabilistic ending, and
        # read by `_event_value_uncached` right after the call that set it.
        # The sandbox's own decisions are played by `_event_helper`, a
        # *separate* player instance, so a simulated event cannot reach in and
        # reset this one mid-simulation.
        self._sandbox_terminal = False
        self._placement_values = {}
        self._relocation_gain = None
        self._space_card = None
        self._un_card = None
        self._planner = None
        # Fix the VP price now, from a cold cache, so it cannot depend on
        # which arm of the ranking happened to ask for it first. Everything
        # downstream reads the memo.
        self.vp_value(observation)
        if decision.kind in (K.ACTION_ROUND_PLAY, K.HEADLINE_PLAY, K.PLAY_MODE, K.EVENT_CHOICE,
                             K.QUAGMIRE_DISCARD, K.OPS_TYPE, K.COUP_TARGET):
            self._planner = self.planner_for(observation)
        try:
            return sorted(((self.safety_key(observation, a), a) for a in decision.options),
                          key=lambda pair: pair[0], reverse=True)
        finally:
            self._base_regions = self._base_margins = None  # callers may move the board after ranking

    def prepare(self, observation: Observation) -> None:
        """Point the player at `observation`: the board, the snapshot of it,
        and the scoring weight of every country. Everything that evaluates a
        position starts here, so that nothing downstream has to ask an
        observation what a country is worth."""
        _sync_board(self.board, observation)
        self._position.sync(self.board)
        self._obs = observation
        self._urgency = self._urgency_for(observation)
        self._scoring_flags = scoring_flags(observation.game_effects)
        self._coup_bans = coup_bans(observation.game_effects)

    def _urgency_for(self, obs: Observation) -> tuple[float, ...]:
        """Every country's scoring weight, in terrain order. It is a function
        of the observation alone, so it is computed once here rather than
        memoised country by country while the board is being searched.
        `scoring_cards_for` reads only a country's region and whether it is in
        South East Asia, so this computes at most seven distinct sums."""
        countries, seen, out = self.board.countries, {}, []
        for cid in self._terrain.ids:
            info = countries[cid]
            key = (info.region, Subregion.SOUTHEAST_ASIA in info.subregions)
            weight = seen.get(key)
            if weight is None:
                weight = seen[key] = self._scoring_weight_uncached(obs, cid)
            out.append(weight)
        return tuple(out)

    def _set_influence(self, cid: str, us: int, ussr: int) -> None:
        """Write one country's influence to the board and to the snapshot.

        Every write to `self.board.influence` goes through here or through
        `prepare`. The snapshot's control and reachability vectors are
        incremental, so one write that skips this leaves them describing a
        board that no longer exists -- the same defect the removed `_access`
        memo had. `CHECK_SNAPSHOT` is what pins it."""
        influence = self.board.influence[cid]
        influence['US'] = us
        influence['USSR'] = ussr
        self._position.place(self._terrain.index[cid], us, ussr)

    def _add_influence(self, cid: str, side: Side, points: int) -> None:
        influence = self.board.influence[cid]
        self._set_influence(cid, influence['US'] + points * (side is Side.US),
                            influence['USSR'] + points * (side is Side.USSR))

    def _urgency_vector(self) -> tuple[float, ...]:
        """The prepared scoring weights, or all ones for a bare evaluation
        (no observation: every country counts for its printed value)."""
        return self._urgency if self._urgency is not None else ev.ones(self._terrain)

    def _shuttle_region(self) -> Region:
        """Where a whole-board value spends Shuttle Diplomacy.

        The card drops one USSR Battleground from *one* scoring: whichever of
        the Middle East and Asia is scored first. A position value sums both
        regions, so crediting the discount in each would book a one-shot
        twice -- and it is not a rounding error, since dropping a Battleground
        can cost a whole tier. It goes to the region whose scoring is nearer,
        which is the bot's best guess at which one spends it; ties go to the
        Middle East, the smaller region, where one Battleground is the larger
        share of the tier."""
        urgency, t = self._urgency_vector(), self._terrain
        return max((Region.MIDDLE_EAST, Region.ASIA),
                   key=lambda r: urgency[t.members[r][0]])

    def _overrides_for(self, region: Region, pos: ev.Position, flags=None):
        """The scoring adjustments `region` scores under, as the index sets
        `evaluator.region_vp` takes.

        They are a function of control, so they are derived per call rather
        than frozen at `prepare`: taking Taiwan is what turns Formosan
        Resolution on, and the bot has to see that in the placement that does
        it. `flags` overrides the observation's events, for pricing a sandbox
        that has just turned one of them on."""
        formosan, shuttle = self._scoring_flags if flags is None else flags
        if not (formosan or shuttle):
            return ev.NO_OVERRIDES
        return ev.scoring_overrides(
            self._terrain, pos, region,
            formosan_resolution=formosan,
            shuttle_diplomacy=shuttle and region is self._shuttle_region())

    def _overrides_map(self, pos: ev.Position, flags=None):
        """`_overrides_for` for every region, or None when nothing is in
        force -- which is what `evaluator.board_value` wants."""
        formosan, shuttle = self._scoring_flags if flags is None else flags
        if not (formosan or shuttle):
            return None
        return {r: self._overrides_for(r, pos, (formosan, shuttle)) for r in Region}

    def _position_for(self, board: Board, pos: ev.Position | None = None) -> ev.Position:
        """A snapshot of `board`, brought up to date first.

        These are the diagnostic entry points -- tests, the benchmark, the
        corpus probes -- and they are reached with the board in whatever state
        the caller left it, including states written straight into
        `board.influence`. The ranking hot path never comes through here; it
        holds `self._position` and keeps it current via `_set_influence`.

        `pos` is a snapshot the caller has already built of *this* board, and
        is returned untouched. Passing it is not an optimisation of one call
        but of a loop: valuing every country of a sandbox board through these
        entry points rebuilt the whole snapshot once per country, which is
        quadratic in the map for a walk that is linear."""
        if pos is not None:
            return pos
        if board is self.board:
            return self._position.refresh(board)
        return ev.Position(self._terrain).sync(board)

    def _log_choice(self, obs, decision, ranked):
        """Explain the ranking: forced losses at WARNING, accepted risk at INFO, everything at DEBUG."""
        if not log.isEnabledFor(logging.INFO):
            return
        prefix = 'T%d AR%d %s %s' % (obs.turn, obs.action_round, obs.side.value, decision.kind.value)
        card = decision.context.get('card') or decision.context.get('event')
        if card:
            prefix += ' [%s]' % card
        def describe(key, action):
            lost, neg_risk, score = key
            return '%s lost=%d risk=%.3f score=%.2f' % (action.payload, -lost, -neg_risk, score)
        best_key, best = ranked[0]
        forced_loss, neg_risk, _ = best_key
        if forced_loss < 0:
            log.warning('%s: EVERY option is a certain loss; picking %s', prefix, describe(best_key, best))
        elif -neg_risk > 0:
            # Prior-sized risk (a held hazard the opponent might steal a spare
            # from) is routine at DEFCON 2; only a real gamble is a warning.
            log.log(logging.WARNING if -neg_risk >= RISK_WARNING else logging.INFO,
                    '%s: accepting turn-loss risk %.3f with %s', prefix, -neg_risk, describe(best_key, best))
        if self._planner is not None and decision.kind in (K.ACTION_ROUND_PLAY, K.HEADLINE_PLAY):
            log.info('%s: hand=%s DEFCON=%d rounds_left=%d china=%s', prefix, list(obs.hand), obs.defcon,
                     self._planner.rounds, self._planner.china)
        narrated = (K.ACTION_ROUND_PLAY, K.HEADLINE_PLAY, K.PLAY_MODE, K.EVENT_CHOICE, K.QUAGMIRE_DISCARD)
        if log.isEnabledFor(logging.DEBUG) or decision.kind in narrated:
            shown = ranked if log.isEnabledFor(logging.DEBUG) else ranked[:5]
            log.info('%s: chose %s', prefix, describe(best_key, best))
            for key, action in shown[1:]:
                log.log(logging.INFO if decision.kind in narrated else logging.DEBUG,
                        '%s:   also %s', prefix, describe(key, action))

    def planner_for(self, obs: Observation) -> DefconPlanner:
        return DefconPlanner(obs, self.public_engine(obs), self.survival_prior, self.opponent_model)

    def safety_key(self, obs, action):
        """Certain defeat is refused outright; conditional risk is priced
        against the game (`game_value`) rather than ranked ahead of it."""
        kind = action.kind
        immediate, risk = self.action_risk(obs, action)
        score = self.score(obs, action)
        certain = -int(immediate >= 1 or score <= LOSS)
        if kind in _RAW_SCORE_KINDS:
            # Risk priced, not ranked. As a separate key element ahead of
            # score it was lexicographic: a risk of 1e-8 lost to a risk of 0
            # whatever was on the table, so nothing could ever be bought with
            # risk. That is the likeliest reason this bot loses to DEFCON 1
            # 38x to 82x less often than a human tournament field.
            #
            # Only the *residual* risk is charged here, because `score`
            # already owns the immediate one: `event_value` prices a firing
            # event as `(1-r)*result - r*game_value`, spending the event's own
            # chance of ending the game. `risk` is the whole turn-loss chance
            # and contains that same `r` -- `transition` returns
            # `r + (1-r)*future` -- so charging `risk` here billed `r` twice.
            # Summit at DEFCON 2 came out at -974.51 where the honest
            # expectation is -485.57: an implied loss chance of 0.79 against a
            # true 0.4167, worse than losing the game outright is.
            # `(1-f)*score - f*game_value` with `f` the residual is exactly
            # the total expectation, since score is already unconditional.
            if certain:
                # Certain defeat is already ordered by the first element, and
                # `score` here is the sentinel, not a number to blend: losing
                # the game is worth exactly the game. The old formula reached
                # this by `(1-1)*score - 1*game_value`; it has to be said
                # explicitly now that the coefficient is the residual.
                return (certain, 0.0, -self.game_value(obs))
            residual = (risk - immediate) / (1 - immediate) if immediate < 1 else 0.
            residual = max(0., min(1., residual))  # a headline blends two DEFCONs; keep it a probability
            return (certain, 0.0, (1 - residual) * score - residual * self.game_value(obs))
        return (certain, -round(risk, 8), score)

    def action_risk(self, obs, action) -> tuple[float, float]:
        """`(immediate, risk)` for `action`: the chance its event ends the
        game as it fires, and the chance the turn is lost from where it
        leaves us. Split out so the key is not the only way to read them --
        the tests used to recover the risk from the key's second element,
        which stopped meaning that once risk was priced into the score."""
        kind, p = action.kind, action.payload
        planner = self._planner
        immediate = risk = 0.
        if planner and kind in (K.ACTION_ROUND_PLAY, K.HEADLINE_PLAY, K.PLAY_MODE):
            cid = p.get('card', obs.pending_decision.context.get('card'))
            if kind is K.HEADLINE_PLAY:
                immediate = planner.event_risk(cid)
                risk = planner.headline_pick_risk(cid)
            elif kind is K.PLAY_MODE:
                fires = p['mode'] == 'event' or p['mode'] == 'ops' and planner.opponent_event(cid)
                immediate = planner.event_risk(cid) if fires else 0.
                risk = planner.risk(cid, p['mode'])
            elif cid == 'Missile_Envy' and obs.game_effects.get('missile_envy_forced') == obs.side.value:
                # This forced play explicitly suppresses the event.
                risk = planner.transition(cid, 'un_intervention', planner.hand, planner.rounds,
                                          obs.defcon, obs.space_race[obs.side.value],
                                          obs.space_race_attempts[obs.side.value], planner.china)
            else:
                # An opponent event fires whichever mode we pick, so its
                # terminal chance is already in `score` (through
                # `event_value`) exactly as it is in `risk`. One of our own
                # fires only in event mode, which `modes` offers only for the
                # raisers, Ask Not and Five Year Plan -- and `risk` mins over
                # modes, so it need not have taken that one. This mirrors
                # `DefconPlanner.transition`'s own `fires` rule.
                immediate = planner.event_risk(cid) if planner.opponent_event(cid) else 0.
                risk = planner.risk(cid)
                # The mode is not chosen yet and `risk` mins over the ones on
                # offer, so a Space Race play can dodge the event entirely.
                # The immediate ending is one way the turn is lost, never a
                # bigger chance than losing it: without this, a Lone Gunman
                # the US could still have spaced was refused outright as
                # certain defeat.
                immediate = min(immediate, risk)
        elif planner and kind is K.COUP_TARGET:
            risk = self.coup_survival_risk(obs, p['country'])
        elif planner and kind is K.OPS_TYPE:
            # Compare Ops types on the same footing: a coup may lower DEFCON
            # and hand the opponent a target; the other types leave both alone.
            risk = planner.discard_risk(None)
            if p['type'] == 'coup':
                engine = self.public_engine(obs)
                targets = [c for c in self.board.countries if engine._usable_coup_realign_target(obs.side, c, for_coup=True)]
                risk = min((self.coup_survival_risk(obs, c) for c in targets), default=risk)
        elif planner and kind is K.QUAGMIRE_DISCARD:
            # A trap step: the discard fires no event, then a 1-4 roll escapes.
            cid = p['card']
            risk = planner.discard_risk(None if cid == 'none' else cid, escape_roll=cid != 'none')
        elif planner and kind is K.EVENT_CHOICE and obs.pending_decision.context.get('event') in US_PAYABLE_DISCARDS:
            # Blockade / Debt Crisis: pay a 3+ Ops card (no event) or take the board hit.
            choice = p['choice']
            risk = planner.discard_risk(None if choice == 'refuse' else choice)
        return immediate, risk

    def region_score(self, board: Board, region: Region, side: Side,
                     snapshot: ev.Position | None = None) -> float:
        """Net VP from scoring `region` now. Europe's control tier has no
        scoring value, so it stands in as +/-100 (see `evaluator.region_vp`)."""
        pos = self._position_for(board, snapshot)
        net = ev.region_vp(self._terrain, pos, region, *self._overrides_for(region, pos))
        return net if side is Side.US else -net

    def region_margin(self, board: Board, region: Region, side: Side,
                      snapshot: ev.Position | None = None) -> float:
        """Partial credit toward the region's next scoring tier."""
        net = ev.margin_basis(self._terrain, self._position_for(board, snapshot), region,
                              self.weights, self._urgency_vector())[0]
        return net if side is Side.US else -net

    def _margin_basis(self, region: Region):
        """The region margin's aggregates for the board as this ranking found
        it. Cached per region under the same contract as `_base_regions` (a
        caller that commits a change mid-ranking clears both), so the hot path
        neither walks the region nor builds an influence-keyed cache key."""
        base = self._base_margins
        hit = None if base is None else base.get(region)
        if hit is None:
            hit = ev.margin_basis(self._terrain, self._position, region,
                                  self.weights, self._urgency_vector())
            if base is not None:
                base[region] = hit
        return hit

    def region_margin_after(self, board: Board, region: Region, side: Side, cid: str,
                            before: dict) -> float:
        """The region margin after `cid` moved from `before` to what the board
        now holds, swapped into the pre-change aggregates. Kept for callers
        (and the parity test) that hold no basis. Reads the snapshot only: the
        board is not touched."""
        t = self._terrain
        pos = self._position_for(board)
        i, was_us, was_ussr = t.index[cid], before['US'], before['USSR']
        now = pos.place(i, was_us, was_ussr)
        try:
            basis = ev.margin_basis(t, pos, region, self.weights, self._urgency_vector())
        finally:
            pos.place(i, now[0], now[1])
        net = ev.margin_swapped(t, pos, region, basis, i, was_us, was_ussr,
                                self.weights, self._urgency_vector())
        return net if side is Side.US else -net

    def country_value(self, board: Board, cid: str, side: Side,
                      snapshot: ev.Position | None = None) -> float:
        """What `cid` is worth to `side` on this board."""
        t = self._terrain
        return ev.country_value(t, self._position_for(board, snapshot), t.index[cid],
                                ev.SIDE_INDEX[side], self.weights, self._urgency_vector(),
                                self._obs.defcon if self._obs is not None else 5,
                                self._coup_bans)

    def _access(self, board: Board, cid: str, side: Side) -> float:
        """The reach a holding in `cid` gives `side` (see `evaluator.access`)."""
        t = self._terrain
        return ev.access(t, self._position_for(board), t.index[cid], ev.SIDE_INDEX[side],
                         self.weights, self._urgency_vector())

    def evaluate(self, observation: Observation, board: Board | None = None) -> float:
        """The board value for `observation`'s side in that observation's own
        context: scoring weights from its turn, hand and discards, DEFCON
        from its board, fresh caches. Use this for search leaves. `value()`
        alone evaluates in whatever context the last `rank_actions` left
        behind, which made an identical leaf return three different values
        depending on which position had been ranked before it."""
        # Both Ops caches are per position, so they are put back with the
        # board they describe. Leaving this leaf's behind would price the
        # interrupted ranking's Ops from a board it never saw.
        # Everything `prepare` sets, not just the caches: it also rewrites
        # `_scoring_flags` and `_coup_bans` from the observation's
        # game_effects, and a leaf evaluated under Formosan Resolution left
        # the caller scoring Taiwan as a Battleground afterwards.
        saved = (self._obs, self._urgency, self.__dict__.get('_ops_values'),
                 self.__dict__.get('_vp_price'),
                 self.__dict__.get('_placement_values'),
                 self.__dict__.get('_unseen_hold_values'),
                 self.__dict__.get('_scoring_flags'), self.__dict__.get('_coup_bans'),
                 {c: dict(v) for c, v in self.board.influence.items()})
        self.prepare(observation)  # `board`, if given, must describe the same position
        self._ops_values = {}
        self._vp_price = None
        self._placement_values = {}
        self._unseen_hold_values = {}  # per position too: it reads card states and scoring
        try:
            return self.value(self.board, observation.side)
        finally:
            (self._obs, self._urgency, ops_values, vp_price, placements, unseen,
             flags, bans, influence) = saved
            self._vp_price = vp_price
            for name, value in (('_ops_values', ops_values), ('_placement_values', placements),
                                ('_unseen_hold_values', unseen),
                                ('_scoring_flags', flags), ('_coup_bans', bans)):
                if value is not None:
                    setattr(self, name, value)
            for c, v in influence.items():
                self.board.influence[c].update(v)
            self._position.sync(self.board)

    def value(self, board: Board, side: Side) -> float:
        """`board`'s whole value to `side`.

        The board comes from the caller, but the *context* does not: scoring
        urgency and DEFCON come from whatever observation this player was last
        prepared for, and from a fresh player they are all-ones urgency at
        DEFCON 5. So the same board scores differently on two players, by
        design -- a battleground is worth more where more scoring is still to
        come. Use `evaluate(observation)`, which prepares that context and puts
        it back, for anything that compares positions, such as a search leaf.
        Call `value` directly only for a bare, context-free reading of a
        board, or after `prepare`. `evaluator.board_value` takes the context
        explicitly and is the honest form of this call."""
        pos = self._position_for(board)
        return ev.board_value(self._terrain, pos, ev.SIDE_INDEX[side],
                              self.weights, self._urgency_vector(),
                              self._obs.defcon if self._obs is not None else 5,
                              self._overrides_map(pos), self._coup_bans)

    def scoring_weight(self, obs: Observation, cid: str) -> float:
        """How much the area around `cid` will still score, discounted by
        how far off each scoring is (see StrategicWeights.scoring_discount).

        Answered from the prepared vector when `obs` is the observation this
        player was prepared for, which is every call on the hot path."""
        if self._urgency is not None and obs is self._obs:
            return self._urgency[self._terrain.index[cid]]
        return self._scoring_weight_uncached(obs, cid)

    def _scoring_weight_uncached(self, obs: Observation, cid: str) -> float:
        w = self.weights
        total = 0.
        for card in scoring_cards_for(self.board.countries[cid]):
            held = card in obs.hand
            for turns in scoring_schedule(obs, card):
                total += w.scoring_discount ** turns * (w.scoring_hand if held and turns == 0 else 1.)
        # Every region is scored once more at the end of the last turn, if the
        # game gets there. Most do not: two thirds end early on the 20 VP
        # auto-victory. So this is priced at its measured odds
        # (`public_cards.FINAL_SCORING_ODDS`) rather than discounted like a
        # scheduled card scoring, which would put it at more than double.
        # Without the term at all, the Late War priced a region whose card had
        # just been played as dead ground, in the era that decides the game.
        total += w.scoring_final * final_scoring_odds(obs)
        return total

    def importance(self, info) -> float:
        """The country's tier: battleground or not."""
        return self.weights.battleground if info.battleground else self.weights.control

    def delta(self, obs: Observation, cid: str, own: int = 0, opp: int = 0) -> float:
        """What adding `own` of our influence and `opp` of theirs to `cid` is
        worth: the country, its region's score and its region's margin, after
        minus before."""
        if own == 0 and opp == 0:
            return 0.
        if self._base_regions is None:
            # Outside a ranking this is a diagnostic call, and the board may
            # have been written to directly since the last `prepare`. Inside
            # one, every write went through `_set_influence` and the snapshot
            # is already current, which is what CHECK_SNAPSHOT asserts.
            self._position.refresh(self.board)
        elif CHECK_SNAPSHOT:
            assert self._position.matches(self.board), f'snapshot stale before delta({cid})'
        t, w, pos = self._terrain, self.weights, self._position
        i = t.index[cid]
        region = t.region_of[i]
        s = ev.SIDE_INDEX[obs.side]
        sign = 1 if s == ev.US else -1
        vector = self._urgency_vector()
        defcon = self._obs.defcon if self._obs is not None else 5
        urgency = self.scoring_weight(obs, cid)
        # While rank_actions runs, every caller enters with the board as it
        # was synced (each restores its own trial changes first), so the
        # region's starting score is fixed; anyone committing a change
        # mid-ranking must clear `_base_regions`.
        base = self._base_regions
        net_before = None if base is None else base.get(region)
        # The scoring overrides in force are a function of control, which the
        # trial change below can move, so they are derived on both sides of it.
        overrides = self._overrides_for(region, pos)
        if net_before is None:
            net_before = ev.region_vp(t, pos, region, *overrides)
            if base is not None:
                base[region] = net_before
        region_before = sign * net_before
        # The margin's aggregates for the unchanged board, cached per region
        # for this ranking exactly like `region_before` above: the trial
        # change below then swaps this one country's contribution, so no
        # call here walks the region or builds a per-influence cache key.
        basis = self._margin_basis(region)
        margin_before = sign * basis[0]
        before = (ev.country_value(t, pos, i, s, w, vector, defcon, self._coup_bans)
                  + w.region * urgency * region_before + margin_before)
        controller = pos.control[i]
        was_us, was_ussr = pos.inf[ev.US][i], pos.inf[ev.USSR][i]
        if s == ev.US:
            self._set_influence(cid, max(0, was_us + own), max(0, was_ussr + opp))
        else:
            self._set_influence(cid, max(0, was_us + opp), max(0, was_ussr + own))
        try:
            # Partial influence and overprotection cannot change regional VP;
            # the margin term (progress toward presence) can move on either.
            # No control change in the region means no tier change and no
            # change to the overrides, which read control too.
            region_after = (region_before if pos.control[i] == controller
                            else sign * ev.region_vp(
                                t, pos, region, *self._overrides_for(region, pos)))
            margin_after = sign * ev.margin_swapped(t, pos, region, basis, i,
                                                    was_us, was_ussr, w, vector)
            return (ev.country_value(t, pos, i, s, w, vector, defcon, self._coup_bans)
                    + w.region * urgency * region_after + margin_after - before)
        finally:
            self._set_influence(cid, was_us, was_ussr)

    @staticmethod
    def _is_phasing(obs: Observation) -> bool:
        """Whether we are the player whose Action Round this is -- the one
        who loses if DEFCON reaches 1 (8.1.3), whoever spends the Ops."""
        ctx = obs.pending_decision.context if obs.pending_decision else {}
        return ctx.get('phasing_player', obs.side.value) == obs.side.value

    def coup_survival_risk(self, obs: Observation, country: str) -> float:
        """Turn-loss risk of the hand after couping `country` now.

        A battleground coup lowers DEFCON (Nuclear Subs aside) and, if it
        succeeds, leaves our influence there: a target for any coup the
        opponent's events grant later. Seed 2402 lost exactly so (a USSR coup
        into Zaire at DEFCON 3 created the CIA Created target); seed 2400 lost
        by couping to DEFCON 2 with its own Lone Gunman headline still pending."""
        info = self.board.countries[country]
        if not _coup_risks_defcon(obs, obs.side, info):
            return self._planner.discard_risk(None)
        if obs.defcon - 1 <= 1:
            # Nuclear war costs the *phasing* player the game, and the phasing
            # player is whoever played the card -- not whoever is spending the
            # Operations. When an opponent's event hands us Ops on their own
            # Action Round (Lone Gunman, CIA Created, Grain Sales, ABM Treaty
            # via Missile Envy), couping a Battleground here wins outright.
            # `score` already returns -LOSS for it; returning 1. regardless
            # meant this key vetoed the win, and the bot took 26 points of
            # Influence over the game.
            return 1. if self._is_phasing(obs) else 0.
        influence = {c: dict(v) for c, v in obs.influence.items()}
        influence[country][obs.side.value] = max(1, influence[country][obs.side.value])
        after = replace(obs, defcon=obs.defcon-1, influence=influence)
        planner = self.planner_for(after)
        risk = planner.discard_risk(None)
        log.debug('T%d AR%d %s coup %s%s -> DEFCON %d, turn-loss risk %.3f', obs.turn, obs.action_round,
                  obs.side.value, country, ' [BG]' if info.battleground else '', obs.defcon-1, risk)
        return risk

    def public_engine(self, obs: Observation) -> Engine:
        # A new, idle sandbox, never a clone of the live game's hidden state.
        engine = Engine(seed=0)
        engine.log = SANDBOX_LOG
        _sync_board(engine.board, obs)
        for name in ('defcon', 'vp', 'turn', 'action_round'):
            setattr(engine, name, getattr(obs, name))
        for name in ('space_race', 'military_ops', 'space_race_attempts', 'turn_effects', 'game_effects'):
            setattr(engine, name, _copy_state(dict(getattr(obs, name))))
        engine.hands[obs.side.value] = list(obs.hand)
        engine.china_card_owner = obs.china_card_owner.value
        engine.china_card_available = obs.china_card_available
        engine.discard_pile = list(obs.discard_pile)
        engine.removed_cards = list(obs.removed_cards)
        return engine

    def scoring_card_value(self, obs: Observation, cid: str) -> float:
        """What playing scoring card `cid` right now is worth to `obs.side`,
        in the same raw units as everything else `score` returns.

        Resolved in the idle sandbox rather than estimated, because the tiers
        are discontinuous and a near-miss is worth nothing. A play that ends
        the game returns the win/loss sentinel. Ask Not... prices a *discard*
        of the same card as the negation of this.
        """
        engine = self.public_engine(obs)
        engine._resolve_scoring_card(cid)
        if engine.is_terminal:
            return -LOSS if engine.winner is obs.side else LOSS
        net = (engine.vp - obs.vp) * (1 if obs.side is Side.US else -1)
        return net * self.vp_value(obs)

    def game_value(self, obs: Observation) -> float:
        """What the game itself is worth here, in the same raw units as
        everything else: the whole VP track at this turn's price per VP."""
        return GAME_SWING_VP * self.vp_value(obs)

    def vp_value(self, obs: Observation) -> float:
        """What one VP is worth here, in raw units: the era's Ops-per-VP
        (StrategicWeights.vp_early/mid/late) times what one Op buys on this
        board, so VP and Ops stay on one scale as the board's Ops value moves."""
        w = self.weights
        per_vp = w.vp_early if obs.turn <= 3 else w.vp_mid if obs.turn <= 7 else w.vp_late
        fixed = self.__dict__.get('_vp_price')
        if fixed is not None:
            return per_vp * fixed
        cached = self._ops_values.get(1) if hasattr(self, '_ops_values') else None
        if cached is not None:
            return per_vp * cached
        # ops_value prices coups and placements, either of which may price VP
        # (Yuri and Samantha, wars, the neural correction): while the one-Op
        # value is itself being computed, a VP is priced at a flat 20 raw per
        # Op, the opening board's order of magnitude.
        if getattr(self, '_vp_reentrant', False):
            return per_vp * 20.
        self._vp_reentrant = True
        try:
            one_op = self.ops_value(obs, 1)
        finally:
            self._vp_reentrant = False
        if hasattr(self, '_ops_values'):
            self._vp_price = one_op
        return per_vp * one_op

    def ops_value(self, obs: Observation, ops: int) -> float:
        """What `ops` Operations are worth here: the best influence spend
        (a greedy plan, so the value is concave in Ops: the fourth point
        buys less than the first) or the best coup on this board, not a
        flat rate. Puts Ops, events and VP on one scale, so a 4-Ops card on
        turn 1 outranks 3 VP and a late 1-Op card does not."""
        if ops <= 0:
            return 0.
        # Tolerate being called outside a ranking, the way `vp_value`
        # already does. Every production caller is inside one, so this
        # changes nothing there; it stops a bare `coup()` on a synced board
        # from raising now that the Military Ops credit prices a VP.
        cached = self.__dict__.setdefault('_ops_values', {}).get(ops)
        if cached is not None:
            return cached
        total = self._placement_ops_value(obs, ops)
        engine = self.public_engine(obs)
        side, board = obs.side, self.board
        # A coup that ends the game is worth the sentinel, and this is a
        # *price* -- what one Op buys on this board, the denominator half the
        # value function divides by. Letting the sentinel through made
        # ops_value(n) 1,000,000 for every n whenever a winning coup was
        # available, so vp_value became 1,000,000 and game_value 40,000,000,
        # and every card, hand term and risk price on that board was junk.
        # The winning coup is priced where it is chosen, not here.
        coups = [v for v in (self.coup(obs, c, ops) for c in board.countries
                             if engine._usable_coup_realign_target(side, c, for_coup=True))
                 if abs(v) < -LOSS]
        value = max([total, 0.] + coups)
        self._ops_values[ops] = value
        return value

    def _placement_ops_value(self, obs: Observation, ops: int) -> float:
        """The best greedy influence spend of `ops` on this board (no coups).

        Memoised for the life of one ranking, like `_ops_values` and under the
        same contract: every caller restores the board it borrowed. Both
        `ops_value`, which prices a card, and the Ops-type choice, which spends
        it, ask for this, and the search is not cheap enough to run twice."""
        cache = self.__dict__.get('_placement_values')
        if cache is not None and ops in cache:
            return cache[ops]
        side, board = obs.side, self.board
        reachable = [c for c in board.countries if board.is_reachable(side, c)
                     and not (side is Side.USSR and obs.turn_effects.get('chernobyl') == board.countries[c].region.value)]
        original = {c: dict(board.influence[c]) for c in reachable}
        total, remaining = 0., ops
        try:
            while remaining > 0:
                best = None
                for c in reachable:
                    if board.influence_cost(side, c) > remaining:
                        continue
                    gain, points = self._investment(obs, c, remaining)
                    if best is None or gain > best[0]:
                        best = (gain, c, points)
                if best is None or best[0] <= 0:
                    break
                gain, c, points = best
                for _ in range(points):
                    cost = board.influence_cost(side, c)
                    if cost > remaining:
                        break
                    remaining -= cost
                    total += gain * cost
                    self._add_influence(c, side, 1)
                self._base_regions = {} if self._base_regions is not None else None
                self._base_margins = {} if self._base_margins is not None else None
        finally:
            for c, inf in original.items():
                self._set_influence(c, inf['US'], inf['USSR'])
            self._base_regions = {} if self._base_regions is not None else None
            self._base_margins = {} if self._base_margins is not None else None
        if cache is not None:
            cache[ops] = total
        return total

    def _investment(self, obs: Observation, cid: str, ops: int) -> tuple[float, int]:
        """Best value per Op of investing in `cid`, and the points that earn it."""
        original = dict(self.board.influence[cid])
        spent = 0
        best = (LOSS, 1)
        try:
            for points in range(1, ops + 1):
                spent += self.board.influence_cost(obs.side, cid)
                if spent > ops:
                    break
                self._set_influence(cid, original['US'], original['USSR'])
                gain = self.delta(obs, cid, own=points) / spent
                if gain > best[0]:
                    best = (gain, points)
                self._add_influence(cid, obs.side, points)
        finally:
            self._set_influence(cid, original['US'], original['USSR'])
        return best

    def _event_helper(self) -> 'StrategicPlayer':
        # Plays the EVENT_INFLUENCE decisions of a simulated event; one
        # instance serves every event this player evaluates.
        # Rebuilt when the weights object is replaced: training mutates
        # `bot.weights` on a live player, and a helper left on the old weights
        # would play the simulated event's choices by one value function while
        # the result was scored by another.
        helper = self.__dict__.get('_event_policy')
        if helper is None or helper.weights is not self.weights:
            helper = self._event_policy = StrategicPlayer(self.weights)
        return helper

    def influence(self, obs: Observation, cid: str, ops: int) -> float:
        # Search the feasible investment into this country; account for the
        # doubled cost ending immediately after enemy control is broken.
        original = dict(self.board.influence[cid])
        spent = 0
        best = LOSS
        try:
            for points in range(1, ops + 1):
                spent += self.board.influence_cost(obs.side, cid)
                if spent > ops:
                    break
                self._set_influence(cid, original['US'], original['USSR'])
                gain = self.delta(obs, cid, own=points)
                best = max(best, gain / spent)
                self._add_influence(cid, obs.side, points)
        finally:
            self._set_influence(cid, original['US'], original['USSR'])
        return best

    def _rounds_left(self, obs: Observation) -> int:
        """Action rounds still to play this turn, counting the current one."""
        total = 6 if obs.turn <= 3 else 7
        if obs.phase == 'headline':
            return total
        return max(1, total - obs.action_round + 1)

    def military_credit(self, obs: Observation, gained: int, already: int, defcon: int) -> float:
        """What `gained` Military Ops are worth to a side already holding
        `already` of them, in raw units.

        The requirement itself is exact (6.3.5): a side below the DEFCON
        level at the end of the turn hands the difference over as VP, so an
        Op that closes the deficit is worth one VP and an Op past it is
        worth nothing.

        The discount is the part that is not exact. A flat one VP an Op
        overshoots badly early in a turn, because some *later* card would
        very likely have covered the requirement anyway, and only the Ops
        that end up uncovered are really worth a VP. Charging the full VP on
        turn 1 put Korean War 1.07 Ops and Indo-Pakistani War 1.09 Ops past
        the expert's values and took the fixture from 23 misses to 26.
        Spreading it over the rounds still to play is the same shape the
        Containment and Red Scare riders already use, and it has no free
        parameter: full value in the last round, a sixth of it in the first.
        Whether a later card *actually* covers the requirement is the hand
        planner's question, not this one's.
        """
        deficit = max(0, defcon - already)
        if gained <= 0 or deficit <= 0:
            return 0.
        return (self.weights.military * min(gained, deficit)
                * self.vp_value(obs) / self._rounds_left(obs))

    def coup(self, obs: Observation, cid: str, ops: int, military: bool = True) -> float:
        """What couping `cid` with `ops` is worth.

        `military=False` for a Coup the card calls *free* (Junta, Ortega
        Elected in Nicaragua, Tear Down This Wall): it does not advance the
        Military Operations track, so it earns no credit against the
        requirement, while still degrading DEFCON on a Battleground like any
        other Coup. See `Engine.resolve_free_op_choice`."""
        info = self.board.countries[cid]
        if obs.turn_effects.get('cuban_missile_crisis') == obs.side.value:
            return LOSS
        if obs.defcon <= 2 and _coup_risks_defcon(obs, obs.side, info):
            return LOSS if self._is_phasing(obs) else -LOSS
        enemy = self.board.influence[cid][obs.side.opponent.value]
        mod = _coup_roll_modifier_estimate(obs, obs.side, info)
        gain = 0.0
        for roll in range(1, 7):
            margin = max(0, int(roll + ops - 2 * info.stability + mod))
            removed = min(enemy, margin)
            gain += self.delta(obs, cid, own=margin-removed, opp=-removed) / 6
        gain *= self.weights.coup_discount
        if military:
            gain += self.military_credit(obs, ops, obs.military_ops.get(obs.side.value, 0), obs.defcon)
        if obs.side is Side.US and obs.game_effects.get('yuri_samantha'):
            gain -= self.vp_value(obs)
        return gain

    def realign(self, obs: Observation, cid: str) -> float:
        side = obs.side
        bonus = _realignment_bonus(self.board, side, cid) - _realignment_bonus(self.board, side.opponent, cid) + _realignment_modifier(obs, side)
        total = 0.0
        outcomes = {}
        for a in range(1, 7):
            for b in range(1, 7):
                margin = int(a-b+bonus)
                if margin not in outcomes:
                    outcomes[margin] = self.delta(obs, cid, own=min(0, margin), opp=-max(0, margin)) / 36
                # Keep the original addition order (and floating-point ties).
                total += outcomes[margin]
        return total * self.weights.coup_discount

    def _public_event_value(self, obs: Observation, cid: str) -> float:
        """Simulate a whitelisted event in an idle sandbox and value the change.

        Every whitelisted event at one decision starts from the same board,
        so its per-country and per-region terms are computed once and only
        the countries and regions the event touched are re-evaluated,
        preserving the original summation order.
        """
        engine = self.public_engine(obs)
        basis_key = (self.weights, obs.side, tuple((c, v['US'], v['USSR'])
                                                 for c, v in obs.influence.items()))
        if self._event_basis is None or self._event_basis[0] != basis_key:
            # One snapshot for the whole basis. Each of these entry points
            # would otherwise build its own, so the 85-country walk below
            # rebuilt an 85-country snapshot 85 times.
            snap = ev.Position(self._terrain).sync(engine.board)
            countries = {c: self.country_value(engine.board, c, obs.side, snap)
                         for c in engine.board.countries}
            regions = {r: self.region_score(engine.board, r, obs.side, snap) for r in Region}
            margins = {r: self.region_margin(engine.board, r, obs.side, snap) for r in Region}
            before = sum(countries.values()) + self.weights.region * sum(regions.values()) + sum(margins.values())
            self._event_basis = (basis_key, countries, regions, margins, before)
        _, countries, regions, margins, before = self._event_basis
        engine._fire_event(obs.side, cid)
        self._sandbox_terminal = False
        return self._resolve_sandbox(engine, obs, cid, countries, regions, margins, before, self._event_helper())

    def _resolve_sandbox(self, engine: Engine, obs: Observation, cid: str, countries, regions, margins,
                         before, policy, rolls: int = 0) -> float:
        """Drive the sandbox to rest and value the board change. A die
        (`*_ROLL` chance decision) is not sampled: every face is followed
        on a forked engine and the results averaged, so a war event is
        worth its expected outcome, not a certain success. Other chance
        decisions (reveals, deals) take their middle option."""
        for _ in range(64):
            if engine.is_terminal or engine.pending_decision is None:
                break
            d = engine.pending_decision
            if d.actor is Side.CHANCE:
                if d.kind.name.endswith('_ROLL') and rolls < 2:
                    # Outside physical mode the engine exposes only the face
                    # its RNG drew; the sandbox wants all six. A dice contest
                    # (Olympic Games, Summit) rolls both sides at once and
                    # carries two dice in the one option, so the faces are the
                    # 36 combinations, not six. Reading exactly one key here
                    # is what made those two events unpriceable.
                    faces = d.options
                    if len(faces) == 1:
                        dice = d.options[0].payload
                        if not dice or not all(isinstance(v, int) and 1 <= v <= 6 for v in dice.values()):
                            raise SandboxUnsupported(
                                '%s carries %r, which is not a set of dice' % (d.kind.name, dice))
                        faces = tuple(Action(d.kind, dict(zip(dice, values)))
                                      for values in itertools.product(range(1, 7), repeat=len(dice)))
                    total = 0.
                    for option in faces:
                        fork = Engine.deserialize(engine.serialize())
                        fork.log = SANDBOX_LOG
                        fork._decision_stack[-1] = replace(fork.pending_decision, options=faces)
                        fork.step(option)
                        total += self._resolve_sandbox(fork, obs, cid, countries, regions, margins, before, policy, rolls+1)
                    return total / len(faces)
                engine.step(d.options[len(d.options) // 2])  # the middle option
            else:
                engine.step(policy.choose_action(engine.observe(d.actor), []))
        else:
            raise SandboxUnsupported('event %s did not reach rest in 64 steps' % cid)
        if engine.is_terminal:
            # `rolls` counts the dice this branch is one face of. At zero the
            # event ends the game outright and the sentinel is right: nothing
            # on the board buys it back. Inside a fork it is one face of an
            # average, and the sentinel makes the average meaningless -- a
            # Summit at DEFCON 2 priced at 0.4167 * LOSS, which is 15/36 of a
            # number chosen to be unreachable rather than 15/36 of what losing
            # actually costs. A probabilistic ending is worth the game.
            end = -LOSS if rolls == 0 else self.game_value(obs)
            if rolls:
                # A probabilistic ending, priced right here as its share of
                # the game. `event_value` must not then charge `event_risk`
                # for the same dice: that is the third count on Summit.
                self._sandbox_terminal = True
            return end if engine.winner is obs.side else -end
        changed = {c for c in engine.board.countries if engine.board.influence[c] != obs.influence[c]}
        changed_regions = {engine.board.countries[c].region for c in changed}
        affected = self._value_dependents(changed)
        t, w, side = self._terrain, self.weights, ev.SIDE_INDEX[obs.side]
        sign = 1 if side == ev.US else -1
        vector = self._urgency_vector()
        defcon = self._obs.defcon if self._obs is not None else 5
        position = ev.Position(t).sync(engine.board)
        # Read the sandbox's own effects, not the observation's: an event that
        # turns Formosan Resolution or Shuttle Diplomacy on is worth exactly
        # the scoring it changes, and that is only visible from after it fired.
        flags = scoring_flags(engine.game_effects)
        changed_regions |= {r for r in Region
                            if self._overrides_for(r, position, flags)
                            != self._overrides_for(r, position, self._scoring_flags)}
        # An event that turns NATO or the pact on changes what the opponent
        # may coup, so the after-value reads the sandbox's own prohibitions.
        bans = coup_bans(engine.game_effects)
        if bans != self._coup_bans:
            affected = set(countries)
        after = sum(ev.country_value(t, position, t.index[c], side, w, vector, defcon, bans)
                    if c in affected else v for c, v in countries.items())
        after += w.region * sum(
            sign * ev.region_vp(t, position, r, *self._overrides_for(r, position, flags))
            if r in changed_regions else v for r, v in regions.items())
        after += sum(sign * ev.margin_basis(t, position, r, w, vector)[0] if r in changed_regions else v
                     for r, v in margins.items())
        result = after - before
        result += self.vp_value(obs) * (engine.vp-obs.vp) * (1 if obs.side is Side.US else -1)
        # Military Operations the event awarded, on the same VP scale as the
        # VP it awarded. The wars hand Ops to whoever the event belongs to,
        # which is not always the side playing the card -- the US playing
        # Korean War for its Ops gives the *USSR* the credit -- so both sides
        # are priced. Only the part that closes a real deficit is worth
        # anything: past the requirement the track pays nothing (6.3.5).
        for who, sign_of in ((obs.side, 1), (obs.side.opponent, -1)):
            already = obs.military_ops.get(who.value, 0)
            gained = engine.military_ops.get(who.value, 0) - already
            result += sign_of * self.military_credit(obs, gained, already, engine.defcon)
        return result

    def _value_dependents(self, changed) -> set[str]:
        """Every country whose `country_value` can move when the influence in
        `changed` moves.

        Not just `changed` itself: `country_value` reads out to
        `evaluator.VALUE_RADIUS` hops, so a country keeps its basis value only
        when nothing that close to it moved. With `wipe` on, `_coup_targets`
        counts the whole board and nothing keeps its value. Reusing the basis
        for `changed` alone priced Nasser at -67.83 where a full recomputation
        gives -65.89, the whole 1.94 being Israel, whose own influence the
        event never touched."""
        if self.weights.wipe > 0:
            return set(self.board.countries)
        t = self._terrain
        return {t.ids[i] for i in ev.dependents(t, {t.index[c] for c in changed})}

    def event_value(self, obs: Observation, cid: str) -> float:
        if cid in self._events:
            return self._events[cid]
        card = CARDS[cid]
        sign = -1 if card.side.value == obs.side.opponent.value else 1
        if cid in self._events_in_progress:
            # A hand term is valuing this card through a hand that holds it:
            # Ask Not prices the hand, which holds Five Year Plan, which
            # prices the hand, which holds Ask Not. The inner reference gets
            # the shallow Ops estimate; the outer call is the one that counts.
            return sign * self.ops_value(obs, card.ops) * 0.8
        self._events_in_progress.add(cid)
        try:
            return self._event_value_uncached(obs, cid, card, sign)
        finally:
            self._events_in_progress.discard(cid)

    def _event_value_uncached(self, obs: Observation, cid: str, card, sign: int) -> float:
        result = None
        sandbox_owns_ending = False
        if cid in OPS_MODIFIER_EVENTS:
            result = self._ops_modifier_value(obs, cid)
        elif cid in PUBLIC_EVENTS:
            try:
                result = self._public_event_value(obs, cid)
                sandbox_owns_ending = self._sandbox_terminal
            except SandboxUnsupported as exc:  # a branch the sandbox cannot drive
                log.debug('event %s not simulated (%s); using the estimate', cid, exc)
                self.sandbox_failures[cid] = 'unsupported'
            except Exception as exc:
                # Not a branch the sandbox declined: something broke. Still fall
                # back, so one bad event cannot end a game, but say so, and
                # record it where a caller can see the value is an estimate.
                log.warning('event %s failed in the sandbox (%s: %s); using the estimate',
                            cid, type(exc).__name__, exc)
                self.sandbox_failures[cid] = '%s: %s' % (type(exc).__name__, exc)
        elif cid == ASK or cid in HAND_ATTACK_EVENTS:
            # These terms read the hand and the deck rather than the sandbox,
            # so they skip the engine's own prerequisite check -- and priced
            # Star Wars at +50 with neither side ahead in space, and Our Man
            # In Tehran at +25 with no US-controlled Middle Eastern country.
            # An event that cannot occur is worth nothing.
            if not self._event_eligible(obs, cid):
                result = 0.
            elif cid == ASK:
                result = self._hand_upgrade_value(obs)
            else:
                result = self._hand_attack_value(obs, cid)
        if result is None:
            # Explicit approximation for events beyond the public simulator:
            # the card's Ops on this board, discounted -- and on the same
            # scale as everything else. This used to be `card.ops *
            # weights.ops * 0.8`, a raw weight of 2.0 where `ops_value(1)`
            # is ~30 on turn 1 and ~75 on turn 6, so every card that fell
            # through here was priced at 0.02-0.06 Ops: CIA Created, which
            # grants a literal Op, came out at 1.6 raw against 28.6 for one
            # Op. The same defect was found and fixed for `vp` (see the
            # StrategicWeights comment on vp_early); `ops` was left behind.
            result = sign * self.ops_value(obs, card.ops) * 0.8
        # No event is worth more than winning, so a value term is bounded by
        # the game before any risk arithmetic touches it (the convex
        # combination below then preserves the bound). This is the boundary
        # between the two kinds of number in this file: below it, `LOSS` is
        # an unreachable *ordering* sentinel that only `safety_key` reads;
        # above it, every number is a price. Aggregates crossed the bound on
        # their own -- Ask Not summed a whole hand's upgrades to 1.06x the
        # game, Aldrich Ames to 1.13x -- quite apart from the sentinel
        # leaks that clamping `hold_value` fixed.
        cap = self.game_value(obs)
        result = max(-cap, min(cap, result))
        # Opponent-granted operations may coup a battleground at DEFCON 2.
        planner = self._planner or self.planner_for(obs)
        risk = planner.event_risk(cid)
        if risk >= 1:
            result = LOSS  # certain: the sentinel, not a price
        elif risk and not sandbox_owns_ending:
            result = (1-risk)*result - risk*self.game_value(obs)
        self._events[cid] = result
        return result

    def _event_eligible(self, obs: Observation, cid: str) -> bool:
        """Whether `cid`'s event can occur at all here, asked of the engine
        rather than reimplemented (Star Wars needs the Space Race lead, Our
        Man In Tehran a US-controlled Middle Eastern country, Willy Brandt an
        un-torn-down wall...)."""
        if cid not in EVENTS:
            return True
        try:
            return bool(EVENTS[cid].eligible(self.public_engine(obs), obs.side))
        except Exception:  # a prerequisite the idle sandbox cannot answer
            return True

    def _shallow_event_value(self, obs: Observation, cid: str) -> float:
        """A card's event value for use *inside* a hand term.

        The hand terms are mutually recursive by nature: Ask Not prices the
        hand, which holds Five Year Plan, which prices the hand, which holds
        Ask Not. `_events_in_progress` breaks the loop, but whichever card is
        reached first gets the full value and the other gets the estimate --
        so reversing the legal-option order moved Ask Not by 170 raw units.
        Hand terms therefore never ask for another hand-attack card's full
        value; they take the flat estimate for those, which depends on
        nothing but the card and the board, and the full value for every
        other card, which cannot recurse back into a hand term."""
        card = CARDS[cid]
        if cid in HAND_ATTACK_EVENTS or cid == ASK:
            sign = -1 if card.side.value == obs.side.opponent.value else 1
            return sign * self.ops_value(obs, card.ops) * 0.8
        return self.event_value(obs, cid)

    def hold_value(self, obs: Observation, cid: str, shallow: bool = False) -> float:
        """What having `cid` in hand is worth to `obs.side`: a scoring card
        scores its region, anything else gets played (`card_play_value`, so
        an opponent event carries its harm). Negative for a card you would
        rather not hold -- which is what makes losing it a gift.

        A card that would end the game is clamped rather than carrying the
        win/loss sentinel out: this is a value term, and the sentinel is
        `safety_key`'s to use. Both branches need the clamp. The scoring one
        always had it; the branch below did not, so an event that is certain
        defeat (`event_value` returns `LOSS` by design -- "certain: the
        sentinel, not a price") walked straight into the callers, every one
        of which averages, mins or maxes these. A USSR hand holding a
        Duck and Cover it cannot safely play at DEFCON 2 priced that hold at
        -999,904, and the mean of a hand containing it is not a number: Ask
        Not came out at +999,948, 742x the whole game, so the bot would play
        it ahead of a winning move, and Aldrich Ames landed past the
        sentinel and was refused as certain defeat. The bound is what the
        game itself is worth -- no card in hand is worth more than winning."""
        card = CARDS[cid]
        if card.scoring:
            value = self.scoring_card_value(obs, cid)
            cap = 20 * self.vp_value(obs)
            return max(-cap, min(cap, value))
        event = (self._shallow_event_value(obs, cid) if shallow
                 else self.event_value(obs, cid))
        value = self.card_play_value(obs, cid, _effective_ops_estimate(card, obs, obs.side), event)
        cap = self.game_value(obs)  # GAME_SWING_VP: the whole -20..+20 track
        return max(-cap, min(cap, value))

    def _unseen_holds(self, obs: Observation, side: Side) -> list[float]:
        """A hold value for every unseen card, from `side`'s seat, on Ops
        alone (valuing ~100 unseen events would cost more than the decision).
        Scoring cards are the exception and are exact: their region nets the
        same VP whoever plays them, so `side`'s hold is ours or its negation."""
        cached = self._unseen_hold_values.get(side)
        if cached is not None:
            return cached  # the same pool for every hand-attack card in one ranking
        holds = []
        for card in CARDS.values():
            if card_state(obs, card.id) != 'unseen':
                continue
            if card.scoring:
                value = self.hold_value(obs, card.id)
                holds.append(value if side is obs.side else -value)
            else:
                holds.append(self.ops_value(obs, _effective_ops_estimate(card, obs, side)))
        self._unseen_hold_values[side] = holds
        return holds

    @staticmethod
    def _expected_min(values: list[float], n: int) -> float:
        """The expected smallest of `n` draws, the mirror of `_expected_max`."""
        if not values:
            return 0.
        ranked = sorted(values)
        return ranked[min(len(ranked) - 1, len(ranked) // (max(1, n) + 1))]

    @staticmethod
    def _expected_max(values: list[float], n: int) -> float:
        """The expected largest of `n` draws without replacement from
        `values`, by the order-statistic rule of thumb: the top 1/(n+1)
        quantile."""
        if not values:
            return 0.
        ranked = sorted(values, reverse=True)
        return ranked[min(len(ranked) - 1, len(ranked) // (max(1, n) + 1))]

    def _hand_attack_value(self, obs: Observation, cid: str) -> float:
        """The hidden-information cards that take, discard or reveal cards,
        priced by what the cards involved are worth to whoever holds them.

        Every term below is "gain to the card's beneficiary", returned from
        our seat. Where the affected hand is ours it is priced exactly through
        `hold_value`; where it is the opponent's it is unseen (mandate #4), so
        the term uses `_unseen_holds` and the hand size we can see.

        Two consequences worth knowing. A random or chosen discard from a
        hand whose cards all have *negative* hold value is a gain to the
        victim -- which is the end-of-turn Five Year Plan play, dumping a
        scoring card that would score against you, and it falls out of the
        arithmetic rather than being special-cased. And the generic estimate
        these replace priced all of them at 0.8 of their own Ops, which for
        Missile Envy against a hand of 4s is short by a factor of five.
        """
        me = obs.side
        card = CARDS[cid]
        player = me  # event_value is asked for a card we hold, so we would be playing it
        own_hand = [c for c in obs.hand if c != cid]

        def seat(gain: float, beneficiary: Side) -> float:
            return HAND_ATTACK_REALISED * gain if beneficiary is me else -gain

        denial = CARD_DENIAL_OPS * self.ops_value(obs, 1)
        total_rounds = 6 if obs.turn <= 3 else 7
        rounds = total_rounds if obs.phase == 'headline' else max(0, total_rounds - obs.action_round)

        def held(holds: list[float], hand_size: int, scoring_free: list[float] | None = None) -> float:
            """What the holder would have held anyway: the worst non-scoring
            hold, when the hand is larger than the rounds left to play it.
            A card lost from such a hand costs only its excess over that --
            you play the card you were going to hold instead. Nothing, when
            every card was going to be played."""
            if hand_size <= rounds:
                return 0.
            pool = scoring_free if scoring_free is not None else holds
            return min(pool) if pool else 0.

        if cid in ('CIA_Created', 'Lone_Gunman'):
            beneficiary = Side.US if cid == 'CIA_Created' else Side.USSR
            # One Op of Operations for the beneficiary; the hand reveal is
            # information only, unpriced.
            return seat(self.ops_value(obs, 1), beneficiary)

        if cid in ('Five_Year_Plan', 'Terrorism'):
            # The victim loses a uniformly random card. Five Year Plan's
            # "a US event fires" rider is not priced.
            victim = Side.USSR if cid == 'Five_Year_Plan' else player.opponent
            if victim is me:
                holds = [self.hold_value(obs, c, shallow=True) for c in own_hand]
                keepable = [self.hold_value(obs, c, shallow=True)
                            for c in own_hand if not CARDS[c].scoring]
                floor = held(holds, len(own_hand), keepable)
            else:
                holds = self._unseen_holds(obs, victim)
                floor = (self._expected_min(holds, obs.opponent_hand_size)
                         if obs.opponent_hand_size > rounds else 0.)
            mean = sum(holds) / len(holds) if holds else 0.
            loss = max(0., mean - floor) if floor else mean
            loss += denial if mean > 0 else 0.  # no premium for losing a card you wanted gone
            if cid == 'Terrorism' and player is Side.USSR and obs.game_effects.get('iranian_hostage'):
                loss *= 2  # two discards after the Iranian Hostage Crisis
            return seat(loss, victim.opponent)

        if cid == 'Aldrich_Ames_Remix':
            # The USSR sees the US hand and discards the card the US values most.
            if me is Side.US:
                holds = [self.hold_value(obs, c, shallow=True) for c in own_hand]
                keepable = [self.hold_value(obs, c, shallow=True)
                            for c in own_hand if not CARDS[c].scoring]
                best = max(holds, default=0.)
                floor = held(holds, len(own_hand), keepable)
            else:
                holds = self._unseen_holds(obs, Side.US)
                best = self._expected_max(holds, obs.opponent_hand_size)
                floor = (self._expected_min(holds, obs.opponent_hand_size)
                         if obs.opponent_hand_size > rounds else 0.)
            loss = (max(0., best - floor) if floor else best) + (denial if best > 0 else 0.)
            return seat(loss, Side.USSR)

        if cid == 'Missile_Envy':
            # The player takes the opponent's highest-Ops card, and the
            # opponent must spend their next round on Missile Envy's 2 Ops.
            # The player gains that card's Ops; the opponent swaps their best
            # card for a 2.
            victim = player.opponent
            unseen = [c for c in CARDS.values() if card_state(obs, c.id) == 'unseen' and not c.scoring]
            if unseen:
                best_ops = self._expected_max(
                    [_effective_ops_estimate(c, obs, victim) for c in unseen], obs.opponent_hand_size)
            else:
                best_ops = 2
            taken = self.ops_value(obs, int(best_ops))
            gain = taken + (taken - self.ops_value(obs, 2))
            return seat(gain, player)

        if cid == 'Grain_Sales_to_Soviets':
            # A random USSR card is shown; the US plays it or hands it back
            # for 2 Ops. Taking it is worth its Ops to the US, plus the card
            # the USSR loses, plus the denial premium -- this card actually
            # discards, which is what puts it above Missile Envy -- less the
            # estimated harm if it is a Soviet event. Scoring cards net the
            # same whoever plays them, so they count as a return.
            floor = self.ops_value(obs, 2)
            options = []
            for c in CARDS.values():
                if card_state(obs, c.id) != 'unseen':
                    continue
                if c.scoring:
                    options.append(floor)
                    continue
                us_ops = self.ops_value(obs, _effective_ops_estimate(c, obs, Side.US))
                take = (us_ops + self.ops_value(obs, _effective_ops_estimate(c, obs, Side.USSR))
                        + denial - (0.8 * us_ops if c.side.value == 'USSR' else 0.))
                options.append(max(floor, take))
            gain = sum(options) / len(options) if options else floor
            return seat(gain, Side.US)

        if cid == 'Salt_Negotiations':
            # The player takes any non-scoring card from the discard pile
            # into hand -- a card fetched and a card more to hold, for the
            # Action Round the event costs; `card_play_value` weighs that
            # against the 3 Ops. Priced as the best hold in the pile over the
            # dozen highest-Ops candidates. The DEFCON +2 is the planner's
            # (RAISERS); the -1 to coup rolls this turn is not priced.
            pool = sorted((c for c in obs.discard_pile if not CARDS[c].scoring),
                          key=lambda c: -CARDS[c].ops)
            best = max((self.hold_value(obs, c, shallow=True) for c in pool[:12]), default=0.)
            return seat(max(0., best), player)

        if cid == 'Our_Man_In_Tehran':
            # The US looks at the top five of the draw pile and discards any
            # of them. Worth what the US would rather not see drawn: five
            # draws' worth of the cards whose existence hurts it. Scoring
            # cards are exact -- a region scoring against the US is delayed
            # -- and a Soviet event is the generic estimate of its harm,
            # halved for the seat that would have drawn it. Every other card
            # is a card the US is happy to leave. Rarely large, as the expert
            # says, unless the pile is holding a Lone Gunman or a bad scoring.
            harms = []
            for card in CARDS.values():
                if card_state(obs, card.id) != 'unseen':
                    continue
                if card.scoring:
                    value = self.hold_value(obs, card.id)
                    harm = -(value if me is Side.US else -value)
                elif card.side.value == 'USSR':
                    harm = 0.5 * 0.8 * self.ops_value(obs, card.ops)
                else:
                    harm = 0.
                harms.append(max(0., harm))
            gain = 5 * sum(harms) / len(harms) if harms else 0.
            return seat(gain, Side.US)

        if cid == 'Star_Wars':
            # The US plays the event of any non-scoring card in the discard
            # pile. Public, so exact -- over the dozen highest-Ops US or
            # neutral candidates, each an event simulation.
            pool = [c for c in obs.discard_pile
                    if not CARDS[c].scoring and CARDS[c].side.value != 'USSR']
            pool.sort(key=lambda c: -CARDS[c].ops)
            # The US chooses, so the maximum is taken over what the *US*
            # gains, then converted back. Maximising our own seat's value and
            # clamping at zero priced Star Wars at nothing for the USSR --
            # the retrieved Marshall Plan lands either way, and costs them
            # exactly what it gains the US.
            gains = [self.event_value(obs, c) if me is Side.US else -self.event_value(obs, c)
                     for c in pool[:12]]
            return seat(max([0.] + gains), Side.US)

        return None

    def _hand_upgrade_value(self, obs: Observation) -> float:
        """Ask Not...: what replacing the worst of a hand is worth.

        The card's whole strength is that the discard is *chosen*. Every
        opponent event you were otherwise going to have to play for its Ops
        -- eating the event to get the Operations -- and every card too small
        to buy anything becomes an average draw instead. So it is worth the
        sum of the positive upgrades over a hand, and nothing like the flat
        `ops * 0.8` estimate it used to fall through to, which priced a
        3-Ops US card and said nothing about what the card does.

        Our own hand is priced exactly, by `card_play_value`, so an opponent
        event carries its harm and one of our own carries the better of its
        Ops and its Event. The replacement is priced on Ops alone: valuing
        the ~100 unseen events would cost more than the whole decision, and
        the omission understates the draw and therefore understates this
        card, which is the safe direction for a term that decides whether to
        spend an Action Round.

        When the opponent is the beneficiary their hand is unseen (mandate
        #4), so what they gain is the expected positive deviation over the
        unseen cards, applied to the hand size we can see.

        A scoring card in hand is deliberately not counted here. Dumping one
        is often the point -- and legal, see docs/RULES_SOURCES.md -- but it
        is priced where the choice is actually made, by `scoring_card_value`
        in `score(EVENT_CHOICE)`. Folding it in here would mean pricing a
        game-ending scoring card with the win/loss sentinel inside an
        ordinary value term.
        """
        beneficiary = Side.US  # US-associated: the event favours the US whoever plays it
        unseen = [c for c in CARDS.values()
                  if not c.scoring and card_state(obs, c.id) == 'unseen']
        if not unseen:
            return 0.
        draw = [self.ops_value(obs, _effective_ops_estimate(c, obs, beneficiary)) for c in unseen]
        mean = sum(draw) / len(draw)
        # Upgrading a card you will never get to play is worth nothing, so
        # the count is bounded by the Action Rounds left after this one --
        # the same horizon `_ops_modifier_value` applies to Containment.
        # This is what stops a seven-card hand of small cards from pricing
        # Ask Not above any card in the game on turn 9.
        total_rounds = 6 if obs.turn <= 3 else 7
        rounds = total_rounds if obs.phase == 'headline' else max(0, total_rounds - obs.action_round)
        if beneficiary is obs.side:
            gains = []
            for cid in obs.hand:
                card = CARDS[cid]
                if card.scoring or cid == ASK:
                    continue
                # `hold_value`, not a re-derivation of its body: this was a
                # near-duplicate of that branch and so missed the clamp added
                # there, pricing a hand holding one unplayable card at the
                # sentinel and Ask Not at +999,948 -- 742x the whole game.
                held = self.hold_value(obs, cid, shallow=True)
                gains.append(max(0., mean - held))
            gains.sort(reverse=True)  # the worst cards go first
            return sum(gains[:rounds])
        # Their hand is unseen: the mean upgrade an unknown card offers,
        # over the cards they hold and can still play.
        per_card = sum(max(0., mean - value) for value in draw) / len(draw)
        return -per_card * min(obs.opponent_hand_size, rounds)

    def _ops_modifier_value(self, obs: Observation, cid: str) -> float:
        """Containment / Brezhnev Doctrine: +1 Op (to a maximum of 4) on every
        Ops card the beneficiary plays for the rest of the turn; Red Scare /
        Purge: -1 (to a minimum of 1) on every card the victim plays. Priced
        directly as the marginal Ops over the cards concerned, on our Ops
        scale: our own hand exactly (every other card, scoring cards worth
        nothing), the opponent's as their hand size times the expected
        marginal over the unseen cards. Positive when the hand affected is
        the one it helps, from our seat."""
        from struggler.bots.strategic.public_cards import card_state
        if cid == 'Red_Scare_Purge':
            target, delta = obs.side.opponent, -1
        else:
            target = Side.US if cid == 'Containment' else Side.USSR
            delta = +1

        def marginal(ops: int) -> float:
            if delta > 0:
                return self.ops_value(obs, min(4, ops+1)) - self.ops_value(obs, ops)
            return self.ops_value(obs, ops) - self.ops_value(obs, max(1, ops-1))

        def per_card(c) -> float:
            return 0. if c.scoring or c.ops <= 0 else marginal(c.ops)

        # Only the cards that will actually be played this turn count: the
        # action rounds left after this play, not the hand (one card is held).
        total_rounds = 6 if obs.turn <= 3 else 7
        rounds = total_rounds if obs.phase == 'headline' else max(0, total_rounds - obs.action_round)
        if target is obs.side:
            others = sorted((per_card(CARDS[c]) for c in obs.hand if c != cid), reverse=True)
            n = min(len(others), rounds)
            total = sum(others) * n / len(others) if others else 0.
        else:
            unseen = [c for c in CARDS.values() if card_state(obs, c.id) == 'unseen' and c.id != cid]
            mean = sum(per_card(c) for c in unseen) / len(unseen) if unseen else 0.
            total = mean * min(max(0, obs.opponent_hand_size - 1), rounds)
        if obs.china_card_available and obs.china_card_owner is target:
            total += per_card(CARDS['The_China_Card'])
        # Good for us when our own Ops grow or the opponent's shrink.
        helps_us = (target is obs.side) == (delta > 0)
        return total if helps_us else -total

    def card_play_value(self, obs: Observation, cid: str, ops: int, event: float) -> float:
        """A card played from hand: its Ops (the opponent's event fires too,
        unless this is the card UN Intervention is kept for) or, for our own
        and neutral cards, its event if that is better."""
        opponents = CARDS[cid].side.value == obs.side.opponent.value
        harm = min(0, event) if opponents and cid != self.un_card(obs) else 0
        value = self.ops_value(obs, ops) + harm
        return value if opponents else max(value, event)

    def un_card(self, obs: Observation) -> str | None:
        """The opponent's card UN Intervention in hand is kept for: the one
        whose event hurts most. Its Ops then come clean, which is what
        makes UN plus Marshall Plan (or Decolonization) so strong."""
        if 'UN_Intervention' not in obs.hand:
            return None
        if self._un_card is None:
            worst = min(((self.event_value(obs, c), c) for c in obs.hand
                         if c != 'UN_Intervention' and CARDS[c].side.value == obs.side.opponent.value
                         and not CARDS[c].scoring), default=(0., ''))
            self._un_card = worst[1] if worst[0] < 0 else ''
        return self._un_card or None

    def space_value(self, obs: Observation, ops: int) -> float:
        return self.vp_value(obs) * _space_race_expected_vp(obs, obs.side) - 0.4 * self.ops_value(obs, ops)

    def space_card(self, obs: Observation) -> str | None:
        """The card this turn's space slot is for: the opponent's card whose
        Ops-plus-event is worst, among those the Space Race accepts now."""
        if self._space_card is None:
            engine = self.public_engine(obs)
            worst = None
            for cid in obs.hand:
                card = CARDS[cid]
                if card.side.value != obs.side.opponent.value or not engine._can_space_race(obs.side, card):
                    continue
                if cid == self.un_card(obs):
                    continue  # UN Intervention already neutralises it
                value = self.card_play_value(obs, cid, _effective_ops_estimate(card, obs, obs.side),
                                             self.event_value(obs, cid))
                if worst is None or value < worst[0]:
                    worst = (value, cid)
            self._space_card = worst[1] if worst else ''
        return self._space_card or None

    def score(self, obs: Observation, action: Action) -> float:
        kind, p = action.kind, action.payload
        ctx = obs.pending_decision.context
        if kind is K.PLACE_INFLUENCE and ctx.get('setup'):
            # The opening is a book, not a search: the standard openings
            # keep control through East European Unrest / Socialist
            # Governments and take the access points strong players take.
            book = OPENING_BOOK.get((obs.side.value, ctx.get('subregion')), ())
            index = len(book) - int(ctx['remaining'])
            wanted = book[index] if 0 <= index < len(book) else None
            if wanted is not None and any(a.payload['country'] == wanted for a in obs.pending_decision.options):
                return float(p['country'] == wanted)
            return self.influence(obs, p['country'], 1)
        if kind is K.PLACE_INFLUENCE:
            ops = int(ctx.get('ops_remaining', ctx.get('remaining', ctx.get('ops', 1))))
            if ctx.get('bonus'):
                ops = ctx['base'] - ctx['spent']
                # One extra point per bonus whose region has held every point
                # so far and holds this one too; two are possible at once.
                ops += sum(1 for outside, tag in zip(ctx['non_bonus'], ctx['bonus'])
                           if outside == 0
                           and _in_bonus_region(self.board.countries[p['country']], tag))
            return self.influence(obs, p['country'], ops)
        if kind is K.EVENT_INFLUENCE:
            cid = p['country']
            amount = int(ctx.get('amount', 1))
            if ctx['op'] == 'remove':
                amount = -self.board.influence[cid][ctx['inf_side']] if ctx.get('whole') else -amount
            return self.delta(obs, cid, **{'own' if ctx['inf_side'] == obs.side.value else 'opp': amount})
        if kind is K.COUP_TARGET:
            ops = ctx['ops'] + _bonus_ops(self.board.countries[p['country']], ctx.get('bonus'))
            return self.coup(obs, p['country'], ops)
        if kind is K.REALIGNMENT_TARGET:
            return self.realign(obs, p['country'])
        if kind is K.OPS_TYPE:
            ops = ctx['ops']
            if p['type'] == 'influence':
                # The same greedy multi-country spend `ops_value` prices a card
                # with. Taking the best single country's value per Op and
                # multiplying by the Ops, as this did, is a different estimate:
                # it assumes every point goes to that one country at the first
                # point's rate, so it overprices a spend whose best target
                # saturates after a point or two. A card could then be chosen
                # on one estimate and its Ops spent on the strength of another.
                return self._placement_ops_value(obs, ops)
            engine = self.public_engine(obs)
            coup = p['type'] == 'coup'
            return max(((self.coup(obs, c, ops + _bonus_ops(i, ctx.get('bonus'))) if coup else self.realign(obs, c) * ops)
                        for c, i in self.board.countries.items() if engine._usable_coup_realign_target(obs.side, c, for_coup=coup)), default=LOSS)
        if kind in (K.HEADLINE_PLAY, K.ACTION_ROUND_PLAY):
            cid = p['card']
            card = CARDS[cid]
            if card.scoring:
                value = self.scoring_card_value(obs, cid)
                if abs(value) >= -LOSS:  # scoring it ends the game
                    return value
                return value + (0 if kind is K.HEADLINE_PLAY else 2 * obs.action_round)
            event = self.event_value(obs, cid)
            ops = _effective_ops_estimate(card, obs, obs.side)
            if kind is K.HEADLINE_PLAY:
                return event - 0.5 * self.ops_value(obs, ops)
            value = self.card_play_value(obs, cid, ops, event)
            if cid == 'The_China_Card':
                value -= 4
            if cid == 'UN_Intervention' and self.un_card(obs):
                # Played alone it is a 1-Op card; it is worth keeping for
                # the card it neutralises.
                value = min(value, self.ops_value(obs, 1) + min(0, self.event_value(obs, self.un_card(obs))))
            if cid == 'Five_Year_Plan' and obs.side is Side.USSR:
                # Prefer the controlled late-hand use when survival risks tie.
                value -= max(0, len(obs.hand)-3)
            # One space slot a turn: it goes to the worst card in hand, and
            # only that card is valued as a space play here.
            if cid == self.space_card(obs):
                value = max(value, self.space_value(obs, ops))
            return value
        if kind is K.PLAY_MODE:
            cid = ctx['card']
            event = self.event_value(obs, cid)
            ops = _effective_ops_estimate(CARDS[cid], obs, obs.side)
            if p['mode'] == 'event':
                return event
            if p['mode'] == 'space_race':
                return self.space_value(obs, ops) + 1
            return self.ops_value(obs, ops) + (min(0, event) if p['mode'] != 'un_intervention' and CARDS[cid].side.value == obs.side.opponent.value else 0)
        if kind is K.WAR_TARGET:
            cid = p['country']
            penalty = sum(self.board.control(n) is obs.side.opponent for n in self.board.neighbors(cid))
            penalty += int(ctx.get('count_target_control', True) and self.board.control(cid) is obs.side.opponent)
            probability = max(0, min(6, 7 - ctx['win_from'] - penalty)) / 6
            enemy = self.board.influence[cid][obs.side.opponent.value]
            return probability * (self.delta(obs, cid, own=enemy, opp=-enemy) + self.vp_value(obs) * ctx['vp'])
        if kind in (K.QUAGMIRE_DISCARD, K.HELD_CARD_DISCARD):
            cid = p['card']
            return 0 if cid == 'none' else -CARDS[cid].ops - min(0, self.event_value(obs, cid))
        if kind is K.EVENT_OPS_ORDER:
            # Resolve damage first so operations can repair it afterwards.
            return float(p['order'] == 'event_first')
        if kind is K.EVENT_CHOICE:
            choice = p['choice']
            event = ctx.get('event')
            responsible = ctx.get('phasing_player', obs.side.value) == obs.side.value
            if event == 'How_I_Learned_to_Stop_Worrying':
                if choice == '1':
                    return LOSS if responsible else -LOSS
                return float(choice)  # a larger buffer permits later dangerous events
            if event == ASK:
                if choice == 'stop':
                    return 0
                if CARDS[choice].scoring:
                    # Discarding a scoring card is legal -- the illegal act is
                    # holding one (FAQ 5.0) -- and it is much of what this card
                    # is for. Priced as the exact negation of playing it: dump
                    # the regions that would score against us, keep the ones
                    # that would not. Without this a scoring card came out at
                    # 0 (its Ops value), tying with "stop" and falling to hand
                    # order.
                    return -self.scoring_card_value(obs, choice)
                risk = self._planner.event_risk(choice, 2) if self._planner.opponent_event(choice) else 0
                return 100*risk - CARDS[choice].ops
            if event == 'Salt_Negotiations':
                if choice == 'none':
                    return -1
                return CARDS[choice].ops - 100*(self._planner.event_risk(choice, 2) if self._planner.opponent_event(choice) else 0)
            if event == 'Grain_Sales_to_Soviets':
                # The shown USSR card: take it -- the US plays it in full, so
                # `hold_value` carries a Soviet event's harm -- and the USSR
                # is a card down, with the denial premium if it was an asset;
                # or hand it back for Grain Sales' own 2 Ops. This used to
                # fall through to 0 for both, so "take" won by option order,
                # Soviet events included.
                shown = ctx['card']
                if choice == 'return':
                    return self.ops_value(obs, 2)
                theirs = self.ops_value(obs, _effective_ops_estimate(CARDS[shown], obs, obs.side.opponent))
                return (self.hold_value(obs, shown) + theirs
                        + (CARD_DENIAL_OPS * self.ops_value(obs, 1) if theirs > 0 else 0.))
            if event == 'Star_Wars':
                # Any non-scoring card in the discard pile, its event played
                # now by the US. Worth the event, so a Soviet card prices
                # negative and "none" beats it. The generic card-choice rule
                # below scored this -ops, picking the *weakest* card.
                if choice == 'none':
                    return 0.
                return self.event_value(obs, choice)
            if event == 'Missile_Envy_pick':
                # Tied on Ops by construction; give up the one worth least to us.
                return -self.hold_value(obs, choice)
            if event == 'Aldrich_Ames_Remix':
                # These options are the legitimately revealed US hand.
                hand = tuple(a.payload['choice'] for a in obs.pending_decision.options)
                target = replace(obs, side=Side.US, hand=tuple(c for c in hand if c != choice))
                planner = self.planner_for(target)
                # The US card worth most to the US: its Ops, or its event if
                # that is better -- which from our seat is the harm it does us,
                # negated. Printed Ops alone would hand back a 1-Op Marshall
                # Plan while discarding a 3-Op nothing.
                return 1000*planner.risk() + max(self.ops_value(obs, CARDS[choice].ops),
                                                 -self.event_value(obs, choice))
            if event == 'Wargames':
                if choice != 'end_game':
                    return 0
                engine = self.public_engine(obs)
                engine._fire_event(obs.side, 'Wargames')
                if engine.pending_decision is None:
                    return LOSS
                engine.step(Action(K.EVENT_CHOICE, {'choice': 'end_game'}))
                return -LOSS if engine.winner is obs.side else LOSS
            if event == 'De_Stalinization_remove':
                # Keep relocating while the cheapest point to lift is worth
                # less than the best place it can go (max 2 per country,
                # never into US control). A whole-relocation plan (four
                # best destinations against four cheapest lifts) measured
                # 0.44 against this on seeds 4000-4015: it lifts Austria and
                # Laos first because the value function prices those single
                # points below an over-protection point on Poland.
                if choice == 'done':
                    return 0.
                gains = self.__dict__.get('_relocation_gain')
                if gains is None:
                    gains = self._relocation_gain = max(
                        (self.delta(obs, c, own=1) for c in self.board.countries
                         if self.board.control(c) is not Side.US and self.board.influence[c]['USSR'] < 2),
                        default=0.)
                return self.delta(obs, choice, own=-1) + gains
            if event == 'Blockade' and choice == 'refuse':
                return self.delta(obs, 'West_Germany', own=-self.board.influence['West_Germany'][obs.side.value])
            if event == 'Independent_Reds' and choice in self.board.countries:
                inf = self.board.influence[choice]
                return self.delta(obs, choice, own=max(0, inf['USSR']-inf['US']))
            if event == 'Summit_defcon':
                if choice == 'lower' and obs.defcon <= 2:
                    return LOSS if responsible else -LOSS
                return float(choice == 'raise')
            if choice in ('none', 'coup', 'realign') and ctx.get('countries') is not None and 'ops' in ctx:
                # A free Coup/Realignment offer (`push_free_coup_or_realign`:
                # Junta, Ortega Elected in Nicaragua, Tear Down This Wall).
                # Without this the three branches all fell to the 0.0 below,
                # and because `sorted` is stable and the engine offers "none"
                # first, the bot declined every free Coup it was ever handed.
                # Keyed on the offer's shape rather than on three card names,
                # so a future card routed through the same helper is priced
                # too. `none` is the do-nothing baseline at 0, so a Coup worth
                # less than nothing (or forbidden, scoring LOSS) is still
                # correctly refused.
                if choice == 'none':
                    return 0.
                engine = self.public_engine(obs)
                coup = choice == 'coup'
                # `ignore_defcon` matches how the engine filtered the offer:
                # a free Coup is exempt from 8.1.5's DEFCON geography, though
                # not from the DEFCON degradation `coup` already prices.
                return max((self.coup(obs, c, ctx['ops'], military=False) if coup
                            else self.realign(obs, c) * ctx['ops']
                            for c in ctx['countries']
                            if engine._usable_coup_realign_target(
                                obs.side, c, for_coup=coup, ignore_defcon=True)),
                           default=0.)
            if choice in CARDS:
                return CARDS[choice].ops if event == 'Aldrich_Ames_Remix' else -CARDS[choice].ops
            if choice == 'boycott':
                return (LOSS if responsible else -LOSS) if obs.defcon <= 2 else 0
        return 0.0
