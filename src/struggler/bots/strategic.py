"""Observation-only tactical policy with trainable linear evaluation weights.

Searches local influence investments and enumerates combat dice. Selected
public-information events are evaluated using an isolated engine; unknown
hands and the real engine RNG are never consulted. This is a bounded tactical
AI, not full-game minimax or a pretrained neural network.
"""
from __future__ import annotations

import copy
import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Sequence

from struggler.engine import Action, DecisionKind as K, Engine, Observation, Region, Side
from struggler.engine.board import Board
from struggler.engine.cards import load_cards
from struggler.engine.core import SCORING_CARD_REGION
from struggler.engine.player import Event
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
    control: float = 2.0
    battleground: float = 5.0
    progress: float = 2.8
    reserve: float = 0.35
    access: float = 0.65
    region: float = 1.3
    vp: float = 3.0
    military: float = 2.0
    event: float = 1.0
    ops: float = 2.0

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
    def __init__(self, weights: StrategicWeights | None = None):
        self.weights = weights or StrategicWeights()
        self.board = Board()
        self._events: dict[str, float] = {}

    def choose_action(self, observation: Observation, history: Sequence[Event]) -> Action:
        decision = observation.pending_decision
        if decision is None or not decision.options:
            raise ValueError('StrategicPlayer requires a pending decision with legal options')
        _sync_board(self.board, observation)
        self._events = {}
        return max(decision.options, key=lambda a: self.score(observation, a))

    def region_score(self, board: Board, region: Region, side: Side) -> float:
        try:
            net = board.score_region(region)
        except RuntimeError:  # Europe control has no numeric scoring value.
            net = 100 if board.region_tier(Side.US, region).value == 'control' else -100
        return net if side is Side.US else -net

    def country_value(self, board: Board, cid: str, side: Side) -> float:
        w = self.weights
        info = board.countries[cid]
        own, opp = (board.influence[cid][s.value] for s in (side, side.opponent))
        margin = own - opp
        importance = w.battleground if info.battleground else w.control
        value = importance * (1 if margin >= info.stability else -1 if margin <= -info.stability else 0)
        # Smooth progress prevents indifference among all multi-point captures.
        value += w.progress * importance * max(-1, min(1, margin / info.stability))
        value += w.reserve * importance * (min(2, max(0, margin-info.stability)) - min(2, max(0, -margin-info.stability)))
        # First footholds open nearby battlegrounds on a later action round.
        access = sum(1 / board.countries[n].stability for n in board.neighbors(cid)
                     if n in board.countries and board.countries[n].battleground)
        value += w.access * access * ((own > 0) - (opp > 0))
        return value

    def value(self, board: Board, side: Side) -> float:
        return sum(self.country_value(board, c, side) for c in board.countries) + self.weights.region * sum(self.region_score(board, r, side) for r in Region)

    def delta(self, obs: Observation, cid: str, own: int = 0, opp: int = 0) -> float:
        board, side = self.board, obs.side
        region = board.countries[cid].region
        urgency = 1.6 if any(SCORING_CARD_REGION.get(c) is region for c in obs.hand) else 1.0
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

    def public_engine(self, obs: Observation) -> Engine:
        # A new, idle sandbox, never a clone of the live game's hidden state.
        engine = Engine(seed=0)
        _sync_board(engine.board, obs)
        for name in ('defcon', 'vp', 'turn', 'action_round'):
            setattr(engine, name, getattr(obs, name))
        for name in ('space_race', 'military_ops', 'space_race_attempts', 'turn_effects', 'game_effects'):
            setattr(engine, name, copy.deepcopy(dict(getattr(obs, name))))
        engine.hands[obs.side.value] = list(obs.hand)
        engine.china_card_owner = obs.china_card_owner.value
        engine.china_card_available = obs.china_card_available
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
            return LOSS
        enemy = self.board.influence[cid][obs.side.opponent.value]
        mod = _coup_roll_modifier_estimate(obs, obs.side, info)
        gain = 0.0
        for roll in range(1, 7):
            margin = max(0, int(roll + ops - 2 * info.stability + mod))
            removed = min(enemy, margin)
            gain += self.delta(obs, cid, own=margin-removed, opp=-removed) / 6
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
        return total

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
        if obs.defcon <= 2 and ((cid == 'CIA_Created' and obs.side is Side.USSR) or (cid == 'Lone_Gunman' and obs.side is Side.US) or cid == 'Olympic_Games'):
            result = LOSS
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
            if event == 'Wargames':
                if choice != 'end_game':
                    return 0
                engine = self.public_engine(obs)
                engine._award_vp(obs.side.opponent, 6)
                if not engine.is_terminal:
                    engine._finish_game()
                return -LOSS if engine.winner is obs.side else LOSS
            if event == 'Blockade' and choice == 'refuse':
                return self.delta(obs, 'West_Germany', own=-self.board.influence['West_Germany'][obs.side.value])
            if event == 'Independent_Reds' and choice in self.board.countries:
                inf = self.board.influence[choice]
                return self.delta(obs, choice, own=max(0, inf['USSR']-inf['US']))
            if event == 'Summit_defcon':
                return LOSS if choice == 'lower' and obs.defcon <= 2 else 0
            if choice in CARDS:
                return CARDS[choice].ops if event == 'Aldrich_Ames_Remix' else -CARDS[choice].ops
            if choice == 'boycott':
                return LOSS
        return 0.0
