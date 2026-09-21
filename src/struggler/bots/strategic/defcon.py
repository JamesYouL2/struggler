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
from struggler.engine.core import effective_ops
from struggler.engine.rules import RULES

# `struggler.bots.strategic.defcon`, matching the module path. It was
# `struggler.bots.defcon` -- the name from before this file moved into the
# strategic package -- which made it a *sibling* of
# `struggler.bots.strategic` rather than a child, so raising the strategic
# logger's level silently missed the survival planner. That is about 60% of
# a full game's work and the first thing worth tracing.
log = logging.getLogger('struggler.bots.strategic.defcon')

CARDS = load_cards()
CHINA = 'The_China_Card'

# Which side's event each card carries, partitioned once at import. A planner
# used to rebuild its half by walking every card and reading `CardSide.value`
# -- constant data, re-derived 5,984 times a game.
_EVENTS_BY_SIDE = {
    'US': frozenset(cid for cid, info in CARDS.items() if info.side.value == 'US'),
    'USSR': frozenset(cid for cid, info in CARDS.items() if info.side.value == 'USSR'),
}
ASK = 'Ask_Not_What_Your_Country_Can_Do_For_You'
RAISERS = {'How_I_Learned_to_Stop_Worrying': 5, 'Salt_Negotiations': 2,
           'Nuclear_Test_Ban': 2, 'ABM_Treaty': 1}
REDUCERS = {'Duck_and_Cover', 'We_Will_Bury_You', 'Soviets_Shoot_Down_KAL_007'}
# Events that hand the opponent a Coup (or Ops they may Coup with): card ->
# the side that Coups. Lethal at DEFCON 2 only while that side has a
# battleground to Coup, so their danger is a property of the board, not the
# card -- the board can create it (F3 of the 2026-09-18 audit).
BORROWED_COUPS = {'CIA_Created': Side.US, 'Lone_Gunman': Side.USSR,
                  'Grain_Sales_to_Soviets': Side.US, 'Tear_Down_This_Wall': Side.US,
                  'Ortega_Elected_in_Nicaragua': Side.USSR}
# Events that make the US discard a 3+-Ops card (modified value, per FAQ
# 7.4 -- see DefconPlanner.payable) or take a board hit.
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
    # The chance the opponent lowers DEFCON before our next card, applied
    # once per remaining round in `_next`. It shipped at 0.75 with no
    # recorded rationale, which over seven rounds is a planner that expects
    # DEFCON to fall almost every round.
    #
    # It is measurable, and it was measured:
    # `models/opponent-model-v1.json.report.json` labels exactly this event
    # ("did the opponent lower DEFCON between our pick and our next pick")
    # over recorded games, and the base rate is **0.098 on 973 test samples
    # and 0.108 on 697 validation samples**. 0.75 was seven times too high,
    # and an over-cautious survival prior is the likeliest remaining reason
    # this bot reaches DEFCON 1 far less often than a human field.
    #
    # Set above the measured rate rather than at it: those are games against
    # *this* bot, strong humans Coup more freely (Sankt Coups Italy on turn
    # 1), and a survival planner should be wrong toward caution. 0.10 is the
    # obvious ablation if this gates well.
    opponent_lowers_defcon: float = .15
    # Deliberately *not* lowered to its measured base rate, which is 0.003
    # to 0.006. That number is an artefact of the opponent being a bot:
    # these bots play Grain Sales, Aldrich Ames Remix and Terrorism for Ops
    # or Space, so they almost never attack a hand, while strong humans
    # always event them (docs/EXPERT_STRATEGY.md). Fitting this to bot games
    # would tune the planner to an opponent it should not expect to face.
    opponent_hand_attack: float = .10
    unknown_chain_loss: float = .25
    replacement_hazard: float = .15
    max_states: int = 20000
    # The same budget for a planner run INSIDE the event sandbox, where the
    # position is hypothetical and its helper is simulating one line of one
    # simulated event. Measured over three self-play games (2275 decisions):
    # 60% of all planner nodes are spent inside the sandbox, and in the worst
    # decisions it is 96% -- 510,698 nodes against the top level's 19,661,
    # because every fork builds a planner with the FULL budget. The tail is
    # not a slow decision, it is dozens of full-depth searches of positions
    # that may never happen. 2000 leaves the top level untouched and bounds
    # the tail; the fallback when it runs out is the conservative one every
    # truncated search already uses.
    sandbox_states: int = 2000

    def __post_init__(self):
        for p in (self.opponent_lowers_defcon, self.opponent_hand_attack,
                  self.unknown_chain_loss, self.replacement_hazard):
            if not math.isfinite(p) or not 0 <= p <= 1:
                raise ValueError('survival probabilities must be finite and in [0, 1]')
        if self.max_states < 1 or self.sandbox_states < 1:
            raise ValueError('search budgets must be positive')


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
        # Hoisted out of the search's inner loops. `opponent` is a property
        # with a branch, and `opponent_event` was calling it once per card per
        # node; both are constant for the life of a planner.
        self.other = obs.side.opponent
        self._side_key = obs.side.key
        self._other_key = self.other.key
        # Which cards carry whose event does not change during a game, let
        # alone during a planner, and this walked all of CARDS asking each one
        # -- 329,000 `CardSide.value` reads a game for a partition of a
        # constant. `_EVENTS_BY_SIDE` is that partition, built at import.
        self._opponent_events = _EVENTS_BY_SIDE[self._other_key]
        # The Space Race boxes as of the root observation, which the search
        # never moves; `attempts_allowed` asked for these on every node.
        self._root_space = obs.space_race[self._side_key]
        self._other_space = obs.space_race[self._other_key]
        self.solve = lru_cache(maxsize=None)(self._solve)
        # The two combinators between `solve` and itself. `solve` was memoised
        # and these were not, so the same (hand, rounds, defcon, ...) state
        # re-did the DEFCON-drop split and the hand-attack maximum on every
        # path that reached it: 235k `_next` and 453k `_after_hand_attack`
        # calls in the worst corpus position, against 74k distinct solves.
        self.next = lru_cache(maxsize=None)(self._next)
        self.after_hand_attack = lru_cache(maxsize=None)(self._after_hand_attack)
        self._minus = lru_cache(maxsize=None)(self._hand_minus)
        self._hazard = lru_cache(maxsize=None)(self._event_risk)
        self.hazardous = lru_cache(maxsize=None)(self._hazardous)
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
        """Whether `cid` is the opponent's event, so playing it fires for them.

        A set lookup, because this is the planner's hottest predicate: the
        worst corpus position asked it 1.68 million times in one ranking, and
        the old form -- `CARDS[cid].side.value == self.side.opponent.value` --
        walked `Side.opponent` and two `.value`s on every one of them, which
        was 4.2 million enum lookups and about a third of the ranking. The
        set is a fact about the deck and our seat, so it is built once."""
        return cid in self._opponent_events

    def _hazardous(self, cid, hand=None):
        """Whether being forced to play `cid` can lose the game at DEFCON 2.

        Memoised per planner (`self.hazardous`): the search asks it for every
        card at every node and the answer depends only on the card and the
        hand it is held with. 1.32 million calls in the worst corpus position,
        almost all of them repeats. `hand` must therefore be hashable -- the
        search already passes tuples."""
        return self.opponent_event(cid) and self.event_risk(cid, 2, hand) > 0

    def coup_threat(self, actor, defcon, countries=None, ignore_defcon=False):
        if actor is self.side or defcon > 2:
            return False
        return self.battleground_coup(actor, defcon, countries, ignore_defcon)

    def opponent_can_lower_defcon(self):
        """Whether the opponent has a legal battleground Coup right now that
        would lower DEFCON: a fact about the public board, not a forecast.
        Their unseen hand may lower it other ways; that stays in the prior."""
        return self.obs.defcon > 2 and self.battleground_coup(self.other, self.obs.defcon)

    def latent_hazards(self, hand):
        """Borrowed-Coup cards in `hand` that would be lethal at DEFCON 2 but
        for want of a target: safe on this board, not on one we move to."""
        return [c for c in hand if c in BORROWED_COUPS and self.opponent_event(c)
                and not self.coup_threat(BORROWED_COUPS[c], 2)]

    def battleground_coup(self, actor, defcon, countries=None, ignore_defcon=False):
        """Whether `actor` can Coup a battleground at `defcon` and lower it."""
        # CMC makes the coup actor lose instead -- unless the actor can still
        # pay to lift it, which the engine offers at every atomic boundary,
        # our own borrowed-Coup action included. Paying removes the actor's
        # OWN influence and a target needs ours, so it never removes one.
        if (self.obs.turn_effects.get('cuban_missile_crisis') == actor.value
                and not self.engine.cmc_defuse_countries(actor)):
            return False
        # Nuclear Subs: US battleground Coups do not lower DEFCON.
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
            b = self.engine._regions_dominated(self.other)
            return sum(y+b > x+a for x in range(1, 7) for y in range(1, 7))/36
        actor = BORROWED_COUPS.get(cid)
        if actor:
            countries = None
            if cid == 'Tear_Down_This_Wall':
                countries = [c for c, i in self.engine.board.countries.items() if i.region is Region.EUROPE]
            if cid == 'Ortega_Elected_in_Nicaragua':
                countries = self.engine.board.neighbors('Nicaragua')
            risk = float(self.coup_threat(actor, defcon, countries, countries is not None))
            if cid == 'Grain_Sales_to_Soviets' and self.side is Side.USSR and hand:
                # US can choose a neutral DEFCON setter on USSR's action.
                nested = [1.0 if c == 'How_I_Learned_to_Stop_Worrying' else
                          self._hazard(c, defcon, tuple(x for x in hand if x != c), depth+1)
                          for c in hand]
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
                pos < RULES['space_race_max_box'] and attempts < self.attempts_allowed(pos) and
                self.engine._effective_ops(self.side, CARDS[cid]) >= RULES['space_race_boxes'][str(pos+1)]['ops'])

    def attempts_allowed(self, pos):
        """Space Race attempts this turn with our marker at simulated box
        `pos`. The root engine only knows the box we are in now; reaching
        box 2 first in the search grants the second attempt at once (6.4.4),
        exactly as `Engine.advance_space_race_box` would. The opponent's
        marker is frozen with the rest of the board."""
        allowed = self.engine._space_attempts_allowed(self.side)
        # Both boxes are read off the observation, which is frozen for the
        # planner's life, so they are read once in `__init__` rather than
        # 342,000 times here. `allowed` still asks the engine: it reads
        # `game_effects`, and this is not the place to assume that cannot move.
        if allowed < 2 and self._root_space < 2 <= pos and self._other_space < 2:
            return 2
        return allowed

    def modes(self, cid, hand, pos, attempts):
        if cid == '@replacement':
            return ('ops',)
        if CARDS[cid].scoring:
            return ('event',)
        modes = ['ops']
        if cid in RAISERS or (cid == ASK and self.side is Side.US) or cid == 'Five_Year_Plan':
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
        return ((1-p)*self.after_hand_attack(hand, rounds, defcon, pos, attempts, china, trapped) +
                p*self.after_hand_attack(hand, rounds, max(2, defcon-1), pos, attempts, china, trapped))

    def _hand_minus(self, hand, cid):
        """`hand` without one copy of `cid`, cached: the hand-attack maximum
        rebuilt these tuples 3.6 million times in one ranking."""
        return tuple(c for c in hand if c != cid)

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
        worst = max(self.solve(self._minus(hand, s), rounds, defcon, pos, attempts, china, trapped)
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
            return self.next(h, rounds-1, d, p, a, china, t)
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

    def payable(self, hand, minimum=3):
        """Cards the engine accepts for a discard clause (Blockade: 3, traps: 2).

        The *modified* Ops value, matching `Engine.effective_ops`: the FAQ
        applies a modified value "for all purposes", Beartrap/Quagmire named
        among them. Red Scare can strand this side in a trap the printed
        values would have let it escape, and the planner has to model the
        trap the engine will actually run.
        """
        effects = self.obs.turn_effects
        return [c for c in hand
                if c in CARDS and not CARDS[c].scoring
                and effective_ops(CARDS[c].ops, effects, self.side) >= minimum]

    def trap_step(self, hand, rounds, defcon, pos, attempts, china):
        """One trapped round: discard a 2+ Ops card (no event) and roll 1-4 to escape."""
        payable = self.payable(hand, 2)
        if not payable:
            # No roll; scoring cards in hand resolve, the round passes.
            rest = tuple(c for c in hand if not (c in CARDS and CARDS[c].scoring))
            return self.next(rest, rounds-1, defcon, pos, attempts, china, True)
        best = 1.
        for paid in payable:
            rest = tuple(c for c in hand if c != paid)
            value = (4/6)*self.next(rest, rounds-1, defcon, pos, attempts, china, False) + \
                    (2/6)*self.next(rest, rounds-1, defcon, pos, attempts, china, True)
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
            value = (4/6)*self.next(hand, self.rounds, *state, False) + \
                    (2/6)*self.next(hand, self.rounds, *state, True)
        else:
            value = self.next(hand, self.rounds, *state, self.trapped)
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
                'space_attempts_left': max(0, self.attempts_allowed(self.obs.space_race[self.side.value])-self.obs.space_race_attempts[self.side.value]),
                'china_available': int(self.china), 'rounds_left': self.rounds,
                'trapped': int(self.trapped),
                'search_truncated': self.truncated}
