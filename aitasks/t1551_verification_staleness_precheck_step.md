---
priority: medium
effort: medium
depends: [1549, 1550]
issue_type: feature
status: Ready
labels: [verification, task-workflow]
gates: [risk_evaluated]
anchor: 1538
created_at: 2026-08-17 18:02
updated_at: 2026-08-17 18:02
---

Wire the staleness pre-check into the manual-verification procedure, per
`aidocs/framework/manual_verification_staleness.md` (read it first — it is the
source of truth). Slice 3 of 3. Depends on t1549 (helper + field) and t1550
(seeding).

## Placement — both bounds are load-bearing

Insert a new step in `.claude/skills/task-workflow/manual-verification.md`
**between step 1 (pre-loop check — ensure the task has a checklist) and step 1.5
(the autonomous-verification offer)**:

- It must run **before** 1.5, because that step can dispatch autonomous
  verification, which would otherwise work through stale items unattended.
- It must run **after** 1, because step 1's seed path can create the checklist
  mid-step (so a check placed earlier would see no checklist).

Number it `### 1.3` in that file's scheme (its steps run 1, 1.5, 2, 3, 4, 5).

## Behaviour

Run `./.aitask-scripts/aitask_verification_stale.sh check <task_file>` and
dispatch on `DECISION`:

- `SKIP` / `FRESH` → continue silently to 1.5. (`SKIP` is the common case for
  existing tasks — do not warn.)
- `ASK_STALE` → print the `DISPLAY:` line **verbatim**, then `AskUserQuestion`,
  mirroring the `ASK_STALE` prompt shape in `planning.md`:
  - "Amend the checklist" — show the changed files' diffs against the baseline
    beside the current checklist, propose item edits, user accepts / edits /
    rejects per item.
  - "Proceed unchanged" — staleness noted, judged immaterial.
  - "Abort" — Task Abort Procedure; baseline untouched.

Advisory only: it must **never** block archival, and nothing is rewritten without
the user accepting it.

## The review transaction — ordering is load-bearing

On the amend path the baseline advance happens **only after** the user's final
accept/edit decision, and the checklist edit and the baseline update are written
**together**.

Advancing first and then failing — or the user abandoning the edit — would
permanently dismiss the very change the user was brought in to review, and with
the baseline already at HEAD **no later pick would ever raise it again**. That is
a silent, unrecoverable loss of the signal the feature exists to produce.

Both writes target the same file (baseline in frontmatter, items in body), so
compose them into a single `ait_atomic_render` call from `lib/atomic_write.sh`.

**Rule: decide → write both → commit.** Never advance → edit.

"Proceed unchanged" advances the baseline immediately (there is no edit to pair it
with). Advancing on dismissal is what stops the prompt re-firing on every later
pick; omitting it is the single easiest way to make this feature worse than
nothing.

Amendment is a direct edit of the item text — `seed` refuses when a checklist
section already exists, and v1 adds **no** `amend` verb. The audit trail is the
task file's git history plus the advanced baseline.

## Tests

- **Transaction:** a failure injected between the decision and the write leaves
  the task file **byte-identical** — neither the items nor the baseline advanced
  (follow the `tests/test_atomic_task_file_writes.sh` shape).
- **No re-fire:** after "Proceed unchanged", a re-run of the check returns
  `FRESH`.
- **Ordering:** the check runs before the 1.5 autonomous offer (a stale checklist
  must not reach autonomous verification unprompted).

## Acceptance

- Run `./.aitask-scripts/aitask_skill_verify.sh` before committing.
- Rerender the per-profile variants — one call per profile, e.g.
  `./.aitask-scripts/aitask_skill_rerender.sh <profile>` — and regenerate the
  affected goldens **in the same commit** (see
  `aidocs/framework/skill_authoring_conventions.md`).
- Suggest separate tasks to port the change to the Codex CLI and OpenCode skill
  trees (per CLAUDE.md: Claude Code version first).
