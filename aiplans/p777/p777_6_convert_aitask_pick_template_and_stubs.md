---
Task: t777_6_convert_aitask_pick_template_and_stubs.md
Parent Task: aitasks/t777_modular_pick_skill.md
Sibling Tasks: aitasks/t777/t777_*_*.md
Parent Plan: aiplans/p777_modular_pick_skill.md
Base branch: main
Plan revised: 2026-05-18 (re-verified vs current code; hand-off target = task-workflown/)
Depends: [t777_5, t777_21, t777_22, t777_7]
plan_verified:
  - claudecode/opus4_7 @ 2026-05-18 08:52
---

# Plan: t777_6 — Convert `aitask-pick` (PILOT) across all 4 agents

## Context

t777_5/21/22/7 all shipped. Concretely verified on 2026-05-18:
- `aitask_skill_render.sh` (107 lines) + `lib/skill_template.py` implement
  uniform recursive rendering: `walk-write` / `walk-check`, 3-shape ref
  regex (`FULL_PATH_REF_RE`), BFS walk with visited-set cycle detection,
  per-agent path rewriting, closure-aware skip-if-fresh.
- `aitask_skill_verify.sh` does `walk-check` per agent (lines 73–90).
- `.gitignore` covers `<root>/skills/*-/` for all 4 agents.
- `ait skillrun` (269 lines) supports `--profile`, `--profile-override`,
  `--agent-string`, `--dry-run`, `-- <args>`; dispatcher entry at `ait:192`.
- `aitask_skill_resolve_profile.sh` resolves profile names for stubs.
- t777_21 audit lives in the archived plan
  `aiplans/archived/p777/p777_21_*.md` and enumerates a 23-file closure +
  6 files needing edits + 12-key profile-key universe.
- t777_7 wrapped 5 task-workflow files (SKILL.md, planning.md,
  manual-verification-followup.md, remote-drift-check.md,
  satisfaction-feedback.md) under the **parallel name** `task-workflown/`
  per the stage-under-<name>n convention. Live `task-workflow/` is
  untouched.
- Test infra: `tests/test_skill_template.sh` (35 pass),
  `tests/test_skill_render_uniform.sh` (29 pass),
  `tests/test_skill_render.sh` (31 pass).

**Hand-off target decision (user, 2026-05-18):** the pilot template
references `.claude/skills/task-workflown/...` (staged, Jinja-wrapped),
NOT live `task-workflow/`. The pilot thereby exercises every wrapped
profile branch end-to-end. **t777_23** (the swap follow-up, already
filed) will rename `task-workflown` → `task-workflow` AND update
`aitask-pick/SKILL.md.j2`'s references from `task-workflown/...` back
to `task-workflow/...` in the same commit.

## Correction vs the previously-approved plan

The earlier plan had three stale references that the re-verification
caught:

1. `aidocs/stub-skill-pattern.md` (NOT `task-workflow/stub-skill-pattern.md`)
   — the doc was moved to `aidocs/` during t777_22.
2. Hand-off target — now explicitly `task-workflown/` (was ambiguous).
3. The two `skip_task_confirmation` profile-check blocks in current
   `aitask-pick/SKILL.md` are at **lines 44 and 72** (single-line
   "Profile check:" headers), not 44-46 / 72-74. The surrounding blocks
   (Profile-check header + auto-confirm description + skip-question
   text) span ~10 lines each.

## Render model recap (already shipped by t777_22)

When `ait skill render aitask-pick --profile fast --agent claude` runs:

1. Render entry-point `.claude/skills/aitask-pick/SKILL.md.j2` against
   `(profile=fast, agent=claude)` → `.claude/skills/aitask-pick-fast-/SKILL.md`.
2. Scan output for `(\.claude|\.agents|\.gemini|\.opencode)/skills/[^/]+/[^/]+\.md`.
3. Render each referenced file through minijinja (identity pass for
   files without Jinja markers).
4. Write to per-profile sibling location, e.g.
   `.claude/skills/task-workflown-fast-/SKILL.md` for `(fast, claude)`.
5. Rewrite the reference inline: `<root>/skills/<dir>/<file>.md` →
   `<target_root>/skills/<dir>-<profile>-/<file>.md`.
6. Recurse with cycle detection.

Per-profile dir is a self-contained snapshot; runtime stays under
`<root>/skills/<name>-<profile>-/`.

## Scope of t777_6 (5 phases; stage-under-`aitask-pickn` pattern)

The currently-running `aitask-pick` is the very skill executing this
workflow. Broken pilot = broken pick. Stage under parallel name
`aitask-pickn`, verify end-to-end, then atomic rename.

### Phase 1 — Smoke-check infrastructure

Pick any wrapped file from t777_7 and render it standalone to confirm
the toolchain end-to-end:

```bash
./ait skill render task-workflown --profile fast --agent claude --force
ls .claude/skills/task-workflown-fast-/  # entry-point SKILL.md present
```

Verify the rendered `SKILL.md` contains the `default_email` auto-resolve
branch (the fast profile sets `default_email: userconfig`). If this
fails, stop and fix t777_22 / t777_7 before touching the pilot.

### Phase 2 — Author the entry-point template at `aitask-pickn/SKILL.md.j2`

Path: `.claude/skills/aitask-pickn/SKILL.md.j2`.

Source: copy current `.claude/skills/aitask-pick/SKILL.md` (225 lines).

Three edits to the copy:

**Edit 1 — frontmatter name (line ~2):**
```
name: aitask-pick      →   name: aitask-pickn-{{ profile.name }}
```
Rationale: rendered variant directories are `aitask-pickn-<profile>-/`;
the slash-command name must match for stub dispatch.

**Edit 2 — parent-task profile check (around line 44).** Wrap the
"Profile check: If the active profile has `skip_task_confirmation`…"
block plus its trailing `AskUserQuestion` block:
```jinja
{% if profile.skip_task_confirmation %}{# ---------- skip_task_confirmation ---------- #}
- Display: "Profile '<name>': auto-confirming task selection"
- Proceed directly to **Step 3** (Task Status Checks).
{% else %}{# skip_task_confirmation: when false / undefined #}
<existing AskUserQuestion block, unchanged>
{% endif %}{# ---------- end skip_task_confirmation ---------- #}
```
Follow the Jinja comment conventions documented in
`aidocs/skill_authoring_conventions.md` (same-line separator and
inline `endif` label).

**Edit 3 — child-task profile check (around line 72).** Same wrap shape,
same comment labels.

**Reference rewriting:** EVERY mention of `.claude/skills/task-workflow/`
inside the template body must be rewritten to `.claude/skills/task-workflown/`.
This is the hand-off target the user picked. (t777_23 reverts this when
it renames `task-workflown` → `task-workflow`.)

**Sanity checks before commit:**
- No literal Jinja outside the two wrapped blocks (`grep -nE '\{\{|\{%' SKILL.md.j2`
  should only match the two wraps + the `{{ profile.name }}` in frontmatter).
- No per-call-site `{% if agent %}` branches — tool-name mapping handled
  by per-agent prereq files.

### Phase 3 — Write the 4 stubs under `aitask-pickn`

Source: `aidocs/stub-skill-pattern.md` (185 lines). Substitutions per
§3b/§3c/§3d:

| Agent     | Stub path                                         | Section | `<agent_literal>` | `<agent_root>` |
|-----------|---------------------------------------------------|---------|-------------------|----------------|
| Claude    | `.claude/skills/aitask-pickn/SKILL.md`            | §3b     | `claude`          | `.claude/skills` |
| Codex     | `.agents/skills/aitask-pickn/SKILL.md`            | §3b     | `codex`           | `.agents/skills` |
| Gemini    | `.gemini/commands/aitask-pickn.toml` (`prompt`)   | §3c     | `gemini`          | `.gemini/skills` |
| OpenCode  | `.opencode/commands/aitask-pickn.md`              | §3d     | `opencode`        | `.opencode/skills` |

`<skill_short_name>` = `aitask-pickn` in all four.

Each stub calls `aitask_skill_resolve_profile.sh aitask-pickn` (or honors
`--profile <name>` from argv per §3h), then `ait skill render aitask-pickn
--profile <p> --agent <agent_literal>`, then Reads the rendered SKILL.md
and follows it.

**Path collision note:** template is `.../aitask-pickn/SKILL.md.j2`
(extension `.md.j2`), stub is `.../aitask-pickn/SKILL.md` (extension
`.md`). No collision; `.md.j2` is the entry-point convention.

### Phase 4 — Golden-file tests + verify

**Test file:** `tests/test_skill_render_aitask_pickn.sh`.

Matrix: 3 profiles {default, fast, remote} × 4 agents {claude, codex,
gemini, opencode} = 12 entry-point renders. For each:
1. `./ait skill render aitask-pickn --profile <p> --agent <a> --force`
2. Diff entry-point against committed golden
   `tests/golden/skills/aitask-pickn-<p>-<a>/SKILL.md`.
3. Diff every transitively-rendered file in the closure
   (`tests/golden/skills/aitask-pickn-<p>-<a>/<closure-path>`).
4. Assert empty diff per file.

**Stub-marker regression checks:** assert each of the 4 stub files
contains the §3b/§3c/§3d marker comment(s) per stub-skill-pattern.md.

**Verify pass:** `./ait skill verify` exits 0; the dep-walker validates
the new entry-point template + its closure for all 12 combos.

**Live dispatch test (Claude, fresh session) — user-driven:**
- `/aitask-pickn 16` — stub resolves the project default profile
  (`fast` per `aitasks/metadata/userconfig.yaml`), renders, Reads,
  follows. The auto-confirm branch fires inline; control hands to
  `.claude/skills/task-workflown-fast-/SKILL.md`; workflow continues.
- `/aitask-pickn --profile default 16` — stub captures `default`,
  strips `--profile default` from ARGUMENTS, dispatches with `16`
  forwarded; interactive confirm fires.
- Live `/aitask-pick` is untouched throughout.

### Phase 4b — Manual end-to-end verification gate (user-driven, BLOCKS Phase 5)

**Hard gate.** Phase 5 (atomic rename) does NOT begin until the user has
manually exercised `aitask-pickn` end-to-end in a fresh Claude session
and explicitly signed off. Automated goldens / `ait skill verify`
PASSING is necessary but NOT sufficient — only live dispatch confirms
that the rendered closure actually drives a real workflow.

**Verification checklist** (the user runs each; the implementer reads
results and decides whether to advance to Phase 5):

1. **Fast profile, parent-task path** — In a fresh Claude session in
   this repo, type `/aitask-pickn 16` (substitute any open parent task
   the user wants to test against, or a placeholder ID that exists).
   Expected: auto-confirm fires inline (no "Is this the correct task?"
   AskUserQuestion); flow lands in `task-workflown-fast-/SKILL.md` at
   Step 3; the userconfig email resolves silently per `default_email:
   userconfig`. **Abort the run before any state-changing tool call**
   so the test does not actually claim a real task.

2. **Default profile, interactive path** — In a fresh session, type
   `/aitask-pickn --profile default 16`. Expected: the stub strips the
   `--profile default` arg, dispatches to
   `aitask-pickn-default-/SKILL.md`, the interactive AskUserQuestion
   for parent confirmation appears. Cancel via "No, abort".

3. **Child task, fast profile** — In a fresh session, type
   `/aitask-pickn 777_6` (this very task; safe because it is
   already-owned by the user, so `aitask_pick_own.sh` will produce
   `LOCK_RECLAIM:` / `RECLAIM_CRASH:` / `RECLAIM_STATUS:` rather than
   `OWNED:`). Expected: stub dispatches to fast variant; profile-check
   for child task auto-confirms; archived sibling plans are gathered;
   flow lands at Step 3. Abort before destructive ops.

4. **Remote profile (no Claude dispatch — `--dry-run` only)** —
   `./ait skillrun pick --profile remote --dry-run 16`. Expected:
   prints a synthesized Claude argv with `/aitask-pickn --profile remote 16`
   (or equivalent). No process spawn.

5. **Stub-marker spot-check (all 4 agents)** — Read each of the 4 stub
   files and confirm visually that the stub-skill-pattern.md §3b/§3c/§3d
   marker comments are present. (Programmatic checks already ran in
   Phase 4; this is the human eyes-on pass.)

6. **Rendered closure inspection (claude/fast)** — Open
   `.claude/skills/aitask-pickn-fast-/SKILL.md` and visually confirm:
   - Frontmatter `name: aitask-pickn-fast-` (matches dir).
   - No `{% if`, `{% else`, `{% endif`, `{{ profile.` markers leak in
     the rendered output (Jinja fully expanded).
   - Auto-confirm text appears inline at the two `skip_task_confirmation`
     sites; no "Profile check:" headers visible.
   - References to `task-workflown` are rewritten to
     `.claude/skills/task-workflown-fast-/...`.

7. **Original `/aitask-pick` regression check** — `/aitask-pick 16`
   in a fresh session still works exactly as it did before this task
   landed (it has not been touched yet — but verify nothing in the
   `aitask-pickn` rollout accidentally broke the live skill, e.g. via a
   shared stub-skill-pattern.md edit). Abort before destructive ops.

**Sign-off:** the user runs the 7 checks and reports
PASS / FAIL / DEFER per item. Any FAIL blocks Phase 5; the implementer
diagnoses, fixes, re-runs `ait skill verify`, re-renders, and re-issues
the verification request. Any DEFER must be resolved before Phase 5
unless explicitly waived by the user.

**Optional: file a `manual_verification` sibling task.** If the user
prefers to track the verification via the framework's own
`issue_type: manual_verification` flow, the implementer creates
`t777_<next>_manual_verify_aitask_pickn` via
`aitask_create_manual_verification.sh` with the 7-item checklist above,
sets `depends: [t777_6]`, and Phase 5 waits until that task is marked
`Done`. This is the recommended path because it leaves a durable record
in the archive. The implementer offers this option at the end of Phase 4
via the standard manual-verification-followup procedure.

### Phase 5 — Atomic rename `aitask-pickn` → `aitask-pick`

Only after Phase 4b sign-off. Single commit:
1. Delete the 4 original `aitask-pick` artifacts (the live old-style
   stubs): `.claude/skills/aitask-pick/SKILL.md`,
   `.agents/skills/aitask-pick/SKILL.md`,
   `.gemini/commands/aitask-pick.toml`,
   `.opencode/commands/aitask-pick.md`.
2. `mv` every staged `aitask-pickn` file to its `aitask-pick` counterpart
   (including the `.md.j2` template).
3. String-replace `aitask-pickn` → `aitask-pick` inside each moved file
   AND in `tests/test_skill_render_aitask_pickn.sh` (rename file too).
4. Move `tests/golden/skills/aitask-pickn-*/` → `tests/golden/skills/aitask-pick-*/`.
5. Delete now-empty `.claude/skills/aitask-pickn/`,
   `.agents/skills/aitask-pickn/`. Local rendered `aitask-pickn-*-/`
   trees are gitignored — leave or `rm -rf` as housekeeping.
6. `./ait skill render aitask-pick --profile <p> --agent <a> --force`
   for all 12 combos.
7. `bash tests/test_skill_render_aitask_pick.sh` + `./ait skill verify`
   — both green.

### Phase 6 — Append pilot findings to `aidocs/stub-skill-pattern.md`

New section `## Pilot findings (t777_6)` documenting:
- Uniform recursive rendering renders every referenced markdown.
- Stage-under-`<skill>n` pattern is required when the skill is in active
  use (canonical entry: `feedback_stage_under_parallel_name`).
- Golden-file tests are a hard requirement per
  `feedback_golden_file_tests_for_template_engines`.
- Entry-point templates use `.md.j2`; referenced procedures keep `.md`.
- Per-agent tool-name mapping (AskUserQuestion vs request_user_input
  vs human-prompt) stays in per-agent prereq files, NOT in `{% if agent %}`
  branches inside the template body.

## Verification (end-to-end)

1. `./ait skill verify` exits 0 — entry-point + closure walk for all
   12 (profile × agent) combos.
2. `bash tests/test_skill_render_aitask_pick.sh` passes.
3. **Phase 4b sign-off**: the user's 7-item manual checklist on
   `aitask-pickn` is all PASS (no FAIL, no unresolved DEFER) BEFORE
   Phase 5 begins.
4. Post-rename: live Claude dispatch handles `/aitask-pick 16`,
   `/aitask-pick --profile default 16`, and the existing pick flow.
5. `git status` clean of `aitask-pickn` artifacts after Phase 5.
6. Rendered `<root>/skills/*-/` dirs unstaged (gitignore intact).

## Step 9 (Post-Implementation) reference

Per `task-workflow/SKILL.md` Step 9:
- Code commit: source template + 4 stubs + test script + goldens, using
  `refactor: <description> (t777_6)`.
- Plan commit (separately, via `./ait git`).
- `aitask_archive.sh 777_6`, then `./ait git push`.

No linked issue.

## Follow-up: t777_23 (already filed, depends on this task)

After t777_6 lands and manual verification passes, t777_23:
1. Renames `.claude/skills/task-workflown/` → `.claude/skills/task-workflow/`
   (overwriting the live, untouched copy).
2. Updates `aitask-pick/SKILL.md.j2`'s body references from
   `.claude/skills/task-workflown/...` back to `.claude/skills/task-workflow/...`.
3. Re-renders all 12 combos, re-runs goldens (which now reference
   `task-workflow-<p>-` paths), commits.

This 2-step landing is the cost of the user's "Reference `task-workflown/`
(staged)" decision, in exchange for full Jinja-branch exercise in the
pilot.
