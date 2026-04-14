---
priority: low
effort: low
depends: []
issue_type: feature
status: Done
labels: [aitask-create, bash_scripts]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_6
created_at: 2026-04-14 10:15
updated_at: 2026-04-14 23:34
completed_at: 2026-04-14 23:34
---

t540_6: add a "use labels from previous task" option to the interactive
label picker in `aitask_create.sh`. Per-user, stored in
`aitasks/metadata/userconfig.yaml`. Independent of the other t540
children — can land in parallel with any of them.

## Context

Users creating a batch of related tasks frequently repeat the same
label set. Today, every task requires re-selecting labels from
scratch. The parent task description explicitly asks for a per-user
convenience option: "in the phase where we choose the labels for a
task, propose to add the labels used from the previous created task
(this is a local setting)".

## Design decisions (from parent plan)

- **Storage:** new `last_used_labels` field in
  `aitasks/metadata/userconfig.yaml` (gitignored, per-user).
- **Format:** YAML list of strings, same as labels frontmatter:
  `last_used_labels: [codebrowser, aitask-create]`
- **UX:** prepend a single extra fzf option in the first iteration
  of `get_labels_interactive()`:
  `>> Use labels from previous task (label1, label2)`. Only shown
  when `last_used_labels` is non-empty.
- **Behavior when selected:** seed `SELECTED_LABELS` with the
  previous list, then continue the normal add-loop (user can still
  add or delete labels). The option disappears from subsequent
  iterations of the same session so it is not offered twice.
- **Persist on exit:** after `get_labels_interactive()` finalizes
  the selection, write the final list back to
  `userconfig.yaml:last_used_labels`. This happens for every
  interactive create, so the field is always fresh.

## Key files to modify

1. `.aitask-scripts/lib/task_utils.sh`
   - New `get_last_used_labels()` — parses the field, prints CSV
     on stdout, empty when field absent. Mirror of
     `get_user_email()` at lines 163-170.
   - New `set_last_used_labels <csv>` — writes the field to
     userconfig.yaml. Must create the file if missing (with the
     standard `# Local user configuration (gitignored, not
     shared)` header comment, per the existing pattern). Must
     update an existing field in place (not append).
   - Both helpers must guard against double-sourcing with the
     existing `_AIT_*_LOADED` variable pattern.

2. `.aitask-scripts/aitask_create.sh`
   - `get_labels_interactive()` at lines 801-899:
     - Before the fzf loop, read `last_used_labels` via
       `get_last_used_labels`.
     - If non-empty, prepend an extra option to the menu:
       `>> Use labels from previous task (label1, label2)`.
     - Handle selection of that option: seed
       `SELECTED_LABELS` with the list, set a flag so the
       option is not offered in subsequent iterations of the
       loop, and continue adding labels as normal.
   - After `get_labels_interactive()` returns (around line
     1036, just before the description-file step or wherever the
     label array is finalized), call `set_last_used_labels
     "$SELECTED_LABELS"`.

3. `tests/test_last_used_labels.sh` *(new)*
   - Set up: write a temporary `userconfig.yaml` with
     `last_used_labels: [a, b]`.
   - `get_last_used_labels` returns `a,b`.
   - `set_last_used_labels "c,d"` — re-read returns `c,d`.
   - Field absent: `get_last_used_labels` returns empty; set
     then read round-trips.
   - File missing: `set_last_used_labels` creates the file
     with the header comment AND writes the field.
   - File exists without the field: `set_last_used_labels`
     appends the field without clobbering existing keys (e.g.,
     `email: foo@bar`).

## Reference files for patterns

- `.aitask-scripts/lib/task_utils.sh`
  `get_user_email()` at lines 163-170 — grep/sed idiom to
  mirror.
- `.aitask-scripts/aitask_create.sh` `get_labels_interactive()`
  at lines 801-899 — fzf loop to extend.
- `.aitask-scripts/aitask_create.sh` `format_labels_yaml()` at
  lines 1112-1120 — YAML serialization idiom.

## Implementation plan

1. Add `get_last_used_labels` / `set_last_used_labels` to
   `task_utils.sh`.
2. Add the `>> Use labels from previous task (...)` menu entry
   in `get_labels_interactive()`.
3. Add the post-selection persistence call.
4. Write `tests/test_last_used_labels.sh`.
5. Run shellcheck.

## Verification

- `bash tests/test_last_used_labels.sh` — PASS.
- Manual: run `./.aitask-scripts/aitask_create.sh`
  interactively, pick labels, finalize. Re-run interactively
  and confirm the first fzf menu shows the `>> Use labels from
  previous task (...)` option with the previous selection.
- Manual: select the `>> Use labels from previous task`
  option, confirm the labels array is pre-filled and the
  option is not shown on subsequent iterations in the same
  session.
- Manual: inspect `userconfig.yaml` after a create — field
  matches the final label selection.

## Out of scope

- Any other t540 feature. This task is independent and self-
  contained.
