"""Low-compute supervised bootstrap; no full games or external API calls.

python -m struggler.bots.event_value.train --output models/event-value-v1.json
"""
import argparse
import copy
import json
import random
import time
from pathlib import Path

from struggler.engine import Engine, Region, Side
from struggler.engine.core import SCORING_CARD_REGION
from .features import CARDS, ENTRY_TURN, EVENTS, FEATURE_NAMES, encode, score
from .network import ValueNetwork
from .scenarios import expected_score


def examples(count, seed, prior):
    """Synthetic stress positions, not purported samples from expert play.

    Keep whole independently generated positions in one dataset split.
    Future learning can feed (features, observed future VP - current VP)
    rows to the same network instead of this explicit-prior teacher.
    """
    rng = random.Random(seed)
    rows = []
    regions = (Region.MIDDLE_EAST, Region.ASIA, Region.AFRICA, Region.CENTRAL_AMERICA)
    for _ in range(count):
        engine = Engine(seed=0)
        engine.turn = rng.choice((1, 3, 4, 6, 8, 10))
        engine.action_round = rng.randint(1, 6)
        engine.defcon = rng.randint(2, 5)
        engine.vp = rng.randint(-15, 15)
        region = rng.choice(regions)
        side = rng.choice((Side.US, Side.USSR))
        for cid, info in engine.board.countries.items():
            if info.region is region:
                controller = rng.choice(('US', 'USSR'))
                engine.board.influence[cid][controller] = rng.randint(0, info.stability+2)
                engine.board.influence[cid][Side(controller).opponent.value] = rng.randint(0, 2)
        # Unknown identities stay unknown. Only size is used by the prior.
        engine.hands[side.opponent.value] = ['?']*rng.randint(1, 8)
        engine.draw_pile = ['?']*rng.randint(1, 45)
        scoring = next(c for c, r in SCORING_CARD_REGION.items() if r is region)
        for card in (*EVENTS, scoring):
            # Do not create impossible early hands containing mid-war cards.
            if engine.turn < ENTRY_TURN[CARDS[card].period]:
                continue
            location = rng.randrange(4)
            if location == 0:
                engine.hands[side.value].append(card)
            elif location == 1:
                engine.discard_pile.append(card)
            elif location == 2 and CARDS[card].remove_after_event:
                engine.removed_cards.append(card)
        obs = engine.observe(side)
        current = score(engine.board, obs, region)
        rows.append((encode(obs, engine.board, region, prior), expected_score(obs, region, prior)-current))
    return rows


def metrics(model, rows):
    errors = [model.predict(x)-y for x, y in rows]
    return dict(mse=sum(e*e for e in errors)/len(rows),
                mae=sum(abs(e) for e in errors)/len(rows),
                zero_residual_mse=sum(y*y for _, y in rows)/len(rows))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--samples', type=int, default=512)
    parser.add_argument('--epochs', type=int, default=40)
    parser.add_argument('--hidden', type=int, default=16)
    parser.add_argument('--seed', type=int, default=7)
    parser.add_argument('--output', default='models/event-value-v1.json')
    parser.add_argument('--save-data', help='Save generated train/validation/test arrays for reuse')
    parser.add_argument('--data', help='Reuse a previously saved dataset with fixed splits')
    args = parser.parse_args()
    if min(args.samples, args.epochs, args.hidden) < 1:
        parser.error('samples, epochs and hidden must be positive')
    start = time.monotonic()
    model = ValueNetwork(args.hidden, args.seed)
    if args.data:
        data = json.loads(Path(args.data).read_text())
        if data.get('features') != list(FEATURE_NAMES) or data.get('prior') != model.prior.__dict__:
            parser.error('dataset feature schema or timing prior does not match')
        train, valid, test = (data[k] for k in ('train', 'validation', 'test'))
        import math
        if any(not split for split in (train, valid, test)) or any(
            len(x) != len(FEATURE_NAMES) or not all(math.isfinite(v) for v in [*x, y])
            for split in (train, valid, test) for x, y in split
        ):
            parser.error('dataset splits must be nonempty with finite, correctly shaped rows')
    else:
        train = examples(args.samples, args.seed, model.prior)
        valid = examples(max(64, args.samples//4), args.seed+1, model.prior)
        test = examples(max(64, args.samples//4), args.seed+2, model.prior)
    if args.save_data:
        Path(args.save_data).write_text(json.dumps(dict(features=FEATURE_NAMES,
            prior=model.prior.__dict__, train=train, validation=valid, test=test))+'\n')
    best, best_loss, best_epoch = copy.deepcopy(model), metrics(model, valid)['mse'], 0
    rng = random.Random(args.seed)
    for epoch in range(1, args.epochs+1):
        model.fit_epoch(train, rng=rng)
        loss = metrics(model, valid)['mse']
        if loss < best_loss:
            best, best_loss, best_epoch = copy.deepcopy(model), loss, epoch
        if epoch % 10 == 0:
            print(json.dumps(dict(epoch=epoch, validation_mse=loss)), flush=True)
    report = dict(seed=args.seed, samples=len(train), validation_samples=len(valid),
                  test_samples=len(test), epochs=args.epochs, selected_epoch=best_epoch,
                  parameters=best.parameter_count, validation=metrics(best, valid),
                  test=metrics(best, test), seconds=time.monotonic()-start,
                  target='event-scenario regional VP residual; includes both Nasser/Sadat orders',
                  data_source=args.data or 'synthetic positions')
    best.save(args.output, **report)
    Path(args.output+'.report.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
