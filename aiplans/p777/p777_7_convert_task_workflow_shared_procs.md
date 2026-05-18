---
Task: t777_7_convert_task_workflow_shared_procs.md
Parent Task: aitasks/t777_modular_pick_skill.md
Sibling Tasks: aitasks/t777/t777_*_*.md
Archived Sibling Plans: aiplans/archived/p777/p777_*_*.md
Worktree: (none — work on current branch)
Branch: main
Base branch: main
plan_verified:
  - claudecode/opus4_7 @ 2026-05-18 12:31
---

# Plan: t777_7 — Wrap profile-check sites in `task-workflow/*.md`

## Context

Re-scoped on 2026-05-18 after the t777_22 verify-pass. The earlier draft
of this plan called for renaming files to `.j2` and rewriting
cross-references in templates — both obsoleted by the t777_22 dep-walker
which renders every reachable `.md` through minijinja (identity-transform
when no Jinja markers) and rewrites cross-references at render time.

**What this task ships:** the 9 `{% if profile.<key> %}…{% else %}…{% endif %}`
wraps enumerated in t777_21's audit, across 5 task-workflow procedure
files — **staged under a parallel directory `.claude/skills/task-workflown/`
so the live `task-workflow/` stays untouched until t777_6 (pilot) is
manually verified.**

This follows the memory rule
[`feedback-stage-under-parallel-name`]: never overwrite an actively-running
skill directly. The current aitask-pick workflow (and every other skill
in active use) reads `.claude/skills/task-workflow/*.md` directly today;
overwriting them in-place before t777_6 lands AND is manually verified
would leave users mid-workflow with no working `/aitask-pick` if anything
in the wrap-or-render chain is wrong.

**Prerequisites already landed:**
- t777_21 — audit (closure walk + per-file branch-site table) — archived.
- t777_22 — dep-walker `walk-write` / `walk-check` + `aidocs/stub-skill-pattern.md` §3i — archived.

**Downstream consumers** (require the staged directory):
- t777_6 (pilot pick conversion, `Ready`) — its `aitask-pick/SKILL.md.j2`
  references `.claude/skills/task-workflown/SKILL.md` (and siblings via
  the same dir). After t777_6 lands and is manually verified, the
  atomic-rename follow-up swaps `task-workflown` → `task-workflow`.
- t777_8..t777_15 — also reference `task-workflown/` until the swap.

## Staging directory `.claude/skills/task-workflown/`

The new directory contains a copy of **every** file in `task-workflow/`
(22 files total per t777_21's audit), so the dep-walker's closure can
resolve entirely within `task-workflown/`:

- **5 files with wraps** applied (this task's net new prose).
- **17 files as byte-identical copies** of the originals (identity-render
  passthrough).

Both kinds use the same filename as in `task-workflow/`. The 17
identity copies are committed as plain files (not symlinks) for two
reasons: (a) cleaner git diff post-rename, (b) Windows / cross-platform
checkouts treat tracked symlinks inconsistently.

The original `.claude/skills/task-workflow/*.md` files stay UNTOUCHED.
Live agents (pre-t777_6) continue to read the original directory and
behave exactly as today.

### Cleanup follow-up (new sibling task)

Surface a new sibling task `t777_23_swap_task_workflown_to_task_workflow`
(or similarly named) with:

- `depends: [t777_6]` — must wait for the pilot conversion AND its
  manual-verification follow-up to land.
- Scope: delete `task-workflow/`, `git mv task-workflown → task-workflow`,
  string-replace `task-workflown` → `task-workflow` inside every file
  that references it (aitask-pick/SKILL.md.j2, t777_8..15 templates as
  they land, etc.), all in one commit.
- Verification: `./ait skill verify` clean; live `/aitask-pick` smoke from
  a fresh agent session.

Creating this follow-up is **part of t777_7's deliverables** (so the
swap doesn't get forgotten). It is filed during Step 1's planning
phase and committed alongside the staged dir.

## Wrap Convention

Per `aidocs/stub-skill-pattern.md` and t777_22's `render_skill` (strict
undefined mode), we use `is defined` to test key presence:

1. **Outer guard:** `{% if profile.<key> is defined %}…{% else %}<existing
   interactive block>{% endif %}`. For sites that consult multiple keys
   (e.g. `plan_preference` + `plan_preference_child`), use
   `{% if profile.A is defined or profile.B is defined %}`.
2. **Boolean values** (`create_worktree`): nested
   `{% if profile.X %}<true-branch text>{% else %}<false-branch text>{% endif %}`.
3. **String values** (`base_branch`): inline via `{{ profile.<key> }}`.
4. **Enum values** (`plan_preference`, `post_plan_action`,
   `manual_verification_followup_mode`, `remote_drift_check`): nested
   `{% if value == "X" %}…{% elif value == "Y" %}…{% endif %}`.
5. **Display message format:** rewrite `"Profile '<name>': ..."` to
   `"Profile '{{ profile.name }}': ..."`.
6. **`is_child` priority resolution stays as prose inside the true
   branch** (chosen 2026-05-18 by user; option A in the planning
   AskUserQuestion). `is_child` is not a render-time Jinja variable;
   extending the t777_22 renderer signature is explicitly out of scope.

## Wrap Sites (9 total, 5 files)

Confirmed against current file content on 2026-05-18 (line numbers
stable vs. t777_21 audit). All edits land in `task-workflown/`, not
`task-workflow/`.

### `task-workflown/SKILL.md` (3 sites)

| Source line | Block | Key(s) |
|------|-------|--------|
| 98–102 | Step 4 default-email selection | `default_email` |
| 183–191 | Step 5 worktree create/skip | `create_worktree` |
| 198–205 | Step 5 base-branch | `base_branch` |

### `task-workflown/planning.md` (2 wraps spanning 3 sites)

| Source line | Block | Key(s) |
|------|-------|--------|
| 29–62 | Step 6.0 plan-preference + Verify Decision sub-procedure | `plan_preference`, `plan_preference_child`, `plan_verification_required`, `plan_verification_stale_after_hours` |
| 290–310 | Checkpoint effective-action resolution | `post_plan_action`, `post_plan_action_for_child` |

Note: L29's wrap subsumes the Verify Decision sub-procedure (L35–62)
because the sub-procedure runs only when the effective preference is
`"verify"`. `plan_verification_required` /
`plan_verification_stale_after_hours` get inlined via
`{{ profile.X | default(1) }}` / `{{ profile.X | default(24) }}` so the
defaults from existing prose are preserved.

### `task-workflown/manual-verification-followup.md` (1 site)

| Source line | Block | Key(s) |
|------|-------|--------|
| 31–37 | Step 1 profile check (`never` short-circuit) | `manual_verification_followup_mode` |

### `task-workflown/remote-drift-check.md` (1 site)

| Source line | Block | Key(s) |
|------|-------|--------|
| 17 | Step 1 profile check (`skip` short-circuit) | `remote_drift_check` |

Special care: the value appears as the backticked phrase
`` `remote_drift_check: skip` `` in source. Wrap converts to
`{% if profile.remote_drift_check is defined and profile.remote_drift_check == "skip" %}…{% else %}…{% endif %}`.

### `task-workflown/satisfaction-feedback.md` (1 site)

| Source line | Block | Key(s) |
|------|-------|--------|
| 48–50 | Step 1.1 feedback-disable short-circuit | `enableFeedbackQuestions` |

## Step Order

### Step 1 — Create the staging directory

```bash
mkdir -p .claude/skills/task-workflown
cp -a .claude/skills/task-workflow/. .claude/skills/task-workflown/
```

This produces an exact 22-file copy. The original `task-workflow/`
remains untouched.

### Step 2 — Wrap the 9 sites in `task-workflown/`

Edit each of the 5 target files via `Edit`, applying the convention
above. The other 17 files in `task-workflown/` stay byte-identical to
their `task-workflow/` siblings.

### Step 3 — File the cleanup follow-up sibling task

```bash
./.aitask-scripts/aitask_create.sh --batch \
  --parent 777 \
  --name swap_task_workflown_to_task_workflow \
  --priority high --effort low \
  --issue-type chore \
  --add-depends 777_6 \
  --desc "Atomic swap of staged \`task-workflown/\` → \`task-workflow/\` after t777_6 (pilot) lands and its manual verification passes. Deletes the original, renames the staged dir, and rewrites \`task-workflown\` → \`task-workflow\` references in every template / authoring file. Single commit."
```

### Step 4 — Golden-file regression tests

Create `tests/golden/procs/task-workflown/<name>-<profile>.md` for each
(file, profile) combination across {default, fast, remote}. Total: 5
files × 3 profiles = **15 golden files**.

Single-file `render_skill` CLI is sufficient (no dep-walker needed) —
task-workflow files reference each other via sibling refs which the
walker would leave unchanged. The agent dimension is verified as
byte-identity separately.

### Step 5 — New test script `tests/test_skill_render_task_workflown.sh`

Cases:

1. **Per-(file, profile) golden diff** — render each of the 5 modified
   files via `python skill_template.py
   .claude/skills/task-workflown/<file>.md aitasks/metadata/profiles/<profile>.yaml claude`
   and diff against
   `tests/golden/procs/task-workflown/<file-stem>-<profile>.md`. Fail
   on non-empty diff.
2. **Agent byte-identity** — render `SKILL.md` with profile=fast for
   each of {claude, codex, gemini, opencode}; assert all 4 outputs are
   byte-identical.
3. **`default` profile is interactive-equivalent** — for each modified
   file, the `default`-profile render must include every existing
   interactive `AskUserQuestion` block verbatim. Spot-check via
   `assert_contains` on `"Otherwise, use \`AskUserQuestion\`"` and
   similar key phrases.
4. **Untouched 17 files are byte-identical** to their `task-workflow/`
   siblings (regression guard against accidental edits in the staged
   identity-render copies).

### Step 6 — Verification

1. `bash tests/test_skill_render_task_workflown.sh` passes.
2. `bash tests/test_skill_template.sh` still passes (sanity).
3. `bash tests/test_skill_render.sh` still passes (sanity).
4. `bash tests/test_skill_render_uniform.sh` still passes (sanity).
5. `./ait skill verify` exits 0 — still no `.j2` entry templates exist
   (t777_6 not landed yet); verify prints "no .j2 templates found —
   nothing to verify".
6. Manual smoke: `python .aitask-scripts/lib/skill_template.py
   .claude/skills/task-workflown/SKILL.md
   aitasks/metadata/profiles/fast.yaml claude` produces output where
   the `create_worktree` block emits straight-line "Work on current
   branch" text (fast.yaml has `create_worktree: false`) and the
   AskUserQuestion block is absent.
7. **Live `task-workflow/` still works untouched:** `diff -r
   .claude/skills/task-workflow/ <previous-HEAD-snapshot>` shows zero
   changes. Live `/aitask-pick` continues to read the original
   `task-workflow/` files.

## Critical Files

- **New directory:** `.claude/skills/task-workflown/` (22 files: 5 with
  wraps, 17 byte-identical copies)
- **New test:** `tests/test_skill_render_task_workflown.sh`
- **New goldens (15):** `tests/golden/procs/task-workflown/<name>-<profile>.md`
  - `SKILL-{default,fast,remote}.md`
  - `planning-{default,fast,remote}.md`
  - `manual-verification-followup-{default,fast,remote}.md`
  - `remote-drift-check-{default,fast,remote}.md`
  - `satisfaction-feedback-{default,fast,remote}.md`
- **New task (filed in Step 3):**
  `aitasks/t777/t777_NN_swap_task_workflown_to_task_workflow.md`

**Untouched:** `.claude/skills/task-workflow/*` — every file stays
byte-identical to current HEAD until the swap follow-up lands.

## Out of scope

- Editing the live `.claude/skills/task-workflow/` files (the entire
  point of staging).
- File extension changes (`.md` stays `.md` per t777_22 Decision 1).
- Render-path rewriting in templates (the dep-walker handles
  cross-references at render time).
- Adding `is_child` as a render-time Jinja variable.
- Wrapping `aitask-pick/SKILL.md` (owned by t777_6).
- The atomic swap itself (owned by the new follow-up sibling filed in
  Step 3).

## Step 9 — Post-Implementation

Standard child-task archival via
`./.aitask-scripts/aitask_archive.sh 777_7`. Commit the staging dir
contents + new test script + goldens under
`refactor: Stage wrapped profile-check sites under task-workflown (t777_7)`.
The follow-up sibling task file is committed under `ait:` via `./ait git`.
Plan file commit goes through `./ait git`. Push.

## Notes for sibling tasks

- **t777_6 (PILOT pick conversion):** the `aitask-pick/SKILL.md.j2`
  template MUST reference `.claude/skills/task-workflown/...` (not
  `.claude/skills/task-workflow/...`) until the swap follow-up lands.
  Update t777_6's plan accordingly when picking it.
- **t777_8..t777_15:** same — author their templates to reference
  `task-workflown/`.
- **The swap follow-up (filed in Step 3):** must rewrite every
  `task-workflown` reference back to `task-workflow` in a single
  commit, after t777_6's manual verification passes.
- **is_child priority caveat:** L29 (`plan_preference`) and L290–294
  (`post_plan_action`) wraps preserve `is_child` priority logic as
  prose. If a future task adds `is_child` as a render-time variable,
  those prose blocks can be tightened to straight-line. Not in scope.
