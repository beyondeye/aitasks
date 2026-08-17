---
priority: medium
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [workflow, skills]
assigned_to: dario-e@beyond-eye.com
anchor: 1536
created_at: 2026-08-17 23:06
updated_at: 2026-08-17 23:12
---

## Problem

t1536 deferred the worktree fork from Step 5 to Step 7 and reworded Step 5's
base-branch surfaces to say so — both the interactive question and the
profile-driven display line now end with "… the branch and worktree are created
after plan approval and the remote drift check, not now."

The `create_worktree` profile-check line immediately above them was missed and
still announces creation at Step 5:

```
- **Profile check:** If the active profile has `create_worktree` set:
  - If `true`: Create worktree. Display: "Profile '<name>': creating worktree"
```

Under a `create_worktree: true` profile — the exact configuration t1546's
checklist item 1 asks to exercise — Step 5's *first* output tells the user a
worktree is being created, while nothing is cut until Step 7's "Deferred
worktree fork" block. A user who believes the fork already happened will
misjudge every later stop path (drift stop, approve-and-stop, decomposed
parent), which is precisely the misreading the t1536 wording change exists to
prevent.

The interactive counterpart, "Do you want to create a separate branch and
worktree for this task?", has the same tense problem and no deferral sentence.

## Occurrences

Authoring template `.claude/skills/task-workflow/SKILL.md`, **both** branches:
- the Jinja-baked branch (`{% if profile.create_worktree %}` — "Create a
  separate branch and worktree for this task. Display: … creating worktree")
- the runtime profile-check branch (`If \`true\`: Create worktree. Display: …`)

Rendered at L323 in all 9 variants (claude / codex / opencode × default / fast /
remote) and in `tests/golden/procs/task-workflow/SKILL-{default,remote}.md`.

## Proposed fix

Give both lines the same treatment the base-branch surfaces got in t1536:

- Display line → "Profile '<name>': worktree mode — the branch and worktree are
  created after plan approval and the remote drift check, not now."
- Question text → state inside the widget that the branch and worktree are cut
  after plan approval and the drift check, not on answering.

Edit the `.j2` authoring template only, then regenerate the affected goldens in
the same commit (see "Regenerate goldens after any `.md.j2` or closure edit" in
`aidocs/framework/skill_authoring_conventions.md`) and run
`./.aitask-scripts/aitask_skill_verify.sh`.

## Provenance

Found during t1546 (manual verification of t1536) by autonomous auto-execution;
recorded in `aiplans/p1546_manual_verification_auto.md` under "## Finding". It
falsifies no checklist item's literal criterion — nothing *is* created at Step 5
— so it was not recorded as a verification failure.
