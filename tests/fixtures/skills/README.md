# Pre-rewrite skill fixtures

Frozen copies of pre-rewrite skill text used by
`tests/test_skill_parity_runtime_vs_rendered.sh`.

## Sources

- `aitask-pick/SKILL.md.pre-rewrite` ← `f1b01895:.claude/skills/aitask-pick/SKILL.md`
  (parent of `b6dabc19 refactor: Convert aitask-pick to template + stubs (t777_6)`).
- `task-workflow/*.pre-rewrite` ← `c46366fc:.claude/skills/task-workflow/*`
  (parent of `70f7daf2 refactor: Stage wrapped profile-check sites under task-workflown (t777_7)`).
  25 files total; the parent commit predates t777_7 / t777_23 which deleted
  the originals as part of the Jinja conversion.

## Frozen — do not edit

These files record the baseline that the current Jinja-rendered output
must preserve. They must NEVER be edited to match newer behaviour — only
deleted if the rewrite goal itself changes (in a separate task).

`tests/` is excluded from the release tarball
(`.github/workflows/release.yml`) and from `install.sh`, so nothing
under this directory ever ships downstream.
