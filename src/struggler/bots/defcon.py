"""Cheap, observation-only hand survival search; probabilities are conditional priors.

Board/eligibility is frozen, except DEFCON and Space Race. Unknown draws are
approximated explicitly, never read from an engine's hidden state. This is a
risk feature and policy guard, not a calibrated prediction of match outcomes.
"""
from dataclasses import dataclass
from functools import lru_cache
import logging
import math

from struggler.engine import Side, Region
from struggler.engine.cards import load_cards
from struggler.engine.rules import RULES

log = logging.getLogger('struggler.bots.defcon')

CARDS = load_cards()
CHINA = 'The_China_Card'
ASK = 'Ask_Not_What_Your_Country_Can_Do_For_You'
RAISERS = {'How_I_Learned_to_Stop_Worrying': 5, 'Salt_Negotiations': 2,
           'Nuclear_Test_Ban': 2, 'ABM_Treaty': 1}
REDUCERS = {'Duck_and_Cover', 'We_Will_Bury_You', 'Soviets_Shoot_Down_KAL_007'}


@dataclass(frozen=True)
class SurvivalPrior:
    opponent_lowers_defcon: float = .75
    unknown_chain_loss: float = .25
    replacement_hazard: float = .15
    max_states: int = 3000

    def __post_init__(self):
        for p in (self.opponent_lowers_defcon, self.unknown_chain_loss, self.replacement_hazard):
            if not math.isfinite(p) or not 0 <= p <= 1:
                raise ValueError('survival probabilities must be finite and in [0, 1]')
        if self.max_states < 1:
            raise ValueError('max_states must be positive')


class DefconPlanner:
    def __init__(self, obs, engine, prior=None):
        self.obs, self.engine = obs, engine
        self.prior = prior or SurvivalPrior()
        self.side = obs.side
        self.hand = tuple(sorted(obs.hand))
        self.rounds = max(0, (6 if obs.turn <= 3 else 7) - max(1, obs.action_round) + 1)
        if obs.phase == 'headline':
            self.rounds += 1  # headline consumes a card, but no action round
        self.china = obs.china_card_owner is obs.side and obs.china_card_available
        self.nodes = 0
        self.truncated = False
        self.solve = lru_cache(maxsize=None)(self._solve)
        self._hazard = lru_cache(maxsize=None)(self._event_risk)
        log.debug(
            "planner %s T%d AR%d %s: DEFCON %d, rounds_left=%d, hand=%s, china=%s, space=%d/%d attempts",
            self.side.value, obs.turn, obs.action_round, obs.phase, obs.defcon, self.rounds,
            list(self.hand), self.china, obs.space_race[self.side.value],
            obs.space_race_attempts[self.side.value],
        )

    def opponent_event(self, cid):
        return cid in CARDS and CARDS[cid].side.value == self.side.opponent.value

    def coup_threat(self, actor, defcon, countries=None, ignore_defcon=False):
        if actor is self.side or defcon > 2:
            return False
        # CMC makes the coup actor lose instead; Nuclear Subs prevents US drops.
        if self.obs.turn_effects.get('cuban_missile_crisis') == actor.value:
            return False
        if actor is Side.US and self.obs.turn_effects.get('nuclear_subs'):
            return False
        old = self.engine.defcon
        self.engine.defcon = defcon
        try:
            return any(info.battleground and (countries is None or cid in countries)
                       and self.engine._usable_coup_realign_target(actor, cid, for_coup=True,
                                                                  ignore_defcon=ignore_defcon)
                       for cid, info in self.engine.board.countries.items())
        finally:
            self.engine.defcon = old

    def event_risk(self, cid, defcon=None, hand=None):
        return self._hazard(cid, self.obs.defcon if defcon is None else defcon,
                            self.hand if hand is None else tuple(hand), 0)

    def _event_risk(self, cid, defcon, hand, depth):
        if depth > 3:
            return self.prior.unknown_chain_loss
        if cid in REDUCERS:
            return float(defcon <= 2)
        if cid == 'Olympic_Games':
            return float(defcon <= 2)
        if cid == 'Summit' and defcon <= 2:
            a = self.engine._regions_dominated(self.side)
            b = self.engine._regions_dominated(self.side.opponent)
            return sum(y+b > x+a for x in range(1, 7) for y in range(1, 7))/36
        actor = {'CIA_Created': Side.US, 'Lone_Gunman': Side.USSR,
                 'Grain_Sales_to_Soviets': Side.US, 'Tear_Down_This_Wall': Side.US,
                 'Ortega_Elected_in_Nicaragua': Side.USSR}.get(cid)
        if actor:
            countries = None
            if cid == 'Tear_Down_This_Wall':
                countries = [c for c, i in self.engine.board.countries.items() if i.region is Region.EUROPE]
            if cid == 'Ortega_Elected_in_Nicaragua':
                countries = self.engine.board.neighbors('Nicaragua')
            risk = float(self.coup_threat(actor, defcon, countries, countries is not None))
            if cid == 'Grain_Sales_to_Soviets' and self.side is Side.USSR and hand:
                nested = []
                for c in hand:
                    # US can choose a neutral DEFCON setter on USSR's action.
                    nested.append(1.0 if c == 'How_I_Learned_to_Stop_Worrying' else
                                  self._hazard(c, defcon, tuple(x for x in hand if x != c), depth+1))
                risk = max(risk, sum(nested)/len(nested))
            return risk
        if cid == 'Five_Year_Plan':
            if self.side is Side.US:
                return self.prior.unknown_chain_loss if self.obs.opponent_hand_size else 0.
            remaining = tuple(c for c in hand if c != cid)
            return sum(self._hazard(c, defcon, tuple(x for x in remaining if x != c), depth+1)
                       for c in remaining if CARDS.get(c) and CARDS[c].side.value == 'US'
                       and not CARDS[c].scoring)/max(1, len(remaining))
        if cid == 'Star_Wars' and self.side is Side.USSR and self.obs.space_race['US'] > self.obs.space_race['USSR']:
            return max((1. if c == 'How_I_Learned_to_Stop_Worrying' else
                        self._hazard(c, defcon, hand, depth+1)
                        for c in self.obs.discard_pile if not CARDS[c].scoring and c != cid), default=0.)
        if cid == 'Missile_Envy' and self.obs.opponent_hand_size:
            return self.prior.unknown_chain_loss
        return 0.

    def space_ok(self, cid, pos, attempts):
        return (cid in CARDS and cid != CHINA and not CARDS[cid].scoring and
                pos < RULES['space_race_max_box'] and attempts < self.engine._space_attempts_allowed(self.side) and
                self.engine._effective_ops(self.side, CARDS[cid]) >= RULES['space_race_boxes'][str(pos+1)]['ops'])

    def modes(self, cid, hand, pos, attempts):
        if cid == '@replacement':
            return ('ops',)
        if CARDS[cid].scoring:
            return ('event',)
        modes = ['ops']
        if cid in RAISERS or cid == ASK and self.side is Side.US or cid == 'Five_Year_Plan':
            modes.append('event')
        if self.space_ok(cid, pos, attempts):
            modes.append('space_race')
        if self.opponent_event(cid) and 'UN_Intervention' in hand:
            modes.append('un_intervention')
        return tuple(modes)

    def _next(self, hand, rounds, defcon, pos, attempts, china):
        if rounds <= 0:
            return 0.
        p = self.prior.opponent_lowers_defcon if defcon > 2 else 0.
        return ((1-p)*self.solve(hand, rounds, defcon, pos, attempts, china) +
                p*self.solve(hand, rounds, max(2, defcon-1), pos, attempts, china))

    def transition(self, cid, mode, hand, rounds, defcon, pos, attempts, china):
        remaining = list(hand)
        if cid == CHINA:
            china = False
        elif cid in remaining:
            remaining.remove(cid)
        remaining = tuple(remaining)
        def onward(h=remaining, d=defcon, p=pos, a=attempts):
            return self._next(h, rounds-1, d, p, a, china)
        if mode == 'space_race':
            # Disposal is certain even when the roll fails. Advancement can change eligibility.
            probability = RULES['space_race_boxes'][str(pos+1)]['roll_max']/6
            return probability*onward(p=pos+1, a=attempts+1)+(1-probability)*onward(a=attempts+1)
        if mode == 'un_intervention':
            return onward(tuple(c for c in remaining if c != 'UN_Intervention'))
        fires = mode == 'event' or self.opponent_event(cid)
        if not fires:
            return onward()
        if cid in RAISERS:
            d = 5 if cid == 'How_I_Learned_to_Stop_Worrying' else min(5, defcon+RAISERS[cid])
            if cid == 'Salt_Negotiations':
                safe = next((c for c in self.obs.discard_pile if not CARDS[c].scoring
                             and (not self.opponent_event(c) or self.event_risk(c, 2, remaining) == 0)), None)
                if safe:
                    return min(onward(d=d), onward(tuple(sorted(remaining+(safe,))), d=d))
            return onward(d=d)
        if cid == ASK and self.side is Side.US:
            dangerous = [c for c in remaining if self.opponent_event(c) and self.event_risk(c, 2, remaining) > 0]
            replacement = tuple(sorted([c for c in remaining if c not in dangerous]+['@replacement']*len(dangerous)))
            # Replacements are unknown; explicit pessimistic penalty, not a sampled hidden draw.
            risk = 1-(1-self.prior.replacement_hazard)**len(dangerous)
            return risk+(1-risk)*onward(replacement)
        if cid == 'Aldrich_Ames_Remix' and self.side is Side.US and remaining:
            # The opponent chooses the worst continuation for us.
            return max(onward(tuple(c for c in remaining if c != discarded)) for discarded in remaining)
        if cid == 'Five_Year_Plan' and self.side is Side.USSR and remaining:
            values = []
            for c in remaining:
                rest = list(remaining);rest.remove(c)
                risk = self.event_risk(c, defcon, rest) if c in CARDS and CARDS[c].side.value == 'US' and not CARDS[c].scoring else 0.
                d = defcon-1 if c in REDUCERS else defcon
                values.append(risk+(1-risk)*onward(tuple(rest), max(2,d)))
            return sum(values)/len(values)
        risk = self.event_risk(cid, defcon, remaining)
        return risk+(1-risk)*onward(d=max(2,defcon-1) if cid in REDUCERS else defcon)

    def _solve(self, hand, rounds, defcon, pos, attempts, china):
        if rounds <= 0 or not hand:
            return 0.
        self.nodes += 1
        if self.nodes > self.prior.max_states:
            if not self.truncated:
                log.warning("planner %s: search budget of %d states exhausted; using conservative fallback",
                            self.side.value, self.prior.max_states)
            self.truncated = True
            # Conservative fallback: any forced hazardous card is treated as loss.
            safe = sum(not self.opponent_event(c) or self.event_risk(c, 2, hand) == 0 for c in hand)
            return float(safe + int(china) < min(rounds, len(hand)+int(china)))
        scoring = [c for c in hand if c in CARDS and CARDS[c].scoring]
        candidates = scoring if len(scoring) >= rounds else list(hand)+([CHINA] if china else [])
        # Exact special scoring-discard escape implemented by the engine.
        if self.side is Side.USSR and 'Five_Year_Plan' in hand and len(scoring) == len(hand)-1:
            candidates = list(dict.fromkeys(candidates+['Five_Year_Plan']))
        best = 1.
        for cid in candidates:
            for mode in self.modes(cid, hand, pos, attempts):
                if len(scoring) >= rounds and cid == 'Five_Year_Plan' and mode not in ('ops','event'):
                    continue
                risk = self.transition(cid, mode, hand, rounds, defcon, pos, attempts, china)
                best = min(best, risk)
                if best == 0:
                    return 0.
        return best

    def risk(self, cid=None, mode=None):
        state = (self.hand, self.rounds, self.obs.defcon, self.obs.space_race[self.side.value],
                 self.obs.space_race_attempts[self.side.value], self.china)
        if cid is None:
            value = self.solve(*state)
            log.debug("planner %s: whole-hand turn-loss risk=%.3f (%d states searched)",
                      self.side.value, value, self.nodes)
            return value
        modes = (mode,) if mode else self.modes(cid, self.hand, state[3], state[4])
        per_mode = {m: self.transition(cid, m, *state) for m in modes}
        log.debug("planner %s: %s risk by mode %s", self.side.value, cid,
                  {m: round(v, 3) for m, v in per_mode.items()})
        return min(per_mode.values())

    def features(self):
        risk = self.risk()
        hazards = [c for c in self.hand if self.opponent_event(c) and self.event_risk(c, 2) > 0]
        if hazards:
            log.info("planner %s T%d AR%d: hazardous cards in hand %s (DEFCON %d, turn-loss risk %.3f)",
                     self.side.value, self.obs.turn, self.obs.action_round, hazards, self.obs.defcon, risk)
        return {'turn_loss_risk': risk,
                'hazardous_cards': sum(self.opponent_event(c) and self.event_risk(c, 2) > 0 for c in self.hand),
                'space_attempts_left': max(0, self.engine._space_attempts_allowed(self.side)-self.obs.space_race_attempts[self.side.value]),
                'china_available': int(self.china), 'rounds_left': self.rounds,
                'search_truncated': self.truncated}
