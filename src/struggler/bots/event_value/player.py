"""Optional learned regional correction to the existing tactical policy."""
from struggler.bots.strategic import StrategicPlayer
from .features import EVENT_COUNTRIES, encode
from .network import ValueNetwork


class EventValuePlayer(StrategicPlayer):
    def __init__(self, model: ValueNetwork, **kwargs):
        super().__init__(**kwargs)
        self.model = model
        self._corrections = {}

    def choose_action(self, observation, history):
        self._corrections.clear()
        return super().choose_action(observation, history)

    def _correction(self, obs, region):
        # Uncovered regions have no bootstrap examples: do not extrapolate.
        if not any(self.board.countries[c].region is region
                   for countries in EVENT_COUNTRIES.values() for c in countries):
            return 0.0
        key = (region, obs.side, tuple((v['US'], v['USSR']) for v in self.board.influence.values()))
        if key not in self._corrections:
            self._corrections[key] = self.model.predict(encode(obs, self.board, region, self.model.prior))
        return self._corrections[key]

    def delta(self, obs, cid, own=0, opp=0):
        base = super().delta(obs, cid, own, opp)
        region = self.board.countries[cid].region
        before = self._correction(obs, region)
        original = dict(self.board.influence[cid])
        try:
            self.board.influence[cid][obs.side.value] = max(0, original[obs.side.value]+own)
            self.board.influence[cid][obs.side.opponent.value] = max(0, original[obs.side.opponent.value]+opp)
            after = self._correction(obs, region)
        finally:
            self.board.influence[cid].update(original)
        return base + self.vp_value(obs)*(after-before)

    def country_values(self, observation):
        """Explain +1 friendly influence's regional VP change, before Ops cost.

        These are marginal changes, not an additive allocation of all board VP.
        """
        from struggler.bots.greedy import _sync_board
        from .features import score
        self._corrections.clear()
        _sync_board(self.board, observation)
        result = {}
        for cid, info in self.board.countries.items():
            before = score(self.board, observation, info.region) + self._correction(observation, info.region)
            self.board.influence[cid][observation.side.value] += 1
            try:
                after = score(self.board, observation, info.region) + self._correction(observation, info.region)
            finally:
                self.board.influence[cid][observation.side.value] -= 1
            result[cid] = after-before
        return result
