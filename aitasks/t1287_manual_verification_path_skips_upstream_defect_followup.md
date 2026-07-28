---
priority: medium
effort: medium
depends: []
issue_type: bug
status: Ready
labels: [workflow]
gates: [risk_evaluated]
anchor: 1142
created_at: 2026-07-28 11:50
updated_at: 2026-07-28 11:50
---

Manual-verification tasks never reach Step 8b (Upstream Defect Follow-up), so
any defect an agent notices *while verifying* is written into the plan file and
then silently buried when the plan is archived.

## The gap

`task-workflow` Check 3 dispatches `issue_type: manual_verification` tasks to
the checklist runner and skips Steps 6-8:

- `.claude/skills/task-workflow/SKILL.md` Check 3 — "Skip Steps 6-8; proceed to
  Step 9 after the procedure returns"
- Step 8b is entered only from Step 8's "Commit changes" branch ("Proceed to
  Step 8b"), so on this path it is unreachable.
- Neither `manual-verification.md` nor `auto-verification.md` references Step 8b
  or `upstream-followup.md`.

Meanwhile `auto-verification.md` has the agent write a plan file whose Final
Implementation Notes carry the canonical **"Upstream defects identified"**
bullet — the exact subsection `upstream-followup.md` parses. Nothing consumes
it on this path.

The checklist-item **failure** path is fine and unaffected:
`aitask_verification_followup.sh` files a bug task per failed item. The gap is
specifically for defects found *incidentally*, which by definition are not
checklist items.

## Concrete instance

The t1142 run (dir backend against a real mount) surfaced two defects unrelated
to any checklist item. Both were written to the canonical bullet; neither was
offered for filing; the plan archived to
`aiplans/archived/p1142_manual_verification_auto.md`. They were filed by hand
afterwards as t1285 and t1286, only because the user asked why they had not
been.

## Design question to settle first

Where should the offer live?

- **In `manual-verification.md` step 3/4** (post-loop, before hand-off to Step
  9) — keeps it on the interactive path, but the autonomous auto-verification
  plan file is written by `auto-verification.md` step 3, so ordering matters.
- **In Step 9, before archival**, gated on the plan file existing — one call
  site covering every path that skips Steps 6-8, not just manual verification.

Prefer whichever keeps a single call site: Check 1, Check 2 and Check 4 also
jump straight to Step 9, and any future path that skips Step 8 inherits the
same hole.

## Acceptance

- A manual-verification run whose plan records a non-`None` "Upstream defects
  identified" bullet reaches the Upstream Defect Follow-up offer before
  archival.
- A run recording `None` (verbatim) is a no-op — no prompt.
- The offer fires for both auto-verification strategies (autonomous and
  pre-built) and for a purely interactive run that produced a plan file.
- The checklist-item failure path (`aitask_verification_followup.sh`) is
  unchanged — no double-filing of an item failure.
- Behavioral test: a fixture task whose plan carries a seeded defect bullet
  drives the real entry point and the offer is reached; a negative control with
  `None` proves the test discriminates.

## Note on scope

Per CLAUDE.md, make this change in the Claude Code skill tree first. Closure
procedures auto-render, so this is likely a no-op for the other agent trees —
verify before proposing port tasks.

## Source

Found during the t1142 verification run; the buried defects are recorded under
"Upstream defects identified" in
`aiplans/archived/p1142_manual_verification_auto.md`.
