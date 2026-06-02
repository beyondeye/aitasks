---
Task: t903_regenerate_stale_t884_5_planning_renders_and_goldens.md
Base branch: main
plan_verified: []
---

# Plan: Regenerate stale t884_5 planning renders and goldens (t903)

## Context

Commit t884_5 ("Force-reverify task plan when a risk mitigation lands") edited
the source closure `.claude/skills/task-workflow/planning.md` (adding the
**Step 6.0a Force-reverify** content) and other source procedures, but did not
regenerate the downstream rendered variants and procedure goldens in the same
commit — violating the "regenerate goldens / renders in the same commit" rule
in `aidocs/framework/skill_authoring_conventions.md`. This left two pre-existing
drifts, surfaced (but deliberately not fixed) during t901:

1. **Stale committed `remote` renders** — the 3 prerendered, git-tracked
   `task-workflow-remote-` `planning.md` variants are missing the Step 6.0a
   content present in their source since t884_5:
   - `.claude/skills/task-workflow-remote-/planning.md`
   - `.opencode/skills/task-workflow-remote-/planning.md`
   - `.agents/skills/task-workflow-remote-codex-/planning.md`
   (These `remote`-profile dirs are un-ignored in `.gitignore` lines 54–56
   because they are prerendered for headless contexts. `default`/`fast`
   rendered dirs are gitignored and render on demand, so they are not in
   scope. No `.gemini/.../planning.md` exists.)

2. **Stale tracked `fast` goldens** — `tests/test_skill_render_task_workflow.sh`
   Test 1 fails 2 assertions at HEAD (confirmed: 91 tests, 89 pass, 2 fail):
   - `tests/golden/procs/task-workflow/SKILL-fast.md`
   - `tests/golden/procs/task-workflow/planning-fast.md`

This is a pure regeneration chore — no source `.md`/`.md.j2` edits.

## Implementation

### 1. Refresh the committed `remote` rendered variants

```bash
./.aitask-scripts/aitask_skill_rerender.sh remote
```

This walks the claude/codex/opencode skill roots and re-renders every
`*-remote-` dir in place (atomic per-file overwrite, skip-if-fresh). Expected
git diff: only the 3 stale `task-workflow-remote-*/planning.md` files change
(picking up Step 6.0a). Review `git status` afterward to confirm no unexpected
files moved.

### 2. Regenerate the 2 stale `fast` procedure goldens

Use the exact render invocation the test uses (`skill_template.py <closure>
<profile.yaml> claude`), writing to the golden paths:

```bash
PYTHON="$(source .aitask-scripts/lib/python_resolve.sh && require_ait_python)"
RENDER=".aitask-scripts/lib/skill_template.py"
WF=".claude/skills/task-workflow"
P="aitasks/metadata/profiles/fast.yaml"
G="tests/golden/procs/task-workflow"

"$PYTHON" "$RENDER" "$WF/SKILL.md"    "$P" claude > "$G/SKILL-fast.md"
"$PYTHON" "$RENDER" "$WF/planning.md" "$P" claude > "$G/planning-fast.md"
```

### 3. Review the diffs (audit signal, do not rubber-stamp)

`git diff` the regenerated goldens and the 3 remote renders. The diff must be
**only** the t884_5 content (Step 6.0a Force-reverify in planning; the
corresponding Step 7 risk-mitigation / Step 6.0a-related additions in SKILL).
An unrelated diff means a regression and must be investigated before commit.

## Verification

```bash
bash tests/test_skill_render_task_workflow.sh      # expect: Failed: 0
./.aitask-scripts/aitask_skill_verify.sh           # expect: pass (stub markers,
                                                   # dep-closure render cleanliness,
                                                   # headless prerender freshness)
```

Both must be green before commit.

## Files changed

- `.claude/skills/task-workflow-remote-/planning.md` (regenerated)
- `.opencode/skills/task-workflow-remote-/planning.md` (regenerated)
- `.agents/skills/task-workflow-remote-codex-/planning.md` (regenerated)
- `tests/golden/procs/task-workflow/SKILL-fast.md` (regenerated)
- `tests/golden/procs/task-workflow/planning-fast.md` (regenerated)

Commit type: `chore: <description> (t903)`. Per CLAUDE.md these are framework
skill artifacts (not `aitasks/`/`aiplans/`), so they commit with regular `git`.

## Step 9 (Post-Implementation)

Standard archival via `./.aitask-scripts/aitask_archive.sh 903` after commit
and review approval. Working on the current branch (profile `fast`), so no
worktree/branch merge step.

## Final Implementation Notes

- **Actual work done:** Regenerated the 5 stale artifacts exactly as planned.
  The 3 committed `remote` `planning.md` renders now carry the **Step 6.0a
  Force-reverify** block (+`--force-verify` append note) from t884_5; the 2
  `fast` goldens now carry the `risk_evaluation`-gated content (SKILL.md Step 7
  two-field write + "before" creation, Step 8c→8d pointer, new Step 8d;
  planning.md risk-evaluation + risk-mitigation-design steps). Verified the
  diffs contain only t884_5 content — no unrelated drift.
- **Deviations from plan:** The plan's step 1 (`aitask_skill_rerender.sh
  remote`) did **not** refresh the stale renders — see upstream defect below.
  Had to instead force-render the headless entry-point skills whose closure
  walks write `task-workflow-remote-/planning.md`:
  `aitask_skill_render.sh aitask-pickrem|aitask-pickweb --profile remote
  --agent claude|codex|opencode --force`. Net effect on tracked files is
  identical to what the plan intended (the same 3 `planning.md` files), so the
  "Files changed" list is unchanged.
- **Issues encountered:** `aitask_skill_rerender.sh remote` reported
  `RERENDERED:30` but produced an empty diff. Two causes: (1) it deliberately
  skips `task-workflow` (no `SKILL.md.j2` authoring template — it is rendered
  only via other skills' closure walks); (2) its mtime-based skip-if-fresh
  considered the git-stale committed renders fresh. Resolved by `--force` on
  the two headless entry points.
- **Key decisions:** Only the `fast` goldens were stale because `fast.yaml` is
  the only committed profile setting `risk_evaluation: true`; default/remote
  goldens correctly remained unchanged (proven by render test Test 5 +
  zero-diff on their goldens). Staged only the 5 task files — the working tree
  also held unrelated `brainstorm/` edits from a concurrent session, left
  untouched.
- **Upstream defects identified:**
  - `.aitask-scripts/aitask_skill_rerender.sh:67-68 — invokes aitask_skill_render.sh without --force; the renderer's mtime-based skip-if-fresh treats git-committed prerenders that drifted via a source-only commit as fresh (mtimes equalize on checkout/clone), so committed `*-remote-` prerenders silently stay stale and rerender reports RERENDERED:N with an empty diff. Recovering t903's stale renders required a manual --force on the headless entry points. Consider passing --force in the rerender driver, or making skip-if-fresh content-hash based rather than mtime based.`
- **Verification:** `bash tests/test_skill_render_task_workflow.sh` → 91/91,
  Failed: 0. `./.aitask-scripts/aitask_skill_verify.sh` → OK (10 templates × 3
  agents).
