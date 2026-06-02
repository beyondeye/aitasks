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
