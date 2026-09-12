"""A cheap stand-in for StrategicPlayer below the MCTS root.

The rollout world is a sampled sandbox where every card is in hand or in a
pile, so a suicide inside it costs the simulation a loss the tree can see.
What the full policy spends most of its time on -- the probabilistic
whole-hand survival search and re-ranking every Ops decision from scratch --
buys little there. This policy keeps the certain-loss guards and answers
the Ops decisions of one card play from a plan made once.

Observation-only, like its parent: it never receives a live engine.
"""
from __future__ import annotations

from collections.abc import Mapping


from struggler.engine import DecisionKind as K
from struggler.bots.strategic.defcon import DefconPlanner
from struggler.bots.strategic import (LOSS, StrategicPlayer, bonus_ops, coup_risks_defcon,
                                      in_bonus_region, sync_board)


def _freeze(value):
    # `Mapping`, not `dict`: an Action's payload is a read-only view
    # (`MappingProxyType`, so a Player cannot edit the engine's legal moves
    # through its own observation), and a proxy is not a dict subclass. This
    # said "frozen generically" while type-checking one concrete class, so
    # the proxy fell straight through and left an unhashable value in a
    # cache key.
    if isinstance(value, Mapping):
        return tuple((k, _freeze(v)) for k, v in sorted(value.items()))
    if isinstance(value, (tuple, list)):
        return tuple(map(_freeze, value))
    return value


def information_key(obs):
    """Only information available to this seat; decision IDs are bookkeeping.

    Influence is read in the board's fixed country order; the small
    effect maps and the decision are frozen generically.
    """
    d = obs.pending_decision
    decision = None if d is None else (
        d.actor, d.kind, tuple((a.kind, _freeze(a.payload)) for a in d.options), _freeze(d.context))
    return (obs.side, obs.phase, obs.defcon, obs.vp, obs.turn, obs.action_round,
            tuple(v['US'] for v in obs.influence.values()),
            tuple(v['USSR'] for v in obs.influence.values()),
            decision, tuple(obs.hand), obs.opponent_hand_size, obs.draw_pile_size,
            tuple(obs.discard_pile), tuple(obs.removed_cards), obs.china_card_owner,
            obs.china_card_available, _freeze(obs.space_race), _freeze(obs.space_race_attempts),
            _freeze(obs.military_ops), _freeze(obs.turn_effects), _freeze(obs.game_effects),
            tuple(obs.headline_pending))


class ImmediatePlanner(DefconPlanner):
    """Hand survival without lookahead: only what fires right now can lose.

    Everything after this play is left to the sandbox, which actually plays
    the sampled hands out; a card that would be forced later is caught
    when it is forced.
    """

    def _next(self, hand, rounds, defcon, pos, attempts, china, trapped=False):
        return 0.


class RolloutPolicy(StrategicPlayer):
    def __init__(self, weights=None, *, opponent_model=None, full_planner=False, serve_plans=True):
        super().__init__(weights, opponent_model=opponent_model)
        # Ablation switches: the parent's survival search everywhere, and
        # re-ranking every Ops decision instead of serving the plan.
        self.full_planner = full_planner
        self.serve_plans = serve_plans
        self.reset()

    def reset(self):
        """Forget rankings and plans; call at the start of every search."""
        self._rankings = {}
        self._plan = None
        self._placements = None
        self.hits = self.misses = self.served = 0

    def planner_for(self, obs):
        # A hand that can be forced into a loss needs the real search even
        # in a rollout, or every simulation from it suicides and the root
        # learns nothing. Elsewhere the immediate guard suffices.
        planner = DefconPlanner(obs, self.public_engine(obs), self.survival_prior, self.opponent_model)
        if self.full_planner or obs.defcon <= 3 and any(planner.hazardous(c) for c in planner.hand):
            return planner
        planner.__class__ = ImmediatePlanner
        return planner

    def coup_survival_risk(self, obs, country):
        # The full policy re-plans the whole hand at DEFCON-1 for every
        # target; here only the certain loss matters.
        if not coup_risks_defcon(obs, obs.side, self.board.countries[country]):
            return self._planner.discard_risk(None)
        return 1. if obs.defcon - 1 <= 1 else self._planner.discard_risk(None)

    # -- one plan per card play -------------------------------------------

    def rank_actions(self, observation):
        # Named `observation` to match `StrategicPlayer.rank_actions`: a
        # keyword call would otherwise work on the parent and fail here.
        # Found by ty's invalid-method-override.
        obs = observation
        d = obs.pending_decision
        if d is None or not d.options:
            raise ValueError('RolloutPolicy requires a pending decision with legal options')
        key = information_key(obs)
        cached = self._rankings.get(key)
        if cached is not None:
            self.hits += 1
            ranked, self._plan, self._placements = cached
            sync_board(self.board, obs)  # callers read the board after a hit too
            self._position.refresh(self.board)  # ... and the snapshot goes with it
            return ranked
        ranked = self._served(obs) if self.serve_plans else None
        if ranked is not None:
            self.served += 1
        else:
            self.misses += 1
            self._targets = {}
            ranked = super().rank_actions(obs)
            if d.kind is K.OPS_TYPE:
                chosen = ranked[0][1].payload['type']
                self._plan = (obs.side, obs.turn, obs.action_round, chosen, self._targets.get(chosen))
        self._rankings[key] = (ranked, self._plan, self._placements)
        return ranked

    def rank_for_target(self, obs, target):
        """A full ranking for a placement decision the search wants steered
        to `target`: the served plan (one planned country) cannot contain
        it, so re-rank as the parent would and drop the plan, since the
        rest of this spend must follow the target, not the plan."""
        d = obs.pending_decision
        if d is None or d.kind is not K.PLACE_INFLUENCE or not any(a.payload.get('country') == target for a in d.options):
            return self.rank_actions(obs)
        self._placements = None
        self.misses += 1
        self._targets = {}
        ranked = super().rank_actions(obs)
        self._rankings[information_key(obs)] = (ranked, self._plan, None)
        return ranked

    def _served(self, obs):
        """Answer a target or placement decision from the current plan."""
        d = obs.pending_decision
        stamp = (obs.side, obs.turn, obs.action_round)
        if d.kind in (K.COUP_TARGET, K.REALIGNMENT_TARGET):
            plan = self._plan
            self._plan = None
            if plan and plan[:3] == stamp and plan[3] == ('coup' if d.kind is K.COUP_TARGET else 'realignment'):
                action = next((a for a in d.options if a.payload['country'] == plan[4]), None)
                if action is not None:
                    return [((0, 0., 0.), action)]
            return None
        if d.kind is K.PLACE_INFLUENCE and not d.context.get('setup'):
            options = {a.payload['country']: a for a in d.options}
            if not (self._placements and self._placements[0] == stamp
                    and self._placements[1] and self._placements[1][0] in options):
                self._placements = (stamp, self._placement_plan(obs, options))
            queue = self._placements[1]
            if not queue:
                self._placements = None
                return None
            country, queue = queue[0], queue[1:]  # cached entries keep their own list
            self._placements = (stamp, queue)
            return [((0, 0., 0.), options[country])]
        return None

    def _placement_plan(self, obs, options):
        """Spend the Ops as the parent would, but commit each country's best
        point count at once instead of re-ranking after every point."""
        ctx = obs.pending_decision.context
        ops = int(ctx.get('ops_remaining', ctx.get('remaining', ctx.get('ops', 1))))
        if ctx.get('bonus'):
            ops = ctx['base'] - ctx['spent']
            # One extra point per bonus still intact whose region holds every
            # country this plan would place in.
            ops += sum(1 for outside, tag in zip(ctx['non_bonus'], ctx['bonus'])
                       if outside == 0
                       and all(in_bonus_region(self.board.countries[c], tag) for c in options))
        super().rank_actions(obs)  # sync the board and caches
        self._base_regions = {}
        board, side = self.board, obs.side
        original = {c: dict(board.influence[c]) for c in options}
        plan = []
        try:
            remaining = ops
            while remaining > 0:
                best = None
                for c in options:
                    if board.influence_cost(side, c) > remaining:
                        continue
                    value, points = self._investment(obs, c, remaining)
                    if best is None or value > best[0]:
                        best = (value, c, points)
                if best is None:
                    break
                _, c, points = best
                for _ in range(points):
                    cost = board.influence_cost(side, c)
                    if cost > remaining:
                        break
                    remaining -= cost
                    self._add_influence(c, side, 1)
                    plan.append(c)
                self._base_regions = {}  # the committed points moved the board
        finally:
            self._base_regions = None
            for c, inf in original.items():
                self._set_influence(c, inf['US'], inf['USSR'])
        return plan

    def score(self, obs, action):
        if action.kind is not K.OPS_TYPE:
            return super().score(obs, action)
        ctx, kind = obs.pending_decision.context, action.payload['type']
        if kind == 'influence':
            # No single target to remember: a placement spend is served by
            # `_placement_plan`, not by `_plan`. Let the parent price it, so
            # the two do not drift apart.
            return super().score(obs, action)
        ops = ctx['ops']
        board, side = self.board, obs.side
        engine = self.public_engine(obs)
        coup = kind == 'coup'
        candidates = ((self.coup(obs, c, ops + bonus_ops(i, ctx.get('bonus'))) if coup
                       else self.realign(obs, c) * ops, c)
                      for c, i in board.countries.items()
                      if engine._usable_coup_realign_target(side, c, for_coup=coup))
        value, target = max(candidates, default=(LOSS, None))
        self._targets[kind] = target
        return value
