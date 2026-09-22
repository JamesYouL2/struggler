"""The turn's card assignment: one headline, R rounds, space, UN, holds.

Shape (a) of `docs/notes/pi/2026-09-22-assignment-planner-design.md`:
**separable prices, exact constraints.** The per-card prices this project
has calibrated (`card_play_value`, the headline price, `space_value`,
`value_as_held`, `_non_firing_value`) arrive here unchanged; what this
module adds is that the turn's allocation is *solved* -- one objective
over one hand -- instead of tie-broken card by card. That is what makes
"space the Soviet card I cannot answer, or hold it and eat a smaller
event next turn" an expressible trade.

The problem, exactly (the whole-hand planner note's table):

    max   sum of value(card, slot) + value(held)
    s.t.  one headline; R round units; at most one UN unit (the UN
          Intervention card plus one opponent card, consumed together in
          one round); each space unit consumes its policy pick and its
          round; every remaining card is held; a scoring card is NEVER
          held.

Solved by DP over subsets: a hand is 8-9 cards and a turn 6-7 rounds, so
(mask, slot, un_used, space_used) is ~58k states and the answer is exact
-- no heuristic inside the allocation, only in the prices fed to it.

Pure by contract, like `evaluator.py`: this module imports nothing from
the engine or the evaluator and owns no state. The caller (policy, behind
`weights.hand_assignment`) builds the price table; a test can check the
solver's arithmetic exactly.

Rulings carried here (2026-09-20, the whole-hand planner note):

- **Ruling 1** -- the second space slot is opened by a die roll, so
  `plan_hand` solves once per slot count and returns a probability-
  weighted list of allocations rather than one plan.
- **Ruling 4** -- the space unit goes to "the worst opponent card the
  Space Race accepts": the caller passes those picks (`space_keys`); the
  solver only decides whether and when to spend the slot.
- **Ruling 5** -- scoring timing comes from the plan, not a constant:
  a scoring card's price in round k carries the gains the plan's own
  earlier plays make to its region (`plan_hand`'s fixed point).
- **Ruling 2** -- `DefconPlanner` is untouched and keeps its veto on
  hazard hands; subsuming it is a later step, measured on the corpus.
"""
from __future__ import annotations

import dataclasses
from functools import lru_cache

NEG = float('-inf')

# A round unit, as it appears in Assignment.rounds:
#   ('play', key)          -- the card as an ordinary play in that round
#   ('space', key)         -- the card spent on a space attempt
#   ('un', key, partner)   -- UN Intervention paired with `partner`
Unit = tuple


@dataclasses.dataclass(frozen=True)
class Card:
    """One card's prices. `NEG` (minus infinity) marks an ineligible
    slot; a candidate that reaches for it is poisoned rather than
    ranked, which is what eligibility should do."""

    key: str
    headline: float = NEG
    play: tuple[float, ...] = ()  # per round index: price as an ordinary play
    space: float = NEG
    un_play: float = NEG  # UN Intervention's unit value (clean Ops)
    un_partner: float = NEG  # value of pairing THIS card (suppressing its event)
    hold: float = 0.0
    may_hold: bool = True  # False for scoring cards: they are never held


@dataclasses.dataclass(frozen=True)
class Assignment:
    headline: str | None
    rounds: tuple[Unit, ...]
    holds: tuple[str, ...]
    value: float


@dataclasses.dataclass(frozen=True)
class WeightedPlan:
    """One allocation with the probability its space-slot count realises
    (ruling 1's two-solve approximation)."""

    probability: float
    slots: int
    assignment: Assignment


def _unit_price(card: Card, round_index: int) -> float:
    if round_index < len(card.play):
        return card.play[round_index]
    return NEG


def solve_hand(
    cards: tuple[Card, ...] | list[Card],
    rounds: int,
    *,
    headline_slots: int = 1,
    un_key: str | None = None,
    space_keys: tuple[str, ...] = (),
) -> Assignment | None:
    """The exact best allocation, or None when the constraints cannot be
    met (more scoring cards than play slots, or no eligible fill for some
    slot). The caller then keeps its per-card behaviour; a plan is
    allowed to decline, never to crash.

    `space_keys` are ruling 4's policy picks in slot order; a pick may
    still be played or held -- the solver only knows that IF the j-th
    space slot is spent, it spends that card. `un_key` is the UN
    Intervention card; its partner is chosen here from the cards priced
    as pairable (`un_partner`).
    """
    by_key = {c.key: c for c in cards}
    ordered = tuple(sorted(by_key.values(), key=lambda c: c.key))
    n = len(ordered)
    if n > 24:  # 2**24 states is the outer edge of "tiny"
        return None
    space_index = {key: j for j, key in enumerate(space_keys)}
    total_slots = headline_slots + rounds

    # state: (mask, slot, un_used, space_used) -> (best value, choice)
    # choice: ('holds',) | ('play', i) | ('space', i) | ('un', i, j)
    @lru_cache(maxsize=None)
    def best(mask: int, slot: int, un_used: int, space_used: int):
        if slot == total_slots:
            value = 0.0
            for i, card in enumerate(ordered):
                if not mask >> i & 1:
                    if not card.may_hold:
                        return (NEG, None)  # a scoring card would be held
                    value += card.hold
            return (value, ('holds',))
        round_index = slot - headline_slots  # < 0 on the headline slot
        top_value, top_choice = NEG, None

        def offer(candidate: float, choice) -> None:
            nonlocal top_value, top_choice
            if candidate > top_value:
                top_value, top_choice = candidate, choice

        for i, card in enumerate(ordered):
            if mask >> i & 1:
                continue
            bit = 1 << i
            if round_index < 0:  # the headline slot
                if card.headline > NEG:
                    rest, _ = best(mask | bit, slot + 1, un_used, space_used)
                    if rest > NEG:
                        offer(card.headline + rest, ('play', i))
                continue
            price = _unit_price(card, round_index)
            if price > NEG:
                rest, _ = best(mask | bit, slot + 1, un_used, space_used)
                if rest > NEG:
                    offer(price + rest, ('play', i))
            if card.space > NEG and space_index.get(card.key) == space_used:
                rest, _ = best(mask | bit, slot + 1, un_used, space_used + 1)
                if rest > NEG:
                    offer(card.space + rest, ('space', i))
            if card.un_play > NEG and not un_used:
                for j, partner in enumerate(ordered):
                    if mask >> j & 1 or j == i or partner.un_partner <= NEG:
                        continue
                    rest, _ = best(mask | bit | (1 << j), slot + 1, 1, space_used)
                    if rest > NEG:
                        offer(card.un_play + partner.un_partner + rest,
                              ('un', i, j))
        return (top_value, top_choice)

    total, _ = best(0, 0, 0, 0)
    if total <= NEG:
        return None

    # Walk the memoised argmax choices back into an Assignment.
    mask, slot, un_used, space_used = 0, 0, 0, 0
    headline: str | None = None
    round_units: list[Unit] = []
    while slot < total_slots:
        _, choice = best(mask, slot, un_used, space_used)
        if choice is None:  # unreachable: total was feasible
            return None
        if choice[0] == 'play':
            i = choice[1]
            card = ordered[i]
            if round_index_is_headline(slot, headline_slots):
                headline = card.key
            else:
                round_units.append(('play', card.key))
            mask |= 1 << i
        elif choice[0] == 'space':
            i = choice[1]
            round_units.append(('space', ordered[i].key))
            mask |= 1 << i
            space_used += 1
        elif choice[0] == 'un':
            i, j = choice[1], choice[2]
            round_units.append(('un', ordered[i].key, ordered[j].key))
            mask |= (1 << i) | (1 << j)
            un_used = 1
        slot += 1
    holds = tuple(c.key for i, c in enumerate(ordered) if not mask >> i & 1)
    return Assignment(headline, tuple(round_units), holds, total)


def round_index_is_headline(slot: int, headline_slots: int) -> bool:
    """The headline slot is slot 0 when there is one (the turn table's
    'exactly 1')."""
    return headline_slots > 0 and slot == 0


def plan_hand(
    cards: tuple[Card, ...] | list[Card],
    rounds: int,
    *,
    headline_slots: int = 1,
    un_key: str | None = None,
    space_keys: tuple[str, ...] = (),
    space_slot_weights: tuple[tuple[int, float], ...] = ((1, 1.0),),
    gain: dict[str, float] | None = None,
    max_passes: int = 3,
) -> tuple[WeightedPlan, ...] | None:
    """Rulings 1 and 5 on top of the solver.

    Ruling 1: solve once per space-slot count and return each allocation
    weighted by P(that count realises) -- the cheap approximation, exact
    if nothing else in the turn depends on the roll.

    Ruling 5: a scoring card (`may_hold=False`) priced flat by the
    caller has its round-k price uplifted by the gains the plan's own
    rounds j < k make to its region (`gain`, the caller's per-card
    number; only ordinary plays carry gain). The uplift depends on the
    assignment, so it is a fixed point: solve, re-price, re-solve, until
    the prices stop changing (`max_passes` caps it). This is what
    replaces `+2 x action_round`.

    Returns None only if every slot count is infeasible.
    """
    plans: list[WeightedPlan] = []
    for slots, probability in space_slot_weights:
        picks = tuple(space_keys[: max(slots, 0)])
        current = tuple(cards)
        assignment: Assignment | None = None
        for _ in range(max(1, max_passes)):
            assignment = solve_hand(
                current, rounds,
                headline_slots=headline_slots, un_key=un_key, space_keys=picks)
            if assignment is None or not gain:
                break
            # What the plan's own plays before round k add to a scoring
            # region: `planned[k]`, from this assignment's rounds.
            planned = [0.0] * (rounds + 1)
            running = 0.0
            for k, unit in enumerate(assignment.rounds):
                planned[k] = running
                if unit[0] == 'play':
                    running += gain.get(unit[1], 0.0)
            rebuilt: list[Card] = []
            stable = True
            for card in current:
                if card.may_hold or not card.play:
                    rebuilt.append(card)
                    continue
                base = card.play[0]  # the caller prices scoring cards flat
                new_play = tuple(base + (planned[k] if k < len(planned) else 0.0)
                                 for k in range(len(card.play)))
                if new_play != card.play:
                    stable = False
                rebuilt.append(dataclasses.replace(card, play=new_play))
            if stable:
                break
            current = tuple(rebuilt)
        if assignment is not None:
            plans.append(WeightedPlan(probability, slots, assignment))
    return tuple(plans) if plans else None
