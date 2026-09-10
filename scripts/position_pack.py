"""Generate the annotated position pack: the one instrument that sees a
mistake both sides make.

The mirror gate plays the bot against itself, so a move that is wrong for
both seats cancels out and scores 0.500 -- which is how the bot declined
every free Coup for its entire existence without a single gate noticing.
It also needs ~96 seeds to resolve a six-point swing. Annotated positions
see both.

Two parts, because the maintainer has to answer two different kinds of
question:

  A. Calibration boards. Real boards at the start of turn 4 with the
     scoring cards still in the deck -- the one point where a flat
     per-Battleground table is even coherent, since that is when the three
     Mid War regions stop being discounted and all six weigh the same.
     Every row is pre-filled with what the bot currently believes, in VP,
     so the job is to correct the wrong ones rather than price 26 blanks.

  B. Decisions. Positions where the bot's top two choices are close enough
     that the ranking is doing real work, with its own scores shown. Mark
     the better move and one line of why.

    uv run python scripts/position_pack.py --out docs/POSITION_PACK.md
"""
from __future__ import annotations

import argparse
import gzip
import json
import pathlib
import sys

from struggler.bots.strategic import StrategicPlayer, StrategicWeights
from struggler.bots.strategic.defcon import SurvivalPrior
from struggler.engine import Engine, Region, Side

CALIBRATION_TURN = 4  # the maintainer's calibration point, and the only turn
# at which a flat per-Battleground table is coherent: it is where the three
# Mid War regions stop being discounted (0.51 at turn 1, 0.80 at turn 3, 1.64
# at turn 4) and all six weigh the same. The parity corpus captures turns
# 1/3/5/7/9 only, so these boards are played fresh rather than read from it.


def play_to_turn(seed: int, turn: int = CALIBRATION_TURN) -> Engine | None:
    """A real board at the start of `turn`, from a self-played game."""
    engine = Engine.new_game(seed=seed, setup_bonus=True)
    bots = {Side.US: StrategicPlayer(), Side.USSR: StrategicPlayer()}
    while not engine.is_terminal:
        if engine.turn >= turn and engine.action_round >= 1:
            return engine
        d = engine.pending_decision
        if d.actor is Side.CHANCE:
            engine.step(d.options[0])
            continue
        engine.step(bots[d.actor].choose_action(engine.observe(d.actor), list(d.options)))
    return None

CORPUS = pathlib.Path(__file__).parent.parent / 'tests' / 'corpus' / 'positions.json.gz'
SCORING = ('Europe_Scoring', 'Asia_Scoring', 'Middle_East_Scoring', 'Africa_Scoring',
           'Central_America_Scoring', 'South_America_Scoring', 'Southeast_Asia_Scoring')
REGION_ORDER = (Region.EUROPE, Region.ASIA, Region.MIDDLE_EAST, Region.AFRICA,
                Region.CENTRAL_AMERICA, Region.SOUTH_AMERICA)


def _bot(record) -> StrategicPlayer:
    return StrategicPlayer(StrategicWeights(**record['weights']),
                           survival_prior=SurvivalPrior(**record['prior']))


def render_board(engine: Engine) -> str:
    """Region by region, only the countries anyone holds. `*` marks a
    Battleground, `[US]`/`[SU]` who controls it."""
    out = []
    for region in REGION_ORDER:
        rows = []
        for cid, info in engine.board.countries.items():
            if info.region is not region:
                continue
            inf = engine.board.influence[cid]
            if not (inf['US'] or inf['USSR']):
                continue
            ctrl = engine.board.control(cid)
            tag = '[US]' if ctrl is Side.US else '[SU]' if ctrl is Side.USSR else '    '
            rows.append(f"  {'*' if info.battleground else ' '}{cid:22} "
                        f"US {inf['US']}  SU {inf['USSR']}  (stab {info.stability}) {tag}")
        if rows:
            out.append(f'{region.name}')
            out.extend(rows)
    return '\n'.join(out)


def scoring_left(engine: Engine) -> list[str]:
    gone = set(engine.discard_pile) | set(getattr(engine, 'removed_cards', ()) or ())
    return [c for c in SCORING if c not in gone]


def battleground_table(engine: Engine, side: Side) -> str:
    """Every Battleground, with the bot's own valuation converted to VP.

    `country_value` is in board units where one Op is worth roughly 28, so
    it is divided by the bot's price of a VP to land on a scale the
    maintainer can answer in.
    """
    obs = engine.observe(side)
    bot = StrategicPlayer(StrategicWeights())
    bot.rank_actions(obs)
    vp = bot.vp_value(obs) or 1.0
    lines = ['| Battleground | Region | Holder | Bot says (VP) | Your VP | Note |',
             '| --- | --- | --- | ---: | ---: | --- |']
    for region in REGION_ORDER:
        for cid, info in engine.board.countries.items():
            if info.region is not region or not info.battleground:
                continue
            ctrl = engine.board.control(cid)
            holder = 'US' if ctrl is Side.US else 'USSR' if ctrl is Side.USSR else '--'
            worth = bot.country_value(bot.board, cid, side) / vp
            lines.append(f'| {cid} | {region.name.title().replace("_"," ")} | {holder} '
                         f'| {worth:.1f} |  |  |')
    return '\n'.join(lines)


def option_lines(record, bot: StrategicPlayer, limit: int = 6) -> list[str]:
    """The bot's ranking, with the margin between the top two spelled out --
    that margin is the whole reason the position is in the pack."""
    ranked = record['ranking'][:limit]
    lines = []
    for i, entry in enumerate(ranked, 1):
        payload = entry['payload']
        label = ', '.join(f'{k}={v}' for k, v in payload.items() if v is not None)
        score = entry['key'][-1]
        lines.append(f'{i:>2}. {label:<44} {score:>12.2f}{"   <- the bot plays this" if i == 1 else ""}')
    return lines


def closeness(record) -> float:
    """How close the top two are, relative to the top score. Small means the
    ranking is deciding something delicate; a runaway first place is not
    worth an expert's time."""
    r = record['ranking']
    if len(r) < 2:
        return 1e9
    a, b = r[0]['key'][-1], r[1]['key'][-1]
    return abs(a - b) / max(1.0, abs(a))


# Below this the two choices are the same number to the bit, which is not a
# close call: it is the bot expressing no preference and the engine's option
# order deciding. Those belong in Part C, as defects, not in front of an
# expert -- asking someone to break a tie the bot never saw wastes the one
# instrument that can see what the mirror gate cannot.
TIE = 1e-9


def pick_decisions(records, want=12):
    """Genuinely close calls -- close enough that the ranking is deciding
    something, far enough apart that it decided at all -- spread across
    decision kinds and turns so the pack is not twelve of one placement."""
    scored = sorted((r for r in records
                     if len(r['ranking']) >= 2 and closeness(r) > TIE),
                    key=closeness)
    picked, seen = [], {}
    for r in scored:
        bucket = (r['kind'], r['turn'])
        if seen.get(bucket, 0) >= 2:
            continue
        seen[bucket] = seen.get(bucket, 0) + 1
        picked.append(r)
        if len(picked) >= want:
            break
    return sorted(picked, key=lambda r: (r['seed'], r['turn'], r['action_round']))


def exact_ties(records):
    """Positions where the top two score identically, grouped by decision
    kind. The bot is indifferent and the engine's tuple order decides, which
    is the same shape as the free-Coup defect and the branch choices in
    `docs/EXPERT_ASKS.md` item 5."""
    out = {}
    for r in records:
        if len(r['ranking']) >= 2 and closeness(r) <= TIE:
            out.setdefault(r['kind'], []).append(r)
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--out', default='docs/POSITION_PACK.md')
    ap.add_argument('--decisions', type=int, default=12)
    ap.add_argument('--boards', type=int, default=2)
    args = ap.parse_args(argv)

    records = json.loads(gzip.open(CORPUS).read())['records']

    doc = [
        '# Annotated position pack',
        '',
        'Generated by `scripts/position_pack.py` from the parity corpus. Two',
        'parts, two different questions. Partial answers are useful: every row',
        'left blank simply keeps the bot\'s current number.',
        '',
        '**Why this exists.** The gate plays the bot against itself, so a move',
        'that is wrong for *both* seats scores a dead heat -- which is how the',
        'bot declined every free Coup for its entire existence unnoticed. And it',
        'needs about 96 seeds to resolve a six-point swing. This pack is the only',
        'instrument that sees either.',
        '',
    ]

    # -- Part A ------------------------------------------------------------
    doc += ['## Part A -- calibration boards', '',
            'Real boards with the scoring cards still live. Every Battleground row',
            'is pre-filled with what the bot believes today, converted to VP.',
            '**Correct the ones that are wrong and leave the rest.** The residual',
            'is what gets fitted.', '']

    # Played fresh: the corpus holds turns 1/3/5/7/9 and the calibration point
    # is turn 4. Seeds are tried in order and only boards with every scoring
    # card still live are kept, since that is the condition the maintainer set.
    boards, tried, skipped = [], 0, []
    for seed in range(4000, 4000 + 12):
        tried += 1
        engine = play_to_turn(seed)
        if engine is None:
            continue
        left = scoring_left(engine)
        if len(left) < 7:
            skipped.append((seed, len(left)))
            print(f'seed {seed}: only {len(left)} scoring cards live, skipped',
                  file=sys.stderr)
            continue
        boards.append((seed, engine))
        if len(boards) >= args.boards:
            break
    if skipped:
        doc += [f'*A board with all seven scoring cards still live at turn 4 is '
                f'uncommon: {len(boards)} of {tried} seeds qualified, the rest '
                f'having already played one or two '
                f'({", ".join(f"seed {s}: {n} live" for s, n in skipped)}). '
                f'Worth knowing, since the calibration point assumes a board that '
                f'most games have already left.*', '']

    for n, (seed, engine) in enumerate(boards, 1):
        left = scoring_left(engine)
        doc += [f'### Board {n} -- seed {seed}, turn {engine.turn} '
                f'action round {engine.action_round}',
                '',
                f'- VP **{engine.vp:+d}** (positive is US), DEFCON **{engine.defcon}**',
                f'- Military Ops: US {engine.military_ops["US"]}, USSR {engine.military_ops["USSR"]}',
                f'- Space race: US {engine.space_race["US"]}, USSR {engine.space_race["USSR"]}',
                f'- Scoring still live ({len(left)} of 7): '
                + (', '.join(c.replace('_Scoring', '').replace('_', ' ') for c in left) or 'none'),
                '',
                '```', render_board(engine), '```', '',
                battleground_table(engine, Side.US), '',
                '> Anything else about this board that changes the numbers:', '', '']

    # -- Part B ------------------------------------------------------------
    doc += ['## Part B -- decisions', '',
            'Positions where the bot\'s top two are close, so the ranking is doing',
            'real work. Scores are the bot\'s internal units, where one Op is worth',
            'roughly 28 -- their *order* is the question, not their size.', '']

    for n, rec in enumerate(pick_decisions(records, args.decisions), 1):
        engine = Engine.deserialize(rec['engine'])
        side = Side(rec['side'])
        bot = _bot(rec)
        hand = [c for c in engine.hands[side.value]]
        doc += [f'### Decision {n} -- seed {rec["seed"]}, turn {engine.turn} '
                f'action round {engine.action_round}, **{side.value} to move**',
                '',
                f'- Decision: `{rec["kind"]}`'
                + (f', context {rec["context"]}' if rec.get('context') else ''),
                f'- VP **{engine.vp:+d}** (positive is US), DEFCON **{engine.defcon}**',
                f'- Hand: {", ".join(hand) or "(empty)"}',
                f'- Top two differ by {closeness(rec)*100:.1f}%',
                '',
                '```', render_board(engine), '```',
                '', 'The bot\'s ranking:', '', '```'] + option_lines(rec, bot) + ['```', '',
                '> **Better move:**', '',
                '> **Why (one line):**', '', '']

    # -- Part C ------------------------------------------------------------
    ties = exact_ties(records)
    n_ties = sum(len(v) for v in ties.values())
    doc += ['## Part C -- where the bot is indifferent (not for the expert)',
            '',
            f'**{n_ties} of {len(records)} corpus positions '
            f'({100*n_ties/max(1,len(records)):.0f}%) have a top two that score '
            'identically to the bit.** The ranking is not choosing; the engine\'s '
            'option order is. This is the shape of the free-Coup defect and of the '
            'branch choices in `docs/EXPERT_ASKS.md` item 5, and it is work for me, '
            'not a question for anyone. Listed so the count is tracked rather than '
            'rediscovered.',
            '',
            '| Decision kind | Positions | Example |',
            '| --- | ---: | --- |']
    for kind, rs in sorted(ties.items(), key=lambda kv: -len(kv[1])):
        r = rs[0]
        top = ', '.join(str(v) for v in r['ranking'][0]['payload'].values() if v is not None)
        second = ', '.join(str(v) for v in r['ranking'][1]['payload'].values() if v is not None)
        doc += [f'| `{kind}` | {len(rs)} | seed {r["seed"]} T{r["turn"]} '
                f'AR{r["action_round"]}: {top} = {second} at '
                f'{r["ranking"][0]["key"][-1]:.2f} |']
    doc += ['']

    out = pathlib.Path(args.out)
    out.write_text('\n'.join(doc))
    print(f'{len(boards)} boards + {args.decisions} decisions -> {out}')


if __name__ == '__main__':
    sys.exit(main())
