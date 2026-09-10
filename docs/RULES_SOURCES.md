# Rules sources

The arbiter for any rules question in this engine, in order of authority:

1. **The printed card face.** Card text beats everything, and the wording is
   load-bearing in ways that are easy to miss — "free Coup" versus "a Coup
   attempt using this card's Operations value" is the whole of whether a card
   advances the Military Operations track.
2. **[Twilight Struggle Deluxe Edition rules](https://www.gmtgames.com/living_rules/TS_Rules_Deluxe.pdf)**
   (GMT Games). The second-edition rules are at
   [TSRules2nd.pdf](https://www.gmtgames.com/living_rules/TSRules2nd.pdf);
   several cards were reworded between editions and the FAQ notes which.
3. **[FAQ v5](https://www.gmtgames.com/nnts/FAQv5.pdf)** — compiled from
   ConsimWorld and BoardGameGeek, "authorized as official by designer Jason
   Matthews". It settles most of what the card text leaves ambiguous.

`src/struggler/data/cards.json`'s `event_summary` fields are **not** a source.
They are hand-maintained paraphrases and they drift; `docs/LIMITATIONS.md`
says so. They have been both right when the code was wrong (Marine Barracks
Bombing) and wrong when the code was right (Che). Use them as a hint about
intent, never as evidence.

## Getting the text

The PDFs are GMT Games' copyrighted work and this repository is MIT-licensed,
so their text is not committed here. `scripts/extract_rules_pdf.py` pulls
readable text out of a locally downloaded copy using only the standard
library:

```
curl -o /tmp/ts-faq.pdf https://www.gmtgames.com/nnts/FAQv5.pdf
python scripts/extract_rules_pdf.py /tmp/ts-faq.pdf --faq | grep -i quagmire
```

Coverage is partial and worth knowing: the FAQ extracts to about 87 Q/A pairs
across 36 card sections, well short of the whole document, because some
streams do not decode. **Absence from the extract is not evidence that the
FAQ is silent.** Go to the PDF before concluding a question is unanswered.

## Rulings this engine's behaviour rests on

Each of these was checked against the source and is pinned by a test. They are
recorded because every one of them is a place where a plausible reading of the
code disagrees with the game, and several were defects until recently.

| Ruling | Source | Where it lives |
| --- | --- | --- |
| "Free coups from event cards do not count towards required military ops — see rule 8.2.5." Free also means the coup ignores DEFCON's geography restriction, but **not** its DEFCON degrade on a Battleground. | FAQ, under Tear Down This Wall | `resolve_free_op_choice` |
| Junta, Ortega and Tear Down This Wall print "free Coup". **Che does not** — it is an ordinary Coup using the card's Ops, and advances the track once per attempt. | Card faces; [Twilight Strategy on Che](https://twilightstrategy.com/2012/11/27/che/) ("Che earns you Mil Ops (unlike Junta)") | `begin_che_coup` |
| "When a card's Ops value is modified, does this apply for all purposes (Beartrap/Quagmire, coup rolls, Space Race, military ops credit)…? **A. Yes, it applies for all purposes.**" And the modification follows the player playing the card, not the card's own side. | FAQ §7.4 | `effective_ops`, `_trap_discard_candidates`, `_payable_cards` |
| A trapped player who has had Missile Envy played against them must discard it next "if its value has not been degraded by Red Scare/Purge" — the same rule from the other side. | FAQ, Missile Envy | `_trap_discard_candidates` |
| Containment and Brezhnev Doctrine raise Ops "to a maximum of 4"; Red Scare lowers "to a minimum of 1". No card has a printed value above 4, so the ceiling only ever caps a modifier. | Card faces | `effective_ops` |
| The Military Operations track runs 0–5; Ops past the top are not recorded. Matters because Arms Race compares the two sides' positions. | Board | `_add_military_ops` |
| UN Intervention "may not be played during headline phase" (second edition). A headline and an Action Round are different things. | FAQ, card #32 | `_push_headline` |
| We Will Bury You is cancelled only by UN Intervention "on the US's next Action Round" — "The US would cancel the effect… if UN Intervention was played in the first US action round." | Card face; FAQ | `_handle_play_mode`, `_next_play_index_for` |
| Events played on the Space Race do not occur (6.4.5) — Defectors on the Space Race earns the US nothing. | FAQ, Defectors | `_handle_play_mode` |
| The US playing the China Card cancels Formosan Resolution, **including** when it is played onto the Space Race. | FAQ, Formosan Resolution | `_file_card` |
| Formosan Resolution's Taiwan promotion applies during Final Scoring, not only to the Asia Scoring card. | FAQ, card #35 | `Board.scoring_overrides` |
| Southeast Asia "is scored normally as part of the Asian scoring card"; the Southeast Asia Scoring card scores only that subregion. | FAQ | `_score_southeast_asia` |
| A Realignment needs at least one enemy Influence in the target: "Despite previous rulings, at least one enemy influence must be present." | FAQ | `_usable_coup_realign_target` |
| The two superpower spaces "provide the same benefits as 'adjacent controlled countries' for the purposes of events, and realignments". So a war roll is -1 for the defender's own superpower next to the target, not only for its countries. The FAQ flags this under Brush War as "a REVERSAL of a previous ruling due to a change in the rules". | Rules §2.1.5; FAQ, Brush War | `_handle_war_roll`, `_realignment_bonus` |
| Shuttle Diplomacy "does not count for Final Scoring at the end of Turn 10", and does not affect Summit or Kitchen Debates. Formosan Resolution is the opposite: its Deluxe text adds "or during Final Scoring at the end of Turn 10". | FAQ, cards #73 and #35 | `_scoring_overrides`, `_finish_game` |
| We Will Bury You: "Unless UN Intervention is played as an Event on the US player's next round, USSR gains 3 VP **prior to any US VP award**." The FAQ works the auto-victory case through — "the text of We Will Bury You was played prior to Duck and Cover, its text must be resolved first" — and rules out the no-window case: "there has to be a next Action Round for the VP to be awarded." | Card face; FAQ #50 | `_settle_we_will_bury_you` |
| UN Intervention must be paired with "an opponent's associated Event, defined as a Red or White Star (Rule 2.2.2) regardless of whether the Event can occur or not under Rule 5.2". | FAQ, card #32 | `_play_modes` |
| Ops granted *by an event* (ABM Treaty, CIA Created, Lone Gunman, Glasnost) are not modified: "The reduction is for any use of Ops, including Space Race. Ops from events are not affected." Nor may they be spent on the Space Race: "players must play a card in order to advance". | FAQ, Red Scare/Purge and §6.4 | `push_event_operations`, `_ops_type_options` |
| Chernobyl bars only Influence placed with Operations. "Realignments do not add influence, so the USSR player could still make a Realignment roll. Coups are also allowed... the Soviet player could also add Influence in the selected region through the play of events." | FAQ, card #94 | `_chernobyl_blocks` |
| Truman Doctrine's "uncontrolled" means controlled by neither power, not merely un-Soviet. | FAQ, card #19 | `push_event_influence(requires_uncontrolled=True)` |
| Rule 9.5: the China Card may not be played as a discard required by an event, so it is never a Quagmire/Bear Trap or Blockade candidate. It is not in `hands`, which is what keeps it out. | Rules §9.5; FAQ, card #6 | `_trap_discard_candidates`, `_payable_cards` |
| NORAD places its Influence "at the conclusion of any Action Round in which the DEFCON Status was placed on 2" -- after the round, not when DEFCON moved, so the side whose play degraded DEFCON cannot answer the placement with the Operations it has left. And "it does not apply if DEFCON goes to 2 during the headline": a headline is not an Action Round, so nothing is armed there. | Card face; ruling supplied by the expert | `_change_defcon`, `_push_pending_norad` |
| Forcing yourself to discard a scoring card is legal — "The illegal act would be holding the scoring card" — which is why Five Year Plan draws from the whole hand and Ask Not… offers them. | FAQ §5.0 and card #5 | `push_random_discard`, `_push_ask_not` |
| "Reaching 20 VPs does **not** result in Automatic Victory during scoring at the end of turn 10; however, Control of Europe does grant automatic victory to the controlling player, regardless of scoring elsewhere. Once all regions have been scored, victory goes to the player who has accrued most VPs." The two automatic victories part company at Final Scoring. | Rules §10.3.2 | `_finish_game`, `_change_vp_by(auto_victory=False)` |
| The Chinese Civil War space is the **optional variant** of rules section 12. Within it the space "does not affect any scoring card" and the US "may not use Operations or events of any kind" on it. This engine does not implement the variant, and the space is not on its map. | Rules §12.1 | `data/countries.json` |

## Reading the sources for defects

What worked, in case it is worth repeating: take a mechanic, find its card
text or rule, then read the implementation and ask whether it can produce a
different answer. Two shapes accounted for most of what was found —

- **A bound implemented on one side only.** Red Scare's floor was there and
  Containment's ceiling was not; the Military Operations track had neither.
- **A conditional clause dropped.** U-2 Incident's second VP, Tear Down This
  Wall's "prevents" as well as "cancels", AWACS setting a flag nothing read.
- **A rule read as if it only covered the ordinary case.** Rule 2.1.5's
  superpower adjacency was implemented for Realignments and not for war
  rolls, because `Board.control` returns `None` for the superpower nodes and
  the war code asked it the obvious question. Nothing looked wrong.
- **An effect that outlives the clause bounding it.** Shuttle Diplomacy is
  consumed by the next Middle East or Asia scoring, so it usually never
  reaches Final Scoring — until no such scoring card comes up. We Will Bury
  You's 3 VP were banked to end of turn, which is the right *amount* on the
  wrong *tick*, and only auto-victory can tell the difference.

And a warning: a comment claiming a rule is "not modelled" is not evidence
that it does not matter. The China Card + Vietnam Revolts stack was dismissed
in a comment as rare, and it is a standard USSR line worth 6 Ops.
