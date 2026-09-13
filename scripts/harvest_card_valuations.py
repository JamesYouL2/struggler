#!/usr/bin/env python
"""Ask a model to price the cards the maintainer has not priced yet.

`models/expert_valuations.json` holds 27 card valuations in US Ops on one
specific board -- "opening book, seed 4000, before the headline" -- and
`benchmark.expert_check` diffs the bot against them. 110 cards exist. The
remaining 83 are the backlog in docs/EXPERT_ASKS.md, and they are the one
job an LLM is plausibly better at than this bot: reading a card and saying
what it is worth. It needs ONE call per card, not 270 per game.

VALIDATION COMES FIRST AND IS THE POINT. A number for an unpriced card is
worth nothing unless the model can reproduce the priced ones, so the 27
known cards are split: a few are shown as worked examples, the REST are
held out and scored. The verdict is USABLE only when BOTH hold:

- coverage: every held-out card came back with a finite number
  (`MIN_COVERAGE`). A failed call, a NaN, an infinity or a non-number is a
  failure and counts against coverage -- it is never dropped from the score;
- tolerance: no held-out row is further than the file's `tolerance_ops`
  from the reference (`MAX_MISSES`). That is the per-row test
  `benchmark.expert_check` applies to the bot. The mean error is reported
  but decides nothing: an average lets one badly wrong card hide among
  exact ones.

This never writes `expert_valuations.json`. The maintainer's valuations are
the reference standard for this project; proposals land in a separate file
with the bot's current number beside them, to be accepted one at a time.

    python scripts/harvest_card_valuations.py --dry-run
    python scripts/harvest_card_valuations.py --out logs/harvest.json
"""
from __future__ import annotations

import argparse
import json
import math
import os
import random
import statistics
import sys
from pathlib import Path

from struggler.engine import Side
from struggler.bots.benchmark import opening_board, to_ops
from struggler.bots.strategic import StrategicPlayer
from struggler.bots.strategic.public_cards import CARDS
from struggler.bots.llm.board_report import build_board_report
from struggler.bots.llm.client import LLMMessage, LLMRequest, StructuredOutputSpec

ROOT = Path(__file__).resolve().parents[1]
VALUATIONS = ROOT / 'models' / 'expert_valuations.json'

# Every held-out card must be answered with a finite number. There are 19,
# so a single missing one is 5% of the evidence, and the misses are not a
# random sample: a refusal, a schema failure or a timeout is likelier on the
# awkward cards, which are the ones the check exists to test. The remedy for
# a flaky call is to retry the run, not to certify on what came back.
MIN_COVERAGE = 1.0
# Held-out rows allowed outside `tolerance_ops`. Zero: the reference is 19
# rows, and a model allowed to be wrong on some of them gives no way to tell
# which of its 83 proposals are the wrong ones.
MAX_MISSES = 0

SCHEMA = {
    'type': 'object',
    'additionalProperties': False,
    'required': ['ops', 'note'],
    'properties': {
        'ops': {'type': 'number',
                'description': 'The card\'s worth in US Ops, from the US seat. '
                               'Positive is good for the US; a USSR event is negative.'},
        'note': {'type': 'string',
                 'description': 'One sentence: what the number is made of.'},
    },
}
OUTPUT = StructuredOutputSpec(
    name='card_valuation',
    description='One card, priced in US Ops from the US seat.',
    schema=SCHEMA,
)


def card_text(cid: str) -> str:
    c = CARDS[cid]
    bits = [f'{c.name} (#{c.number}, {c.period.name.replace("_", " ").title()})',
            f'  side: {c.side.value}   ops: {c.ops}' +
            ('   SCORING CARD' if c.scoring else '') +
            ('   removed after event' if c.remove_after_event else '') +
            ('   event is optional' if c.optional else '')]
    if c.event_summary:
        bits.append(f'  event: {c.event_summary}')
    return '\n'.join(bits)


def build_request(system: str, cid: str) -> LLMRequest:
    ask = (f'Price this card.\n\n{card_text(cid)}\n\n'
           'Answer with its worth in US Ops on the board above, from the US seat.')
    return LLMRequest(system=system, messages=[LLMMessage(role='user', content=ask)],
                      output=OUTPUT, max_tokens=1000)


def parse_ops(structured) -> float:
    """The `ops` a response carries, or ValueError. Only a finite JSON number
    counts: a bool, a string (even a numeric one), NaN or an infinity is a
    failed answer, never an error of undefined size."""
    ops = structured['ops']
    if isinstance(ops, bool) or not isinstance(ops, (int, float)):
        raise ValueError(f'ops is not a number: {ops!r}')
    if not math.isfinite(ops):
        raise ValueError(f'ops is not finite: {ops!r}')
    return float(ops)


def score_held_out(held, priced, tol, ask, out=sys.stdout) -> dict:
    """Ask for every held-out card and judge the answers against the reference.

    `ask(cid)` returns `(ops, note, error)` with `ops` None on failure. The
    verdict is USABLE only if coverage reaches `MIN_COVERAGE` and at most
    `MAX_MISSES` answered rows are outside `tol`; see the module docstring.
    """
    rows, failures = [], []
    for cid in held:
        got, note, err = ask(cid)
        if got is None:
            failures.append({'card': cid, 'error': err})
            print(f'  {cid:<40} FAILED  {err}', file=out)
            continue
        want = priced[cid]
        miss = abs(got - want) > tol
        rows.append({'card': cid, 'expert': want, 'model': got, 'note': note,
                     'within_tolerance': not miss})
        flag = ' <--' if miss else '    '
        print(f'  {cid:<40}{want:>+8.2f}{got:>+8.2f}{got - want:>+8.2f}{flag}', file=out)

    n = len(held)
    errs = [abs(r['model'] - r['expert']) for r in rows]
    misses = sum(not r['within_tolerance'] for r in rows)
    coverage = len(rows) / n if n else 0.0
    usable = n > 0 and coverage >= MIN_COVERAGE and misses <= MAX_MISSES
    return {
        'verdict': 'USABLE' if usable else 'NOT USABLE',
        'criterion': (f'coverage >= {MIN_COVERAGE:.0%} of held-out cards answered with a '
                      f'finite number, and at most {MAX_MISSES} answered rows outside '
                      f'{tol} Ops (per row, as benchmark.expert_check counts misses)'),
        'n': n,
        'answered': len(rows),
        'failed': len(failures),
        'coverage': round(coverage, 3),
        'min_coverage': MIN_COVERAGE,
        'within_tolerance': len(rows) - misses,
        'misses': misses,
        'max_misses': MAX_MISSES,
        'mae': round(statistics.fmean(errs), 3) if errs else None,
        'max_error': round(max(errs), 3) if errs else None,
        'rows': rows,
        'failures': failures,
    }


def main(argv=None, client=None) -> int:
    """`client` is injectable for tests; by default the environment's LLM client."""
    ap = argparse.ArgumentParser()
    ap.add_argument('--valuations', default=str(VALUATIONS),
                    help='the reference valuations; read only, never written')
    ap.add_argument('--seed', type=int, default=4000, help='must match the file\'s board')
    ap.add_argument('--examples', type=int, default=8, help='worked examples shown to the model')
    ap.add_argument('--split-seed', type=int, default=1, help='which priced cards become examples')
    ap.add_argument('--out', default='logs/harvest-card-valuations.json')
    ap.add_argument('--dry-run', action='store_true',
                    help='build everything and print one prompt; no API call, no key needed')
    ap.add_argument('--limit', type=int, default=0, help='only price this many unpriced cards')
    args = ap.parse_args(argv)

    if os.path.realpath(args.out) == os.path.realpath(args.valuations):
        print(f'REFUSING: --out {args.out} is the reference valuations file. Proposals '
              'never overwrite or merge into the maintainer\'s values.', file=sys.stderr)
        return 2
    with open(args.valuations) as f:
        expert = json.load(f)
    if str(args.seed) not in expert['board']:
        print(f"REFUSING: --seed {args.seed} is not the board the file was priced on "
              f"({expert['board']!r}). The unit is board-specific; a number from a "
              f"different board is not comparable to anything.", file=sys.stderr)
        return 2

    engine, _ = opening_board(args.seed)
    obs = engine.observe(Side.US)
    bot = StrategicPlayer()
    bot.rank_actions(obs)
    scale = {n: bot.ops_value(obs, n) for n in (1, 2, 3, 4)}
    tol = expert.get('tolerance_ops', 0.5)

    priced = {cid: row['ops'] for cid, row in expert['cards'].items()
              if row.get('ops') is not None}
    rng = random.Random(args.split_seed)
    shown = sorted(rng.sample(sorted(priced), min(args.examples, len(priced) - 1)))
    held = sorted(set(priced) - set(shown))
    unpriced = sorted(set(CARDS) - set(priced))
    if args.limit:
        unpriced = unpriced[:args.limit]

    report = build_board_report(obs)
    examples = '\n\n'.join(
        f'{card_text(cid)}\n  VALUE: {priced[cid]:+.2f} US Ops'
        + (f'\n  because: {expert["cards"][cid].get("note", "")}' if expert['cards'][cid].get('note') else '')
        for cid in shown)
    system = (
        'You price Twilight Struggle cards for a bot\'s value function.\n\n'
        f'UNIT: {expert["unit"]}\n'
        f'BOARD: {expert["board"]}. Every valuation is on THIS board and no other.\n'
        f'SCALE on this board: 1 Op = {scale[1]:.1f} raw, 2 = {scale[2]:.1f}, '
        f'3 = {scale[3]:.1f}, 4 = {scale[4]:.1f} -- concave, so the 4th Op is worth '
        'less than the 1st.\n'
        f'TOLERANCE: {tol} Ops. A number inside that of the reference is correct.\n\n'
        'THE BOARD:\n' + report + '\n\nWORKED EXAMPLES, priced by a strong player:\n\n'
        + examples + '\n\n'
        'Price the card you are given the same way. A card whose event helps the '
        'USSR is NEGATIVE. Judge the card as held on this board, not its effect in '
        'the abstract: a big board effect that never lands is not value.'
    )

    print(f'board: {expert["board"]}   tolerance {tol} Ops   1 Op = {scale[1]:.1f} raw')
    print(f'priced {len(priced)}  ->  {len(shown)} shown as examples, {len(held)} HELD OUT for scoring')
    print(f'unpriced to harvest: {len(unpriced)} of {len(CARDS)} cards')
    print(f'system prompt: {len(system):,} chars\n')

    if args.dry_run:
        print('--- one request, verbatim ---')
        req = build_request(system, held[0] if held else unpriced[0])
        print(req.system[:1200] + '\n  [...]\n')
        print(req.messages[0].content)
        print('\n--- held out for scoring ---')
        print('  ' + ', '.join(held))
        print('\nDry run: nothing was sent. Re-run without --dry-run to call a model.')
        return 0

    # Imported late: it pulls in a vendor SDK that the test extra does not
    # install, and --dry-run must work without one.
    if client is None:
        from main import build_llm_client
        client = build_llm_client()

    def ask(cid):
        try:
            resp = client.complete(build_request(system, cid))
            return parse_ops(resp.structured), str(resp.structured.get('note', '')), None
        except Exception as exc:
            return None, '', f'{type(exc).__name__}: {exc}'

    print(f'scoring {len(held)} held-out cards against the reference...')
    score = score_held_out(held, priced, tol, ask)

    if not score['answered']:
        print('\nNo held-out card was priced. Nothing can be said about the rest.')
        return 1
    verdict = score['verdict']
    print(f"\nHELD-OUT SCORE: {score['answered']}/{score['n']} answered "
          f"({score['failed']} failed), {score['misses']} of them outside the {tol} "
          f"tolerance; MAE {score['mae']:.2f} Ops (reported, not the verdict)")
    print(f"  {verdict}: requires {score['criterion']}.")
    if verdict != 'USABLE':
        print('  The proposals below are recorded but should not be accepted: a model '
              'that has not reproduced every known valuation has not earned the unknown ones.')

    proposals = {}
    for i, cid in enumerate(unpriced, 1):
        got, note, err = ask(cid)
        botv = to_ops(bot.event_value(obs, cid), scale)
        proposals[cid] = {'ops': got, 'note': note, 'bot_ops': round(botv, 2), 'error': err}
        print(f'  [{i}/{len(unpriced)}] {cid:<40}'
              + (f'{got:>+8.2f}  (bot {botv:+.2f})' if got is not None else f'  FAILED {err}'))

    os.makedirs(os.path.dirname(args.out) or '.', exist_ok=True)
    held_out = {k: v for k, v in score.items() if k not in ('rows', 'failures')}
    with open(args.out, 'w') as f:
        json.dump({'board': expert['board'], 'unit': expert['unit'], 'tolerance_ops': tol,
                   'model': getattr(client, 'model_name', 'unknown'),
                   'held_out': held_out,
                   'examples_shown': shown,
                   'held_out_rows': score['rows'],
                   'held_out_failures': score['failures'],
                   'proposals': proposals}, f, indent=2)
    print(f'\n-> {args.out}')
    print('NOT written into models/expert_valuations.json. The maintainer\'s '
          'valuations are the reference standard; these are proposals to accept '
          'one at a time.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
