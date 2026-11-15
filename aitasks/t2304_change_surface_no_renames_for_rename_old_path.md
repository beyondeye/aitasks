---
priority: high
risk_code_health: low
risk_goal_achievement: low
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [testmap, bash_scripts]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 4a36c12bb96d.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus5_5
created_at: 2026-11-15 17:53
updated_at: 2026-11-15 22:39
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

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t61_1** id=2026-11-15T16:06:21Z.65cdbac9b78ea27e16d271ca from=aitasks_go#t61_1 from_verified=yes at=2026-11-15T16:06:21Z base=57b660ff0c0fa2d3eaf836a353acbae7849414c6 base_branch=main dirty=yes host=omg16
>
> | Advisory from aitasks_go#t61_1, observed by running the real script on a scratch repository (aitasks @ d97bc80d8 script; dirty=moment-relative, the scratch repo is gone).
> | 1. Confirmed the defect. With default rename detection, a staged rename keep.sh->staged_new.sh and a committed (t9) rename old.sh->b.sh list only the new path.
> | 2. Emulating --no-renames with GIT_CONFIG_* diff.renames=false gives COMMITTED:lib/old.sh and UNKNOWN:lib/keep.sh (the old half is unnamed by the plan, so it is refused). The intended shape holds: no new prefixes.
> | 3. Side finding, possibly in scope for "consistent handling": git C-quotes non-ASCII paths ("d\303\251 j\303\240.md"), and the plan-token match compares that quoted form, so such a path can never be attributed as TASK, even when the plan names it in either form. `docs/a|b.md` also stayed UNKNOWN although the plan named it. Worth checking how plan tokens are split.
> | The engine fixtures are in aitasks_go goengines/internal/testmap/changesurface/testdata/ (README names the emulation). Please replace producer_norenames.txt with the real output after landing.

> **👁 note:read** id=2026-11-15T19:56:33Z.cf81c167686e9e1a91078d40 by=t2304 at=2026-11-15T19:56:33Z mode=explicit ids=2026-11-15T16:06:21Z.65cdbac9b78ea27e16d271ca

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-11-15T20:39:12Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-11-15T21:10:43Z status=pass attempt=1 type=human
