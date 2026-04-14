---
Task: t540_6_use_labels_from_previous_task.md
Parent Task: aitasks/t540_task_creation_from_codebrowser.md
Parent Plan: aiplans/p540_task_creation_from_codebrowser.md
Sibling Tasks: aitasks/t540/t540_1_*.md, aitasks/t540/t540_2_*.md, aitasks/t540/t540_3_*.md, aitasks/t540/t540_4_*.md, aitasks/t540/t540_5_*.md, aitasks/t540/t540_7_*.md
Worktree: (none — working on current branch)
Branch: main
Base branch: main
plan_verified:
  - claudecode/opus4_6 @ 2026-04-14 18:18
---

# Plan — t540_6: "use labels from previous task" option (verified)

## Context

Users creating a batch of related tasks frequently repeat the same label set. Today, every task requires re-selecting labels from scratch. Add a per-user convenience option to `aitask_create.sh`'s interactive label picker: the first fzf iteration gains a `>> Use labels from previous task (...)` menu entry that seeds `SELECTED_LABELS` with the previous task's label list. On exit of the picker, the final list is persisted to `aitasks/metadata/userconfig.yaml` (gitignored, per-user) so the next interactive run sees it.

This is the parent t540's simplest child, independent of t540_1/t540_2/t540_3 and the codebrowser/board integrations. It touches only `aitask_create.sh`, `lib/task_utils.sh`, and a new test.

## Verification status

Re-read on 2026-04-14 against `main`. Plan assumptions are intact; only line-number anchors drifted. Corrections applied below.

**Anchor drift (from the original plan):**
- `get_labels_interactive()` is at `aitask_create.sh:828-926` (plan said 801-899). Fzf loop + finalization unchanged.
- Post-picker call site is at `aitask_create.sh:1696-1697` (plan said ~1036). Inside `run_draft_interactive` where `SELECTED_LABELS` is copied to local `labels`. This is the only interactive caller of `get_labels_interactive`.
- `format_labels_yaml()` is at `aitask_create.sh:1157-1165` (plan said 1112-1120).
- `get_user_email()` is at `lib/task_utils.sh:165-170` (plan said 163-170).
- `LABELS_FILE` is defined at `aitask_create.sh:747` as `aitasks/metadata/labels.txt`.

**No re-design needed.** The approach (extend picker menu + persist on exit) still fits the current code shape cleanly.

## Design (locked)

### Storage

New field in `aitasks/metadata/userconfig.yaml`:
```yaml
last_used_labels: [codebrowser, aitask-create]
```
YAML list of strings, same shape as the frontmatter `labels` field. Empty or missing is valid (menu entry is suppressed). The file is gitignored per `aitask_setup.sh:1031-1036`, so this is a per-user, per-PC signal.

### Helpers (new in `lib/task_utils.sh`)

Add next to the existing `get_user_email()` at lines 165-170. The `_AIT_TASK_UTILS_LOADED` guard at line 6 already protects the whole file — no new guard variable needed.

1. **`get_last_used_labels()`** — returns the comma-separated list (no brackets, no quotes), empty when the field or file is absent. Mirror of `get_user_email`: `grep` the field, `sed` to strip the `last_used_labels:` prefix + surrounding brackets, then normalize `, ` → `,`.

2. **`set_last_used_labels <csv>`** — writes/updates the field. Must handle three cases:
   - **File missing:** create it with the standard header comment (`# Local user configuration (gitignored, not shared)`) and write the field. Mirror the `setup_userconfig()` create path at `aitask_setup.sh:2625-2638`.
   - **File exists, field absent:** append `last_used_labels: [...]` at EOF.
   - **File exists, field present:** replace the line in-place using `sed_inplace` (from `terminal_compat.sh`) with a pattern matching `^last_used_labels:.*$`. **Do NOT use GNU-only sed features** per `CLAUDE.md`.
   
   Empty input writes an empty list `last_used_labels: []` (rather than deleting the field). This keeps the semantics predictable: "the most recent selection was empty" vs "no prior selection" are both treated as "no offer in the menu" by the getter, so they're equivalent at the consumption site.

### UX (in `aitask_create.sh`)

Modify `get_labels_interactive()` at `aitask_create.sh:828-926`:

1. Before the `while true` loop at line 835, read the previous list once:
   ```bash
   local prev_labels_csv
   prev_labels_csv=$(get_last_used_labels)
   local prev_labels_display=""
   if [[ -n "$prev_labels_csv" ]]; then
       prev_labels_display=">> Use labels from previous task (${prev_labels_csv})"
   fi
   local offered_prev=false
   ```

2. In the options-build section (lines 861-866), when `prev_labels_display` is non-empty AND `offered_prev` is false, prepend the new line to `options`:
   ```bash
   if [[ -n "$prev_labels_display" && "$offered_prev" == "false" ]]; then
       options="${prev_labels_display}"$'\n'"${options}"
   fi
   ```

3. In the selection-handling block after line 872 (`if [[ -n "$selected" ]]; then`), add a new branch BEFORE the existing `">> Done adding labels"` check:
   ```bash
   if [[ "$selected" == "$prev_labels_display" ]]; then
       # Seed the current selection with the previous labels and continue the loop
       IFS=',' read -ra _prev_split <<< "$prev_labels_csv"
       for _pl in "${_prev_split[@]}"; do
           [[ -n "$_pl" ]] && selected_labels+=("$_pl")
           success "Added label: $_pl"
       done
       offered_prev=true
       continue   # Skip the current_round update / continue prompt; loop again
   fi
   ```
   The `continue` bypasses the "Add another label / Done with labels" fzf at lines 908-913 so the user immediately sees the label menu again with the prev-labels option removed (since `offered_prev=true`) and can add more or select `>> Done adding labels`.

### Persistence (in `run_draft_interactive`)

At `aitask_create.sh:1696-1697`, the call site is:
```bash
    get_labels_interactive
    local labels="$SELECTED_LABELS"
```
Add one line immediately after line 1697:
```bash
    set_last_used_labels "$labels"
```
The persistence runs on every interactive create regardless of whether the user accepted the prev-labels offer, selected labels from scratch, or ended with an empty list. Batch mode is NOT touched — `--labels` on the CLI is automation-land and should not mutate userconfig.

## Key files to modify

1. **`.aitask-scripts/lib/task_utils.sh`**
   - Add `get_last_used_labels()` and `set_last_used_labels()` right after `get_user_email()` (after line 170). See Design → Helpers.

2. **`.aitask-scripts/aitask_create.sh`**
   - `get_labels_interactive()` at lines 828-926 — pre-loop setup, options prepend, and new selection branch.
   - `run_draft_interactive()` at line 1697 — one-line `set_last_used_labels "$labels"` call.

3. **`tests/test_last_used_labels.sh`** *(new)*
   - Model on the first helper-test sections of `tests/test_file_references.sh` (setup_project pattern). For purely-helper coverage, a minimal self-contained test (no need to spin up a full fake repo) is sufficient — source `lib/task_utils.sh` directly after setting `TASK_DIR=<tmpdir>/aitasks` and exercise the helpers.
   - Cases:
     1. **Field round-trip:** write `[a, b]`, read returns `a,b`.
     2. **File missing:** `set_last_used_labels "x,y"` creates the file with the header comment AND the field.
     3. **File exists without the field:** `set_last_used_labels "x,y"` appends without clobbering existing `email: foo@bar` line.
     4. **File exists with the field:** `set_last_used_labels "c,d"` replaces the prior value in place. Verify only one `last_used_labels:` line remains.
     5. **Empty input:** `set_last_used_labels ""` → `last_used_labels: []` is written and `get_last_used_labels` returns empty.
     6. **Absent field:** `get_last_used_labels` returns empty when the field is not in the file.
     7. **macOS sed compat sanity:** the test should not rely on `sed -i` directly — it will run against whatever `set_last_used_labels` uses under the hood (`sed_inplace`), so just assert behavior.

## Reference files for patterns

- `.aitask-scripts/lib/task_utils.sh:165-170` (`get_user_email`) — grep/sed idiom for the reader.
- `.aitask-scripts/aitask_setup.sh:2625-2638` (`setup_userconfig`) — file-create-with-header pattern.
- `.aitask-scripts/lib/terminal_compat.sh` (`sed_inplace`) — portable in-place edit helper.
- `.aitask-scripts/aitask_create.sh:1157-1165` (`format_labels_yaml`) — CSV-to-YAML-list idiom (may be used from the setter to format the list literal).
- `.aitask-scripts/aitask_create.sh:828-926` (`get_labels_interactive`) — the fzf loop to extend.
- `tests/test_file_references.sh:67-109` — `setup_project()` template if a full fake repo is needed; otherwise a plain `TMPDIR` + `TASK_DIR` export is simpler for pure helper tests.

## Implementation sequence

1. Add `get_last_used_labels` / `set_last_used_labels` to `lib/task_utils.sh`.
2. Write `tests/test_last_used_labels.sh` against the new helpers and run it — this gates the helper implementation before touching `aitask_create.sh`.
3. Extend `get_labels_interactive()` with the pre-loop setup, options prepend, and new selection branch.
4. Add the `set_last_used_labels "$labels"` call at line 1697 in `run_draft_interactive`.
5. Run `shellcheck` on both touched scripts.
6. Manual interactive smoke test (see Verification).

## Verification

- `bash tests/test_last_used_labels.sh` — PASS (all 7 cases).
- `shellcheck .aitask-scripts/aitask_create.sh .aitask-scripts/lib/task_utils.sh` — no new warnings beyond pre-existing ones.
- **Manual interactive:**
  1. `./.aitask-scripts/aitask_create.sh` interactively (or `./ait create`), select labels `testing, backend`, finalize the task.
  2. Re-run `./ait create` interactively — the first fzf menu shows `>> Use labels from previous task (testing, backend)` as the top option.
  3. Select that option → selection is seeded with `testing, backend`, and the label menu redraws without the prev-labels option.
  4. Add one more label `ui` via `>> Add new label`, finish with `>> Done adding labels`. The new task has `labels: [testing, backend, ui]`.
  5. Inspect `aitasks/metadata/userconfig.yaml` — `last_used_labels: [testing, backend, ui]` is present.
  6. Run interactively a third time without picking the prev-labels option → picker loop still works normally; on finalize, userconfig is updated to the latest selection.
- **Regression:** `bash tests/test_draft_finalize.sh` — PASS (closest existing test that exercises the create path end-to-end).

## Out of scope

- Batch mode (`--batch --labels ...`) is deliberately untouched. CLI automation should not mutate userconfig.
- Storing per-project "last used labels" — only per-user/global is in scope. Different projects with their own labels just overwrite each other.
- Folding this with the broader label suggestion / prediction feature — not the goal here.

## Post-implementation

Standard archival via `./.aitask-scripts/aitask_archive.sh 540_6` per task-workflow Step 9. Include a Final Implementation Notes section on commit (before archival) per the child-task documentation conventions in `task-workflow/SKILL.md`.
