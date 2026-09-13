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
held out and scored. The file's own `tolerance_ops` is the bar the bot is
held to, so it is the bar the model is held to.

This never writes `expert_valuations.json`. The maintainer's valuations are
the reference standard for this project; proposals land in a separate file
with the bot's current number beside them, to be accepted one at a time.

    python scripts/harvest_card_valuations.py --dry-run
    python scripts/harvest_card_valuations.py --out logs/harvest.json
"""
from __future__ import annotations

import argparse
import json
import random
import statistics
import sys

from struggler.engine import Side
from struggler.bots.benchmark import opening_board, to_ops
from struggler.bots.strategic import StrategicPlayer
from struggler.bots.strategic.public_cards import CARDS
from struggler.bots.llm.board_report import build_board_report
from struggler.bots.llm.client import LLMMessage, LLMRequest, StructuredOutputSpec

VALUATIONS = 'models/expert_valuations.json'

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


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--seed', type=int, default=4000, help='must match the file\'s board')
    ap.add_argument('--examples', type=int, default=8, help='worked examples shown to the model')
    ap.add_argument('--split-seed', type=int, default=1, help='which priced cards become examples')
    ap.add_argument('--out', default='logs/harvest-card-valuations.json')
    ap.add_argument('--dry-run', action='store_true',
                    help='build everything and print one prompt; no API call, no key needed')
    ap.add_argument('--limit', type=int, default=0, help='only price this many unpriced cards')
    args = ap.parse_args(argv)

    with open(VALUATIONS) as f:
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
    from main import build_llm_client
    client = build_llm_client()

    def ask(cid):
        try:
            resp = client.complete(build_request(system, cid))
            return float(resp.structured['ops']), str(resp.structured.get('note', '')), None
        except Exception as exc:
            return None, '', f'{type(exc).__name__}: {exc}'

    print(f'scoring {len(held)} held-out cards against the reference...')
    errs, failures = [], 0
    rows = []
    for cid in held:
        got, note, err = ask(cid)
        if got is None:
            failures += 1
            print(f'  {cid:<40} FAILED  {err}')
            continue
        want = priced[cid]
        errs.append(abs(got - want))
        flag = ' <--' if abs(got - want) > tol else '    '
        rows.append((cid, want, got, note))
        print(f'  {cid:<40}{want:>+8.2f}{got:>+8.2f}{got - want:>+8.2f}{flag}')

    if not errs:
        print('\nNo held-out card was priced. Nothing can be said about the rest.')
        return 1
    mae = statistics.fmean(errs)
    within = sum(e <= tol for e in errs)
    print(f'\nHELD-OUT SCORE: MAE {mae:.2f} Ops, {within}/{len(errs)} inside the '
          f'{tol} tolerance, {failures} failed to answer')
    verdict = 'USABLE' if mae <= tol else 'NOT USABLE'
    print(f'  {verdict}: the bot is held to {tol} Ops on these same rows.')
    if mae > tol:
        print('  The proposals below are recorded but should not be accepted: a model '
              'that cannot reproduce the known valuations has not earned the unknown ones.')

    proposals = {}
    for i, cid in enumerate(unpriced, 1):
        got, note, err = ask(cid)
        botv = to_ops(bot.event_value(obs, cid), scale)
        proposals[cid] = {'ops': got, 'note': note, 'bot_ops': round(botv, 2), 'error': err}
        print(f'  [{i}/{len(unpriced)}] {cid:<40}'
              + (f'{got:>+8.2f}  (bot {botv:+.2f})' if got is not None else f'  FAILED {err}'))

    import os
    os.makedirs(os.path.dirname(args.out) or '.', exist_ok=True)
    with open(args.out, 'w') as f:
        json.dump({'board': expert['board'], 'unit': expert['unit'], 'tolerance_ops': tol,
                   'model': getattr(client, 'model_name', 'unknown'),
                   'held_out': {'mae': round(mae, 3), 'within_tolerance': within,
                                'n': len(errs), 'failed': failures, 'verdict': verdict},
                   'examples_shown': shown,
                   'held_out_rows': [{'card': c, 'expert': w, 'model': g, 'note': n}
                                     for c, w, g, n in rows],
                   'proposals': proposals}, f, indent=2)
    print(f'\n-> {args.out}')
    print('NOT written into models/expert_valuations.json. The maintainer\'s '
          'valuations are the reference standard; these are proposals to accept '
          'one at a time.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
