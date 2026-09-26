"""Which countries each card's event moves, measured by firing it.

The maintainer's rule (2026-09-26): a country an event is aimed at is worth
less while that card is still to come -- Vietnam less than Laos while
Vietnam Revolts is live, South Korea less than North Korea (Korean War),
Egypt less than Libya (Nasser) -- and Mid and Late War cards count before
they enter the deck. That needs, per card, WHICH countries its event moves.
The engine has no such table: events are code (`engine/events.py`). A
hand-written list would miss cards and drift from the code, so this derives
it from the code itself.

Every card with an event is fired for its own side (both sides for a
neutral card) on `--trials` random boards -- both sides on every country,
a random DEFCON and turn, with a card's precondition forced when the board
misses it (`unlock`) -- and every decision the event asks is answered with
a random legal option. A single die rolls 6, so a war counts its target
whatever one roll would do (`roll`). A country's
EXPOSURE to a card is its share of the firings that moved ANY influence:
the event's reach when it lands. A fixed target reads 1.0, a war's target
included (a failed roll moves nothing and does not count against it); a
choice among five reads about 0.2 each; an event that moves no influence
reads nothing.

Deterministic for a given `--trials` and `--seed`, so the table is
reproducible and `tests/test_event_exposure.py` holds the checked-in copy
to it.

    uv run python scripts/probe_event_exposure.py --out src/struggler/bots/strategic/event_exposure.json
"""
from __future__ import annotations

import argparse
import collections
import json
import logging
import random
import sys

from struggler.engine import Engine, Side
from struggler.engine.cards import load_cards
from struggler.engine.events import EVENTS

MAX_STEPS = 200


def random_board(engine: Engine, rng: random.Random) -> None:
    """Both sides on EVERY country, 1-4 each: an event that removes or
    conditions on influence finds some to act on, so its reach shows."""
    for cid in engine.board.countries:
        engine.board.influence[cid]['US'] = rng.randint(1, 4)
        engine.board.influence[cid]['USSR'] = rng.randint(1, 4)
    engine.defcon = rng.choice((2, 3, 4, 5))
    engine.turn = rng.randint(1, 10)


def unlock(engine: Engine) -> None:
    """The preconditions a card may never meet on a random board: John Paul
    II (Solidarity), Marshall Plan / Warsaw Pact (NATO), the US ahead in
    space (Star Wars), US control of the UK (Special Relationship) and of a
    Middle East country (Our Man in Tehran), before the Late War (the
    Cambridge Five)."""
    engine.game_effects.update(john_paul=True, marshall_or_warsaw=True)
    engine.space_race['US'], engine.space_race['USSR'] = 3, 1
    engine.board.influence['UK'].update(US=5, USSR=0)
    engine.board.influence['Israel'].update(US=5, USSR=0)
    engine.turn = min(engine.turn, 7)


def roll(d, rng: random.Random):
    """A single die rolls 6, so a war shows its full reach (the threat is
    the target, whatever this roll does); a dice contest -- two dice in one
    option, Olympic Games and Summit -- stays random, or a tie rerolls
    forever."""
    payload = d.options[0].payload
    if len(d.options) == 1 or len(payload) != 1:
        return rng.choice(d.options)
    return max(d.options, key=lambda o: next(iter(o.payload.values())))


def fire(card: str, side: Side, seed: int) -> tuple[str, set[str]]:
    """One firing on one random board: ('ok' | 'ineligible' | 'error:<name>'
    | 'unfinished', countries whose influence changed)."""
    rng = random.Random(seed)
    engine = Engine(seed=seed)
    engine.events_enabled = True
    random_board(engine, rng)
    if not EVENTS[card].eligible(engine, side):
        unlock(engine)
        if not EVENTS[card].eligible(engine, side):
            return 'ineligible', set()
    before = {c: dict(v) for c, v in engine.board.influence.items()}
    try:
        engine._fire_event(side, card)
        for _ in range(MAX_STEPS):
            d = engine.pending_decision
            if d is None or engine.is_terminal:
                break
            engine.step(roll(d, rng) if d.actor is Side.CHANCE else rng.choice(d.options))
        else:
            return 'unfinished', set()
    except Exception as exc:  # an event the random board cannot host
        return f'error:{type(exc).__name__}', set()
    return 'ok', {c for c, v in engine.board.influence.items() if v != before[c]}


def probe(trials: int, seed: int) -> dict:
    logging.disable(logging.CRITICAL)
    cards = load_cards()
    table = {}
    for cid, card in sorted(cards.items(), key=lambda kv: kv[1].number):
        if card.scoring or cid not in EVENTS:
            continue
        sides = (Side.US, Side.USSR) if card.side.value == 'NEUTRAL' else (Side(card.side.value),)
        touched: collections.Counter = collections.Counter()
        outcomes: collections.Counter = collections.Counter()
        moving = 0
        for side in sides:
            for t in range(trials):
                outcome, moved = fire(cid, side, seed * 100_003 + card.number * 1_009 + t)
                outcomes[outcome.split(':')[0]] += 1
                if outcome == 'ok':
                    touched.update(moved)
                    moving += bool(moved)
        fired = outcomes['ok']
        table[cid] = {
            'number': card.number, 'side': card.side.value, 'period': card.period.name,
            'fired': fired, 'moved': moving, 'outcomes': dict(outcomes),
            'exposure': {c: round(n / moving, 3) for c, n in sorted(touched.items(), key=lambda kv: -kv[1])}
                        if moving else {},
        }
    return table


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--trials', type=int, default=200)
    ap.add_argument('--seed', type=int, default=1)
    ap.add_argument('--out')
    args = ap.parse_args(argv)
    table = probe(args.trials, args.seed)
    text = json.dumps({'_what': __doc__.split('\n\n')[0], 'trials': args.trials, 'seed': args.seed,
                       'cards': table}, indent=1) + '\n'
    if args.out:
        open(args.out, 'w').write(text)
    for cid, row in table.items():
        top = ', '.join(f'{c} {p:.2f}' for c, p in list(row['exposure'].items())[:6])
        extra = f" (+{len(row['exposure']) - 6} more)" if len(row['exposure']) > 6 else ''
        bad = {k: v for k, v in row['outcomes'].items() if k != 'ok'}
        print(f"{row['number']:>3} {cid:34} {row['period'][:4]} {row['side']:7} "
              f"{top or '-'}{extra}{'   ' + str(bad) if bad else ''}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
