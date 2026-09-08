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
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Sequence

from struggler.engine import Action, DecisionKind as K, Engine, Observation, Region, Side, Subregion
from struggler.engine.board import Board
from struggler.engine.cards import load_cards
from struggler.engine.core import SANDBOX_LOG, SCORING_CARD_REGION
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
# Duration effects priced by the Ops they add or take away.
OPS_MODIFIER_EVENTS = ('Containment', 'Brezhnev_Doctrine', 'Red_Scare_Purge')
# Events that simply hand their side Operations (with a reveal we do not price).
OPS_GRANTS = {'CIA_Created': 1, 'Lone_Gunman': 1}
# For the docs and tests: what the sandbox is asked to simulate.
PUBLIC_EVENTS = frozenset(c.id for c in CARDS.values()
                          if not c.scoring and c.id not in HIDDEN_INFO_EVENTS
                          and c.id not in OPS_MODIFIER_EVENTS)


@dataclass(frozen=True)
class StrategicWeights:
    """Every weight is in VP. A country is worth its tier's VP per scoring
    of its region, times the region's expected remaining scorings from the
    static card schedule (bots/public_cards.scoring_schedule, discounted
    per turn away), so the exchange rate between a battleground and a VP
    depends on the turn and on where the scoring cards are. The exact
    region score, scaled the same way, carries the domination/control
    swings; the tiers add what a single country contributes beyond it."""
    # VP per scoring: battlegrounds >> Southeast Asia non-battlegrounds >>
    # other non-battlegrounds (which only count toward domination).
    control: float = 0.3
    battleground: float = 1.0
    southeast_asia: float = 0.6
    # A stake (presence without control) is the control value times the
    # odds of converting it: conversion ** (Ops still needed). Reach into a
    # battleground we could not otherwise place in is worth `access` of
    # that same option.
    conversion: float = 0.65
    progress: float = 1.0
    access: float = 0.5
    # Over-protection: a point beyond control, worth little, and least
    # where stability already makes a coup expensive (reserve_stability
    # divides by stability ** that).
    reserve: float = 0.1
    reserve_stability: float = 0.0
    region: float = 1.0
    vp: float = 1.0
    military: float = 1.0  # a Military Ops shortfall is paid in VP
    event: float = 1.0
    ops: float = 1.5  # fallback VP per Op where the board cannot price them
    # Expected future scorings: scoring_discount ** (turns away), summed
    # over the region's scoring cards' expected plays. Holding the card
    # multiplies this cycle's term by scoring_hand: we pick the moment.
    scoring_hand: float = 1.2
    scoring_discount: float = 0.8
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
        return cls(**data['weights'])

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
        self._region_cache = {}
        self._base_regions = {}
        self._country_cache = {}
        self._ops_values = {}
        self._relocation_gain = None
        self._space_card = None
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
            self._base_regions = None  # callers may move the board after ranking

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
        # Worth per scoring, times what the region will still score (a
        # battleground in an unscored Early War region >> one in a region
        # just scored, or one whose scoring is turns away). Absent an
        # observation (a bare leaf evaluation) the schedule weight is 1.
        importance = self.importance(info) * self._schedule(cid)
        stability = info.stability
        if margin >= stability:
            value = importance
        elif margin <= -stability:
            value = -importance
        elif margin > 0:
            value = w.progress * importance * w.conversion ** (stability - margin)
        elif margin < 0:
            value = -w.progress * importance * w.conversion ** (stability + margin)
        else:
            value = 0.
        guard = w.reserve * importance / stability ** w.reserve_stability
        value += guard * (min(2, max(0, margin-stability)) - min(2, max(0, -margin-stability)))
        # First footholds open nearby battlegrounds on a later action round:
        # a stake is worth a share of the option on each uncontrolled
        # battleground it alone lets us reach. Nothing for ground we already
        # reach (a fourth point in Eastern Europe opens nothing).
        value += w.access * (self._access(board, cid, side) * (own > 0)
                             - self._access(board, cid, side.opponent) * (opp > 0))
        if cache is not None:
            cache[key] = value
        return value

    def _schedule(self, cid: str) -> float:
        weights = self._scoring_weights
        if weights is None:
            return 1.
        cached = weights.get(cid)
        return cached if cached is not None else self.scoring_weight(self._obs, cid)

    def _access(self, board: Board, cid: str, side: Side) -> float:
        cache = getattr(self, '_access_cache', None)
        key = (board, cid, side)
        if cache is not None and key in cache:
            return cache[key]
        inf, key_side = board.influence, side.value
        w = self.weights
        total = 0.
        for n in board.neighbors(cid):
            info = board.countries.get(n)
            if info is None or not info.battleground or board.control(n) is side:
                continue
            if n in board._adjacency.get(key_side, ()) or inf[n][key_side] > 0:
                continue  # reachable anyway
            if any(inf[m][key_side] > 0 for m in board.neighbors(n) if m != cid and m in inf):
                continue  # reachable through another holding
            own, opp = inf[n][key_side], inf[n][side.opponent.value]
            cost = info.stability + opp - own
            if board.control(n) is side.opponent:
                cost += opp - own - info.stability + 1  # doubled until control breaks
            total += self.importance(info) * self._schedule(n) * w.conversion ** max(1, cost)
        if cache is not None:
            cache[key] = total
        return total

    def value(self, board: Board, side: Side) -> float:
        return (sum(self.country_value(board, c, side) for c in board.countries)
                + self.weights.region * sum(self.region_weight(r) * self.region_score(board, r, side) for r in Region))

    def region_weight(self, region: Region) -> float:
        """The region's expected remaining scorings (1 without an observation)."""
        if self._obs is None:
            return 1.
        card = next(c for c, r in SCORING_CARD_REGION.items() if r is region)
        w = self.weights
        return sum(w.scoring_discount ** t * (w.scoring_hand if t == 0 and card in self._obs.hand else 1.)
                   for t in scoring_schedule(self._obs, card))

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
        """The country's tier: battleground, Southeast Asia non-battleground,
        or other non-battleground."""
        if info.battleground:
            return self.weights.battleground
        if Subregion.SOUTHEAST_ASIA in info.subregions:
            return self.weights.southeast_asia
        return self.weights.control

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
        before = self.country_value(board, cid, side) + self.weights.region * urgency * region_before
        controller = board.control(cid)
        original = dict(board.influence[cid])
        try:
            board.influence[cid][side.value] = max(0, original[side.value] + own)
            board.influence[cid][side.opponent.value] = max(0, original[side.opponent.value] + opp)
            # Partial influence and overprotection cannot change regional VP.
            region_after = (region_before if board.control(cid) is controller else
                            self.region_score(board, region, side))
            return self.country_value(board, cid, side) + self.weights.region * urgency * region_after - before
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

    def ops_value(self, obs: Observation, ops: int) -> float:
        """What `ops` Operations are worth here: the best influence spend
        (a greedy plan, so the value is concave in Ops: the fourth point
        buys less than the first) or the best coup on this board, not a
        flat rate. Puts Ops, events and VP on one scale, so a 4-Ops card on
        turn 1 outranks 3 VP and a late 1-Op card does not."""
        if ops <= 0:
            return 0.
        cached = self._ops_values.get((obs.side, ops))
        if cached is not None:
            return cached
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
        finally:
            for c, inf in original.items():
                board.influence[c].update(inf)
            self._base_regions = {} if self._base_regions is not None else None
        engine = self.public_engine(obs)
        best_coup = max((self.coup(obs, c, ops) for c in board.countries
                         if engine._usable_coup_realign_target(side, c, for_coup=True)), default=LOSS)
        value = max(total, best_coup, 0.)
        self._ops_values[(obs.side, ops)] = value
        return value

    def opponent_ops_value(self, obs: Observation, ops: int) -> float:
        """What `ops` Operations are worth to the opponent on this board."""
        other = replace(obs, side=obs.side.opponent, hand=())
        base = self._base_regions
        self._base_regions = {} if base is not None else None
        try:
            return self.ops_value(other, ops)
        finally:
            self._base_regions = {} if base is not None else None

    def marginal_op(self, obs: Observation, side: Side) -> float:
        """The value of one more Op on a typical card for `side`."""
        f = self.ops_value if side is obs.side else self.opponent_ops_value
        return max(0., (f(obs, 4) - f(obs, 1)) / 3)  # smoothed over a card's range

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
            gain -= self.weights.vp
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
            regions = {r: self.region_weight(r) * self.region_score(engine.board, r, obs.side) for r in Region}
            before = sum(countries.values()) + self.weights.region * sum(regions.values())
            self._event_basis = (basis_key, countries, regions, before)
        _, countries, regions, before = self._event_basis
        engine._fire_event(obs.side, cid)
        policy = self._event_helper()
        for _ in range(64):
            if engine.is_terminal or engine.pending_decision is None:
                break
            d = engine.pending_decision
            if d.actor is Side.CHANCE:
                engine.step(d.options[len(d.options) // 2])  # the middle roll
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
        after += self.weights.region * sum(self.region_weight(r) * self.region_score(engine.board, r, obs.side)
                                            if r in changed_regions else v for r, v in regions.items())
        result = after - before
        return result + self.weights.vp * (engine.vp-obs.vp) * (1 if obs.side is Side.US else -1)

    def event_value(self, obs: Observation, cid: str) -> float:
        if cid in self._events:
            return self._events[cid]
        card = CARDS[cid]
        sign = -1 if card.side.value == obs.side.opponent.value else 1
        result = None
        if cid in OPS_MODIFIER_EVENTS:
            # A point of Ops on every card for the rest of the turn, for
            # the side it helps (Containment: US; Brezhnev: USSR; Red
            # Scare/Purge: the opponent loses one), at this board's
            # marginal Op value for that side.
            rounds = max(1, (6 if obs.turn <= 3 else 7) - obs.action_round)
            helped = {'Containment': Side.US, 'Brezhnev_Doctrine': Side.USSR}.get(cid, obs.side)
            result = rounds * self.marginal_op(obs, helped) * (1 if helped is obs.side else -1)
        elif cid in OPS_GRANTS:
            # The event hands its side that many Ops (CIA Created, Lone
            # Gunman): worth what they buy on this board.
            granted = CARDS[cid].side.value
            mine = granted == obs.side.value
            value = self.ops_value(obs, OPS_GRANTS[cid]) if mine else self.opponent_ops_value(obs, OPS_GRANTS[cid])
            result = value if mine else -value
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

    def card_play_value(self, obs: Observation, cid: str, ops: int, event: float) -> float:
        """A card played from hand: its Ops (the opponent's event fires too)
        or, for our own and neutral cards, its event if that is better."""
        opponents = CARDS[cid].side.value == obs.side.opponent.value
        value = self.ops_value(obs, ops) + (min(0, event) if opponents else 0)
        return value if opponents else max(value, event)

    def space_value(self, obs: Observation, ops: int) -> float:
        return self.weights.vp * _space_race_expected_vp(obs, obs.side) - 0.4 * self.ops_value(obs, ops)

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
                return net * self.weights.vp + (0 if kind is K.HEADLINE_PLAY else 2 * obs.action_round)
            event = self.event_value(obs, cid)
            ops = _effective_ops_estimate(card, obs, obs.side)
            if kind is K.HEADLINE_PLAY:
                # Headlining a card fires its event now instead of using
                # the card in an action round; the card it displaces gets
                # that action round instead. So a candidate is worth its
                # event minus its own action-round use.
                return event - self.card_play_value(obs, cid, ops, event)
            value = self.card_play_value(obs, cid, ops, event)
            if cid == 'The_China_Card':
                value -= 4
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
                return event * self.weights.event
            if p['mode'] == 'space_race':
                return self.space_value(obs, ops) + 1
            return self.ops_value(obs, ops) + (min(0, event) if p['mode'] != 'un_intervention' and CARDS[cid].side.value == obs.side.opponent.value else 0)
        if kind is K.WAR_TARGET:
            cid = p['country']
            penalty = sum(self.board.control(n) is obs.side.opponent for n in self.board.neighbors(cid))
            penalty += int(ctx.get('count_target_control', True) and self.board.control(cid) is obs.side.opponent)
            probability = max(0, min(6, 7 - ctx['win_from'] - penalty)) / 6
            enemy = self.board.influence[cid][obs.side.opponent.value]
            return probability * (self.delta(obs, cid, own=enemy, opp=-enemy) + self.weights.vp * ctx['vp'])
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
                # never into US control).
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
