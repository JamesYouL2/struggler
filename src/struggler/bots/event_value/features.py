"""Public information only; stable feature ordering is part of the model format."""
from dataclasses import dataclass

import copy

from struggler.bots.strategic import CARDS, StrategicPlayer
from struggler.engine.core import SANDBOX_LOG
from struggler.engine import Engine
from struggler.engine import Observation, Period, Region, Side
from struggler.engine.board import Board
from struggler.engine.core import SCORING_CARD_REGION

# Explicit factual relationships, not learned from thousands of games.
EVENT_COUNTRIES = {
    'Fidel': ('Cuba',),
    'Nasser': ('Egypt',),
    'Sadat_Expels_Soviets': ('Egypt',),
    'Korean_War': ('South_Korea',),
    'Indo_Pakistani_War': ('India', 'Pakistan'),
    'Portuguese_Empire_Crumbles': ('Angola', 'SE_African_States'),
}
EVENTS = tuple(EVENT_COUNTRIES)
REGIONS = tuple(Region)
STATES = ('hand', 'unseen', 'discard', 'removed', 'future')
ENTRY_TURN = {Period.EARLY_WAR: 1, Period.MID_WAR: 4, Period.LATE_WAR: 8}


def card_state(obs: Observation, card: str) -> str:
    if card in obs.removed_cards:
        return 'removed'
    if card in obs.hand:
        return 'hand'
    if card in obs.discard_pile:
        return 'discard'
    if obs.turn < ENTRY_TURN[CARDS[card].period]:
        return 'future'
    return 'unseen'


@dataclass(frozen=True)
class TimingPrior:
    """Short-horizon assumptions, NOT calibrated probabilities.

    Discards/future cards have zero probability until an observed reshuffle/
    deck entry. Unknown identity is exchangeable over opponent hand + draw.
    """
    trigger_rate: float = 0.65
    hand_horizon: float = 0.35
    unseen_horizon: float = 0.75
    discard_horizon: float = 1.0

    def __post_init__(self):
        if any(not 0 <= x <= 1 for x in self.__dict__.values()):
            raise ValueError('timing probabilities must lie in [0, 1]')

    def exposure(self, obs: Observation, card: str, region: Region) -> float:
        state = card_state(obs, card)
        if state in ('discard', 'removed', 'future'):
            return 0.0
        scoring = next(c for c, r in SCORING_CARD_REGION.items() if r is region)
        scoring_state = card_state(obs, scoring)
        horizon = (self.hand_horizon if scoring_state == 'hand' else
                   self.unseen_horizon if scoring_state == 'unseen' else self.discard_horizon)
        held = 1.0 if state == 'hand' else obs.opponent_hand_size / max(1, obs.opponent_hand_size + obs.draw_pile_size)
        return held * horizon * self.trigger_rate


def public_engine(obs: Observation):
    return StrategicPlayer().public_engine(obs)


def score(board: Board, obs: Observation, region: Region) -> float:
    """Match this repository's scoring, including Shuttle/Formosa overrides.

    A terminal Europe win is represented by +/-20 for a bounded VP regressor.
    Terminal action handling remains the tactical policy's responsibility.
    """
    engine = Engine(seed=0, board=board)
    engine.log = SANDBOX_LOG
    engine.game_effects = copy.deepcopy(dict(obs.game_effects))
    result = engine._score_region_net(region)
    if engine.is_terminal:
        return 20.0 if engine.winner is obs.side else -20.0
    return float(result if obs.side is Side.US else -result)


def feature_names() -> tuple[str, ...]:
    names = [f'region:{r.value}' for r in REGIONS]
    names += ['us', 'turn', 'round', 'defcon', 'vp', 'military_deficit',
              'opponent_hand', 'draw', 'score']
    names += [f'scoring:{s}' for s in STATES]
    names += ['own_countries', 'enemy_countries', 'own_bg', 'enemy_bg',
              'own_progress', 'enemy_progress', 'own_thin', 'enemy_thin']
    for event in EVENTS:
        names += [f'{event}:{s}' for s in STATES] + [f'{event}:exposure', f'{event}:signed_exposure']
        for cid in EVENT_COUNTRIES[event]:
            names += [f'{event}:{cid}:{f}' for f in ('own', 'enemy', 'own_neighbors', 'enemy_neighbors')]
    return tuple(names)


FEATURE_NAMES = feature_names()


def encode(obs: Observation, board: Board, region: Region,
           prior: TimingPrior = TimingPrior()) -> list[float]:
    side = obs.side
    x = [float(r is region) for r in REGIONS]
    x += [float(side is Side.US), obs.turn/10, obs.action_round/8, obs.defcon/5,
          obs.vp * (1 if side is Side.US else -1)/20,
          max(0, obs.defcon-obs.military_ops.get(side.value, 0))/5,
          obs.opponent_hand_size/10, obs.draw_pile_size/60, score(board, obs, region)/20]
    scoring = next(c for c, r in SCORING_CARD_REGION.items() if r is region)
    x += [float(card_state(obs, scoring) == s) for s in STATES]
    ids = board.countries_in(region)
    for bg_only in (False, True):
        for s in (side, side.opponent):
            x.append(sum(board.control(c) is s for c in ids
                         if not bg_only or board.countries[c].battleground)/10)
    for s in (side, side.opponent):
        x.append(sum(max(0, min(1, (board.influence[c][s.value]-board.influence[c][s.opponent.value])
                                / board.countries[c].stability)) for c in ids)/10)
    for s in (side, side.opponent):
        x.append(sum(board.influence[c][s.value]-board.influence[c][s.opponent.value]
                     == board.countries[c].stability for c in ids)/10)
    for event, countries in EVENT_COUNTRIES.items():
        relevant = any(board.countries[c].region is region for c in countries)
        x += [float(relevant and card_state(obs, event) == s) for s in STATES]
        exposure = prior.exposure(obs, event, region) if relevant else 0.0
        beneficiary = CARDS[event].side.value
        if beneficiary == 'NEUTRAL':
            beneficiary = obs.side.value if card_state(obs, event) == 'hand' else obs.side.opponent.value
        x += [exposure, exposure * (1 if beneficiary == side.value else -1)]
        for cid in countries:
            for s in (side, side.opponent):
                x.append(min(12, board.influence[cid][s.value])/6 if relevant else 0.0)
            for s in (side, side.opponent):
                x.append(sum(board.control(n) is s for n in board.neighbors(cid))/6 if relevant else 0.0)
    return x
