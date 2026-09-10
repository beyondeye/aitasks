---
priority: medium
effort: medium
depends: []
issue_type: documentation
status: Ready
labels: [documentation]
anchor: 1661
followup_kind: risk_mitigation
created_at: 2026-09-04 15:52
updated_at: 2026-09-04 15:52
---

## Origin

Risk-mitigation ("after") follow-up for t1698, created at Step 8d after implementation landed.

## Risk addressed

`aitask_update.sh --batch` leaves the task file dirty (measured), so the
preflight will refuse real, previously-working invocations mid-session — most
visibly the `aitask-trail` create flow · severity: medium

t1698 made `ait attach` / `ait artifact` refuse to start when a path they would
stage has uncommitted changes. That is the point of the fix — absorbing the edit
is the defect — but it makes previously-working invocations fail.

`./.aitask-scripts/aitask_update.sh --batch <id> --status …` **writes the task
file and does not commit it** (verified in a scratch repo: ` M
aitasks/t5_demo.md` after the call; the t1677 commit-owner is the *caller*, e.g.
`aitask_pick_own.sh`, not `--batch` itself). So a task file is routinely dirty
mid-session.

The concrete in-tree caller is the **`aitask-trail`** skill, whose create flow
runs `aitask_artifact.sh create <owner_id> <tmpfile>` and stages the owner's
task file. Its step 4 ends with "Any other failure → surface and stop", so the
refusal IS surfaced with an actionable message and nothing is corrupted — but
the guidance is generic, and a user hitting it gets no hint that the fix is to
commit their own in-flight edit.

`--refresh` is unaffected: `aitask_artifact.sh update` stages only the manifest,
never a task file (the stable-handle / mutable-manifest split, asserted in
`tests/test_attach_txn_worktree_isolation.sh` section N1).

## Goal

Document the clean-owner-file precondition in the `aitask-trail` skill, next to
the existing "handle … already exists" guidance at the create step:

1. Edit the Claude Code source of truth — `.claude/skills/aitask-trail/SKILL.md.j2`
   (per CLAUDE.md, skill changes go in the Claude Code version first).
2. Regenerate every rendered variant (`aitask-trail-{default,fast,remote}-`) and
   the goldens under `tests/golden/skills/aitask-trail/`, in the same commit —
   see "Regenerate goldens after any `.md.j2` or closure edit" in
   `aidocs/framework/skill_authoring_conventions.md`.
3. Run `./.aitask-scripts/aitask_skill_verify.sh` before committing.
4. Spawn the companion port tasks for the other supported code agents
   (`.agents/skills/`, `.opencode/skills/`), as CLAUDE.md requires.

Content to add: creating a trail writes the owner task's file, so
`ait artifact create` refuses while that file has uncommitted changes — commit
or revert them first; refreshing a trail only rewrites the manifest and is
unaffected. The equivalent sentence already landed in
`website/content/docs/skills/aitask-trail.md:85` under t1698, so mirror that
wording rather than inventing a second phrasing.

## Why this was not done in t1698

Touching the `.j2`, every rendered per-profile and per-agent variant, the
goldens, and the verifier is a separate change under this repo's
skill-authoring rules — estimated `added_complexity: high` relative to t1698's
own scope at planning time, which is why it was dispositioned as a spawned
"after" mitigation rather than inlined.

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t1243_13** id=2026-09-10T18:36:50Z.1655c625be73cf1ae036de1e from=t1243_13 at=2026-09-10T18:36:50Z base=e2f12c49990459143f2e387db431b5222fc66ef7 base_branch=main dirty=no host=omg16
>
> | Docs-coordination sweep, run outside any task: `from=` names the overlapping
> | task, not an agent working on it, so it is unverified. Advisory only —
> | tree-relative claims are dated by this note's base SHA. Verify before acting.
> | 
> | t1243_13 (blocked on t1243_12) inherits an edit to the same
> | .claude/skills/aitask-trail/SKILL.md.j2 — adding boardgroup to the "never
> | mutate" list at :17 — and regenerates the same tests/golden/skills/aitask-trail/
> | goldens. Whichever of you lands second regenerates on top of the other.
> | 
> | Your premises still hold: the website sentence you mirror is at
> | website/content/docs/skills/aitask-trail.md:85, and no "uncommitted" wording
> | exists yet in the skill, its .agents / .opencode ports, or the goldens.
