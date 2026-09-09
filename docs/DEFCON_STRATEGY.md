# DEFCON strategy and suicide-card checklist

This is a strategy and implementation specification for the bots. It describes
intended play and records the engine audit and its fixes. Card behavior
was checked against `engine/events.py` and `engine/core.py`; those implementations
are not authoritative where discrepancies are identified below.

## Who loses, and when

At DEFCON 2, an ordinary battleground coup causes an immediate loss for the
**phasing player**, even if the roll fails. Opponent-granted operations do not
transfer that responsibility. In the headline phase, responsibility belongs to
the player whose headline is resolving. Playing an opponent-associated card
for operations normally still triggers its event. Own/neutral events can
normally be avoided by using their cards for operations.
[Rules: §§4.5, 5.2, 8.1](https://www.gmtgames.com/nnts/TS_Rules-2015.pdf).

Two exceptions need separate checks: Nuclear Subs prevents US battleground
coups from degrading DEFCON; Cuban Missile Crisis makes a coup by the affected
player a loss for that player, even during somebody else's action. Crisis
cancellation can be performed at any time when its influence payment is
available. [Official FAQ: Cuban Missile Crisis and Lone Gunman](https://www.gmtgames.com/nnts/FAQv5.pdf).

Bot implication: track **phasing player**, **decision actor**, and **event
beneficiary** separately. A single `side` argument is insufficient. Terminal
losses should override country value and expected VP. Being behind makes
forcing the opponent into nuclear defeat attractive; it does not make your
own certain loss attractive.

## Direct reducers and deliberate choices

These event effects are implemented in [events.py](../src/struggler/engine/events.py).
The table assumes the event actually resolves; spacing or suppressing the event
is a different action.

| Card | DEFCON danger | Decision rule |
| --- | --- | --- |
| Duck and Cover | Event lowers DEFCON by one. | At 2, USSR must avoid triggering it, including through Ops. US can normally use its own card for Ops safely. |
| We Will Bury You | Event lowers DEFCON by one. | At 2, US must avoid triggering it; USSR can normally use its own card for Ops. The later VP award does not rescue a prior nuclear loss. |
| Soviets Shoot Down KAL-007 | Event lowers DEFCON by one, before its subsequent benefits. | At 2, USSR must avoid triggering it; US can normally use it for Ops. |
| Olympic Games | Opponent can boycott and lower DEFCON by one. | Do not sponsor the event at 2. On the opponent's action, a boycott may win immediately. Ordinary neutral-card Ops do not trigger it. |
| Summit | Contest winner may lower DEFCON. | At 2, eventing it risks an opponent win followed by a nuclear defeat for the phasing player. If you win on your own action, choose a safe DEFCON option. |
| How I Learned to Stop Worrying | Lets the event controller select DEFCON 1. | Never choose 1 when you are responsible for the resolving action. If an opponent's card chain gives you this choice on their action, 1 can win even from DEFCON 5. |

At DEFCON 3, a reducer followed by a battleground coup in the same resolution
chain can still be fatal. Trace event/operations order and headline order;
checking only the DEFCON value when a card is selected is insufficient.

## Giving the opponent a coup

A coup needs opposing influence in a legal target; it does **not** require
control or a plausible chance of removing influence. Country access for
placement is not the same as coup legality. Consult actual event-specific
options, DEFCON geography, protection effects, and Nuclear Subs.

| Card | Usually endangered player | Condition to check |
| --- | --- | --- |
| CIA Created | USSR triggering the US event | US receives 1 Op. At 2, any legal USSR-influenced battleground target can make this fatal. Without such a target, the ordinary coup route is absent. |
| Lone Gunman | US triggering the USSR event | USSR receives 1 Op. Same target test, with sides reversed. |
| Grain Sales to Soviets | USSR triggering the US event | US can return the revealed card and take 2 Ops, including a fatal battleground coup. An empty USSR hand still grants the operations. Taking the card can also start an event chain. |
| Tear Down This Wall | USSR triggering the US event | US gets a European coup/realignment opportunity. Its regional permission bypasses normal DEFCON geography, not the battleground DEFCON drop. Check USSR influence in European battlegrounds. |
| Ortega Elected in Nicaragua | US triggering the USSR event | The USSR may coup adjacent to Nicaragua. US influence in Cuba is the critical battleground target; the event's removal from Nicaragua does not eliminate Cuba's danger. |

The board can create a trap: Fidel supplies USSR influence in Cuba, which can
make a later CIA coup possible. Conversely, removing the last opposing marker
from every legal battleground target can remove that particular route. Neither
observation guarantees safety from another event chain.
The standard card-family overview is also covered by
[Twilight Strategy's DEFCON guide](https://twilightstrategy.com/2011/12/12/general-strategy-defcon/).

## Five Year Plan: a scoring-card escape, with conditional risk

For USSR, keep Five Year Plan available when planning to dispose of an unwanted
scoring card. If playing it leaves that scoring card as the sole card in hand,
the random discard is guaranteed to hit it. It is discarded without scoring.
USSR can play Five Year Plan for its operations while its US event performs the
discard. The last-action scoring-discard use is explicitly permitted by the
[official FAQ, card #5](https://www.gmtgames.com/nnts/FAQv5.pdf).

With several cards remaining, the target is random. Under the intended rules,
a selected **US-associated event** fires; USSR-associated and neutral cards
are discarded without their events. A selected scoring card is discarded
without scoring. Therefore inspect the remaining hand, not just DEFCON:

- Only a bad scoring card remains: no nuclear danger from the discard itself.
- Duck and Cover or KAL-007 may be selected: direct-reducer risk.
- CIA, Grain Sales, Star Wars, or Tear Down This Wall may be selected: inspect
  their operations, eligibility, targets, and further event chains.

US also risks its own nuclear defeat if its Five Year Plan triggers a direct
reducer. For planning examples, see
[Five Year Plan strategy](https://twilightstrategy.com/2011/12/12/five-year-plan/).

Do not mark Five Year Plan as universally forbidden at DEFCON 2. Plan the hand
sequence so the intended discard is certain, without relying on an unknown
opponent action to leave that sequence intact.

## Card retrieval and nested events

| Card | What must be inspected |
| --- | --- |
| Five Year Plan | Remaining USSR hand and every possible US event it can trigger; see above. |
| Missile Envy | Possible highest-Ops cards surrendered by the opponent. Intended rules force an eligible own/neutral event to resolve; a received reducer or a neutral choice/contest can be lethal. Opponent-associated events are used for Ops without firing. |
| Star Wars | US Space Race lead and non-scoring discard-pile contents. If USSR triggers it, US may retrieve a direct reducer, an operations-granting event, or How I Learned to Stop Worrying. A discarded suicide card is therefore not always inactive. |
| Grain Sales to Soviets | Both return-for-Ops and take-and-play branches. US can use a selected event against the player responsible for the chain. |
| SALT Negotiations | Retrieval goes to hand, rather than forcing immediate resolution. Reassess the retrieved card when scheduling subsequent plays. |

Missile Envy's forced-reducer danger is illustrated in the
[official FAQ, Missile Envy / We Will Bury You](https://www.gmtgames.com/nnts/FAQv5.pdf).
The retrieval distinctions above also have separate handlers in
[core.py](../src/struggler/engine/core.py) and
[events.py](../src/struggler/engine/events.py); see the audit status below.

Do not implement a finite blacklist as the whole safety system. Any future
card that invokes an existing unsafe event inherits that event's risk. Evaluate
the chain recursively with the original responsibility preserved.

## Related cards that are not automatic DEFCON suicide

- **ABM Treaty:** raises DEFCON before granting operations. A subsequent
  battleground coup from 3 returns to 2; evaluate the sequence, not just its
  starting value. Cuban Missile Crisis still needs its own check.
- **Junta:** grants a regional coup/realignment choice. A battleground coup on
  your own action at 2 is fatal; choose a safe alternative or decline when
  available. It also interacts with Cuban Missile Crisis.
- **Che:** its coups target non-battlegrounds, so do not directly lower DEFCON.
  Cuban Missile Crisis can nevertheless make a coup fatal.
- **Korean War, Arab-Israeli War, Indo-Pakistani War, Iran-Iraq War, Brush War:**
  war rolls are not battleground coups. In this edition/engine, they do not
  directly degrade DEFCON; they can supply military operations without a coup.
- **Nuclear Subs:** exempts US coups from the battleground DEFCON reduction,
  including US operations granted by a USSR card. It does not protect against
  direct reducers, a selected DEFCON 1, or Cuban Missile Crisis.
- **Wargames:** an alternative game-ending event, not nuclear suicide. Evaluate
  its terminal result separately; see the engine discrepancy below.
- **Terrorism, Aldrich Ames Remix, Blockade, Quagmire/Bear Trap:** affect card
  disposal, hand size, or available action rounds. They can remove an escape or
  change which dangerous cards must eventually be played. Do not treat every
  discard as an event trigger: ordinary discard is different from Five Year
  Plan or take-and-play effects.

These distinctions follow the separate coup, war, discard, and event handlers
in this repository. They should remain explicit inputs to tactical planning.

## Hand discard effects, traps, and modifiers

Discards are the other half of hand management. Some take a card from you
without firing its event, which can be an escape or a trap depending on
which card leaves and how many safe plays remain afterwards.

| Effect | Who discards | What to check |
| --- | --- | --- |
| Blockade | US, a 3+-Ops card (modified value), or lose all West Germany influence. | Paying is optional. Refusing is a board hit, never a nuclear loss. Paying a 3+ Ops opponent card (We Will Bury You, KAL-007, Tear Down This Wall) is a clean exit because the event does not fire. Paying your last spare safe card can leave a 1-Ops suicide card as the only play for the final round: that is exactly how the seed 2401 game was lost. |
| Latin American Debt Crisis | US, same 3+-Ops clause, or the USSR doubles influence in two South American countries. | Same test as Blockade. The board hit is usually mild, so refusing is cheap when the hand is tight. |

What Blockade costs the US depends entirely on which card pays. Discarding
a US or neutral 3-Ops card is a real loss (those Ops were the US's), and
that is the Blockade the USSR wants. Discarding a USSR 3-Ops card such as
De Gaulle, Socialist Governments or Suez Crisis is good for the US: the
event never fires and the card only comes back at the reshuffle. That
return matters the other way too: a strong USSR card (Decolonization,
De-Stalinization) sent to the discard by any route is back in the next
cycle, so dumping it delays rather than removes it. The bots do not price
this yet: the pay choice is scored as a flat minus modified Ops, and from
the USSR's seat the sandbox assumes the US cannot pay. The right price is
the smaller of "lose West Germany" and the paying card's cost, where the
cost of a US/neutral card is its Ops value and the cost of a USSR card is
negative (the harm avoided), less a discounted return at the reshuffle.
| Quagmire / Bear Trap | The trapped side (US / USSR) discards a 2+ Ops card each action round and rolls 1-4 to escape. | The discard fires no event, so a trapped player cannot be forced into a suicide card; the cost is tempo and the 2+ Ops cards it eats. Without a payable card no roll happens and the round passes. |
| Terrorism | Opponent discards one random card (two if the USSR plays it after Iranian Hostage Crisis). | An attack on the hand: it can strip a spare safe card and leave a held hazard with nowhere to hide. |
| Aldrich Ames Remix | USSR picks the US discard from the revealed hand. | The adversarial case: assume it takes the safe card whose loss hurts most. |
| Grain Sales to Soviets | A random USSR card is revealed; the US keeps it or returns it. | Removes a USSR card, and the US may play it in full. |
| Missile Envy | Opponent surrenders its highest-Ops card. | Both a hand attack and a forced event on receipt; see the retrieval table above. |

**How strong humans use the attack cards.** Assume the worst when the
opponent can hold them: a strong player always events Grain Sales to
Soviets and always events Aldrich Ames Remix, and events Terrorism almost
always when behind and always once Iranian Hostage Crisis is in effect
(two random discards). Bot-versus-bot logs under-represent all three, so a
hand-attack rate learned from them (see
[STRATEGIC_AI.md](STRATEGIC_AI.md#hand-survival)) describes those bots, not
a human opponent; against a human, treat "the opponent may hold the card"
as "the opponent will play it".

**Self-trapping as disposal.** Because a trap's discard fires no event, a
side can play the opponent's trap for Ops on purpose to dump cards it
could never safely play. The USSR playing Bear Trap for Ops can then shed
Grain Sales to Soviets, The Voice of America, Colonial Rear Guards, and
similar 2-Ops US events one round at a time. The US playing Quagmire for
Ops mainly buys a way to discard Decolonization; few other USSR 2-Ops
cards are painful enough to justify the tempo. A 1-Ops suicide card
(CIA Created, Lone Gunman) cannot be paid to a trap, but a trapped side
never has to play it either.

**Red Scare/Purge and SALT.** Under Red Scare/Purge the affected side's
cards are worth one Op less. On the tabletop that shrinks the set of cards
that satisfy a discard clause: a 3-Ops card no longer pays for Blockade,
and 2-Ops cards no longer pay for a trap. Red Scare/Purge plus Blockade is
therefore a near-certain loss of West Germany, and Red Scare/Purge plus
Quagmire or Bear Trap can hold the trapped side for the whole turn with
no roll at all. This engine tests the clauses against **printed** Ops
(see [LIMITATIONS.md](LIMITATIONS.md)), so it is more lenient than the
physical game here; do not train the tabletop instinct out of the bots
on that basis. SALT Negotiations pulls in the other direction: the DEFCON
rise opens an escape window, and the retrieved card is one more safe play
or spare against a hand attack, at the price of -1 on every coup roll.

## Plan survival for the whole turn

Before spending operations on country value, count remaining action rounds,
scoring obligations, cards that can safely be played, space eligibility and
attempts left, and legal discard/suppression opportunities. A card may be safe
to hold now but impossible to hold after another discard or extra action.

Space and UN Intervention are possible exits only if legal and available.
CIA/Lone Gunman have printed 1 Op, so do not assume they meet the current space
box's minimum. Containment/Brezhnev and Red Scare/Purge can change effective Ops.
Using a discard or UN Intervention can solve one problem while leaving too few
cards to hold another. DEFCON-raising events can open a safe window, but the
opponent may close it before the next play. Never assume the opponent chooses
the harmless branch of your event. Count a spare safe card for each opponent
action round in which a hand attack (Terrorism, Aldrich Ames, Grain Sales,
Missile Envy) could remove one; a plan with exactly enough safe plays is one
discard away from a forced suicide card.

Two of your own actions can spring the trap without any card leaving your
hand. A battleground coup from DEFCON 3 both lowers DEFCON to 2 and, if it
wins, places your influence where the opponent's granted coup (CIA Created,
Lone Gunman) can now reach it: check the hand at DEFCON 2 *with* that new
target before couping. And a low-Ops headline resolves after the opponent's
higher-Ops one (ties go to the US), so a card that is harmless at DEFCON 3
at pick time can fire at DEFCON 2 if their headline coups first; when your
headline is still pending, treat it as a forced event before you lower
DEFCON during theirs.

When behind, look for an opponent's **forced** loss: keep DEFCON low, preserve
eligible targets, deny disposal opportunities, and reduce their safe plays.
Keep uncertain hand identity as a belief, not a fact. Use expected win
probability for uncertain traps; an ordinary VP average is insufficient for
terminal outcomes.

## Engine and bot discrepancies to resolve before training on these outcomes

Engine items 1–5 below are now fixed; item 6 remains a bot limitation.

1. **DEFCON responsibility — fixed:** continuation frames carry the original
   `phasing_player`; coups, Summit and retrieved events retain it through
   nested decisions and save/resume. Each headline gets its own responsibility.
2. **Five Year Plan allegiance — fixed:** only discarded US events fire.
   Scoring cards are discarded without scoring. The scoring-deadline filter
   also permits USSR's guaranteed Five Year Plan discard when all other cards
   in hand are scoring and the remaining-round count allows it.
3. **Missile Envy — fixed:** received own/neutral events resolve immediately;
   the recipient cannot choose Ops to evade a reducer. Physical-hand transfers
   follow the same rule and preserve unrelated hidden cards.
4. **Cuban Missile Crisis cancellation — fixed:** a free interrupt is offered
   at atomic decision boundaries on either player's turn. The suspended action
   resumes with refreshed legal options; cancellation cannot wait until after
   committing a coup target while affected.
5. **Wargames — fixed:** ends after the concession without regional scoring;
   a tied VP track is a draw. The strategic bot's Wargames evaluator now uses
   this same event implementation.
6. **Bot hand planning — addressed:** the small match check on seeds
   1200/1201 ended in early nuclear losses. The inspected USSR losses
   against StrategicPlayer played Duck and Cover for Ops at DEFCON 2. A
   mode-level penalty is too late if earlier choices consumed the last
   escape and left only losing options. These outcomes are recorded in
   [event-value-match-check.json](../models/event-value-match-check.json).
   `StrategicPlayer` now ranks every card, mode, event-choice, and discard
   decision by `bots/defcon.py`'s whole-hand survival search before its VP
   score (see [STRATEGIC_AI.md](STRATEGIC_AI.md#hand-survival)). The
   seed 2401 loss above (Blockade paid away the last spare safe card) no
   longer reproduces.

Remaining priority: rerun tournaments under the corrected rules and read
the accepted-risk warnings in the diagnostic log for the next failure
class. Adding more country features alone will not repair tactical losses.
