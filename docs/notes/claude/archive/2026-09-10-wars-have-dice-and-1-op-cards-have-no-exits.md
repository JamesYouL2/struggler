# Wars have dice, and 1-Op cards have no exits

Two qualifiers from the maintainer that change the exposure table above.

**"And wars have dice."** Every war card is `win_from=4`, so the attacker
needs a 4+ on a d6: **50% before penalties**, and −1/6 for every country
adjacent to the target that the *defender* controls, plus the target
itself where the card counts it (Arab-Israeli does). Brush War is
`win_from=3`, so 67%.

So the war cards are not wipes. They are coin flips that the defender can
push below even by holding the neighbourhood -- which is a real strategic
difference, and the only member of the eviction class that responds to
defence at all. That splits the table in two:

| | Certain | Probabilistic |
| --- | --- | --- |
| Cards | Nasser, Sadat, Blockade, Truman, Muslim Revolution, Warsaw Pact, De Gaulle, Iranian Hostage, Iron Lady, Marine Barracks, Ortega | Korean, Arab-Israeli, Indo-Pakistani, Iran-Iraq (50%), Brush War (67%) |

And it isolates Egypt completely: of the five two-sided Battlegrounds,
India, Pakistan, Iran and Iraq are two-sided only through **war cards at
50%**. Egypt is the only Battleground on the map facing a **certain
one-Op eviction from both sides** -- Nasser against the US, Sadat against
the USSR. That is the whole reason it alone drops to adjacency and
urgency value.

**"Getting rid of 1-Op cards is like 10x harder than 2-Op cards."** It is
stronger than that: every exit is closed, not merely dearer.

| Exit | Minimum Ops |
| --- | ---: |
| Space race, boxes 1-4 | **2** |
| Space race, boxes 5-8 | 3 to 4 |
| Quagmire / Bear Trap discard | **2** (`core.py` `_payable_cards`) |
| Blockade / Latin American Debt Crisis payment | 3 |

**A 1-Op card cannot be spaced, cannot be thrown to a trap, and cannot
pay a discard clause.** The only way out is to play it, which fires the
event if it is the opponent's. This is the maintainer's very first
correction of the session -- "you generally can't space Lone Gunman" --
as a general rule rather than a fact about one card.

The fourteen cards with no exit:

| Side | Cards |
| --- | --- |
| USSR | **Lone Gunman**, Blockade, Nasser, Romanian Abdication, Allende |
| US | **CIA Created**, Truman Doctrine, Kitchen Debates, Panama Canal, OAS Founded, Sadat |
| Neutral | Captured Nazi Scientist, UN Intervention, Summit |

Forty cards sit at 2 Ops with every exit open. Two of the no-exit cards,
**Lone Gunman and CIA Created**, are on the maintainer's safe-window list,
and they are the two the planner was found scoring at 0.00 risk.

**And the exits are computed on the *modified* Ops** (`_effective_ops`,
FAQ 7.4), which cuts both ways: Containment or Brezhnev can lift a 1-Op
card to 2 and open every exit, while **Red Scare/Purge can strand a 2-Op
card at 1 and close them all**. Using an Ops modifier to trap an opponent's
card is a line the bot has no way to see.
