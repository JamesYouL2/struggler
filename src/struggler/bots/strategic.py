"""Observation-only tactical policy with trainable linear evaluation weights.

Searches local influence investments and enumerates combat dice. Selected
public-information events are evaluated using an isolated engine; unknown
hands and the real engine RNG are never consulted. This is a bounded tactical
AI, not full-game minimax or a pretrained neural network.
"""
from __future__ import annotations

import copy
import json
import logging
import math
from dataclasses import asdict, dataclass, fields, replace
from pathlib import Path
from typing import Sequence

from struggler.engine import Action, DecisionKind as K, Engine, Observation, Region, Side
from struggler.engine.board import Board
from struggler.engine.cards import load_cards
from struggler.engine.core import RULES, SANDBOX_LOG, SCORING_CARD_REGION
from struggler.bots.public_cards import card_state, scoring_cards_for, scoring_schedule
from struggler.engine.player import Event
from struggler.bots.defcon import DefconPlanner, SurvivalPrior, RAISERS, ASK, US_PAYABLE_DISCARDS

log = logging.getLogger('struggler.bots.strategic')
RISK_WARNING = 0.5  # accepted turn-loss risk at or above this is logged at WARNING
from struggler.bots.greedy import (
    _coup_risks_defcon, _coup_roll_modifier_estimate, _effective_ops_estimate,
    _in_bonus_region, _realignment_bonus, _realignment_modifier,
    _space_race_expected_vp, _sync_board,
)

CARDS = load_cards()
LOSS = -1_000_000.0

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
Our_Man_in_Tehran CIA_Created Lone_Gunman Salt_Negotiations The_China_Card'''.split())
# Duration effects priced by the marginal Ops they add to or take from the hands they touch.
OPS_MODIFIER_EVENTS = ('Containment', 'Brezhnev_Doctrine', 'Red_Scare_Purge')
# For the docs and tests: what the sandbox is asked to simulate.
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
    military: float = 2.0
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


class StrategicPlayer:
    def __init__(self, weights: StrategicWeights | None = None, *, survival_prior: SurvivalPrior | None = None,
                 opponent_model=None):
        self.weights = weights or StrategicWeights()
        self.board = Board()
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
        self._scoring_weights = None

    def choose_action(self, observation: Observation, history: Sequence[Event]) -> Action:
        ranked = self.rank_actions(observation)
        self._log_choice(observation, observation.pending_decision, ranked)
        return ranked[0][1]

    def rank_actions(self, observation: Observation):
        """Prepare this observation and rank legal actions, without choice logging."""
        decision = observation.pending_decision
        if decision is None or not decision.options:
            raise ValueError('StrategicPlayer requires a pending decision with legal options')
        _sync_board(self.board, observation)
        self._events = {}
        # The event sandbox's basis (every country's and region's value on
        # the current board) is keyed on influence alone; the scoring
        # weights it was computed with belong to the previous decision's
        # turn and hand, so it must not survive into this one (the parity
        # corpus caught a headline's basis pricing action round 1's events).
        self._event_basis = None
        self._region_cache = {}
        self._base_regions = {}
        self._base_margins = {}
        self._country_cache = {}
        self._ops_values = {}
        self._relocation_gain = None
        self._space_card = None
        self._un_card = None
        self._obs = observation
        self._scoring_weights = {}
        self._access_cache = {}
        self._region_members = {r: self.board.countries_in(r) for r in Region}
        self._planner = None
        if decision.kind in (K.ACTION_ROUND_PLAY, K.HEADLINE_PLAY, K.PLAY_MODE, K.EVENT_CHOICE,
                             K.QUAGMIRE_DISCARD, K.OPS_TYPE, K.COUP_TARGET):
            self._planner = self.planner_for(observation)
        try:
            return sorted(((self.safety_key(observation, a), a) for a in decision.options),
                          key=lambda pair: pair[0], reverse=True)
        finally:
            self._base_regions = self._base_margins = None  # callers may move the board after ranking

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

    def survival_features(self, observation):
        """Named features usable by a future win-probability model, without retraining VP weights."""
        return self.planner_for(observation).features()

    def planner_for(self, obs: Observation) -> DefconPlanner:
        return DefconPlanner(obs, self.public_engine(obs), self.survival_prior, self.opponent_model)

    def safety_key(self, obs, action):
        """Certain immediate defeat and conditional turn risk precede trainable VP scores."""
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
                risk = planner.risk(cid)
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
        score = self.score(obs, action)
        return (-int(immediate >= 1 or score <= LOSS), -round(risk, 8), score)

    def region_score(self, board: Board, region: Region, side: Side) -> float:
        # Scoring a region is the hottest call in a decision; the same
        # regional position recurs across every candidate country, so
        # memoise on the region's influence for the life of this decision.
        cache = getattr(self, '_region_cache', None)
        key = None
        if cache is not None and board is self.board:
            key = (region, tuple((v['US'], v['USSR']) for v in
                                 map(board.influence.__getitem__, self._region_members[region])))
            if key in cache:
                net = cache[key]
                return net if side is Side.US else -net
        try:
            net = board.score_region(region)
        except RuntimeError:  # Europe control has no numeric scoring value.
            net = 100 if board.region_tier(Side.US, region).value == 'control' else -100
        if key is not None:
            cache[key] = net
        return net if side is Side.US else -net

    def _region_margin(self, board: Board, region: Region) -> float:
        """Partial credit toward the next scoring tier, net for the US in VP
        (see StrategicWeights.margin_presence). Europe's control tier has
        no VP; its domination gap is used as everywhere else."""
        w = self.weights
        if not (w.margin_presence or w.margin_battleground or w.margin_country):
            return 0.
        members = self._region_members.get(region) if hasattr(self, '_region_members') else None
        if members is None:
            members = board.countries_in(region)
        # Memoised like region_score, on the region's influence, per decision.
        cache = getattr(self, '_region_cache', None)
        key = None
        if cache is not None and board is self.board:
            key = ('margin', region, tuple((v['US'], v['USSR']) for v in map(board.influence.__getitem__, members)))
            if key in cache:
                return cache[key][0]
        result = self._region_margin_uncached(board, region, members)
        if key is not None:
            cache[key] = result
        return result[0]

    @staticmethod
    def _margin_contribution(info, us: int, su: int):
        """One country's share of the region aggregates: per side
        (controlled countries, fractional battlegrounds, progress)."""
        margin = us - su
        if margin >= info.stability:
            return (1, float(info.battleground), 1.), (0, 0., 0.)
        if -margin >= info.stability:
            return (0, 0., 0.), (1, float(info.battleground), 1.)
        if us > 0 and margin > 0:
            frac = margin / info.stability
            return (0, info.battleground * frac, frac), (0, 0., 0.)
        if su > 0 and margin < 0:
            frac = -margin / info.stability
            return (0, 0., 0.), (0, info.battleground * frac, frac)
        return (0, 0., 0.), (0, 0., 0.)

    def _margin_unit(self, region: Region, members) -> tuple[float, bool, float]:
        w = self.weights
        presence_vp, domination_vp, _ = RULES['scoring'][region.name]
        sw = (self._scoring_weights.get(members[0]) if self._scoring_weights and members[0] in self._scoring_weights
              else self.scoring_weight(self._obs, members[0]) if self._scoring_weights is not None else 1.)
        # One battleground's control value in this region is the unit; the
        # domination gap is in presence units.
        return w.battleground * sw, sw >= w.margin_live, (domination_vp - presence_vp) / presence_vp

    @staticmethod
    def _margin_bg_total(fractions: dict) -> float:
        """Sum the per-member battleground fractions in member order. The
        full walk adds a 0.0 for every other member and `x + 0.0 == x`, so
        this is bitwise identical to it, which keeps a swapped aggregate from
        reordering near-ties against a freshly computed one."""
        total = 0.
        for _, value in sorted(fractions.items()):
            total += value
        return total

    def _margin_credit(self, agg, unit: float, live: bool, gap: float) -> float:
        """Net US credit from the aggregates {side: [countries, battlegrounds, best progress]}."""
        w = self.weights
        net = 0.
        for side, sign in ((Side.US, 1), (Side.USSR, -1)):
            mine, theirs = agg[side], agg[side.opponent]
            credit = 0.
            if live and mine[0] == 0:
                credit += w.margin_presence * mine[2]
            bg_margin = max(-2., min(2., mine[1] - theirs[1]))
            c_margin = max(-2, min(2, mine[0] - theirs[0]))
            credit += gap * (w.margin_battleground * bg_margin + w.margin_country * c_margin)
            net += sign * credit * unit
        return net

    def _region_margin_uncached(self, board: Board, region: Region, members):
        """Returns (net US credit, aggregates, unit, live, gap)."""
        unit, live, gap = self._margin_unit(region, members)
        inf = board.influence
        agg = {Side.US: [0, 0., 0.], Side.USSR: [0, 0., 0.]}
        fractions = {Side.US: {}, Side.USSR: {}}
        for index, cid in enumerate(members):
            v = inf[cid]
            for side, (c, bgf, prog) in zip((Side.US, Side.USSR), self._margin_contribution(board.countries[cid], v['US'], v['USSR'])):
                a = agg[side]
                a[0] += c
                a[1] += bgf
                if bgf:
                    fractions[side][index] = bgf
                if prog > a[2]:
                    a[2] = prog
        return self._margin_credit(agg, unit, live, gap), agg, unit, live, gap, fractions, members

    def _margin_basis(self, board: Board, region: Region):
        """The region margin's aggregates for the board as this ranking found
        it: `(net, aggregates, unit, live, gap)`. Cached per region under the
        same contract as `_base_regions` (a caller that commits a change
        mid-ranking clears both), so the hot path neither walks the region
        nor builds an influence-keyed cache entry."""
        base = self._base_margins
        hit = None if base is None else base.get(region)
        if hit is None:
            members = self._region_members.get(region) if hasattr(self, '_region_members') \
                else board.countries_in(region)
            hit = self._region_margin_uncached(board, region, members)
            if base is not None:
                base[region] = hit
        return hit

    def _margin_swapped(self, basis, board: Board, region: Region, side: Side, cid: str, before: dict) -> float:
        """The region margin after `cid` moved from `before` to the board's
        current influence, by swapping that one country's contribution into
        `basis`'s aggregates. Falls back to a full pass only when the country
        may have held the region's best progress toward presence."""
        _, agg, unit, live, gap, fractions, members = basis
        info = board.countries[cid]
        current = board.influence[cid]
        index = members.index(cid)
        old = self._margin_contribution(info, before['US'], before['USSR'])
        new = self._margin_contribution(info, current['US'], current['USSR'])
        adjusted = {}
        for s_, o, n in zip((Side.US, Side.USSR), old, new):
            a = agg[s_]
            if o[2] > 0 and o[2] >= a[2] and n[2] < o[2]:
                return self.region_margin(board, region, side)
            if n[1] == o[1]:
                bg_total = a[1]  # unchanged, and exactly as the walk summed it
            else:
                swapped = dict(fractions[s_])
                if n[1]:
                    swapped[index] = n[1]
                else:
                    swapped.pop(index, None)
                bg_total = self._margin_bg_total(swapped)
            adjusted[s_] = [a[0] - o[0] + n[0], bg_total, max(a[2], n[2])]
        net = self._margin_credit(adjusted, unit, live, gap)
        return net if side is Side.US else -net

    def region_margin_after(self, board: Board, region: Region, side: Side, cid: str, before: dict) -> float:
        """`_margin_swapped` against the pre-change board's own aggregates.
        Kept for callers (and the parity test) that do not hold a basis."""
        cache = getattr(self, '_region_cache', None)
        if cache is None or board is not self.board:
            return self.region_margin(board, region, side)
        current = dict(board.influence[cid])
        board.influence[cid].update(before)
        try:
            members = self._region_members.get(region) if hasattr(self, '_region_members') \
                else board.countries_in(region)
            basis = self._region_margin_uncached(board, region, members)
        finally:
            board.influence[cid].update(current)
        return self._margin_swapped(basis, board, region, side, cid, before)

    def country_value(self, board: Board, cid: str, side: Side) -> float:
        w = self.weights
        info = board.countries[cid]
        inf = board.influence[cid]
        us, ussr = inf['US'], inf['USSR']
        own, opp = (us, ussr) if side is Side.US else (ussr, us)
        cache = getattr(self, '_country_cache', None)
        key = (board, cid, side, own, opp)
        if cache is not None and key in cache:
            return cache[key]
        margin = own - opp
        importance = self.importance(info)
        # Control is worth what the region will still score (a battleground
        # in an unscored Early War region >> one in a region just scored,
        # or one whose scoring is turns away). Absent an observation (a
        # bare leaf evaluation) the schedule weight is 1.
        weights = self._scoring_weights
        if weights is not None:
            importance *= weights.get(cid) if cid in weights else self.scoring_weight(self._obs, cid)
        value = importance * (1 if margin >= info.stability else -1 if margin <= -info.stability else 0)
        # Progress toward control is convex: control is worth VP, a lone
        # point is not (it can only lead there), so a half-built country is
        # worth well under half of a controlled one.
        fraction = max(-1.0, min(1.0, margin / info.stability))
        value += w.progress * importance * math.copysign(abs(fraction) ** w.progress_curve, fraction)
        # Wipe risk (see StrategicWeights.wipe): the couper's expected take.
        if own > 0 and w.wipe > 0:
            value -= self._wipe_risk(board, cid, info, side, own, opp, importance)
        if opp > 0 and w.wipe > 0:
            value += self._wipe_risk(board, cid, info, side.opponent, opp, own, importance)
        guard = w.reserve * importance
        value += guard * (min(2, max(0, margin-info.stability)) - min(2, max(0, -margin-info.stability)))
        if info.battleground and (own > 0) != (opp > 0):
            # Tempo is worth most where control is cheap: per stability,
            # like every other per-Op term (a 4-stability contest is the
            # least valuable Op on the board).
            if own > 0 and board.is_reachable(side.opponent, cid):
                value += w.first_mover * importance / info.stability
            elif opp > 0 and board.is_reachable(side, cid):
                value -= w.first_mover * importance / info.stability
        # First footholds open nearby battlegrounds on a later action round:
        # a stake is worth the uncontrolled battlegrounds it alone lets us
        # reach. Nothing for ground we already reach (a fourth point in
        # Eastern Europe opens nothing), and nothing for ground we hold.
        value += w.access * (self._access(board, cid, side) * (own > 0)
                             - self._access(board, cid, side.opponent) * (opp > 0))
        if cache is not None:
            cache[key] = value
        return value

    def _wipe_risk(self, board: Board, cid: str, info, holder: Side, held: int, other: int,
                   importance: float) -> float:
        """Expected loss to `holder` from the opponent's coup wiping this
        country: the chance a 3- or 4-Ops coup removes every point (roll +
        Ops - 2 x stability >= held), where DEFCON allows a coup here,
        shared over the opponent's coupable targets, times the stake.
        Unbacked and the couper gets there first (adjacent already, or the
        coup's excess leaves them influence): the battleground flips, so
        the stake is holder's position plus the country's control value.
        Backed: the stake is holder's position, times `wipe_backed`."""
        if held <= 0:
            return 0.
        w = self.weights
        obs = self._obs
        defcon = obs.defcon if obs is not None else 5
        if defcon < RULES['coup_min_defcon'].get(info.region.name, 2):
            return 0.
        wipes = sum(1 for ops in (3, 4) for roll in range(1, 7) if roll + ops - 2 * info.stability >= held)
        p = wipes / 12
        if p == 0:
            return 0.
        margin = held - other
        position = importance * (1 if margin >= info.stability else 0) \
            + w.progress * importance * max(0., min(1., margin / info.stability))
        key = holder.value
        inf = board.influence
        backed = cid in board._adjacency.get(key, ()) or any(
            inf[n][key] > 0 for n in board.neighbors(cid) if n in inf)
        if backed:
            stake = w.wipe_backed * position
        else:
            couper = holder.opponent
            first = board.is_reachable(couper, cid) or 6 + 4 - 2 * info.stability > held
            stake = w.wipe * (position + (importance * (1 + w.progress) if first else 0.))
        return p * stake / max(1, self._coup_targets(board, holder, defcon))

    def _coup_targets(self, board: Board, holder: Side, defcon: int) -> int:
        """How many battlegrounds `holder` has influence in that the
        opponent could coup at this DEFCON and could wipe with a 4-Ops
        coup on some roll."""
        cache = getattr(self, '_access_cache', None)
        key = ('coup_targets', board, holder, defcon)
        if cache is not None and key in cache:
            return cache[key]
        n = 0
        for cid, info in board.countries.items():
            held = board.influence[cid][holder.value]
            if held <= 0 or not info.battleground:
                continue
            if defcon < RULES['coup_min_defcon'].get(info.region.name, 2):
                continue
            if 6 + 4 - 2 * info.stability >= held:
                n += 1
        if cache is not None:
            cache[key] = n
        return n


    def _access(self, board: Board, cid: str, side: Side) -> float:
        """Reach a holding here gives: the adjacent battlegrounds we do not
        control, each worth its control value scaled by 1/stability. Full weight
        when this holding alone reaches one, `access_redundant` when another
        holding already does (insurance, and one more direction to contest
        from). Chains count too, discounted by `access_chain`: a battleground
        two steps away through a country we do not yet hold (Israel -> Egypt
        -> Libya, Iran -> Pakistan -> India, Australia -> Malaysia ->
        Thailand). Getting to battlegrounds first is most of what a
        non-battleground is for."""
        cache = getattr(self, '_access_cache', None)
        key = (board, cid, side)
        if cache is not None and key in cache:
            return cache[key]
        w = self.weights
        inf, key_side = board.influence, side.value
        home = board._adjacency.get(key_side, ())
        first = set(board.neighbors(cid))
        total = 0.
        for n in first:
            info = board.countries.get(n)
            if info is None:
                continue
            if info.battleground and board.control(n) is not side:
                if n in home or inf[n][key_side] > 0:
                    weight = w.access_redundant  # present already; this adds a direction
                elif any(inf[m][key_side] > 0 for m in board.neighbors(n) if m != cid and m in inf):
                    weight = w.access_redundant  # reachable through another holding
                else:
                    weight = 1.
                if board.is_reachable(side.opponent, n):
                    weight *= w.access_contested
                total += weight * self._importance_of(n, info) / info.stability
            if inf[n][key_side] > 0 or board.control(n) is side.opponent:
                continue  # already ours to build from, or not a step we take
            for m in board.neighbors(n):
                minfo = board.countries.get(m)
                if (minfo is None or not minfo.battleground or m == cid or m in first
                        or board.control(m) is side or inf[m][key_side] > 0 or m in home):
                    continue
                if any(inf[k][key_side] > 0 for k in board.neighbors(m) if k in inf):
                    continue  # reachable directly from somewhere already
                contested = w.access_contested if board.is_reachable(side.opponent, m) else 1.
                total += w.access_chain * contested * self._importance_of(m, minfo) / minfo.stability
        if cache is not None:
            cache[key] = total
        return total

    def _importance_of(self, cid: str, info) -> float:
        """A country's tier times what its region will still score: the
        same scale country_value puts on control."""
        importance = self.importance(info)
        weights = self._scoring_weights
        if weights is not None:
            importance *= weights.get(cid) if cid in weights else self.scoring_weight(self._obs, cid)
        return importance

    def evaluate(self, observation: Observation, board: Board | None = None) -> float:
        """The board value for `observation`'s side in that observation's own
        context: scoring weights from its turn, hand and discards, DEFCON
        from its board, fresh caches. Use this for search leaves. `value()`
        alone evaluates in whatever context the last `rank_actions` left
        behind, which made an identical leaf return three different values
        depending on which position had been ranked before it."""
        saved = (self._obs, self._scoring_weights, self.__dict__.get('_country_cache'),
                 self.__dict__.get('_access_cache'), self.__dict__.get('_region_cache'),
                 self.__dict__.get('_ops_values'), {c: dict(v) for c, v in self.board.influence.items()})
        _sync_board(self.board, observation)  # `board`, if given, must describe the same position
        self._obs = observation
        self._scoring_weights = {}
        self._country_cache = {}
        self._access_cache = {}
        self._region_cache = {}
        self._ops_values = {}
        if not hasattr(self, '_region_members'):
            self._region_members = {r: self.board.countries_in(r) for r in Region}
        try:
            return self.value(self.board, observation.side)
        finally:
            self._obs, self._scoring_weights, country, access, region, ops_values, influence = saved
            for name, val in (('_country_cache', country), ('_access_cache', access),
                              ('_region_cache', region), ('_ops_values', ops_values)):
                if val is not None:
                    setattr(self, name, val)
            for c, v in influence.items():
                self.board.influence[c].update(v)

    def value(self, board: Board, side: Side) -> float:
        return sum(self.country_value(board, c, side) for c in board.countries) \
            + self.weights.region * sum(self.region_score(board, r, side) for r in Region) \
            + sum(self.region_margin(board, r, side) for r in Region)

    def region_margin(self, board: Board, region: Region, side: Side) -> float:
        net = self._region_margin(board, region)
        return net if side is Side.US else -net

    def scoring_weight(self, obs: Observation, cid: str) -> float:
        """How much the area around `cid` will still score, discounted by
        how far off each scoring is (see StrategicWeights.scoring_discount)."""
        cache = self._scoring_weights
        if cache is not None and cid in cache:
            return cache[cid]
        w = self.weights
        total = 0.
        for card in scoring_cards_for(self.board.countries[cid]):
            held = card in obs.hand
            for turns in scoring_schedule(obs, card):
                total += w.scoring_discount ** turns * (w.scoring_hand if held and turns == 0 else 1.)
        if cache is not None:
            cache[cid] = total
        return total

    def importance(self, info) -> float:
        """The country's tier: battleground or not."""
        return self.weights.battleground if info.battleground else self.weights.control

    def delta(self, obs: Observation, cid: str, own: int = 0, opp: int = 0) -> float:
        board, side = self.board, obs.side
        if own == 0 and opp == 0:
            return 0.
        region = board.countries[cid].region
        urgency = self.scoring_weight(obs, cid)
        # While rank_actions runs, every caller enters with the board as it
        # was synced (each restores its own trial changes first), so the
        # region's starting score is fixed; anyone committing a change
        # mid-ranking must clear `_base_regions`.
        base = self._base_regions
        region_before = None if base is None else base.get(region)
        if region_before is None:
            region_before = self.region_score(board, region, side)
            if base is not None:
                base[region] = region_before
        # The margin's aggregates for the unchanged board, cached per region
        # for this ranking exactly like `region_before` above: the trial
        # change below then swaps this one country's contribution, so no
        # call here walks the region or builds a per-influence cache key.
        basis = self._margin_basis(board, region)
        margin_before = basis[0] if side is Side.US else -basis[0]
        before = self.country_value(board, cid, side) + self.weights.region * urgency * region_before + margin_before
        controller = board.control(cid)
        original = dict(board.influence[cid])
        try:
            board.influence[cid][side.value] = max(0, original[side.value] + own)
            board.influence[cid][side.opponent.value] = max(0, original[side.opponent.value] + opp)
            # Partial influence and overprotection cannot change regional VP;
            # the margin term (progress toward presence) can move on either.
            region_after = (region_before if board.control(cid) is controller else
                            self.region_score(board, region, side))
            margin_after = self._margin_swapped(basis, board, region, side, cid, original)
            return (self.country_value(board, cid, side) + self.weights.region * urgency * region_after
                    + margin_after - before)
        finally:
            board.influence[cid].update(original)

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
            return 1.
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

    def vp_value(self, obs: Observation) -> float:
        """What one VP is worth here, in raw units: the era's Ops-per-VP
        (StrategicWeights.vp_early/mid/late) times what one Op buys on this
        board, so VP and Ops stay on one scale as the board's Ops value moves."""
        w = self.weights
        per_vp = w.vp_early if obs.turn <= 3 else w.vp_mid if obs.turn <= 7 else w.vp_late
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
            return per_vp * self.ops_value(obs, 1)
        finally:
            self._vp_reentrant = False

    def ops_value(self, obs: Observation, ops: int) -> float:
        """What `ops` Operations are worth here: the best influence spend
        (a greedy plan, so the value is concave in Ops: the fourth point
        buys less than the first) or the best coup on this board, not a
        flat rate. Puts Ops, events and VP on one scale, so a 4-Ops card on
        turn 1 outranks 3 VP and a late 1-Op card does not."""
        if ops <= 0:
            return 0.
        cached = self._ops_values.get(ops)
        if cached is not None:
            return cached
        total = self._placement_ops_value(obs, ops)
        engine = self.public_engine(obs)
        side, board = obs.side, self.board
        best_coup = max((self.coup(obs, c, ops) for c in board.countries
                         if engine._usable_coup_realign_target(side, c, for_coup=True)), default=LOSS)
        value = max(total, best_coup, 0.)
        self._ops_values[ops] = value
        return value

    def _placement_ops_value(self, obs: Observation, ops: int) -> float:
        """The best greedy influence spend of `ops` on this board (no coups)."""
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
                    board.influence[c][side.value] += 1
                self._base_regions = {} if self._base_regions is not None else None
                self._base_margins = {} if self._base_margins is not None else None
        finally:
            for c, inf in original.items():
                board.influence[c].update(inf)
            self._base_regions = {} if self._base_regions is not None else None
            self._base_margins = {} if self._base_margins is not None else None
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
                self.board.influence[cid].update(original)
                gain = self.delta(obs, cid, own=points) / spent
                if gain > best[0]:
                    best = (gain, points)
                self.board.influence[cid][obs.side.value] += points
        finally:
            self.board.influence[cid].update(original)
        return best

    def _event_helper(self) -> 'StrategicPlayer':
        # Plays the EVENT_INFLUENCE decisions of a simulated event; one
        # instance serves every event this player evaluates.
        helper = self.__dict__.get('_event_policy')
        if helper is None:
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
                self.board.influence[cid].update(original)
                gain = self.delta(obs, cid, own=points)
                best = max(best, gain / spent)
                self.board.influence[cid][obs.side.value] += points
        finally:
            self.board.influence[cid].update(original)
        return best

    def coup(self, obs: Observation, cid: str, ops: int) -> float:
        info = self.board.countries[cid]
        if obs.turn_effects.get('cuban_missile_crisis') == obs.side.value:
            return LOSS
        if obs.defcon <= 2 and _coup_risks_defcon(obs, obs.side, info):
            return LOSS if obs.pending_decision.context.get('phasing_player', obs.side.value) == obs.side.value else -LOSS
        enemy = self.board.influence[cid][obs.side.opponent.value]
        mod = _coup_roll_modifier_estimate(obs, obs.side, info)
        gain = 0.0
        for roll in range(1, 7):
            margin = max(0, int(roll + ops - 2 * info.stability + mod))
            removed = min(enemy, margin)
            gain += self.delta(obs, cid, own=margin-removed, opp=-removed) / 6
        gain *= self.weights.coup_discount
        deficit = max(0, obs.defcon - obs.military_ops.get(obs.side.value, 0))
        gain += self.weights.military * min(ops, deficit)
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
            countries = {c: self.country_value(engine.board, c, obs.side) for c in engine.board.countries}
            regions = {r: self.region_score(engine.board, r, obs.side) for r in Region}
            margins = {r: self.region_margin(engine.board, r, obs.side) for r in Region}
            before = sum(countries.values()) + self.weights.region * sum(regions.values()) + sum(margins.values())
            self._event_basis = (basis_key, countries, regions, margins, before)
        _, countries, regions, margins, before = self._event_basis
        engine._fire_event(obs.side, cid)
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
                    # its RNG drew; the sandbox wants all six.
                    faces = d.options
                    if len(faces) == 1:
                        (key,) = d.options[0].payload
                        faces = tuple(Action(d.kind, {key: v}) for v in range(1, 7))
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
            raise RuntimeError('event %s did not resolve in the sandbox' % cid)
        if engine.is_terminal:
            return -LOSS if engine.winner is obs.side else LOSS
        changed = {c for c in engine.board.countries if engine.board.influence[c] != obs.influence[c]}
        changed_regions = {engine.board.countries[c].region for c in changed}
        after = sum(self.country_value(engine.board, c, obs.side) if c in changed else v
                    for c, v in countries.items())
        after += self.weights.region * sum(self.region_score(engine.board, r, obs.side)
                                            if r in changed_regions else v for r, v in regions.items())
        after += sum(self.region_margin(engine.board, r, obs.side) if r in changed_regions else v
                     for r, v in margins.items())
        result = after - before
        return result + self.vp_value(obs) * (engine.vp-obs.vp) * (1 if obs.side is Side.US else -1)

    def event_value(self, obs: Observation, cid: str) -> float:
        if cid in self._events:
            return self._events[cid]
        card = CARDS[cid]
        sign = -1 if card.side.value == obs.side.opponent.value else 1
        result = None
        if cid in OPS_MODIFIER_EVENTS:
            result = self._ops_modifier_value(obs, cid)
        elif cid in PUBLIC_EVENTS:
            try:
                result = self._public_event_value(obs, cid)
            except Exception as exc:  # a branch the sandbox cannot drive from public state
                log.debug('event %s not simulated (%s); using the estimate', cid, exc)
        if result is None:
            # Explicit approximation for events beyond the public simulator.
            result = sign * card.ops * self.weights.ops * 0.8
        # Opponent-granted operations may coup a battleground at DEFCON 2.
        planner = self._planner or self.planner_for(obs)
        risk = planner.event_risk(cid)
        result = (1-risk)*result + risk*LOSS
        self._events[cid] = result
        return result

    def _ops_modifier_value(self, obs: Observation, cid: str) -> float:
        """Containment / Brezhnev Doctrine: +1 Op (to a maximum of 4) on every
        Ops card the beneficiary plays for the rest of the turn; Red Scare /
        Purge: -1 (to a minimum of 1) on every card the victim plays. Priced
        directly as the marginal Ops over the cards concerned, on our Ops
        scale: our own hand exactly (every other card, scoring cards worth
        nothing), the opponent's as their hand size times the expected
        marginal over the unseen cards. Positive when the hand affected is
        the one it helps, from our seat."""
        from struggler.bots.public_cards import card_state
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
                if not ctx['non_bonus'] and _in_bonus_region(self.board.countries[p['country']], ctx['bonus']):
                    ops += 1
            return self.influence(obs, p['country'], ops)
        if kind is K.EVENT_INFLUENCE:
            cid = p['country']
            amount = int(ctx.get('amount', 1))
            if ctx['op'] == 'remove':
                amount = -self.board.influence[cid][ctx['inf_side']] if ctx.get('whole') else -amount
            return self.delta(obs, cid, **{'own' if ctx['inf_side'] == obs.side.value else 'opp': amount})
        if kind is K.COUP_TARGET:
            ops = ctx['ops'] + int(_in_bonus_region(self.board.countries[p['country']], ctx.get('bonus')))
            return self.coup(obs, p['country'], ops)
        if kind is K.REALIGNMENT_TARGET:
            return self.realign(obs, p['country'])
        if kind is K.OPS_TYPE:
            ops = ctx['ops']
            if p['type'] == 'influence':
                return max((self.influence(obs, c, ops) * ops for c in self.board.countries if self.board.is_reachable(obs.side, c) and not (obs.side is Side.USSR and obs.turn_effects.get('chernobyl') == self.board.countries[c].region.value)), default=LOSS)
            engine = self.public_engine(obs)
            coup = p['type'] == 'coup'
            return max(((self.coup(obs, c, ops + int(_in_bonus_region(i, ctx.get('bonus')))) if coup else self.realign(obs, c) * ops)
                        for c, i in self.board.countries.items() if engine._usable_coup_realign_target(obs.side, c, for_coup=coup)), default=LOSS)
        if kind in (K.HEADLINE_PLAY, K.ACTION_ROUND_PLAY):
            cid = p['card']
            card = CARDS[cid]
            if card.scoring:
                engine = self.public_engine(obs)
                engine._resolve_scoring_card(cid)
                if engine.is_terminal:
                    return -LOSS if engine.winner is obs.side else LOSS
                net = (engine.vp-obs.vp) * (1 if obs.side is Side.US else -1)
                return net * self.vp_value(obs) + (0 if kind is K.HEADLINE_PLAY else 2 * obs.action_round)
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
                risk = self._planner.event_risk(choice, 2) if self._planner.opponent_event(choice) else 0
                return 100*risk - CARDS[choice].ops
            if event == 'Salt_Negotiations':
                if choice == 'none':
                    return -1
                return CARDS[choice].ops - 100*(self._planner.event_risk(choice, 2) if self._planner.opponent_event(choice) else 0)
            if event == 'Aldrich_Ames_Remix':
                # These options are the legitimately revealed US hand.
                hand = tuple(a.payload['choice'] for a in obs.pending_decision.options)
                target = replace(obs, side=Side.US, hand=tuple(c for c in hand if c != choice))
                planner = self.planner_for(target)
                return 1000*planner.risk() + CARDS[choice].ops
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
            if choice in CARDS:
                return CARDS[choice].ops if event == 'Aldrich_Ames_Remix' else -CARDS[choice].ops
            if choice == 'boycott':
                return (LOSS if responsible else -LOSS) if obs.defcon <= 2 else 0
        return 0.0
