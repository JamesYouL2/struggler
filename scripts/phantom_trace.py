#!/usr/bin/env python
"""Where does the China Card phantom's strength come from?

bc5ef93 made `card_state` return 'china' for The China Card, taking it out
of the unseen pool, where it had sat all game as a card nobody holds. The fix
is right -- the China Card is face up -- and it cost HEAD about five points:
restoring the phantom gated at 0.557 [0.507, 0.606] on the rotated books and
0.555 [0.506, 0.603] on iran/austria. So something downstream was tuned
around it. The commit named the chain it expected: `_unseen_holds` ->
hand-attack event values -> `ops_value(1)` -> `vp_value` -> every
delta-based ranking key.

Games cannot say which link it is, and a gate per link would cost a night.
The corpus can, at no game cost. For every recorded position this ranks the
legal actions:

  - shipped (no phantom)
  - phantom everywhere (card_state says 'unseen' for the China Card)
  - phantom inside ONE consumer of card_state at a time, the rest shipped

and records what each changes: the top action, the ordering, and the stage
values along the chain (the unseen pool, `vp_value`, `ops_value(1..4)`,
event values of the cards in hand). The consumer whose phantom alone
reproduces the top-action changes of the full phantom is where the points
live. Attribution is by caller: under Python 3.12 comprehensions are inlined
(PEP 709), so the frame that calls `card_state` is the consumer itself.

Not a strength measurement. It says which code paths the phantom moves
decisions through, not whether those decisions were better.

    python scripts/phantom_trace.py --workers 4 --stride 1
"""
from __future__ import annotations

import argparse
import collections
import gzip
import json
import multiprocessing
import statistics
import sys

from struggler.bots.strategic import StrategicPlayer, StrategicWeights, policy, public_cards
from struggler.bots.strategic.defcon import SurvivalPrior
from struggler.engine import Engine, Side

CORPUS = 'tests/corpus/positions.json.gz'
CHINA = 'The_China_Card'
CONSUMERS = ('_unseen_holds', '_reply_budgets', '_hand_attack_value',
             '_hand_upgrade_value', '_ops_modifier_value')
REAL = public_cards.card_state


def _install(mode):
    """mode: None (shipped), 'all', or a consumer name."""
    if mode is None:
        fn = REAL
    elif mode == 'all':
        def fn(obs, card):
            return 'unseen' if card == CHINA else REAL(obs, card)
    else:
        def fn(obs, card):
            if card == CHINA and sys._getframe(1).f_code.co_name == mode:
                return 'unseen'
            return REAL(obs, card)
    public_cards.card_state = fn
    policy.card_state = fn


def _measure(rec, mode):
    _install(mode)
    try:
        engine = Engine.deserialize(rec['engine'])
        side = Side(rec['side'])
        obs = engine.observe(side)
        bot = StrategicPlayer(StrategicWeights(**rec['weights']), survival_prior=SurvivalPrior(**rec['prior']))
        ranked = [a.payload for _, a in bot.rank_actions(obs)]
        unseen = sum(1 for c in public_cards.CARDS if public_cards.card_state(obs, c) == 'unseen')
        return {
            'ranking': ranked, 'unseen': unseen, 'vp': bot.vp_value(obs),
            'ops': [bot.ops_value(obs, n) for n in (1, 2, 3, 4)],
            'events': {c: bot.event_value(obs, c) for c in obs.hand
                       if c != CHINA and not public_cards.CARDS[c].scoring}}
    finally:
        _install(None)


def _record(args):
    i, rec = args
    out = {'i': i, 'kind': rec.get('kind') or Engine.deserialize(rec['engine']).pending_decision.kind.value}
    for mode in (None, 'all', *CONSUMERS):
        out[mode or 'shipped'] = _measure(rec, mode)
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--workers', type=int, default=4)
    ap.add_argument('--stride', type=int, default=1)
    ap.add_argument('--out', default='logs/phantom-trace.json')
    args = ap.parse_args(argv)
    with gzip.open(CORPUS) as f:
        records = json.loads(f.read())['records'][::args.stride]
    with multiprocessing.Pool(args.workers) as pool:
        rows = list(pool.imap_unordered(_record, list(enumerate(records)), chunksize=4))
    rows.sort(key=lambda r: r['i'])
    with open(args.out, 'w') as f:
        json.dump(rows, f)

    n = len(rows)
    base = [r['shipped'] for r in rows]
    print(f'{n} corpus positions\n')

    def rel(a, b):
        return abs(a - b) / max(abs(b), 1e-9)

    print(f"{'mode':22}{'top changed':>12}{'order changed':>15}{'vp moved':>10}{'ops(1) moved':>14}"
          f"{'median |dvp|/vp':>17}{'agrees with all':>17}")
    full_top = {r['i'] for r in rows if r['all']['ranking'][0] != r['shipped']['ranking'][0]}
    for mode in ('all', *CONSUMERS):
        top = {r['i'] for r in rows if r[mode]['ranking'][0] != r['shipped']['ranking'][0]}
        order = sum(1 for r in rows if r[mode]['ranking'] != r['shipped']['ranking'])
        vp = [rel(r[mode]['vp'], r['shipped']['vp']) for r in rows]
        ops1 = sum(1 for r in rows if r[mode]['ops'][0] != r['shipped']['ops'][0])
        overlap = f'{len(top & full_top)}/{len(full_top)}' if mode != 'all' else '-'
        print(f'{mode:22}{len(top):>12}{order:>15}{sum(v > 0 for v in vp):>10}{ops1:>14}'
              f'{statistics.median(vp):>17.4f}{overlap:>17}')

    print('\nunseen pool size, shipped vs phantom (median):',
          statistics.median(b['unseen'] for b in base), 'vs',
          statistics.median(r['all']['unseen'] for r in rows))
    kinds = collections.Counter(r['kind'] for r in rows if r['i'] in full_top)
    print('full-phantom top-action changes by decision kind:', dict(kinds))
    moved = collections.Counter()
    for r in rows:
        for c, v in r['shipped']['events'].items():
            # `!=`, not a difference: a certain outcome is the LOSS/WIN
            # sentinel, which refuses arithmetic on purpose but compares.
            if r['all']['events'].get(c, v) != v:
                moved[c] += 1
    print('event values the phantom moves most often (card: positions):', moved.most_common(10))
    print('\nNot a strength measurement: it attributes decision changes to code paths.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
