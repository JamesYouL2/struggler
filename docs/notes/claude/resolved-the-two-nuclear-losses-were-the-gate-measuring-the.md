# Resolved: the two "nuclear losses" were the gate measuring the working tree

Gates on 873d9d9 and c5446e0 each reported one nuclear loss as the USSR.
Neither reproduces: the same commit, seeds and opponent, run from a
clean checkout, gives 0.867 and 0 nuclear losses. The gate ran each
benchmark as a fresh process importing the live `src/`, and the working
tree was being edited (the margin term, at its wrong VP scale, among
other drafts) while the later steps ran. Every gate from 50e8bff to
c5446e0 is therefore suspect, including 873d9d9's 0.328 failure.
`scripts/gate.sh` now checks HEAD out into a temporary worktree and runs
from it; the anchor run is off unless GATE_ANCHOR=1; defaults are 32
seeds, 8 workers, base HEAD~1. The chain was re-gated cleanly after.
