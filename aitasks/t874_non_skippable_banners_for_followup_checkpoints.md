---
priority: medium
effort: low
depends: []
issue_type: enhancement
status: Ready
labels: [task_workflow, claudeskills]
created_at: 2026-05-31 12:47
updated_at: 2026-05-31 12:47
boardidx: 240
---

Add `⚠️ NON-SKIPPABLE` banners to task-workflow **Steps 8b, 8c, and 9b**, mirroring
the banners already present on Step 8 (commit review) and Step 9 (merge approval).

## Background

This re-files what the (now-vanished) task **t782** was meant to cover. Surfaced
during t869, when the memory `feedback_system_injected_directives_scope` was
deleted after promoting durable conventions into aidocs. That memory asserted
that all of task-workflow's contractual AskUserQuestion checkpoints — Step 8
commit review, Step 8b upstream-defect follow-up, Step 8c manual-verification
follow-up, Step 9 merge approval, Step 9b satisfaction feedback — must NOT be
skipped by "work without stopping" / auto-mode / execution-profile shortcuts
unless a profile key explicitly named in SKILL.md covers them.

Audit at t869 time (`.claude/skills/task-workflow/SKILL.md`):
- **Step 8** (`~:296`) and **Step 9** (`~:429`) already carry the
  `⚠️ NON-SKIPPABLE — Auto mode and execution profiles do NOT bypass this …`
  banner. These are the load-bearing gates over irreversible actions (commit,
  merge), so the safety net is intact.
- **Step 8b** (`~:403`), **Step 8c** (`~:413`), **Step 9b** (`~:570`) have NO
  banner. They are softer (follow-up offers + feedback/stats collection), which
  is why they were deferred out of the t869 docs task.

## Scope / design decisions to make

1. Decide the exact banner wording for 8b/8c/9b. They are "offer / record"
   steps, not irreversible-action gates — consider whether the banner should be
   identical to 8/9 or a slightly softer "record-the-data / offer-must-fire"
   variant. Note that skipping 9b loses verified-model + usage stats, and
   skipping 8b/8c loses follow-up-task offers.
2. Confirm whether any execution-profile key legitimately opts out of these
   (e.g. a feedback/qa profile knob). If so, the banner must name it as the only
   valid skip — matching how Step 8/9 banners are phrased.

## Key files

- `.claude/skills/task-workflow/SKILL.md` — the profile-aware source of truth.
  This is a rendered closure: editing it requires regenerating the per-profile
  goldens under `tests/golden/skills/task-workflow/` (and `tests/golden/procs/`
  if affected) and running `./.aitask-scripts/aitask_skill_verify.sh`, per the
  "Regenerate goldens after any `.md.j2` or closure edit" rule in
  `aidocs/skill_authoring_conventions.md` and CLAUDE.md.
- Mirror the change into the other code agents' task-workflow copies if they are
  full copies (verify stub-vs-full first — see
  `aidocs/skill_authoring_conventions.md` "Before porting skill-wording fixes").

## Verification

- `grep -n "NON-SKIPPABLE" .claude/skills/task-workflow/SKILL.md` shows banners
  on Steps 8, 8b, 8c, 9, 9b.
- Goldens regenerated and committed in the same change; `aitask_skill_verify.sh`
  passes.

## Why this is a standalone task and not part of t869

t869 was a documentation/memory-consolidation task (markdown only). This is a
profile-aware skill-closure edit with a goldens-regeneration footprint — a
distinct workflow-hardening change that warrants its own review.
