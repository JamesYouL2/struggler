"""The files agents read rather than import: the contract, the skills, the notes index.

`AGENTS.md` and `CLAUDE.md` are one contract under two names, and the
skills are one tree under `.agents/skills/` and `.claude/skills/`, because
harnesses hardcode which name or directory they read. Two copies of one
rule is a shape this repo has been bitten by repeatedly (shape 1 in
`docs/notes/claude/bug-shapes.md`): it already happened here once -- the
`.claude` skill copies learned that `docs/notes/Codex/` was renamed to
`docs/notes/claude/` and the `.agents` copies did not, so one tree linked
a directory that no longer existed -- and the contract pair had drifted
the same way (one side with the CI section and current timings, the other
with a broken notes path).

So the mirrors are byte-identical or the suite fails, every path these
files cite must exist, and every top-level note must be indexed in its
README. Same reasoning as the two registry tests in
`tests/test_experiment_registry.py` and `tests/test_recurring_defects.py`:
these files are read by a runner or an agent rather than by the package,
so nothing else would notice them rotting.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ('AGENTS.md', 'CLAUDE.md')
SKILL_TREES = ('.agents/skills', '.claude/skills')
NOTES_TREES = ('docs/notes/claude', 'docs/notes/codex')
SCANNED_SKILL_NAME = 'SKILL.md'

# A repo-relative path citation, e.g. `docs/ARCHITECTURE.md` or
# .github/experiments.json. The final character class excludes a trailing
# period or paren so prose punctuation is not mistaken for the name.
PATH_REF = re.compile(
    r'(?:docs|scripts|tests|models|\.github)/[A-Za-z0-9_./-]*[A-Za-z0-9_/-]'
)


def _scanned_files() -> list[Path]:
    """Every file whose citations and copies this module gates."""
    files = [ROOT / name for name in CONTRACT]
    for tree in SKILL_TREES:
        files.extend(sorted((ROOT / tree).rglob(SCANNED_SKILL_NAME)))
    return files


def _tree_bytes(tree: Path) -> dict[str, bytes]:
    return {
        str(path.relative_to(tree)): path.read_bytes()
        for path in sorted(tree.rglob('*'))
        if path.is_file()
    }


def test_contract_files_are_identical() -> None:
    """`AGENTS.md` and `CLAUDE.md` are one document under two names."""
    texts = {name: (ROOT / name).read_text() for name in CONTRACT}
    drifted = [name for name, text in texts.items() if text != texts[CONTRACT[0]]]
    assert not drifted, (
        f'{CONTRACT[0]} and {drifted} have drifted apart; they are the same '
        'contract read under two names. Edit one and copy it to the other.'
    )


def test_skill_trees_are_identical() -> None:
    """`.agents/skills/` and `.claude/skills/` are one tree under two roots."""
    trees = {name: _tree_bytes(ROOT / name) for name in SKILL_TREES}
    base, other = SKILL_TREES
    assert trees[base].keys() == trees[other].keys(), (
        f'{base} and {other} do not contain the same files: '
        f'only in {base} = {sorted(trees[base].keys() - trees[other].keys())}, '
        f'only in {other} = {sorted(trees[other].keys() - trees[base].keys())}'
    )
    differing = sorted(
        name for name in trees[base] if trees[base][name] != trees[other][name]
    )
    assert not differing, (
        f'{base} and {other} differ in {differing}; the mirrors are one skill '
        'tree read under two roots. Edit one and copy it to the other.'
    )


def test_every_cited_path_exists() -> None:
    """No contract file or skill may cite a path the repo does not have.

    This is the shape the skill mirrors actually drifted on: one tree
    cited `docs/notes/Codex/bug-shapes.md` after the directory had become
    `docs/notes/claude/`, and nothing but a reader following the link
    would ever find out.
    """
    broken = []
    for file in _scanned_files():
        for ref in PATH_REF.findall(file.read_text()):
            if not (ROOT / ref).exists():
                broken.append(f'{file.relative_to(ROOT)} -> {ref}')
    assert not broken, 'cited paths that do not exist:\n' + '\n'.join(broken)


@pytest.mark.parametrize('tree', NOTES_TREES)
def test_every_note_is_indexed(tree: str) -> None:
    """Every top-level note is linked from its tree's README contents.

    The index is how the next session finds the note; `docs/TESTING.md`
    calls out this class of file -- read by agents and runners rather
    than imported -- as needing a test. `archive/` is exempt: moved notes
    keep their original index line, which is dated and would not match
    `(<name>.md)` anyway.
    """
    readme = (ROOT / tree / 'README.md').read_text()
    missing = [
        path.name
        for path in sorted((ROOT / tree).glob('*.md'))
        if path.name != 'README.md' and f'({path.name})' not in readme
    ]
    assert not missing, f'{tree}/README.md does not index: {missing}'
