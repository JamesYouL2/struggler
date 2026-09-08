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
from struggler.bots.public_cards import card_state
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
# Only deterministic, public-board events whose follow-ups are influence
# decisions. Do not add hand/deck events here without a belief-state model.
PUBLIC_EVENTS = frozenset('''Duck_and_Cover Fidel Romanian_Abdication Nasser
De_Gaulle_Leads_France Captured_Nazi_Scientist Nuclear_Test_Ban COMECON
Marshall_Plan Decolonization Suez_Crisis Truman_Doctrine Socialist_Governments
Muslim_Revolution Colonial_Rear_Guards Liberation_Theology OAS_Founded
Pershing_II_Deployed The_Reformer Solidarity Marine_Barracks_Bombing
Vietnam_Revolts US_Japan_Mutual_Defense_Pact East_European_Unrest'''.split())


@dataclass(frozen=True)
class StrategicWeights:
    # Country importance tiers: battlegrounds >> Southeast Asia
    # non-battlegrounds >> other non-battlegrounds. Battleground Ops score
    # domination and control (or deny them); the cheap SEA countries keep
    # Asia from being dominated and score later; the rest are worth little.
    control: float = 1.0
    battleground: float = 5.0
    southeast_asia: float = 2.0
    progress: float = 2.8
    reserve: float = 0.35
    access: float = 0.65
    region: float = 1.3
    vp: float = 3.0
    military: float = 2.0
    event: float = 1.0
    ops: float = 2.0
    # Regional urgency multipliers by where the region's scoring card is:
    # in our hand, live (draw pile or the opponent's hand: it can be played
    # against us any round), or dead (discarded until the reshuffle, removed,
    # or not yet in the deck), which is the 1.0 baseline.
    scoring_hand: float = 1.6
    scoring_live: float = 1.3
    # Influence value is not linear in principle: control is what scores,
    # uncontrolled influence only has option value, and over-protection
    # matters mostly where a cheap coup can undo it. progress_curve is the
    # exponent on (margin/stability); reserve_stability divides the reserve
    # term by stability ** that. The defaults stay at the linear/flat shape
    # because a one-action-lookahead evaluator needs the linear term to
    # stand in for option value: progress_curve=2 with reserve_stability=1
    # scored 0.33 +/- 0.09 against this shape on seeds 4000-4015 (see
    # docs/STRATEGIC_AI.md). Option value needs lookahead, not a curve.
    progress_curve: float = 1.0
    reserve_stability: float = 0.0
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
        self._planner = None
        if decision.kind in (K.ACTION_ROUND_PLAY, K.HEADLINE_PLAY, K.PLAY_MODE, K.EVENT_CHOICE,
                             K.QUAGMIRE_DISCARD, K.OPS_TYPE, K.COUP_TARGET):
            self._planner = self.planner_for(observation)
        ranked = sorted(((self.safety_key(observation, a), a) for a in decision.options),
                        key=lambda pair: pair[0], reverse=True)
        return ranked

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
            key = (region, tuple((v['US'], v['USSR']) for v in map(board.influence.__getitem__, board.countries_in(region))))
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
        own, opp = (board.influence[cid][s.value] for s in (side, side.opponent))
        margin = own - opp
        importance = self.importance(info)
        value = importance * (1 if margin >= info.stability else -1 if margin <= -info.stability else 0)
        # Progress toward control is convex: control is worth VP, a lone
        # point is not (it can only lead there), so a half-built country is
        # worth well under half of a controlled one.
        fraction = max(-1.0, min(1.0, margin / info.stability))
        value += w.progress * importance * math.copysign(abs(fraction) ** w.progress_curve, fraction)
        # Over-protection is worth little, and least where stability already
        # makes a coup expensive.
        guard = w.reserve * importance / info.stability ** w.reserve_stability
        value += guard * (min(2, max(0, margin-info.stability)) - min(2, max(0, -margin-info.stability)))
        # First footholds open nearby battlegrounds on a later action round.
        access = sum(1 / board.countries[n].stability for n in board.neighbors(cid)
                     if n in board.countries and board.countries[n].battleground)
        value += w.access * access * ((own > 0) - (opp > 0))
        return value

    def value(self, board: Board, side: Side) -> float:
        return sum(self.country_value(board, c, side) for c in board.countries) + self.weights.region * sum(self.region_score(board, r, side) for r in Region)

    def scoring_urgency(self, obs: Observation, cid: str) -> float:
        """How much scoring around country `cid` matters right now, from where
        the scoring cards that count it are: its region's card, plus Southeast
        Asia Scoring for the countries that card actually scores. A live card
        (unseen: draw pile or opponent's hand) can score at any moment, so the
        area must be played around; a dead one cannot score before the
        reshuffle, and a card whose period has not entered the deck is simply
        not in the game yet -- a static, public schedule."""
        info = self.board.countries[cid]
        cards = [c for c, r in SCORING_CARD_REGION.items() if r is info.region]
        if Subregion.SOUTHEAST_ASIA in info.subregions:
            cards.append('Southeast_Asia_Scoring')
        urgency = 1.0
        for card in cards:
            state = card_state(obs, card)
            if state == 'hand':
                return self.weights.scoring_hand
            if state == 'unseen':
                urgency = max(urgency, self.weights.scoring_live)
        return urgency

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
        region = board.countries[cid].region
        urgency = self.scoring_urgency(obs, cid)
        def local():
            return self.country_value(board, cid, side) + self.weights.region * urgency * self.region_score(board, region, side)
        before = local()
        original = dict(board.influence[cid])
        try:
            board.influence[cid][side.value] = max(0, original[side.value] + own)
            board.influence[cid][side.opponent.value] = max(0, original[side.opponent.value] + opp)
            return local() - before
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
        influence = copy.deepcopy(dict(obs.influence))
        influence[country] = dict(influence[country])
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
            setattr(engine, name, copy.deepcopy(dict(getattr(obs, name))))
        engine.hands[obs.side.value] = list(obs.hand)
        engine.china_card_owner = obs.china_card_owner.value
        engine.china_card_available = obs.china_card_available
        engine.discard_pile = list(obs.discard_pile)
        engine.removed_cards = list(obs.removed_cards)
        return engine

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
        for a in range(1, 7):
            for b in range(1, 7):
                margin = int(a-b+bonus)
                total += self.delta(obs, cid, own=min(0, margin), opp=-max(0, margin)) / 36
        return total * self.weights.coup_discount

    def event_value(self, obs: Observation, cid: str) -> float:
        if cid in self._events:
            return self._events[cid]
        card = CARDS[cid]
        sign = -1 if card.side.value == obs.side.opponent.value else 1
        if cid in PUBLIC_EVENTS:
            engine = self.public_engine(obs)
            before = self.value(engine.board, obs.side)
            engine._fire_event(obs.side, cid)
            policy = StrategicPlayer(self.weights)
            for _ in range(32):
                if engine.is_terminal or engine.pending_decision is None:
                    break
                d = engine.pending_decision
                if d.kind is not K.EVENT_INFLUENCE:
                    break
                engine.step(policy.choose_action(engine.observe(d.actor), []))
            if engine.is_terminal:
                result = -LOSS if engine.winner is obs.side else LOSS
            else:
                result = self.value(engine.board, obs.side) - before
                result += self.weights.vp * (engine.vp-obs.vp) * (1 if obs.side is Side.US else -1)
        elif cid in ('Containment', 'Brezhnev_Doctrine', 'Red_Scare_Purge'):
            rounds = max(1, (6 if obs.turn <= 3 else 7) - obs.action_round)
            result = sign * rounds * self.weights.ops
        else:
            # Explicit approximation for events beyond the public simulator.
            result = sign * card.ops * self.weights.ops * 0.8
        # Opponent-granted operations may coup a battleground at DEFCON 2.
        planner = self._planner or self.planner_for(obs)
        risk = planner.event_risk(cid)
        result = (1-risk)*result + risk*LOSS
        self._events[cid] = result
        return result

    def score(self, obs: Observation, action: Action) -> float:
        kind, p = action.kind, action.payload
        ctx = obs.pending_decision.context
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
            if kind is K.HEADLINE_PLAY:
                return event - 0.5 * card.ops
            ops = _effective_ops_estimate(card, obs, obs.side)
            value = self.weights.ops * ops + (min(0, event) if card.side.value == obs.side.opponent.value else 0)
            if card.side.value != obs.side.opponent.value:
                value = max(value, event)
            if cid == 'The_China_Card':
                value -= 4
            if cid == 'Five_Year_Plan' and obs.side is Side.USSR:
                # Prefer the controlled late-hand use when survival risks tie.
                value -= max(0, len(obs.hand)-3)
            # A dangerous card can be disposed of by space, but should not be
            # selected here unless that escape is currently available.
            engine = self.public_engine(obs)
            if engine._can_space_race(obs.side, card):
                value = max(value, self.weights.vp * _space_race_expected_vp(obs, obs.side) - 0.4 * ops)
            return value
        if kind is K.PLAY_MODE:
            cid = ctx['card']
            event = self.event_value(obs, cid)
            ops = _effective_ops_estimate(CARDS[cid], obs, obs.side)
            if p['mode'] == 'event':
                return event * self.weights.event
            if p['mode'] == 'space_race':
                return self.weights.vp * _space_race_expected_vp(obs, obs.side) + 1 - 0.4 * ops
            return self.weights.ops * ops + (min(0, event) if p['mode'] != 'un_intervention' and CARDS[cid].side.value == obs.side.opponent.value else 0)
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
