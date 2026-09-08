"""Small observation-only UCT search over our card plays until turn end.

Opponent responses are a fixed strategic policy, not an adversarial tree.
Each simulation samples a fresh hidden hand/deck; tree nodes use only our
observation. No live engine, private stack, or live RNG is accepted.
"""
from __future__ import annotations

import copy
import logging
import math
import random
import time
from dataclasses import dataclass, fields

from struggler.engine import DecisionKind as K, Side, Subregion
from struggler.engine.core import SCORING_CARD_REGION
from struggler.bots.public_cards import card_state
from struggler.bots.strategic import CARDS, StrategicPlayer

log = logging.getLogger('struggler.bots.mcts')


@dataclass(frozen=True)
class Move:
    card: str
    target: str | None = None


@dataclass
class Edge:
    visits: int = 0
    total: float = 0.

    @property
    def mean(self):
        return self.total / self.visits if self.visits else 0.


def information_key(obs):
    """Only information available to this seat; decision IDs are bookkeeping."""
    def freeze(value):
        if isinstance(value, dict):
            return tuple((k, freeze(v)) for k, v in sorted(value.items()))
        if isinstance(value, (tuple, list)):
            return tuple(map(freeze, value))
        return value
    d = obs.pending_decision
    decision = (d.actor, d.kind, tuple((a.kind, freeze(a.payload)) for a in d.options), freeze(d.context))
    return tuple(decision if f.name == 'pending_decision' else freeze(getattr(obs, f.name))
                 for f in fields(obs))


class MCTSPlayer:
    def __init__(self, weights=None, *, seed=0, simulations=24, max_steps=256,
                 time_limit=None, opponent_model=None):
        if simulations < 1 or max_steps < 1:
            raise ValueError('simulations and max_steps must be positive')
        if time_limit is not None and (not math.isfinite(time_limit) or time_limit <= 0):
            raise ValueError('time_limit must be finite and positive')
        self.policy = StrategicPlayer(weights, opponent_model=opponent_model)
        self.seed = seed
        self.simulations = simulations
        self.max_steps = max_steps
        self.time_limit = time_limit
        self.intent = None
        self.last_search = None

    def ranked(self, obs):
        ranked = self.policy.rank_actions(obs)
        safety = ranked[0][0][:2]
        return [a for key, a in ranked if key[:2] == safety]

    def sample_engine(self, obs, rng):
        """Reconstruct ONLY at a plain action-round card boundary.

        All cards must be accounted for by public counts. Infer optional-card
        inclusion from that inventory; reject unsupported/incomplete states.
        """
        if obs.phase != 'action_rounds' or obs.pending_decision.kind is not K.ACTION_ROUND_PLAY:
            raise ValueError('search requires an action-round card boundary')
        engine = self.policy.public_engine(obs)
        engine.phase = obs.phase
        engine.events_enabled = True
        known = set(obs.hand + obs.discard_pile + obs.removed_cards)
        for optional in (False, True):
            pool = [c.id for c in CARDS.values() if c.in_deck
                    and (optional or not c.optional)
                    and card_state(obs, c.id) == 'unseen']
            if (len(pool) == obs.opponent_hand_size + obs.draw_pile_size
                    and (optional or not any(CARDS[c].optional for c in known))):
                engine.include_optional = optional
                break
        else:
            raise ValueError('public card inventory does not match hand/deck counts')
        rng.shuffle(pool)
        engine.hands[obs.side.opponent.value] = pool[:obs.opponent_hand_size]
        engine.draw_pile = pool[obs.opponent_hand_size:]
        engine._rng.seed(rng.getrandbits(64))
        indices = [i for i in range(engine._total_action_rounds())
                   if i // 2 + 1 == obs.action_round
                   and engine._side_for_play_index(i) is obs.side]
        if len(indices) != 1:
            raise ValueError('ambiguous action-round cursor')
        engine._ars_played = indices[0] + 1
        engine._next_decision_id = obs.pending_decision.id + 1
        engine._push_action_round_play(obs.side)
        if engine.pending_decision.options != obs.pending_decision.options:
            raise ValueError('reconstructed card choices differ from observation')
        # Preserve public continuation metadata (e.g. CMC already offered).
        engine._decision_stack = [copy.deepcopy(obs.pending_decision)]
        return engine

    def moves(self, obs):
        safe = self.ranked(obs)
        cards = safe[:3] + [a for a in safe[3:] if CARDS[a.payload['card']].scoring]
        board = self.policy.board
        regions = {SCORING_CARD_REGION[c] for c in obs.hand if c in SCORING_CARD_REGION}
        sea = 'Southeast_Asia_Scoring' in obs.hand
        targets = [c for c, info in board.countries.items()
                   if info.battleground and board.control(c) is not obs.side
                   and board.is_reachable(obs.side, c)
                   and (info.region in regions or sea and Subregion.SOUTHEAST_ASIA in info.subregions)]
        def priority(cid):
            info = board.countries[cid]
            own, enemy = (board.influence[cid][s.value] for s in (obs.side, obs.side.opponent))
            points = max(1, info.stability + enemy - own)
            cost = points + max(0, enemy - own - info.stability + 1)
            return self.policy.delta(obs, cid, own=points) / cost
        targets.sort(key=priority, reverse=True)
        result = [Move(a.payload['card']) for a in cards]
        for a in cards:
            if not CARDS[a.payload['card']].scoring:
                result.extend(Move(a.payload['card'], c) for c in targets[:2])
        return result

    def continuation(self, obs, target=None):
        safe = self.ranked(obs)
        chosen = safe[0]
        if target is not None and self.policy.board.control(target) is not obs.side:
            d = obs.pending_decision
            for action in safe:
                if (d.kind is K.PLAY_MODE and action.payload.get('mode') == 'ops'
                    or d.kind is K.OPS_TYPE and action.payload.get('type') == 'influence'
                    or d.kind is K.PLACE_INFLUENCE and action.payload.get('country') == target):
                    chosen = action
                    break
        return chosen

    def advance_move(self, engine, move, side, turn, remaining):
        move_round = engine.action_round
        action = next(a for a in engine.legal_actions() if a.payload.get('card') == move.card)
        engine.step(action)
        steps = 1
        # Opponent decisions never receive our target or our sampled hand.
        while not engine.is_terminal and engine.turn == turn and steps < remaining:
            d = engine.pending_decision
            if d.actor is side and d.kind is K.ACTION_ROUND_PLAY:
                break
            if d.actor is Side.CHANCE:
                action = d.options[0]  # outcome drawn by the sandbox's independent RNG
            else:
                obs = engine.observe(d.actor)
                target = move.target if d.actor is side and engine.action_round == move_round else None
                action = self.continuation(obs, target)
            engine.step(action)
            steps += 1
        return steps

    def rollout(self, engine, turn, remaining):
        for _ in range(remaining):
            if engine.is_terminal or engine.turn != turn:
                break
            d = engine.pending_decision
            action = d.options[0] if d.actor is Side.CHANCE else self.continuation(engine.observe(d.actor))
            engine.step(action)

    def leaf_return(self, engine, side):
        """Banked VP PLUS future board potential. Terminal results dominate."""
        if engine.is_terminal:
            return 0. if engine.winner is None else 1. if engine.winner is side else -1.
        sign = 1 if side is Side.US else -1
        value = self.policy.weights.vp * sign * engine.vp + self.policy.value(engine.board, side)
        # Bounded heuristic leaves remain strictly below a certain win/loss.
        return max(-.99, min(.99, math.tanh(value / 100.)))

    def choose_action(self, obs, history):
        d = obs.pending_decision
        if d is None or not d.options:
            raise ValueError('MCTSPlayer requires legal options')
        if d.kind is not K.ACTION_ROUND_PLAY:
            target = self.intent[2] if self.intent and self.intent[:2] == (obs.turn, obs.action_round) else None
            return self.continuation(obs, target)
        self.intent = None
        self.last_search = None
        if not any(CARDS[c].scoring for c in obs.hand):
            return self.policy.choose_action(obs, history)
        start = time.monotonic()
        rng = random.Random(f'{self.seed}:{obs.side.value}:{obs.turn}:{obs.action_round}:{d.id}')
        try:
            first = self.sample_engine(obs, rng)
        except ValueError as exc:
            log.info('MCTS strategic fallback: %s', exc)
            return self.policy.choose_action(obs, history)
        tree = {}
        root_key = information_key(obs)
        completed = 0
        truncated = 0
        for simulation in range(self.simulations):
            if simulation and self.time_limit is not None and time.monotonic() - start >= self.time_limit:
                break
            engine = first if simulation == 0 else self.sample_engine(obs, rng)
            path = []
            steps = 0
            while not engine.is_terminal and engine.turn == obs.turn and steps < self.max_steps:
                current = engine.observe(obs.side)
                key = information_key(current)
                if key not in tree:
                    tree[key] = {m: Edge() for m in self.moves(current)}
                edges = tree[key]
                visits = sum(e.visits for e in edges.values())
                move = max(edges, key=lambda m: (float('inf') if not edges[m].visits else
                           edges[m].mean + math.sqrt(2 * math.log(max(1, visits)) / edges[m].visits)))
                edge = edges[move]
                expand = edge.visits == 0
                path.append(edge)
                steps += self.advance_move(engine, move, obs.side, obs.turn, self.max_steps - steps)
                if expand:
                    self.rollout(engine, obs.turn, self.max_steps - steps)
                    break
            reward = self.leaf_return(engine, obs.side)
            truncated += int(not engine.is_terminal and engine.turn == obs.turn)
            for edge in path:
                edge.visits += 1
                edge.total += reward
            completed += 1
        edges = tree[root_key]
        chosen = max((m for m in edges if edges[m].visits), key=lambda m: edges[m].mean)
        self.intent = (obs.turn, obs.action_round, chosen.target)
        self.last_search = dict(simulations=completed, nodes=len(tree), truncated=truncated,
                                seconds=time.monotonic()-start,
                                moves=[dict(card=m.card, target=m.target, visits=e.visits, value=e.mean)
                                       for m, e in edges.items()])
        log.info('MCTS T%d AR%d %s chose %s: %s', obs.turn, obs.action_round, obs.side.value,
                 chosen, self.last_search)
        return next(a for a in d.options if a.payload['card'] == chosen.card)
