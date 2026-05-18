---
priority: high
effort: low
depends: []
issue_type: chore
status: Implementing
labels: [aitask_pick]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-05-18 08:53
updated_at: 2026-05-18 09:02
---

## Context

Prerequisite for t777_22 (recursive renderer) and t777_7 (task-workflow profile branches). Discovers the static markdown-reference closure starting from `.claude/skills/aitask-pick/SKILL.md` and enumerates every profile-key usage within that closure. Output is a one-shot audit document — no code changes.

Discovered during t777_6 verify-pass on 2026-05-18: aitask-pick's pilot conversion alone proves nothing about real composed skills because Step 3 hands off to `task-workflow/SKILL.md` which itself loads ~16 sub-procedures, many of which contain their own runtime "Profile check:" blocks (`plan_preference`, `post_plan_action`, `default_email`, `create_worktree`, `base_branch`, `plan_verification_required`, …). Without the dep-walker (t777_22) and the task-workflow conversion (t777_7), the templating model leaks at the very first hand-off.

## Scope

1. Walk static markdown references starting from `.claude/skills/aitask-pick/SKILL.md`. Follow any `<root>/skills/<dir>/<file>.md` reference recursively. Cycle-detect.
2. For each file in the closure, run `grep -nE 'Profile check:|profile\.'` and record the exact line numbers + profile keys consumed.
3. Output a markdown table in the plan file (`aiplans/p777/p777_21_*.md`) with columns: file path, total profile-check sites, profile keys consumed, brief sample of the conditional text.
4. Summarize: which files need editing in t777_7 (have profile-check sites) and which pass through identity-render unchanged.

## Deliverables

- Discovery doc inside the plan file. No code changes.
- The doc drives:
  - t777_22's golden-file test corpus (every file with profile keys needs per-profile coverage).
  - t777_7's edit list (only the files with profile-check sites need `{% if profile.<key> %}` wrapping).

## Verification

- `grep -lr 'Profile check:' .claude/skills/task-workflow/` enumeration is reproducible.
- Plan file contains the markdown table covering the full closure.
