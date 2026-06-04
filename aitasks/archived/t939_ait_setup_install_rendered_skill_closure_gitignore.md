---
priority: medium
risk_code_health: low
risk_goal_achievement: low
effort: low
depends: []
issue_type: enhancement
status: Done
labels: []
file_references: [.aitask-scripts/aitask_setup.sh:1347-1390, .gitignore:28-57, .aitask-scripts/aitask_skill_render.sh]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_8
created_at: 2026-06-04 11:57
updated_at: 2026-06-04 12:16
completed_at: 2026-06-04 12:16
---

## Problem

`ait setup` (`aitask_setup.sh` Step 7, "Update .gitignore on main") installs the
data-branch ignore block (`.aitask-data/`, `aitasks`, `aiplans`) into a consumer
project's `.gitignore`, but it does **not** install the per-profile
rendered-skill-closure ignore patterns. As a result, every consumer project that
runs a profile-aware skill (pick/explore/qa/…) accumulates untracked
`.claude/skills/<skill>-<profile>-/` directories (e.g. `aitask-pick-fast-/`,
`task-workflow-default-/`) as `git status` noise, because `aitask_skill_render.sh`
renders those closures on demand.

This repo (`aitasks`) already carries the correct, working scheme in its own
`.gitignore` (the block at lines ~28-57), but consumer projects never receive it
because setup doesn't write it.

## Desired behaviour

Extend `aitask_setup.sh` Step 7 so it also installs the rendered-skill-closure
ignore block into the consumer `.gitignore`, matching the canonical scheme used
in this repo's `.gitignore`:

- Broad ignore (trailing-hyphen convention marks a rendered closure; authoring
  dirs never end in a hyphen):
  ```
  .claude/skills/*-/
  .agents/skills/*-/
  .opencode/skills/*-/
  ```
- Negations (`!`) that re-include the committed headless prerenders so they stay
  tracked for Claude Code Web where `ait setup` has not run — the `*-remote-`
  (and `*-remote-codex-`) closures for `aitask-pickrem`, `aitask-pickweb`, and
  `task-workflow` across the agent roots.

**Note — exclude `.gemini`:** do NOT include any `.gemini/skills/` lines.
`.gemini` is no longer a required agent root. The canonical `.gitignore` block in
this repo still carries stale `.gemini/skills/*-/` and `!.gemini/...` lines from
when it was supported; mirror the scheme **minus** `.gemini`, and drop those
stale lines from this repo's `.gitignore` as part of the change so the two stay
in sync.

Requirements:
- **Idempotent**, like the existing block: detect a sentinel (e.g. grep for
  `.claude/skills/*-/`) and append only if absent; set `gitignore_changed=true`
  so Step 9 commits it.
- Order matters: the `!` negations MUST come after the broad `*-/` patterns.
- Keep it symlink/clone-safe and consistent with the migration handling already
  in Step 7.

## Relationship to t777_29

The negation list in this repo's `.gitignore` is currently hardcoded with a
`TODO(t777_29)` to replace it with an auto-generated section produced by
`aitask_regen_gitignore_prerender.sh` (scan `headless: true` profiles ×
`prerender_for_headless: true` skills × agents). That generator does not exist
yet. Two options:
1. **Interim (recommended, unblocks now):** have setup write the same hardcoded
   block this repo ships, sourced from a single shared snippet so the two stay in
   sync.
2. **Full:** implement `aitask_regen_gitignore_prerender.sh` (as t777_29 plans)
   and have both this repo's `.gitignore` and `ait setup` consume its output.
Coordinate with t777_29 so the negation list has one source of truth rather than
being duplicated in two hardcoded places.

## Key files

- `.aitask-scripts/aitask_setup.sh` — Step 7 "Update .gitignore on main"
  (~lines 1347-1390); Step 9 commit.
- `.gitignore` — the canonical closure-ignore block (~lines 28-57) to mirror.
- `.aitask-scripts/aitask_skill_render.sh` — the `<skill>-<profile>-/` closure
  naming convention (trailing hyphen).
- `.claude/skills/task-workflow/stub-skill-pattern.md` — full design of the
  stub/render/closure pattern.

## Verification

- Run `ait setup` in a fresh consumer repo; confirm its `.gitignore` gains the
  `*-/` block plus the prerender negations.
- After running a profile-aware skill (which renders a local closure), confirm
  the rendered dir is git-ignored (`git check-ignore` hits) and `git status` is
  clean.
- Confirm the committed `*-remote-` prerenders remain tracked (negations win).
- Re-run `ait setup`; confirm the block is not duplicated (idempotent).
