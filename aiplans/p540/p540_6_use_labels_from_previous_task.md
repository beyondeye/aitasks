---
Task: t540_6_use_labels_from_previous_task.md
Parent Task: aitasks/t540_task_creation_from_codebrowser.md
Parent Plan: aiplans/p540_task_creation_from_codebrowser.md
Sibling Tasks: aitasks/t540/t540_1_*.md, aitasks/t540/t540_2_*.md, aitasks/t540/t540_3_*.md, aitasks/t540/t540_4_*.md, aitasks/t540/t540_5_*.md, aitasks/t540/t540_7_*.md
Worktree: (none — working on current branch)
Branch: main
Base branch: main
---

# Plan — t540_6: "use labels from previous task" option

## Scope

Add a per-user "use labels from previous task" option to
`aitask_create.sh`'s interactive label picker. Stored in
`aitasks/metadata/userconfig.yaml` (gitignored, per-user).
Independent of other t540 children — lands in parallel.

## Exploration results (from parent planning)

- **Label picker loop:** `aitask_create.sh:801-899`
  (`get_labels_interactive()`). Fzf loop with:
  - `>> Done adding labels` (exit option at line 836).
  - `>> Add new label` (manual entry).
  - Available labels from `labels.txt` (filtered against
    already-selected).
  - Continuation prompt at lines 882-886.
  - Finalizes to the global `SELECTED_LABELS` variable at lines
    890-895.

- **Finalization callsite:** after `get_labels_interactive()`
  returns in the interactive path (around line ~1036, before
  the description gathering), `SELECTED_LABELS` holds the
  canonical comma-separated list. Persist here.

- **Userconfig pattern:**
  `.aitask-scripts/lib/task_utils.sh` `get_user_email()` at
  lines 163-170:
  ```bash
  get_user_email() {
      local config="${TASK_DIR:-aitasks}/metadata/userconfig.yaml"
      if [[ -f "$config" ]]; then
          grep '^email:' "$config" | sed 's/^email: *//'
      fi
  }
  ```
  Mirror this for the new helpers. For writes, a sed-based
  in-place update is the simplest path; when the field is
  absent, append. When the file is missing entirely, create it
  with the comment header `# Local user configuration
  (gitignored, not shared)` — see the existing create path in
  the workflow that sets `email:` into userconfig.

- **Labels list serialization:** the field should use a YAML
  list `[label1, label2]`, matching the way `labels` is stored
  in task frontmatter. Use the same formatter
  (`format_labels_yaml`) if accessible; otherwise inline.

## Design

- **New fields in `lib/task_utils.sh`:**
  - `get_last_used_labels` — returns the comma-separated list
    (no brackets), empty when absent.
  - `set_last_used_labels <csv>` — writes/updates the field.
    Handles: missing file, existing file without the field,
    existing file with the field (replace in place).
- **UX:** in `get_labels_interactive()`, if
  `get_last_used_labels` returns non-empty, prepend an extra
  option to the first iteration's fzf menu:
  `>> Use labels from previous task (label1, label2)`.
- **Behavior on select:** seed `SELECTED_LABELS` with the
  previous list and set a local flag so the option does not
  appear in subsequent iterations of the same loop.
- **Persist on exit:** call `set_last_used_labels
  "$SELECTED_LABELS"` after the picker finishes.

## Implementation sequence

1. Add `get_last_used_labels` / `set_last_used_labels` to
   `lib/task_utils.sh`.
2. Extend `get_labels_interactive()` to prepend the new
   option.
3. Call the setter after the picker loop exits.
4. Write `tests/test_last_used_labels.sh` (field round-trip,
   file creation, field append, field replace).
5. shellcheck.

## Verification

- `bash tests/test_last_used_labels.sh` — PASS.
- Manual interactive: create a task with labels X, Y. Re-run
  interactively — first fzf menu shows
  `>> Use labels from previous task (X, Y)`.
- Select the option — `SELECTED_LABELS` pre-fills with X, Y
  and the loop continues (can add more or exit).
- Option not shown on second iteration of same session.
- Inspect `userconfig.yaml` — `last_used_labels: [X, Y]`
  present and correct.

## Post-implementation

Archival via `./.aitask-scripts/aitask_archive.sh 540_6`.
