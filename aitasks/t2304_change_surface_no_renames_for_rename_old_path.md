---
priority: high
effort: low
depends: []
issue_type: bug
status: Ready
labels: [testmap, bash_scripts]
created_at: 2026-11-15 17:53
updated_at: 2026-11-15 17:53
---

## Context

`aitask_change_surface.sh` is the authoritative change-surface intake for the
testmap selector: proposal n014, `assumption_change_surface_is_intake`, says
"selection never reads a raw git diff". The engine's selector (aitasks_go#t61_1,
M4.1) parses the `list <id>` lines and escalates a listed path that is absent
from the working tree to a full run (`ESCALATE:<path>|deleted`). Deleting an
imported file drops every scanner-derived relationship to it, so only a full
run is safe.

**Defect.** Git's default rename detection prints only a rename's **new** path
in both `git diff --name-only HEAD` (the shared dirty-set helper, used by
`capture`/`baseline` → `DIRTY_AT_CLAIM` and by `list` pass B, script line ~132)
and `git show --name-only` (pass A, script line ~278). The **old** path of a
renamed file therefore never reaches the intake. A rename of an imported source
then under-selects: dependents that still reference the old path are never
selected, and nothing escalates.

## Scope

- Pass `--no-renames` to **every** git read the script's attribution uses: the
  dirty-set helper (`git diff --name-only HEAD`) and pass A's
  `git show --name-only`. Apply it consistently, so `baseline`/`capture` and
  `list` agree on the same path set.
- **No new line prefixes.** Both halves of a rename arrive as ordinary path
  lines with the existing prefixes (`COMMITTED:`, `TASK:`, `OTHER:`,
  `UNKNOWN:`), so existing consumers keep their grammar: shadow scope, the
  plan-paths seam, parallel admission, revert analyze and gate ledger
  `_DIGEST_EXCLUDES`. Review each consumer for the effect of one more path per
  rename and record the outcome.
- **Classification is unchanged.** The old path is classified by the existing
  rules: plan-named → `TASK`, baseline → `OTHER`, both or neither → `UNKNOWN`.
  `UNKNOWN` refusal is preserved and ownership is never guessed.

## Acceptance

All cases run **through the real script** in `tests/test_change_surface.sh`,
not through a stub:

- a staged rename (`git mv a b`): `list` prints both halves, each with its
  class; covers the old path plan-named, baseline-only and neither (→
  `UNKNOWN:`);
- an unstaged rename (`mv` + untracked new file): the same assertions;
- a committed rename in a `(t<id>)` commit: `COMMITTED:` lines for both halves;
- a plain deletion, which is still listed (regression guard);
- `baseline` / `DIRTY_AT_CLAIM` consistent with `list` for the same tree;
- every existing case still passes.

## Dependency record

This task is a **prerequisite of production wiring** of the M5.1 front
(aitasks#t1856), which pipes this script into `ait testmap select --changes -` /
`test`. The engine side (aitasks_go#t61_1) is tested on fixtures copied from
this task's real-script expected output. Fixtures alone are **not** end-to-end
readiness: until this lands, a production intake lacks a rename's old path.

After landing, re-sync the script copy into aitasks_go by the normal framework
sync, and tell aitasks_go#t61_1 / t61_5 the landing commit with `ait note`.
