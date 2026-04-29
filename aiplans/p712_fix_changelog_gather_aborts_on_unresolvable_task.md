---
Task: aitasks/t712_fix_changelog_gather_aborts_on_unresolvable_task.md
Worktree: (current branch — no worktree)
Branch: main
Base branch: main
---

# Plan: Fix changelog --gather aborting on unresolvable task

## Context

`./.aitask-scripts/aitask_changelog.sh --gather` aborts mid-loop the moment any
task in the commit range has no archive file resolvable in the working tree.
On line 110:

```bash
task_file=$(resolve_task_file "$task_id" 2>/dev/null || echo "")
```

`resolve_task_file` calls `die "..."` (which is `exit 1`) when nothing
resolves. Because that `exit` runs *inside* the `$(...)` subshell, it
terminates the subshell **before** the `|| echo ""` fallback can run. The
subshell ends with status 1, the assignment inherits status 1, and the parent
script's `set -e` then aborts the whole gather loop. Same pattern on line 121
for `resolve_plan_file`.

**About the original repro**: t711 *was* archived — the archive commit is on
`origin/aitask-data` (`92660edb ait: Archive completed t711 task and plan
files`). What was missing at repro time was the **local working-tree state of
`.aitask-data`** (the symlink `aitasks/archived/...` → `.aitask-data/aitasks/archived/...`
pointed into a worktree that was behind `origin/aitask-data`). After the local
worktree synced, the archive file appeared on disk and the abort no longer
reproduces here. The bug class — `die` inside `$(... || ...)` aborting under
`set -e` — is real and I confirmed it with a synthetic repro:

```text
=== Buggy form ===
(immediate exit, no "After:" line printed, outer exit 1)

=== Fixed form ===
After: result='' exit=0
(outer exit 0)
```

## Approach

Two changes ship in this task; one follow-up task is filed.

### In this task

1. **Hotfix (Option 1 from the task description) — stop the abort.**
   Two-line change in `.aitask-scripts/aitask_changelog.sh`. Move `||` from
   inside the command substitution to the assignment level so the subshell's
   non-zero exit is caught by the outer assignment instead of aborting under
   `set -e`. No behavior change for tasks that resolve normally.

2. **Surface desync warning at gather start.**
   When the local `.aitask-data` worktree is behind `origin/aitask-data`,
   `--gather` will silently skip those tasks (with `TITLE: t<id>` fallback and
   empty notes) — even after the hotfix. Add a one-shot check at the start of
   `gather()` that warns the user when this is the case. Without the warning
   the user sees a partial changelog with no signal that anything is missing.

### Filed as a follow-up task (created during implementation)

3. **Follow-up — `ait syncer` TUI.**
   New TUI with tmux integration (matching board / monitor / minimonitor /
   codebrowser conventions): polls remote status, shows desync (tasks landed
   on remote not yet pulled + affected files), supports basic git pull/push,
   and can spawn a code agent to interactively resolve git errors when ops
   fail. Surface desync state in the TUI switcher / monitor / minimonitor as
   info widgets. Add an `ait settings` option to autostart it when `ait ide`
   starts. Independent of t712 (no depends).

**Not pursued — Option 3 (data-branch fallback in resolver helpers).** The
task description mentions extending `resolve_task_file` / `resolve_plan_file`
with a `git show origin/aitask-data:...` fallback tier as the "deepest fix".
Per the user's direction, this is rejected: it is a workaround that does not
solve the desync problem (it just reads behind the user's back, masking the
fact that local state is stale) and adds complexity to core resolver helpers.
The right framework-level answer is making desync **visible and resolvable**
via the syncer TUI follow-up, not silently reading from remote refs.

## Files to modify

- `.aitask-scripts/aitask_changelog.sh` — `gather()` only.
  - Lines 110, 121: hotfix.
  - New helper `check_data_desync()` invoked once at the top of `gather()`
    (after `tag` is resolved, before commit-range processing).

No other source files change in this task. The two follow-up tasks ship as
separate task files in `aitasks/`.

## Implementation steps

### 1. Hotfix (Option 1)

Edit `.aitask-scripts/aitask_changelog.sh`:

- Line 110: `task_file=$(resolve_task_file "$task_id" 2>/dev/null || echo "")`
  → `task_file=$(resolve_task_file "$task_id" 2>/dev/null) || task_file=""`

- Line 121: `plan_file=$(resolve_plan_file "$task_id" 2>/dev/null || echo "")`
  → `plan_file=$(resolve_plan_file "$task_id" 2>/dev/null) || plan_file=""`

The existing `if [[ -n "$task_file" ]]` (line 111) and
`if [[ -n "$plan_file" && -f "$plan_file" ]]` (line 122) branches already
handle the empty-string case correctly — `task_file=""` triggers the existing
fallback emission `ISSUE_TYPE: feature` / `TITLE: t${task_id}`, and the empty
`plan_file` triggers the existing `PLAN_FILE:` (empty) / `NOTES:` (empty)
fallback. No downstream code changes.

### 2. Desync warning

Add a function near the top of `aitask_changelog.sh` (alongside the existing
helpers like `get_latest_tag`):

```bash
# Warn if the local aitask-data worktree is behind origin/aitask-data.
# Tasks archived only on origin will be skipped by --gather (with fallback
# TITLE / empty notes) until the user pulls.
check_data_desync() {
    [[ -d .aitask-data ]] || return 0  # legacy mode — no data branch
    git -C .aitask-data rev-parse --is-inside-work-tree >/dev/null 2>&1 || return 0

    # Best-effort fetch — quiet, ignore failures (offline, auth, etc).
    git -C .aitask-data fetch --quiet origin aitask-data 2>/dev/null || true

    local behind=0
    behind=$(git -C .aitask-data rev-list --count HEAD..origin/aitask-data 2>/dev/null || echo 0)

    if [[ "${behind:-0}" -gt 0 ]]; then
        warn "Local aitask-data branch is $behind commit(s) behind origin/aitask-data."
        warn "Tasks archived only on origin (not pulled locally) will appear with fallback TITLE: t<id> and empty NOTES."
        warn "Run: (cd .aitask-data && git pull) to sync, then re-run --gather for full task data."
    fi
}
```

Invoke at the top of `gather()`, immediately after the `BASE_TAG:` echo:

```bash
gather() {
    local tag="${FROM_TAG:-$(get_latest_tag)}"
    if [[ -z "$tag" ]]; then
        die "No release tags found. Cannot determine base for changelog."
    fi
    echo "BASE_TAG: $tag"
    echo ""

    check_data_desync   # <-- NEW

    local commits
    ...
}
```

Notes:
- `warn()` writes to stderr, so it does NOT interleave with the structured
  stdout output the `aitask-changelog` skill parses. Safe.
- The fetch is best-effort and uses `--quiet`. If the user is offline the
  rev-list comparison still runs against whatever the last successful fetch
  populated — better than nothing.
- `[[ -d .aitask-data ]]` short-circuit makes this a no-op in legacy mode (no
  separate data branch).

### 3. Create follow-up task — `ait syncer` TUI

Same pattern, separate `aitask_create.sh --batch` call:

```bash
./.aitask-scripts/aitask_create.sh --batch \
  --name "ait_syncer_tui_for_remote_desync_tracking" \
  --priority medium --effort high \
  --issue-type feature \
  --label tui --label scripts \
  --desc-file - <<'DESC'
## Goal

Add a new `ait syncer` TUI that tracks remote desync state for the project's
git refs (`main`, `aitask-data`, `aitask-locks`, `aitask-ids`) and provides
an interactive surface for keeping the local worktree(s) in sync with origin.

## Motivation

Surfaced during t712: `aitask_changelog.sh --gather` was silently skipping
tasks whose archive existed on `origin/aitask-data` but had not been pulled
into the local `.aitask-data/` worktree. t712 ships a one-shot warning at
gather start, but the broader pattern (any TUI / script that reads task data
can be looking at stale state) deserves a dedicated tracker.

## Requirements

1. **TUI conventions**: follow the existing aitasks TUI structure
   (board, monitor, minimonitor, codebrowser, brainstorm) — Textual-based
   Python under `.aitask-scripts/board/` (or a dedicated module), tmux
   integration, single-session-per-project model (see CLAUDE.md "Single
   tmux session per project").
2. **Polling**: periodically `git fetch` (configurable interval, default
   ~30s) for the project's tracked branches and recompute desync.
3. **Display**: list of refs with ahead/behind counts, list of tasks
   landed on remote not yet pulled (with affected file paths), commit
   messages, and basic actions (pull / push).
4. **Settings option**: `aitasks/metadata/project_config.yaml` key
   `tmux.syncer.autostart: true|false` — when `ait ide` starts, the syncer
   TUI launches alongside the other TUIs if enabled.
5. **TUI switcher integration**: bind a key in
   `.aitask-scripts/lib/tui_switcher.py` (one of the unused letters; not
   `n` which is reserved for create-task) to switch to the syncer.
   Surface desync count as info widget content in the switcher modal.
6. **Monitor / minimonitor integration**: surface desync count as a small
   line in the existing monitor and minimonitor TUIs (similar to how lock
   warnings or lazygit prompts are surfaced today). One-line summary like
   "aitask-data: 3 commits behind".
7. **Error handling**: when `git pull` or `git push` fails (merge conflict,
   non-fast-forward, auth issue), offer to spawn a code agent in a tmux
   pane (like the existing brainstorm / explore agent dispatch) with
   instructions to resolve the git error interactively with the user.
8. **Tests**: bash test scripts in `tests/` covering the desync calculation
   helpers (the TUI rendering itself follows the existing convention of
   not having Textual snapshot tests).

## Files (anticipated)

- `.aitask-scripts/aitask_syncer.sh` — entrypoint dispatched via `ait`
- `.aitask-scripts/board/aitask_syncer.py` (or sibling module) — Textual
  TUI implementation
- `.aitask-scripts/lib/desync_state.py` (or `.sh`) — pure data helper used
  by syncer + monitor + minimonitor + switcher
- `.aitask-scripts/lib/tui_switcher.py` — add binding + info widget
- `.aitask-scripts/aitask_monitor.py` / minimonitor — add desync line
- `.aitask-scripts/aitask_settings.py` (or its config layer) — add
  autostart option
- Permission/whitelist touchpoints for `aitask_syncer.sh` per CLAUDE.md
  "Adding a New Helper Script" — 5 touchpoints (Claude / Gemini / OpenCode
  runtime configs + 2 seed mirrors).

## Acceptance

- `ait syncer` opens the TUI and shows live desync state for the project's
  branches.
- Toggling `tmux.syncer.autostart: true` causes `ait ide` to spawn the
  syncer alongside the other TUIs.
- Monitor and minimonitor display a desync summary line.
- TUI switcher shows desync count and provides a binding to jump to syncer.
- `git pull` / `git push` actions work; on failure, the code-agent escape
  hatch launches in a sibling tmux pane.
- All 5 helper-script whitelist touchpoints updated for `aitask_syncer.sh`.

## Notes

- This task is **likely complex** and may be split into child tasks during
  its own planning (data helper, TUI shell, monitor integration, autostart,
  agent escape hatch).
- See t712 for the original surfacing context.
DESC
```

## Verification

### V1 — non-regression (archive present)

```bash
./.aitask-scripts/aitask_changelog.sh --gather
echo "exit: $?"
```

Expected: completes with exit 0; emits full structured output for t706–t711
matching the pre-fix output (already verified before the fix on this PC since
the t711 archive is locally present). Stderr may include the new desync
warning if the local data worktree is currently behind — that's informational.

### V2 — simulated repro of the original abort

Reproduce the original failure mode by temporarily moving the t711 archive
files aside, then run `--gather` against the patched script:

```bash
mv aitasks/archived/t711_macos_installation_subpage_terminal_compat.md /tmp/t711_archive.md.bak
mv aiplans/archived/p711_macos_installation_subpage_terminal_compat.md /tmp/p711_archive.md.bak

./.aitask-scripts/aitask_changelog.sh --gather > /tmp/gather_after.out 2>/tmp/gather_after.err
echo "exit: $?"
grep -A 6 '=== TASK t711 ===' /tmp/gather_after.out
cat /tmp/gather_after.err

# Restore
mv /tmp/t711_archive.md.bak aitasks/archived/t711_macos_installation_subpage_terminal_compat.md
mv /tmp/p711_archive.md.bak aiplans/archived/p711_macos_installation_subpage_terminal_compat.md
```

Expected for the t711 block in stdout:

```
=== TASK t711 ===
ISSUE_TYPE: feature
TITLE: t711
PLAN_FILE:
NOTES:
COMMITS:
c85b93cc documentation: ... (t711)
=== END ===
```

Exit code: `0`. Subsequent task blocks (if any) continue to emit normally.

### V3 — desync warning surfaces

If `git -C .aitask-data rev-list --count HEAD..origin/aitask-data` is non-zero
at the time of testing, V1's stderr should contain the three-line warning
block. If it's zero, manually simulate by resetting the local `.aitask-data`
HEAD one commit back:

```bash
# In a scratch worktree, NOT in the live data branch
git -C .aitask-data log --oneline -3   # note current HEAD
git -C .aitask-data reset --hard HEAD~1  # CAREFUL — only if you're sure no in-flight work
./.aitask-scripts/aitask_changelog.sh --gather 2>&1 1>/dev/null | head -5
git -C .aitask-data reset --hard origin/aitask-data  # restore
```

(Skip V3's manual simulation if `.aitask-data` is currently busy with
in-flight work — the warning block has been verified textually in the helper
function.)

### V4 — pre-fix behavior verification (optional)

To confirm the fix is causal: with t711 archives stashed (V2's mv step), undo
the patch via `git stash` (or `git restore`) and re-run `--gather`. Should
abort after `=== TASK t711 ===` with exit 1, no further task blocks. Then
`git stash pop` (or re-apply) and confirm V2 again passes.

### V5 — static analysis

```bash
shellcheck .aitask-scripts/aitask_changelog.sh
```

Expected: same baseline as before — only the pre-existing `SC1091` info on
the `source "$SCRIPT_DIR/lib/task_utils.sh"` line. No new warnings.

### V6 — follow-up task created

```bash
ls aitasks/t*.md | grep ait_syncer_tui
./.aitask-scripts/aitask_ls.sh -v 30 | grep ait_syncer_tui
```

Expected: the new `ait_syncer_tui_for_remote_desync_tracking` task file
exists with correct frontmatter (no `depends`), and appears in the active
task list.

## Step 9 reference

After implementation and user approval (Step 8), proceed to **Step 9
(Post-Implementation)** of `task-workflow/SKILL.md`:
- No worktree was created (profile `fast`, `create_worktree: false`), so the
  branch/worktree cleanup section is skipped.
- `verify_build` is null in `aitasks/metadata/project_config.yaml` → build
  verification is skipped.
- Run `./.aitask-scripts/aitask_archive.sh 712` to handle metadata, archival,
  lock release, and commit; then `./ait git push`.

The follow-up task file is committed to `aitasks/` via `./ait git` during
implementation Step 3 (its own dedicated commit, separate from the code
commit and the t712 plan commit, handled by `aitask_create.sh --batch`) —
it remains as a Ready task in the active backlog for future picking, not
archived along with t712.
