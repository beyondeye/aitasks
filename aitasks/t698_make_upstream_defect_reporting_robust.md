---
priority: medium
effort: medium
depends: []
issue_type: refactor
status: Implementing
labels: [task_workflow]
assigned_to: daelyasy@hotmail.com
created_at: 2026-04-28 11:23
updated_at: 2026-04-28 11:47
boardcol: now
boardidx: 20
---

## Origin

Spawned from t687 review. During Step 8b, the Upstream Defect Follow-up
Procedure (`upstream-followup.md`) returned a no-op even though the
plan's Final Implementation Notes documented a related defect (the
trailing-slash `.gitignore` bug for `aitasks/` / `aiplans/` symlinks).
The agent recorded the defect under a side bullet
(`- **Trailing-slash follow-up:**`) instead of under the canonical
`- **Upstream defects identified:**` bullet, and wrote `None` to the
canonical bullet. The procedure parses only the canonical bullet, so
the defect was invisible to the parser and never offered to the user.

## Problem

The current contract is a structured-parse: Step 8b reads exactly one
bullet by name. Two failure modes:

1. **Mis-categorization** — the agent applies an overly narrow read of
   "seeded the symptom this task fixed" and writes `None` even when a
   related defect was identified during the same investigation. Once
   `None` is written, the parser short-circuits.
2. **Mis-location** — the agent writes the defect bullets in a
   different position (a side bullet, a different section, free prose)
   and the parser doesn't see them.

Both modes are silent: the user gets no signal that a defect was
identified-but-skipped. There's no validation step that cross-checks
the plan body against the canonical bullet.

## Two candidate fixes (decide during planning)

### Option A — Tighten the structured-parse contract

Make the canonical bullet harder to mis-fill:

- Update `SKILL.md` Step 8 plan-consolidation language to explicitly
  list "related defects identified during diagnosis" (not only
  strict-seeded defects) under the canonical bullet. Drop the narrow
  "seeded the symptom" framing or pair it with a broader "related
  defects in the same module / same investigation" clause.
- Add a worked counter-example to `upstream-followup.md` showing what
  NOT to do (a side bullet that the parser misses).
- Optionally have `aitask_archive.sh` (or a new helper) validate that
  the plan file contains exactly one
  `- **Upstream defects identified:**` bullet and warn loudly if it
  doesn't — surfaces mis-location at archive time.

Pros: cheap, no behavioral change. Cons: still relies on the agent
classifying correctly the first time.

### Option B — Replace structured-parse with an agent re-read

Delete the structured-parse step. Instead, Step 8b instructs the agent
to **re-read the plan file end-to-end** and answer: "Did the
investigation surface any pre-existing defect in another script /
helper / module that should become its own follow-up task?" The agent
synthesizes a one-line summary from the plan body and presents it to
the user, regardless of which subsection it lives in.

Pros: robust to formatting drift; matches how humans actually review
plan files. Cons: extra plan re-read on every archive (one full Read
call); slightly less deterministic.

### Option C — Hybrid

Keep the structured bullet as the fast path. If it says `None`, also
have the agent re-read the plan file and confirm there's no
related-defect language — a cheap sanity check that catches the
t687 failure mode without paying the re-read cost on every archive.

## Files to consider

- `.claude/skills/task-workflow/SKILL.md` (Step 8 plan-consolidation
  bullet + Step 8b dispatch)
- `.claude/skills/task-workflow/upstream-followup.md`
- Mirror the same changes into `.opencode/skills/task-workflow/`,
  `.gemini/skills/task-workflow/`, `.agents/skills/task-workflow/`
  per CLAUDE.md "WORKING ON SKILLS" guidance — surface the cross-port
  as separate follow-up aitasks at planning time.
- `aitask_archive.sh` if Option A's validate-on-archive sub-fix lands.

## Acceptance

A planning-phase decision selects A / B / C with rationale. Then the
chosen option is implemented end-to-end and verified against the t687
failure mode: a plan that documents a related defect under any
plausible structure must surface a follow-up offer in Step 8b.

## Related

- t687 (`aitasks/archived/t687_*.md`) — the task whose archival missed
  the upstream-defect follow-up that triggered this task.
