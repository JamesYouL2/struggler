"""Cheap teacher: exact dice and short-horizon event mixtures before scoring.

The event mechanics are exact; event occurrence/timing are explicit priors.
This teacher does not claim to predict actual future play.
"""
from dataclasses import replace

from struggler.engine import Action, DecisionKind as K, Observation, Region, Side
from .features import EVENT_COUNTRIES, TimingPrior, card_state, public_engine, score


def event_score(obs: Observation, region: Region, card: str) -> float:
    engine = public_engine(obs)
    # For neutral wars, the owner chooses the attacker. Unseen here means the
    # opponent-held branch of the prior, not a fabricated actual hidden hand.
    actor = obs.side if card_state(obs, card) == 'hand' else obs.side.opponent
    engine._fire_event(actor, card)
    decision = engine.pending_decision
    if decision is None:
        return score(engine.board, obs, region)
    if decision.kind is K.WAR_TARGET:
        targets = [a.payload['country'] for a in decision.options]
    elif decision.kind is K.WAR_ROLL:
        targets = [decision.context['target']]
    else:
        raise ValueError(f'unsupported event continuation: {decision.kind}')
    results = []
    for target in targets:
        total = 0.0
        for die in range(1, 7):
            trial = public_engine(obs)
            trial._fire_event(actor, card)
            if trial.pending_decision.kind is K.WAR_TARGET:
                choice = next(a for a in trial.pending_decision.options if a.payload['country'] == target)
                trial.step(choice)
            d = trial.pending_decision
            action = Action(K.WAR_ROLL, {'value': die})
            # Override the sandbox's chance option, never the real game's RNG.
            trial._decision_stack[-1] = replace(d, options=(action,))
            trial.step(action)
            total += score(trial.board, obs, region)/6
        results.append(total)
    attacker = Side(decision.context.get('attacker', actor.value))
    return max(results) if attacker is obs.side else min(results)


def expected_score(obs: Observation, region: Region, prior: TimingPrior = TimingPrior()) -> float:
    engine = public_engine(obs)
    baseline = score(engine.board, obs, region)
    exposures = [(c, prior.exposure(obs, c, region)) for c, countries in EVENT_COUNTRIES.items()
                 if any(engine.board.countries[cid].region is region for cid in countries)]
    # Egypt can change hands twice. Preserve Nasser/Sadat interaction instead
    # of summing independent discounts. Conditional order is a 50/50 prior.
    egypt = {'Nasser', 'Sadat_Expels_Soviets'}
    if {c for c, _ in exposures} == egypt:
        probabilities = dict(exposures)
        pn, ps = probabilities['Nasser'], probabilities['Sadat_Expels_Soviets']
        value = (1-pn)*(1-ps)*baseline
        if pn:
            value += pn*(1-ps)*event_score(obs, region, 'Nasser')
        if ps:
            value += ps*(1-pn)*event_score(obs, region, 'Sadat_Expels_Soviets')
        if pn and ps:
            for order in (('Nasser', 'Sadat_Expels_Soviets'), ('Sadat_Expels_Soviets', 'Nasser')):
                trial = public_engine(obs)
                for card in order:
                    trial._fire_event(obs.side, card)
                value += pn*ps*score(trial.board, obs, region)/2
        return value
    # Competing one-event scenarios; normalize if their sum exceeds one.
    mass = max(1.0, sum(p for _, p in exposures))
    return baseline + sum(p/mass * (event_score(obs, region, c)-baseline)
                          for c, p in exposures if p > 0)
