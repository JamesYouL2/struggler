# DEFCON strategy and suicide-card checklist

This is a strategy and implementation specification for the bots. It describes
intended play and flags places where the current engine differs. Card behavior
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
[events.py](../src/struggler/engine/events.py); see the mismatch list below.

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
the harmless branch of your event.

When behind, look for an opponent's **forced** loss: keep DEFCON low, preserve
eligible targets, deny disposal opportunities, and reduce their safe plays.
Keep uncertain hand identity as a belief, not a fact. Use expected win
probability for uncertain traps; an ordinary VP average is insufficient for
terminal outcomes.

## Engine and bot discrepancies to resolve before training on these outcomes

These are observations of the current source, not implemented fixes:

1. **DEFCON responsibility:** `_change_defcon(delta, caused_by)` awards the win
   to `caused_by.opponent`. Coup resolution passes the coup actor, so an
   opponent-granted battleground coup can punish the wrong player. Summit and
   nested event calls likewise need a persistent phasing-player context.
2. **Five Year Plan allegiance:** `_handle_random_discard` currently fires a
   USSR-associated event (`info.side.value == owner.value` with owner USSR).
   Intended behavior fires a US-associated event. The existing comment/test
   behavior follows the reversed implementation. Do not learn its discard risk
   as a rule of the game.
3. **Missile Envy:** `missile_envy_take` offers an Ops-or-Event choice for a
   received own/neutral event. Intended behavior forces that event, so the
   implementation currently supplies an escape from some suicide draws.
4. **Cuban Missile Crisis cancellation:** the engine offers cancellation at
   the affected side's action-round start. Intended at-any-time cancellation
   matters during an opponent-granted operations chain.
5. **Wargames:** `_wargames_choice` calls `_finish_game`, adding regional final
   scoring. Intended Wargames ends after its VP concession, without that extra
   regional scoring. It cannot be used as a trustworthy win-probability label
   until reconciled.
6. **Bot hand planning:** the small match check on seeds 1200/1201 ended in
   early nuclear losses. The inspected USSR losses against StrategicPlayer
   played Duck and Cover for Ops at DEFCON 2. A mode-level penalty is too late
   if earlier choices consumed the last escape and left only losing options.
   These outcomes are recorded in
   [event-value-match-check.json](../models/event-value-match-check.json).

Implementation priority: correct responsibility and event mechanics; add
regressions for the scenarios above; then enforce survival planning before
ranking regional VP. Adding more country features alone will not repair this.
