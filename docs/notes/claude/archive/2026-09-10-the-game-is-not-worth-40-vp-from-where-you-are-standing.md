# The game is not worth 40 VP from where you are standing

The maintainer, on China's insurance value: "China is often worth 30 VP
in late war. Rarely 40, because generally you're not ahead by that much
in final scoring without 20 VP edge."

The first half confirms the bimodal reading above and puts a number on the
bad mode: in the late war, holding China is *often* worth three quarters
of the whole game. Against a median turn-10 gap of 4.3 Ops -- roughly 2 VP
-- the bot captures the ordinary mode and misses the mode that matters.

The second half is a finding about a constant, not about China.

```python
GAME_SWING_VP = 40.0
def game_value(self, obs):
    return GAME_SWING_VP * self.vp_value(obs)
```

Flat, symmetric, and used twice: as the cap on `hold_value`, and by
`priced()` to bound a certain outcome before it may be combined. But the
VP track ends at ±20, so **the swing actually available from VP = v is
`20 - v` upward and `20 + v` downward** -- and those are only equal at
zero. At +15 to the US, the US can gain 5 more VP before the game ends and
can lose 35; a flat 40 overstates its upside eightfold and understates its
downside by five VP. That asymmetry is exactly the maintainer's
observation: a card is rarely worth the full 40 because being worth 40
means converting a certain loss into a certain win, which requires a
position close enough to both.

So `game_value` should take a direction, or return the pair. It is a
small change with a wide blast radius -- it touches every sentinel bound
landed tonight -- so it wants its own gate rather than riding along with
anything else. Recorded now because the constant is currently *documented*
as "the whole -20..+20 track", which is true of the track and false of the
position.
