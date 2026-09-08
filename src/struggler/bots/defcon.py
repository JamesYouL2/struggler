"""Cheap, observation-only hand survival search; probabilities are conditional priors.

Board/eligibility is frozen, except DEFCON and Space Race. Unknown draws are
approximated explicitly, never read from an engine's hidden state. This is a
risk feature and policy guard, not a calibrated prediction of match outcomes.

The search state is (hand, rounds left, DEFCON, space box, space attempts,
China Card, trapped). "Trapped" is Quagmire/Bear Trap: each of our rounds
then discards a 2+ Ops card without firing its event and rolls to escape.
Between our rounds the opponent may lower DEFCON or attack our hand
(Aldrich Ames, Terrorism, Grain Sales, Missile Envy); both are priors, and
the hand attack is adversarial: it takes whichever safe card we could least
afford to lose.
"""
from dataclasses import dataclass, replace
from functools import lru_cache
import logging
import math

from struggler.engine import DecisionKind as K, Side, Region
from struggler.engine.cards import load_cards
from struggler.engine.rules import RULES

log = logging.getLogger('struggler.bots.defcon')

CARDS = load_cards()
CHINA = 'The_China_Card'
ASK = 'Ask_Not_What_Your_Country_Can_Do_For_You'
RAISERS = {'How_I_Learned_to_Stop_Worrying': 5, 'Salt_Negotiations': 2,
           'Nuclear_Test_Ban': 2, 'ABM_Treaty': 1}
REDUCERS = {'Duck_and_Cover', 'We_Will_Bury_You', 'Soviets_Shoot_Down_KAL_007'}
# Events that make the US discard a printed-3+-Ops card or take a board hit.
# The discard never fires an event, so it is also an exit for a hazardous card.
US_PAYABLE_DISCARDS = {'Blockade', 'Latin_American_Debt_Crisis'}
# Card -> the side its event traps (mirrors Engine._TRAP_KEYS).
TRAPS = {'Bear_Trap': Side.USSR, 'Quagmire': Side.US}
TRAP_KEYS = {'bear_trap': Side.USSR, 'quagmire': Side.US}
# Decisions made while our own card play is still resolving: the round is
# already spent, so the hand that matters is what remains for later rounds.
PLAY_KINDS = (K.ACTION_ROUND_PLAY, K.HEADLINE_PLAY, K.PLAY_MODE)


@dataclass(frozen=True)
class SurvivalPrior:
    opponent_lowers_defcon: float = .75
    opponent_hand_attack: float = .10
    unknown_chain_loss: float = .25
    replacement_hazard: float = .15
    max_states: int = 20000

    def __post_init__(self):
        for p in (self.opponent_lowers_defcon, self.opponent_hand_attack,
                  self.unknown_chain_loss, self.replacement_hazard):
            if not math.isfinite(p) or not 0 <= p <= 1:
                raise ValueError('survival probabilities must be finite and in [0, 1]')
        if self.max_states < 1:
            raise ValueError('max_states must be positive')


class DefconPlanner:
    def __init__(self, obs, engine, prior=None, opponent_model=None):
        self.obs, self.engine = obs, engine
        self.prior = prior or SurvivalPrior()
        if opponent_model is not None:
            # Learned from recorded games (bots/opponent_model.py); the flat
            # defaults remain the fallback when no checkpoint is configured.
            learned = opponent_model.priors(obs)
            self.prior = replace(self.prior, opponent_hand_attack=learned['hand_attack'],
                                 opponent_lowers_defcon=learned['defcon_drop'])
        self.side = obs.side
        self.hand = tuple(sorted(obs.hand))
        self.rounds = max(0, (6 if obs.turn <= 3 else 7) - max(1, obs.action_round) + 1)
        self.mid_play = self._mid_play(obs)
        if obs.phase == 'headline' and not self.mid_play:
            self.rounds += 1  # headline consumes a card, but no action round
        if self.mid_play and obs.phase != 'headline':
            self.rounds = max(0, self.rounds - 1)  # this round's card is already out
        # Our own revealed headline still waiting to resolve: a forced event
        # that fires before any of our action rounds.
        self.pending_headline = next((c for s, c in obs.headline_pending if s == self.side.value), None)
        if self.pending_headline and obs.phase == 'headline' and not self.mid_play:
            self.rounds -= 1  # that card already left the hand
        self.china = obs.china_card_owner is obs.side and obs.china_card_available
        self.trapped = any(obs.game_effects.get(k) and s is self.side for k, s in TRAP_KEYS.items())
        self.nodes = 0
        self.truncated = False
        self.solve = lru_cache(maxsize=None)(self._solve)
        self._hazard = lru_cache(maxsize=None)(self._event_risk)
        log.debug(
            "planner %s T%d AR%d %s: DEFCON %d, rounds_left=%d, hand=%s, china=%s, trapped=%s, "
            "mid_play=%s, space=%d/%d attempts",
            self.side.value, obs.turn, obs.action_round, obs.phase, obs.defcon, self.rounds,
            list(self.hand), self.china, self.trapped, self.mid_play,
            obs.space_race[self.side.value], obs.space_race_attempts[self.side.value],
        )
        log.debug("planner %s priors: hand_attack=%.3f defcon_drop=%.3f%s", self.side.value,
                  self.prior.opponent_hand_attack, self.prior.opponent_lowers_defcon,
                  " (learned)" if opponent_model is not None else "")

    def _mid_play(self, obs):
        decision = obs.pending_decision
        if decision is None or decision.kind in PLAY_KINDS:
            return False
        if decision.kind is K.QUAGMIRE_DISCARD:
            return decision.actor is self.side
        responsible = decision.context.get('phasing_player')
        if responsible is None:
            responsible = decision.actor.value if decision.actor is not Side.CHANCE else None
        return responsible == self.side.value

    def opponent_event(self, cid):
        return cid in CARDS and CARDS[cid].side.value == self.side.opponent.value

    def hazardous(self, cid, hand=None):
        """Whether being forced to play `cid` can lose the game at DEFCON 2."""
        return self.opponent_event(cid) and self.event_risk(cid, 2, hand) > 0

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
                # A random USSR discard may fire a US event; only a DEFCON
                # reducer at 2 can hurt.
                return self.prior.unknown_chain_loss if defcon <= 2 and self.obs.opponent_hand_size else 0.
            remaining = tuple(c for c in hand if c != cid)
            return sum(self._hazard(c, defcon, tuple(x for x in remaining if x != c), depth+1)
                       for c in remaining if CARDS.get(c) and CARDS[c].side.value == 'US'
                       and not CARDS[c].scoring)/max(1, len(remaining))
        if cid == 'Star_Wars' and self.side is Side.USSR and self.obs.space_race['US'] > self.obs.space_race['USSR']:
            return max((1. if c == 'How_I_Learned_to_Stop_Worrying' else
                        self._hazard(c, defcon, hand, depth+1)
                        for c in self.obs.discard_pile if not CARDS[c].scoring and c != cid), default=0.)
        if cid == 'Missile_Envy' and defcon <= 2 and self.obs.opponent_hand_size:
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

    # -- chance node: what the opponent may do before our next round --------

    def _next(self, hand, rounds, defcon, pos, attempts, china, trapped=False):
        if rounds <= 0:
            return 0.
        p = self.prior.opponent_lowers_defcon if defcon > 2 else 0.
        return ((1-p)*self._after_hand_attack(hand, rounds, defcon, pos, attempts, china, trapped) +
                p*self._after_hand_attack(hand, rounds, max(2, defcon-1), pos, attempts, china, trapped))

    def _after_hand_attack(self, hand, rounds, defcon, pos, attempts, china, trapped):
        base = self.solve(hand, rounds, defcon, pos, attempts, china, trapped)
        p = self.prior.opponent_hand_attack
        if p <= 0 or base >= 1:
            return base
        # The attacker (Aldrich Ames, Terrorism, Grain Sales, Missile Envy) is
        # assumed to remove the safe card whose loss hurts us most; it cannot
        # take a card that would only have hurt us.
        safe = [c for c in hand if not self.hazardous(c, hand)]
        if not safe:
            return base
        worst = max(self.solve(tuple(c for c in hand if c != s), rounds, defcon, pos, attempts, china, trapped)
                    for s in safe)
        return (1-p)*base + p*worst

    # -- one card play ------------------------------------------------------

    def transition(self, cid, mode, hand, rounds, defcon, pos, attempts, china, trapped=False):
        remaining = list(hand)
        if cid == CHINA:
            china = False
        elif cid in remaining:
            remaining.remove(cid)
        remaining = tuple(remaining)
        def onward(h=remaining, d=defcon, p=pos, a=attempts, t=trapped):
            return self._next(h, rounds-1, d, p, a, china, t)
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
            dangerous = [c for c in remaining if self.hazardous(c, remaining)]
            replacement = tuple(sorted([c for c in remaining if c not in dangerous]+['@replacement']*len(dangerous)))
            # Replacements are unknown; explicit pessimistic penalty, not a sampled hidden draw.
            risk = 1-(1-self.prior.replacement_hazard)**len(dangerous)
            return risk+(1-risk)*onward(replacement)
        if cid == 'Aldrich_Ames_Remix' and self.side is Side.US and remaining:
            # The opponent chooses the worst continuation for us.
            return max(onward(tuple(c for c in remaining if c != discarded)) for discarded in remaining)
        if cid in US_PAYABLE_DISCARDS and self.side is Side.US:
            # Refusing is always allowed (a board hit, never a loss), and a
            # 3+ Ops discard fires no event: a hazardous card can leave this way.
            return min([onward()] + [onward(tuple(c for c in remaining if c != paid))
                                     for paid in self.payable(remaining)])
        if TRAPS.get(cid) is self.side:
            # Self-trapping: later rounds discard 2+ Ops cards without events.
            return onward(t=True)
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

    @staticmethod
    def payable(hand, minimum=3):
        """Cards the engine accepts for a printed-Ops discard clause (Blockade: 3, traps: 2)."""
        return [c for c in hand if c in CARDS and not CARDS[c].scoring and CARDS[c].ops >= minimum]

    def trap_step(self, hand, rounds, defcon, pos, attempts, china):
        """One trapped round: discard a 2+ Ops card (no event) and roll 1-4 to escape."""
        payable = self.payable(hand, 2)
        if not payable:
            # No roll; scoring cards in hand resolve, the round passes.
            rest = tuple(c for c in hand if not (c in CARDS and CARDS[c].scoring))
            return self._next(rest, rounds-1, defcon, pos, attempts, china, True)
        best = 1.
        for paid in payable:
            rest = tuple(c for c in hand if c != paid)
            value = (4/6)*self._next(rest, rounds-1, defcon, pos, attempts, china, False) + \
                    (2/6)*self._next(rest, rounds-1, defcon, pos, attempts, china, True)
            best = min(best, value)
        return best

    def discard_risk(self, cid, escape_roll=False):
        """Turn-loss risk after discarding `cid` right now, mid-play (Blockade,
        Debt Crisis, a trap step). `escape_roll` adds the trap's 1-4 die.
        With `cid` None it is simply the risk of the hand as it stands, the
        current round already spent."""
        hand = tuple(c for c in self.hand if c != cid) if cid else self.hand
        state = (self.obs.defcon, self.obs.space_race[self.side.value],
                 self.obs.space_race_attempts[self.side.value], self.china)
        if escape_roll and cid:
            value = (4/6)*self._next(hand, self.rounds, *state, False) + \
                    (2/6)*self._next(hand, self.rounds, *state, True)
        else:
            value = self._next(hand, self.rounds, *state, self.trapped)
        value = self._with_pending_headline(value, hand)
        log.debug("planner %s: discard %s -> turn-loss risk %.3f (rounds_left=%d)",
                  self.side.value, cid, value, self.rounds)
        return value

    def _with_pending_headline(self, value, hand=None, defcon=None):
        """Fold in our own still-pending headline: it fires, at this DEFCON,
        before the action rounds `value` describes."""
        if not self.pending_headline:
            return value
        r = self.event_risk(self.pending_headline, defcon, self.hand if hand is None else hand)
        return r + (1-r)*value

    def headline_pick_risk(self, cid):
        """Risk of headlining `cid`. The opponent's headline resolves first when
        it has more Ops (ties: US first), and may lower DEFCON before ours fires."""
        state = (self.hand, self.rounds, self.obs.defcon, self.obs.space_race[self.side.value],
                 self.obs.space_race_attempts[self.side.value], self.china, self.trapped)
        now = self.transition(cid, 'event', *state)
        if self.obs.defcon <= 2 or cid not in CARDS or CARDS[cid].scoring:
            return now
        ops = CARDS[cid].ops
        pool = [c for c in CARDS.values() if not c.scoring and c.id != CHINA]
        later = sum(c.ops > ops or (c.ops == ops and self.side is Side.USSR) for c in pool)/len(pool)
        q = later*self.prior.opponent_lowers_defcon
        lowered = self.transition(cid, 'event', self.hand, self.rounds, max(2, self.obs.defcon-1), *state[3:])
        value = (1-q)*now + q*lowered
        log.debug("planner %s: headline %s risk now=%.3f after-drop=%.3f p(drop first)=%.2f -> %.3f",
                  self.side.value, cid, now, lowered, q, value)
        return value

    # -- search -------------------------------------------------------------

    def _solve(self, hand, rounds, defcon, pos, attempts, china, trapped=False):
        if rounds <= 0 or not hand:
            return 0.
        if not any(self.hazardous(c, hand) for c in hand):
            return 0.  # only opponent events fire involuntarily; nothing here can
        self.nodes += 1
        if self.nodes > self.prior.max_states:
            if not self.truncated:
                log.warning("planner %s: search budget of %d states exhausted; using conservative fallback",
                            self.side.value, self.prior.max_states)
            self.truncated = True
            # Conservative fallback: any forced hazardous card is treated as loss.
            safe = sum(not self.hazardous(c, hand) for c in hand)
            return float(safe + int(china) < min(rounds, len(hand)+int(china)))
        if trapped:
            return self.trap_step(hand, rounds, defcon, pos, attempts, china)
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
                 self.obs.space_race_attempts[self.side.value], self.china, self.trapped)
        if cid is None:
            value = self._with_pending_headline(self.solve(*state))
            log.debug("planner %s: whole-hand turn-loss risk=%.3f (%d states searched)",
                      self.side.value, value, self.nodes)
            return value
        if self.trapped:
            return self._with_pending_headline(self.solve(*state))  # a trapped side does not choose a card play
        modes = (mode,) if mode else self.modes(cid, self.hand, state[3], state[4])
        per_mode = {m: self._with_pending_headline(self.transition(cid, m, *state)) for m in modes}
        log.debug("planner %s: %s risk by mode %s", self.side.value, cid,
                  {m: round(v, 3) for m, v in per_mode.items()})
        return min(per_mode.values())

    def features(self):
        risk = self.risk()
        hazards = [c for c in self.hand if self.hazardous(c)]
        if hazards:
            log.info("planner %s T%d AR%d: hazardous cards in hand %s (DEFCON %d, turn-loss risk %.3f)",
                     self.side.value, self.obs.turn, self.obs.action_round, hazards, self.obs.defcon, risk)
        return {'turn_loss_risk': risk,
                'hazardous_cards': len(hazards),
                'space_attempts_left': max(0, self.engine._space_attempts_allowed(self.side)-self.obs.space_race_attempts[self.side.value]),
                'china_available': int(self.china), 'rounds_left': self.rounds,
                'trapped': int(self.trapped),
                'search_truncated': self.truncated}
