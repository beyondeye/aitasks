---
Task: t798_allow_archived_tasks_in_task_dependencies_in_create.md
Base branch: main
plan_verified: []
---

# Plan: Allow archived task references during `ait create` (t798)

## Context

In `ait create`, the description-editing loop already supports appending **file references** inline (a sub-menu run from `get_task_definition()` that pops fzf's file walker and pastes the chosen path into the description body, optionally tracking it in `file_references:` frontmatter).

The user wants the same affordance for **archived tasks** — not as a real dependency (the active `select_dependencies()` flow lists only non-archived tasks via `aitask_ls.sh`) but as a pointer to a previously completed task whose history is relevant context for the new task. The motivation is the same one served by automatic sibling context in child-task workflows, generalised to any archived task.

Per user clarifications:
- **Storage:** inline in the description body only — no new YAML frontmatter field, and the existing `file_references:` field stays untouched.
- **Search scope:** archived task files on disk only (`aitasks/archived/**/t*.md`). No archived plans. No zipped/bundled archives (e.g. `aitasks/archived/old.tar.zst`).
- **Inline format:** just the path (e.g. `aitasks/archived/t42_foo.md`) — same shape file references currently use.

## Approach

Extend the inner sub-menu in `get_task_definition()` (`.aitask-scripts/aitask_create.sh` lines 1127–1179) with a new option **"Add archived task reference"**. When selected, list archived tasks via fzf and append the chosen path to the description body. Track the picked path in the per-round `current_round_refs` array so the existing "Remove" affordance can drop it; do **not** add it to `all_file_refs` so the `file_references:` frontmatter remains free of archived-task entries (matching the "inline only" decision).

Reuse the existing archived-task scanner — `./.aitask-scripts/aitask_query_files.sh recent-archived <limit>` — which already walks both `aitasks/archived/t*_*.md` (parents) and `aitasks/archived/t*/t*_*_*.md` (children) and emits `RECENT_ARCHIVED:<path>|<completed_at>|<issue_type>|<basename>` lines. Sort order (most-recent first) is also what we want here.

## Files to modify

- `.aitask-scripts/aitask_create.sh` — only file changed.

## Implementation steps

### 1. New helper: `select_archived_task_ref()`

Add a helper near `select_dependencies()` (around line 983) — or just above `get_task_definition()` (around line 1093), wherever it reads better. The helper:

- Calls `"$SCRIPT_DIR/aitask_query_files.sh" recent-archived 999` to get up to ~999 archived tasks (effectively all of them; the script's default is 15).
- If the output is `NO_RECENT_ARCHIVED`, prints nothing (the caller will treat empty result as "user cancelled / nothing to add" — same as the existing file-ref path).
- Parses each `RECENT_ARCHIVED:` line into a single fzf row of the form:
  ```
  <path>    [<completed_at>] <basename> (<issue_type>)
  ```
  Path-first so column 1 (whitespace-split) can be re-extracted after selection.
- Pipes to fzf:
  ```bash
  fzf --prompt="Archived task: " --height=20 --no-info \
      --header="Select archived task to reference (Esc to cancel)" \
      --preview 'head -80 {1}' --preview-window=right:60% \
      < /dev/tty 2>/dev/null
  ```
- Extracts the first whitespace-delimited token (the path) from the selection and echoes it. Echoes empty on cancel.

Sketch:

```bash
select_archived_task_ref() {
    local lines selected path
    lines=$("$SCRIPT_DIR/aitask_query_files.sh" recent-archived 999 2>/dev/null || true)

    if [[ -z "$lines" ]] || [[ "$lines" == "NO_RECENT_ARCHIVED" ]]; then
        warn "No archived tasks found." >&2
        echo ""
        return
    fi

    local rows
    rows=$(echo "$lines" | awk -F'|' '
        /^RECENT_ARCHIVED:/ {
            sub(/^RECENT_ARCHIVED:/, "", $1)
            printf "%s    [%s] %s (%s)\n", $1, $2, $4, $3
        }')

    selected=$(echo "$rows" | fzf --prompt="Archived task: " --height=20 --no-info \
        --header="Select archived task to reference (Esc to cancel)" \
        --preview 'head -80 {1}' --preview-window=right:60% \
        < /dev/tty 2>/dev/null || echo "")

    [[ -z "$selected" ]] && { echo ""; return; }

    # First whitespace-separated field is the path.
    path=$(echo "$selected" | awk '{print $1}')
    echo "$path"
}
```

Notes:
- `head -80 {1}` matches the existing file-walker preview style (line 1166 uses `head -50`).
- `999` is a soft cap — pass a high number rather than parsing all entries by hand. If we ever exceed it the worst-case is some old tasks not visible, not a crash.
- `</dev/tty 2>/dev/null` matches the existing file-walker invocation so fzf works inside the subshell pipeline.

### 2. Extend the description-loop sub-menu

In `get_task_definition()` (lines 1127–1179), update the menu and add a branch.

Current menu (line 1129–1133):
```bash
local menu_opts="Add file reference\nDone with files"
if [[ ${#current_round_refs[@]} -gt 0 ]]; then
    menu_opts="Add file reference\nRemove file reference\nDone with files"
fi
add_file=$(echo -e "$menu_opts" | fzf --prompt="Add file? " --height=8 --no-info)
```

New menu:
```bash
local menu_opts="Add file reference\nAdd archived task reference\nDone with files"
if [[ ${#current_round_refs[@]} -gt 0 ]]; then
    menu_opts="Add file reference\nAdd archived task reference\nRemove reference\nDone with files"
fi
add_file=$(echo -e "$menu_opts" | fzf --prompt="Add reference? " --height=8 --no-info)
```

Changes:
- New option `Add archived task reference` (always available).
- Renamed `Remove file reference` → `Remove reference` because it now handles both kinds.
- Renamed prompt `Add file? ` → `Add reference? ` to match the broadened menu.

Update the dispatch:
- Keep the existing `"Done with files"` and `"Remove reference"` branches (the latter just needs its label string updated to `"Remove reference"`).
- Add a new branch above the existing file-walker block:
  ```bash
  elif [[ "$add_file" == "Add archived task reference" ]]; then
      local selected_archived
      selected_archived=$(select_archived_task_ref)
      if [[ -n "$selected_archived" ]]; then
          if [[ -n "$task_desc" ]]; then
              task_desc="$task_desc
  $selected_archived"
          else
              task_desc="$selected_archived"
          fi
          current_round_refs+=("$selected_archived")
          # NOTE: deliberately not added to all_file_refs — archived task
          # references stay inline in the description only, not in the
          # file_references: frontmatter.
          success "Added archived ref: $selected_archived" >&2
      fi
      continue
  ```
- Adjust the `Add file reference` branch so it only fires when `add_file == "Add file reference"` (currently it is a fall-through; with the new option we need an explicit elif). The cleanest shape:
  ```bash
  if [[ "$add_file" == "Done with files" ]] || [[ -z "$add_file" ]]; then
      break
  elif [[ "$add_file" == "Remove reference" ]]; then
      ...
      continue
  elif [[ "$add_file" == "Add archived task reference" ]]; then
      ...
      continue
  fi
  # Fall-through: Add file reference (existing file walker block at line 1163)
  ```

### 3. Removal flow (no logic change required)

The current Remove branch (lines 1137–1160) removes by exact-string match using `grep -vxF "$remove_file"` against `task_desc`, and trims `current_round_refs` and `all_file_refs`. Archived refs are in `current_round_refs` but not `all_file_refs`, so the `all_file_refs` pruning loop is a no-op for them — correct behaviour.

The only required tweak is renaming the matched literal `"Remove file reference"` → `"Remove reference"` in the menu dispatch (one line at 1137).

### 4. Help text

Update the `--help` usage block (lines 60–127) is **not** required — the change is interactive-only. The `--file-ref REF` batch flag continues to mean "add to `file_references:` frontmatter"; archived-task inline references are not exposed through a batch flag in this iteration. If a batch flag is wanted later, that's a follow-up — out of scope for t798 per the task description.

## Verification

1. **Happy path — interactive add:**
   - Run `./ait create` (or `./.aitask-scripts/aitask_create.sh`) in interactive mode against a working repo with archived tasks present (the current repo has many under `aitasks/archived/`).
   - Pick any task type / name / etc. to reach the description loop.
   - In the "Add reference?" menu, choose **Add archived task reference**.
   - Confirm fzf shows archived tasks (parents + children) with completed-at and issue-type columns and shows the file preview on the right.
   - Select one. Confirm the success line prints and the path appears as a new line in the description.
   - Finish task creation. Open the resulting `aitasks/t<N>_*.md`:
     - The path is present inline in the body.
     - The frontmatter has **no** `file_references:` entry pointing to the archived path (since archived refs are not pushed into `all_file_refs`).
2. **Cancel path:** In the archived-task fzf, press Esc → no row is added, description body is unchanged, menu loops back.
3. **Empty archive:** Temporarily move `aitasks/archived/` aside (or test in a fresh repo). Choosing the option prints `No archived tasks found.` and returns — no crash, no description change.
4. **Removal:** After adding both a file ref and an archived ref in the same description round, choose **Remove reference** and confirm both appear in the removal fzf and either can be removed cleanly (description body line vanishes, in-round tracking updates).
5. **Multi-round persistence:** Add an archived ref, then choose "Add more description", finish creating the task. Confirm the archived ref survives in the description body (this also confirms it's not accidentally being treated as a transient).
6. **No regression on `--file-ref` batch flag:** Run `./.aitask-scripts/aitask_create.sh --batch --name regress_check --priority low --effort low --issue-type chore --file-ref "aitasks/t1_foo.md:1"` and confirm the resulting task still gets `file_references:` populated as before. (No code path along this flag changed.)
7. **Linting:** `shellcheck .aitask-scripts/aitask_create.sh` — no new warnings.

## Out of scope (explicitly deferred)

- Searching inside zipped archive bundles (`aitasks/archived/old.tar.zst`). The user noted "probably not for now".
- A batch flag (`--archived-ref`) for non-interactive callers.
- Auto-populating archived references into a new YAML field.
- Showing archived **plan** files (`aiplans/archived/p*.md`) — only task files are searched.

## Step 9 (Post-Implementation)

After implementation and Step 8 review, follow the standard task-workflow Step 9: clean uncommitted state, no separate branch in 'fast' profile (working on current branch), run `aitask_archive.sh 798`, push.

## Final Implementation Notes

- **Actual work done:** Added `select_archived_task_ref()` helper in `.aitask-scripts/aitask_create.sh` just below `select_dependencies()`. It calls `aitask_query_files.sh recent-archived 999`, formats `RECENT_ARCHIVED:` lines into `<path>    [<completed_at>] <basename> (<issue_type>)` rows, and shows them in fzf with a path preview. The first whitespace token of the selected row is echoed back as the path. Extended the description-loop sub-menu in `get_task_definition()` with a new "Add archived task reference" option (always available), renamed "Remove file reference" → "Remove reference" and the prompt "Add file? " → "Add reference? " to match the broadened menu, and added a dispatch branch that appends the selected archived path inline to `task_desc` and tracks it in `current_round_refs` only (NOT in `all_file_refs`, so `file_references:` frontmatter stays clean).
- **Deviations from plan:** None significant. One implementation detail not in the plan sketch: the initial draft included `< /dev/tty` on the fzf call (copy-pasted from the file-walker invocation), which `shellcheck` flagged as `SC2259` because it overrides the piped `echo "$rows"` input. Removed `< /dev/tty`; fzf still draws to the terminal correctly since piped input is the supported mode here.
- **Issues encountered:** Pre-existing dirty state in the working tree (uncommitted edits under `.claude/skills/aitask-explore/`, `.agents/skills/aitask-explore/`, etc.) — left untouched per task scope. Only `.aitask-scripts/aitask_create.sh` was staged for the t798 code commit.
- **Key decisions:**
  - Reused the existing `recent-archived` subcommand of `aitask_query_files.sh` rather than reinventing the archived-task scan loop. Sort order (completed_at desc) matches what an "archived task picker" should default to.
  - Soft cap of 999 for the limit argument — effectively "all archived tasks", but avoids passing a non-numeric value and keeps the helper's contract intact.
  - Tracking archived refs in `current_round_refs` (so the in-round Remove flow can drop them) but NOT in `all_file_refs` (so the `file_references:` frontmatter is unaffected). Matches the user's "inline in description only" decision.
  - Renamed "Remove file reference" → "Remove reference" since the same affordance now drops both kinds; kept the inner `remove_file` variable name to minimise diff noise.
- **Upstream defects identified:** None.

