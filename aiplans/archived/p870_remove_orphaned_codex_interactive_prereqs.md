---
Task: t870_remove_orphaned_codex_interactive_prereqs.md
Base branch: main
plan_verified: []
---

# Plan: Remove orphaned `codex_interactive_prereqs.md` (t870)

## Context

`.agents/skills/codex_interactive_prereqs.md` is an **orphaned** shared helper
doc. Nothing references it by name at runtime: no skill body, no instruction
layer, no `.md.j2` template, and `render_agents_skill()` only emits "read
`<agent>_tool_mapping.md`" lines — never a prereqs line. The actual Codex
plan-mode enforcement is the `/plan` typing in `aitask_codex_plan_invoke.py`,
so this file enforces nothing. It exists only because three release/install
copy loops copy it into `.agents/skills/`.

It was rewritten for accuracy (not removed) during t866 to avoid scope creep
into the install flow. t870 finishes the job: delete the file and prune it from
the copy loops + aidocs.

## Findings from exploration

- File is git-tracked. Confirmed **zero** references in `.aitask-scripts/lib/`,
  render functions, `tests/`, or `tests/golden/` — so no goldens regenerate.
- The task's suggested fix named only **two** copy loops. There are in fact
  **three** in lockstep (documented in `adding_a_new_codeagent.md` §21):
  1. `.aitask-scripts/aitask_setup.sh:1766`
  2. `install.sh:482`
  3. `.github/workflows/release.yml:57`  ← not in the task's fix list
  All three carry the identical tuple `for doc in codex_tool_mapping.md codex_interactive_prereqs.md; do`.
- A copy at `.aitask-crews/crew-brainstorm-427/.agents/skills/codex_interactive_prereqs.md`
  is **gitignored** (separate crew worktree) — leave untouched.
- `codex_tool_mapping.md` IS live-referenced by skill bodies — **keep it**.

## Changes

### 1. Delete the orphaned file
- `git rm .agents/skills/codex_interactive_prereqs.md`

### 2. Prune all three copy loops (in-place; line numbers unchanged)
In each of the three sites, change the loop tuple from
`for doc in codex_tool_mapping.md codex_interactive_prereqs.md; do`
to
`for doc in codex_tool_mapping.md; do`
(keep the single-item loop form and the preceding "Copy shared helper docs (codex)" comment):
- `.aitask-scripts/aitask_setup.sh:1766`
- `install.sh:482`
- `.github/workflows/release.yml:57`

### 3. Update `aidocs/adding_a_new_codeagent.md`
- **§16 (~line 862-889):** Remove the `codex_interactive_prereqs.md` bullet
  (lines 869-870). Soften the intro so it no longer claims codex reads a live
  prereqs doc ("tool-mapping docs (and plan-mode prereq docs where an agent
  needs them)"), point "Mirror the structure of the codex equivalents" at the
  single remaining `codex_tool_mapping.md`, and generalize the retiring note
  ("the two prereq docs" → "its helper doc(s)"). Keep the forward-looking
  `<agent>_planmode_prereqs.md` pattern for future agents.
- **§21 (~line 1129):** Update the `aitask_setup.sh` table row's loop variable
  to `for doc in codex_tool_mapping.md; do`. The `(same tuple)` rows for
  install.sh and release.yml stay correct by reference. Title "(3 sites in
  lockstep)" remains accurate — there are still three loops, now one-item.

## Out of scope
- `opencode_planmode_prereqs.md` (separate file, `.opencode/` tree, not codex).
- Any deeper restructuring of §16's generic prereq-doc guidance.

## Verification
- `grep -rn "codex_interactive_prereqs" . | grep -v .git | grep -v aitasks/ | grep -v .aitask-crews/`
  → expect **no matches** (file gone, loops pruned, docs updated).
- `shellcheck .aitask-scripts/aitask_setup.sh install.sh` → clean (no new findings).
- `bash -n install.sh && bash -n .aitask-scripts/aitask_setup.sh` → syntax OK.
- Confirm `codex_tool_mapping.md` still present and still referenced by skill
  bodies (unchanged).
- `git status` shows: 1 deletion, 2 shell edits, 1 workflow edit, 1 aidocs edit.

## Step 9 (Post-Implementation)
Standard archival: commit code/doc changes (`chore:` prefix, `(t870)` tag),
then `./.aitask-scripts/aitask_archive.sh 870`, then `./ait git push`.

## Final Implementation Notes
- **Actual work done:** Deleted `.agents/skills/codex_interactive_prereqs.md`
  (orphaned shared helper doc). Pruned `codex_interactive_prereqs.md` from all
  three lockstep copy loops — `.aitask-scripts/aitask_setup.sh:1766`,
  `install.sh:482`, and `.github/workflows/release.yml:57` — leaving
  `for doc in codex_tool_mapping.md; do`. Updated `aidocs/adding_a_new_codeagent.md`
  §16 (removed the prereqs bullet; softened intro; repointed "mirror the
  structure" at `codex_tool_mapping.md`; generalized the retiring note to
  "its helper doc(s)") and §21 (updated the `aitask_setup.sh` table row's
  loop variable).
- **Deviations from plan:** None. Implemented exactly as approved.
- **Issues encountered:** The externalize helper returned `MULTIPLE_CANDIDATES`
  (5 recent internal plan files); re-ran with the explicit `--internal` path
  from the plan-mode system reminder. No other issues.
- **Key decisions:** Kept the single-item `for doc in …; do` loop form rather
  than collapsing each to a direct `cp`, to preserve the fan-out pattern and
  keep future helper-doc additions trivial. The crew-worktree copy at
  `.aitask-crews/crew-brainstorm-427/…` is gitignored and was left untouched.
- **Upstream defects identified:** None. (The task's own "Suggested fix"
  listed only two of the three lockstep copy loops — a task-authoring gap, not
  a code defect; all three were handled, consistent with aidocs §21.)
