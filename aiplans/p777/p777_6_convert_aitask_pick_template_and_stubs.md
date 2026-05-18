---
Task: t777_6_convert_aitask_pick_template_and_stubs.md
Parent Task: aitasks/t777_modular_pick_skill.md
Sibling Tasks: aitasks/t777/t777_*_*.md
Parent Plan: aiplans/p777_modular_pick_skill.md
Base branch: main
Plan revised: 2026-05-18 (verify-pass + user-directed scope split into new sibs
+ user-directed uniform recursive rendering — no classification step)
New depends after this plan: [t777_5, t777_21, t777_22, t777_7]
plan_verified:
  - claudecode/opus4_7 @ 2026-05-18 08:52
---

# Plan: t777_6 — Convert `aitask-pick` (PILOT) across all 4 agents

## Context

t777_1..5 delivered the basic template/render/verify/skillrun
machinery. Today's verify-pass exploration surfaced that
`aitask-pick` hands off to `task-workflow/SKILL.md` at Step 3, which
in turn loads ~16 sub-procedures (planning.md, plan-externalization.md,
execution-profile-selection.md, agent-attribution.md, …). Some of
those procedure files contain their own runtime "Profile check:"
blocks. **Without a render-time mechanism that follows the reference
graph, the templating model leaks at the very first hand-off** and
the pilot proves nothing about real composed skills.

Two user directions reshape the plan:

1. **Split the architectural work into new sibling tasks** at the
   t777 level (using next available numbers — t777_20 is the last
   existing child, so new ones are t777_21, t777_22).
2. **Uniform recursive rendering.** The renderer ALWAYS renders every
   referenced markdown file into the per-profile dir, regardless of
   whether the file uses any profile keys. Files without Jinja
   syntax pass through unchanged (minijinja identity transform). This
   removes the audit/classification step entirely, simplifies the
   renderer logic, and makes future drift self-healing (a procedure
   that acquires a profile branch tomorrow is automatically included
   in the per-profile snapshot — no second audit required).

## Render model (uniform recursive rendering, set by user)

When `ait skill render aitask-pick --profile fast --agent claude`
runs:

1. Render the entry-point template
   `.claude/skills/aitask-pick/SKILL.md.j2` against
   `(profile=fast, agent=claude)` → output to
   `.claude/skills/aitask-pick-fast-/SKILL.md`.
2. Scan the rendered output for **all markdown references** matching
   `(\.claude|\.agents|\.gemini|\.opencode)/skills/[^/]+/[^/]+\.md` (or
   the same relative form).
3. For every reference, treat the referenced file as a Jinja template
   regardless of extension. Render it through minijinja against the
   same `(profile, agent)` context. Files without Jinja markers come
   out byte-identical (identity transform).
4. Write each rendered reference to its per-profile sibling location:
   - Source `.claude/skills/task-workflow/SKILL.md`
   - For `(fast, claude)` → `.claude/skills/task-workflow-fast-/SKILL.md`
   - For `(fast, codex)`  → `.agents/skills/task-workflow-fast-/SKILL.md`
   - …same shape for gemini, opencode (using their `<root>/skills/`).
5. Rewrite the reference in the calling rendered file from
   `<root>/skills/<dir>/<file>.md` to
   `<target_root>/skills/<dir>-<profile>-/<file>.md`. `<target_root>`
   is determined by the current `--agent`.
6. Recurse on the newly rendered references (cycle-detect via a
   visited set keyed on source path).

End result: the per-profile dir is a **self-contained snapshot**. The
entry-point skill plus every transitive `.md` it references lives
under `<root>/skills/...-<profile>-/`, all references rewritten to
sibling per-profile paths. Nothing leaks back to the un-suffixed
source dirs at runtime.

Gitignore already covers `<root>/skills/*-/` for all 4 agents, so
none of this output goes into git.

## New / re-scoped sibling tasks

### t777_21 — Map `aitask-pick`'s reference closure + identify profile-key sites within it
- Walk the static reference graph starting from
  `.claude/skills/aitask-pick/SKILL.md` and produce the full closure of
  `<root>/skills/...` markdown references.
- For each file in the closure, grep for `Profile check:` / `profile.`
  to list the **exact profile keys consumed**. Output as a markdown
  table in `aiplans/p777/p777_21_*.md`.
- This is NOT a classification step (uniform recursive rendering
  removes that need). It is just a discovery doc that drives t777_22's
  test cases (which files need profile-branch coverage in the
  golden-file tests) and t777_7's scope (which files need editing to
  add `{% if profile.<key> %}` branches).
- Effort: small. No code changes.

### t777_22 — Extend `aitask_skill_render.sh` + `lib/skill_template.py` for uniform recursive rendering
- Implement the render model above.
- Reference discovery: regex over rendered output for the markdown
  path pattern. Add a small whitelist of skip-paths (e.g.
  `.claude/skills/*/stub-skill-pattern.md` is a doc, not a procedure
  — but actually still safe to render-as-identity, so probably no
  whitelist needed).
- Path rewriting: simple string substitution per reference at write
  time.
- Cycle detection: visited set on source path; second hit re-uses
  the already-rendered target.
- Skip-if-fresh extends to the dep closure: any stale leaf invalidates
  the entire chain back to the entry point.
- `./ait skill verify` extends to walk the dep graph for every
  authoring template found.
- Test coverage:
  - Unit test for reference discovery regex (positive + negative cases).
  - Unit test for path rewriting.
  - Cycle-detection test (synthetic A↔B fixture).
  - Integration test rendering a tiny synthetic skill with one
    reference, verifying the per-profile sibling tree.
- Effort: high.

### t777_7 (existing — re-scope) — Add `{% if profile.<key> %}` branches to `task-workflow/` files identified by t777_21
- The current `t777_7_convert_task_workflow_shared_procs.md` is
  vaguely scoped; tighten to: edit only the specific profile-check
  sites enumerated by t777_21's audit, wrapping each in a Jinja
  conditional. No renaming, no `.j2` extension needed (renderer
  treats every `.md` as a template).
- Add golden-file tests for each modified file, mirroring the pilot's
  pattern (`tests/golden/procs/task-workflow/<name>-<profile>.md`).
- Effort: medium.

### Update existing per-skill conversion tasks
Add `depends: [t777_22, t777_7]` to t777_8..t777_15 (per-skill
conversions). One-line metadata edit per task — handled inside
t777_22's plan, not in pilot scope.

### t777_6 — Pilot conversion of `aitask-pick` (this task, re-scoped)
- New `depends: [t777_5, t777_21, t777_22, t777_7]`.
- Status reverts to `Ready` at the end of the current pick session.

## Scope of t777_6 itself (the pilot, once prereqs land)

Five steps once the dep-walker exists and `task-workflow/` is template-ready:

### Step 1. Smoke-check the new infrastructure
- Run `./ait skill verify` end-to-end on a known-good shared
  procedure already delivered by t777_7. Confirm the rendered
  per-profile snapshot is self-contained.

### Step 2. Stage under `aitask-pickn`
The current `aitask-pick` is the skill running this very workflow; a
broken pilot leaves the user unable to pick anything. Build template +
4 stubs + golden tests under the parallel name `aitask-pickn` and
fully verify before any atomic rename.

### Step 3. Author `.claude/skills/aitask-pickn/SKILL.md`
**Note** (per uniform rendering): no rename to `.md.j2` is required.
The file is just `.md`; the renderer treats all `.md` files as
templates. (We can still adopt `.md.j2` as a *convention* for files
that intentionally contain Jinja syntax — to be decided in t777_22.)

Edits to the staged source:
- Frontmatter `name: aitask-pick` → `name: aitask-pickn-{{ profile.name }}`.
- Lines 44-46 — wrap the `skip_task_confirmation` parent-confirm
  block in `{% if profile.skip_task_confirmation %}…auto-confirm
  straight-line text…{% else %}…current AskUserQuestion block,
  unchanged…{% endif %}`.
- Lines 72-74 — same wrap for the child-confirm block.
- All other content unchanged. Cross-skill references stay as
  `.claude/skills/task-workflow/SKILL.md` literal — the dep-walker
  rewrites per-agent at render time.
- No `{% raw %}` (no literal Jinja in source — verified).
- No per-call-site `{% if agent %}` (tool-name mapping handled by
  per-agent prereq files).

### Step 4. Write the 4 stubs under `aitask-pickn`
Copy `task-workflow/stub-skill-pattern.md` §3b/§3c/§3d verbatim with
`<skill_short_name>=aitask-pickn`:
- `.claude/skills/aitask-pickn/SKILL.md` (§3b, `<agent_literal>=claude`)
- `.agents/skills/aitask-pickn/SKILL.md` (§3b, `<agent_literal>=codex`)
- `.gemini/commands/aitask-pickn.toml` (§3c)
- `.opencode/commands/aitask-pickn.md` (§3d)

**Caveat about staging name + entry-point ambiguity.** If the
authoring template lives at `.claude/skills/aitask-pickn/SKILL.md`
(directly, not as `SKILL.md.j2`), and a stub also lives at that same
path, they collide. Two options to resolve in Step 4:
- (a) Use `.md.j2` convention for entry-point templates (template at
  `.claude/skills/aitask-pickn/SKILL.md.j2`, stub at
  `.claude/skills/aitask-pickn/SKILL.md`). The `.j2` extension is then
  a convention only for the entry-point templates; referenced
  procedures keep their `.md` extension.
- (b) Move the staged template to a sibling dir like
  `.claude/skills/aitask-pickn-src/SKILL.md` and have the stub render
  it from there. More intrusive; (a) is simpler.
- **Recommend (a).** Surface this decision explicitly to t777_22 so
  the renderer canonicalizes one convention.

### Step 5. Golden-file tests + verify + live dispatch
- `tests/test_skill_render_aitask_pickn.sh` — for each
  (profile ∈ {default, fast, remote}) × (agent ∈ {claude, codex,
  gemini, opencode}):
  - Render fresh (`--force`).
  - Diff the entry-point rendered SKILL.md against committed golden
    `tests/golden/skills/aitask-pickn-<p>-<a>.md`.
  - Diff each transitively-rendered file in the per-profile snapshot
    against its committed golden (subdir per profile/agent).
  - Assert empty diff per file.
- Stub-marker regression checks on all 4 stub files.
- `./ait skill verify` — passes (dep-walker validates the
  transitively-rendered files for `aitask-pickn` too).
- **Live Claude dispatch test** (user-driven in a fresh session):
  - `/aitask-pickn 16` — stub resolves `fast`, renders, Reads,
    follows. Auto-confirm fires; control hands to
    `.claude/skills/task-workflow-fast-/SKILL.md`; workflow continues
    to Step 3+.
  - `/aitask-pickn --profile default 16` — interactive confirm; hands
    to `task-workflow-default-/SKILL.md`.
  - Original `/aitask-pick` remains untouched throughout.

### Step 6. Atomic rename `aitask-pickn` → `aitask-pick`
Only after Steps 1-5 pass. Single commit:
1. Delete original `aitask-pick` skill + 3 unified codex/gemini/opencode
   wrapper files (the files at `.claude/skills/aitask-pick/SKILL.md`,
   `.agents/skills/aitask-pick/SKILL.md`, `.gemini/commands/aitask-pick.toml`,
   `.opencode/commands/aitask-pick.md`).
2. `mv` every staged `aitask-pickn` file to its `aitask-pick`
   counterpart.
3. String-replace `aitask-pickn` → `aitask-pick` inside each moved
   file and in the test script + golden files.
4. Delete now-empty `.claude/skills/aitask-pickn/` and
   `.agents/skills/aitask-pickn/`. Clean up local rendered
   `aitask-pickn-*-/` dirs (gitignored).
5. Re-render all 12 combos under `aitask-pick`.
6. Re-run `bash tests/test_skill_render_aitask_pick.sh` and
   `./ait skill verify` — both must pass.

### Step 7. Append pilot findings to stub-skill-pattern.md
Add `## Pilot findings (t777_6)` section documenting:
- Uniform recursive rendering: every referenced markdown is rendered
  to the per-profile sibling, even when profile-neutral.
- Stage-under-`<skill>n` pattern when the skill is currently in use.
- Golden-file tests are a hard requirement (not optional).
- Entry-point templates use the `.md.j2` extension convention
  (resolves stub/template path collision); referenced procedures
  keep `.md`.
- Per-agent tool-name mapping stays in prereq files.

## Verification (end-to-end)

1. `./ait skill verify` exits 0 — finds `aitask-pick/SKILL.md.j2`,
   renders 12 entry-point variants, dep-walks into each per-profile
   snapshot, validates 4 stubs.
2. `bash tests/test_skill_render_aitask_pick.sh` passes (entry-point
   + all transitive goldens + 4 stub-marker checks).
3. Live dispatch tests in Step 5 work for default and fast profile
   invocations and continue cleanly through the rendered
   task-workflow chain.
4. `git status` shows the expected modifications + new files; no
   `aitask-pickn` artifacts remain; rendered `*-/` dirs are unstaged.

## Action items at end of this planning session

t777_6's prereqs do not yet exist or are not yet implemented. This
plan recommends:

1. **Create two new sibling tasks** t777_21 (closure + audit) and
   t777_22 (recursive renderer) via `Batch Task Creation Procedure`
   (mode=child, --parent 777).
2. **Re-scope t777_7** to add profile-key branches in the
   `task-workflow/` files enumerated by t777_21.
3. **Update t777_6's `depends:`** to `[t777_5, t777_21, t777_22, t777_7]`.
4. **Approve this plan and stop here** — release lock, revert t777_6
   to `Ready`. The user picks t777_21 next when ready, then t777_22,
   then t777_7, then resumes t777_6.

## Notes for sibling tasks (t777_8..t777_15)

Once t777_22 lands, each per-skill conversion gets
`depends: [t777_22, t777_7]` added (one-line metadata, handled inside
t777_22's implementation, not the pilot).

## Step 9 (Post-Implementation) reference

When t777_6 eventually fires the actual implementation, follow
`task-workflow/SKILL.md` Step 9: commit code + plan separately, run
`aitask_archive.sh 777_6`, push. No linked issue.
