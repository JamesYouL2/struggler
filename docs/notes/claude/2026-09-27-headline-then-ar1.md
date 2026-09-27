# Headline, then AR1: the USSR's two moves in a row

> **Correction (2026-09-27, Astra's audit):** the USSR headline and USSR
> AR1 are NOT always consecutive. Headlines resolve higher Ops first, ties
> US first, so a higher-Ops USSR headline resolves, THEN the US headline,
> THEN USSR AR1. The next move after both headlines is still always the
> USSR's, but only a USSR headline that resolves second is immediately
> followed by its own AR1. A `headline_combo` must model the intervening
> US headline in the other case, without reading the hidden US hand.
> docs/notes/codex/2026-09-27-correctness-rust-readiness.md.

The maintainer's last question before MCTS (2026-09-27): **is there a
headline plus AR1 combo for the USSR, where the US does not get to see or
place Ops before the USSR's action round 1?**

## The rule that makes it a combo

The engine resolves the two headlines higher Ops first, ties US first
(`Engine._headline_resolution_order`), and **the USSR always acts first in
action round 1.** However the headlines fall, the next move after them is
the USSR's. So:

- **The USSR headline plus USSR AR1 are two consecutive USSR moves.** A
  headline that breaks, places or removes influence can be followed up
  (coup the broken country, finish a control, place where the event
  opened reach) before the US can answer on the board.
- **The US headline is followed by a USSR move.** Whatever the US
  headlines is exposed to an immediate answer, the case `reply_model`
  prices for placements, and it does not reach headlined events.

## What the bot does today

Nothing about either:

- **A headline is priced as one card:** `play_price` for `HEADLINE_PLAY` is
  the event's value minus half its Ops. It never asks what AR1 can do on
  the board the headline leaves.
- **Headline order is not modelled.** The opponent's headline is unknown and
  ignored, and the USSR's certain AR1 follow-up is not used.
- **The US headline's event is valued with no answer** (the event sandbox
  has no reply model), though a USSR move is certain to come next.

## The experiment, and whether it is easy

**Moderately easy: the pieces exist, and the cost is small.**

`headline_combo` (a weight, 0 off). For each USSR headline candidate `h`:

    value(h) += headline_combo * (V_AR1(board after h) - V_AR1(board now))

where `V_AR1` is what the USSR's best AR1 play is worth on that board, from
the hand without `h`.

- **The board after `h`** is the event sandbox's (`public_engine` +
  `_resolve_sandbox`), which already fires `h` on a public copy of the
  board. It has to hand the resulting board back, not just its value.
- **`V_AR1`**, cheap version: a helper player prepared on that board,
  asked `ops_value(max Ops in the remaining hand)`. That is the value of
  spending the best card's Ops, with no card ranking needed. The full
  version ranks every AR1 card play. Measured on corpus positions, a USSR
  headline or AR1 ranking takes about 0.1 s, so the full version costs
  about 8 headlines x 0.1 s per USSR headline: under a second a turn,
  single-digit percent of a game. The cheap version is nearly free.
- **The opponent's headline** is unknown and left out, as it is today.
  (Its Ops decide the order, but not who moves next.)

A second, smaller arm for the US side, `headline_reply` (0 off): charge a
US headline's placements for the USSR's certain next move, using the
existing `_survives_reply` / `_coup_reply` machinery on the post-headline
board.

**How it would be measured:**

1. **Positions first.** The annotated suite has no headline positions.
   The cheapest first step is 3-5 USSR headline decisions from self-play
   where the combo plausibly matters (a headline that breaks or places
   into a battleground with a coup- or placement-ready card in hand), for
   the maintainer to mark. They cost seconds to check and pin what "the
   combo" should choose.
2. **Then arms** against `v0.6.0`, 1024 seeds: `headline_combo` 0.5 and
   1.0 against 0, and `headline_reply` on its own. The rule is written
   before dispatch, as for the event-discount arms.

**What it cannot settle:** a 2-move lookahead for the USSR's opening pair
is a special case of search. MCTS would find these combos in general, for
any consecutive pair of moves. This experiment says whether the special
case is worth pricing before MCTS, and gives MCTS a baseline to beat.
