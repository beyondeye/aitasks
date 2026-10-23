---
Task: t2124_plan_header_records_checked_out_branch_not_primary.md
Base branch: main
Output branch: main
plan_verified: []
---

# t2124 — Plan header records the checked-out branch, not the primary

## Context

Upstream handoff from a downstream project (thinking_backend#t65) that vendors
this framework. `aitask_plan_externalize.sh` has three header defects:

1. **Current-branch mode** (`--no-worktree` / `create_worktree: false`) writes the
   detected primary (e.g. `main`) into both `Base branch:` and `Output branch:`,
   even when the work is on `dev`. A resumed session then drift-checks
   `origin/main`, may cut a worktree from `main` with "plan header" provenance,
   and Step 9 merges into `main`.
2. **`Branch:` in worktree mode** is the repo root's checked-out branch (the fork
   is deferred to Step 7 since t1536), not the documented `aitask/<task_name>`.
3. `git symbolic-ref --short HEAD` answers `heads/dev` when a tag `dev` sits beside
   branch `dev`; read the full ref and strip `refs/heads/` instead.

The downstream fix (commit a2e872d) is in the task body as a diff; it applies
cleanly here (`git apply --check` passed). Without upstreaming, the next
`ait upgrade` downstream reverts it. Sibling `detect_primary_branch` `--short`
defect is t2123 (in flight, touches `lib/git_utils.sh` / `desync_state.py` —
no file overlap with this task).

Verified: nothing in `.aitask-scripts/` or the task-workflow skills reads the
plan header's `Branch:` field (only build_header writes it), so the new
`Branch: aitask/<task_name>` line in worktree-mode plans has no consumer to break.

## Steps

1. **Apply the helper + canonical doc patch** from the task body
   (scratch copy: `/tmp/claude-1000/-home-ddt-Work-aitasks/b5d2ca48-894f-4d61-b76b-36647168e972/scratchpad/t2124.diff`)
   with `git apply`. It changes:
   - `.aitask-scripts/aitask_plan_externalize.sh`: header comments / `--help`
     text; compute `PRIMARY_BRANCH` and `CURRENT_BRANCH` (full ref, strip
     `refs/heads/`, empty on detached HEAD) before the resolution block; in
     non-worktree mode validate `CURRENT_BRANCH` with the existing
     `validate_branch_name` and set base/output to
     `${CURRENT_BRANCH:-$PRIMARY_BRANCH}`; derive `BRANCH_FIELD`
     (`aitask/<task_name>` with `--worktree`, else the checked-out branch when ≠
     primary); `build_header()` emits `BRANCH_FIELD`; `splice_header_branches()`
     gains a 6th `br` arg so `Branch:` is replaced/inserted/dropped alongside a
     worktree claim (left alone with no claim). Replace the `t65` cross-refs in
     new comments with `t2124` (t65 is a downstream id, not this repo's).
   - `.claude/skills/task-workflow/plan-externalization.md` and `planning.md`:
     "detected primary" → "checked-out branch (detected primary only on a
     detached HEAD)"; add the `Branch:` rule.
2. **Port the downstream suite C1–C10 into `tests/test_plan_externalize.sh`** as a
   new `Test 17` block before `# --- Results ---`, using the file's existing
   `assert_eq` / `assert_contains` / `PASS`/`FAIL` helpers (no subshell test
   bodies, so no counter opt-in needed). A dedicated `new_git_sandbox` helper
   (git repo on `main`, `dev` branch, `origin/HEAD -> origin/main`, task t999,
   internal plan) — do not reuse `new_sandbox`, which is deliberately non-git.
   Git runs under an empty scratch `HOME` + `GIT_CONFIG_NOSYSTEM=1` scoped to the
   block. Cases: C1 current-branch on dev; C2 worktree on dev → `Branch:
   aitask/...`; C3 detached HEAD → primary fallback, no Branch; C4 on main; C5
   worktree on main; C6 no claim on dev; C7i/C7ii splice into existing
   frontmatter (value, uniqueness, two fences, body unchanged, stale Worktree
   removed); C8 unsafe checked-out branch `dev$(id)` fails closed with no plan +
   control; C9 no Python invoked by these cases (stub `AIT_PYTHON`/PATH) +
   control; C10 tag beside branch → `dev`, not `heads/dev`.
   **C11 (profile path, beyond the downstream suite):** git sandbox checked out on
   `dev`, profile file `create_worktree: false` + conflicting
   `base_branch: release` / `output_branch: release`, invoked with `--profile`
   only (no worktree flag) and run with the real interpreter (not the C9 stub):
   exit 0, `Base branch: dev`, `Output branch: dev`, `Branch: dev`, no
   `Worktree:` line. A second C11 run adds `--no-worktree` alongside the
   profile — same expectations. Pins that profile-driven current-branch mode
   records the checked-out branch, not the primary, and discards profile values.
   Make the helper path overridable — `EXTERNALIZE="${EXTERNALIZE:-$PROJECT_DIR/.aitask-scripts/aitask_plan_externalize.sh}"`
   — so the negative control can point the suite at a pre-fix tree (same
   convention as the downstream suite).
3. **Propagate the doc edits to every tracked agent tree** by re-rendering:
   `./.aitask-scripts/aitask_skill_rerender.sh remote` (refreshes
   `.claude/skills/task-workflow-remote-/`, `.agents/skills/task-workflow-remote-codex-/`,
   `.opencode/skills/task-workflow-remote-/`), and re-render `fast`/`default`
   locally (gitignored). Check each rendered `planning.md` / `plan-externalization.md`
   carries the new text; commit only those paths (other sessions' dirty files
   stay out).
4. **Regenerate procedure goldens** `tests/golden/procs/task-workflow/planning-{default,fast,remote}.md`
   (and any `plan-externalization-*` golden) per the loop in
   `tests/test_skill_render_task_workflow.sh`; review the diff is exactly the
   doc edit.
5. Step 9 (Post-Implementation): review, commit (`bug: ... (t2124)`), archive.

## Verification

- `bash tests/test_plan_externalize.sh` — all green, including Test 17.
- **Negative control (pre-fix tree with its library layout intact):** the
  helper sources `$SCRIPT_DIR/lib/*.sh`, so a lone copy dies at startup. Extract
  the whole pre-fix scripts tree instead:
  `git archive HEAD .aitask-scripts | tar -x -C <scratchpad>/prefix/`, then run
  `EXTERNALIZE=<scratchpad>/prefix/.aitask-scripts/aitask_plan_externalize.sh bash tests/test_plan_externalize.sh`.
  Accept the result only if (a) the ordinary control cases succeed against the
  old helper — C3, C4, C6's exit 0 + plan written, C8's control run, and the
  pre-existing Tests 1–16 — proving startup and plan generation work, and (b)
  the failures are exactly the branch-field assertions: C1, C2, C5, C7i, C7ii,
  C8, C10 and C11 (old code records `main`). Record the per-case outcome list.
- `bash tests/test_skill_render_task_workflow.sh` green;
  `./.aitask-scripts/aitask_skill_verify.sh` green.
- `shellcheck .aitask-scripts/aitask_plan_externalize.sh`.

## Risk

### Code-health risk: low
None identified. (Change is confined to one helper's header-field resolution;
on-primary current-branch / no-claim output stays byte-identical, and the one
intended on-primary change — `Branch: aitask/<task_name>` in worktree mode — has
no reader and is pinned by C5.)

### Goal-achievement risk: low
None identified. (The patch is the downstream's reviewed fix, applies cleanly, and
the ported suite plus its negative control prove the behaviour.)
