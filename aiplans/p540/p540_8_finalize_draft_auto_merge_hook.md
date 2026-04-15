---
Task: t540_8_finalize_draft_auto_merge_hook.md
Parent Task: aitasks/t540_task_creation_from_codebrowser.md
Sibling Tasks: aitasks/t540/t540_5_*.md, aitasks/t540/t540_7_*.md
Archived Sibling Plans: aiplans/archived/p540/p540_1_*.md, aiplans/archived/p540/p540_2_*.md, aiplans/archived/p540/p540_3_*.md, aiplans/archived/p540/p540_4_*.md, aiplans/archived/p540/p540_6_*.md
Worktree: (none — working on current branch)
Branch: main
Base branch: main
plan_verified:
  - claudecode/opus4_6 @ 2026-04-15 12:02
---

# Plan — t540_8: finalize_draft auto-merge hook

## Context

t540_3 (landed) added `run_auto_merge_if_needed` and wired it into the two `--batch --commit` paths in `aitask_create.sh` (child at `:1555`, parent at `:1591`). The interactive `finalize_draft` path was explicitly **out of scope** there because the flag is consumed at draft time, and t540_3 kept the change surface tight.

t540_4 (landed) wires the codebrowser `n` key to launch `aitask_create.sh --file-ref <path>` in **interactive** mode. That flow goes through `finalize_draft`, which currently has **no** auto-merge hook. Users must manually edit the `AgentCommandScreen` command string to add `--batch --commit --auto-merge` to get the auto-merge behavior — which bypasses the entire interactive flow.

This task closes the gap: after `finalize_draft` commits a task whose frontmatter includes `file_references`, call `run_auto_merge_if_needed` so auto-merge detection runs on the same file paths that triggered t540_3's helper. Because `run_auto_merge_if_needed` already reads `file_references` from the finalized file via `get_file_references` (not from `BATCH_FILE_REFS`), the helper is re-usable as-is from the finalize path.

## Scope

**In scope:**
- Call `run_auto_merge_if_needed` at the end of both paths in `finalize_draft()`:
  - Child path — after the `task_git commit`, before `release_child_lock`.
  - Parent path — after the `task_git commit`.
- In interactive mode (`BATCH_MODE=false`), when candidates exist and `BATCH_AUTO_MERGE=false`, show an fzf "Yes/No" prompt; on "Yes", flip `BATCH_AUTO_MERGE=true` locally and proceed with the fold. On "No", fall through to the existing warn-and-skip path.
- Extend `tests/test_auto_merge_file_ref.sh` with a finalize-path test.

**Out of scope:**
- Changing the default of `BATCH_AUTO_MERGE` from `false` to `true`.
- New `--interactive-auto-merge` CLI flag or `userconfig.yaml` preference (user selected "Always prompt in interactive mode").
- Codebrowser-side changes (t540_4 already landed; the existing `n` binding picks up the new behavior automatically).
- Fold-time `file_references` union — that is t540_7.
- Board `file_references` widget — that is t540_5.

## Verified state of current codebase

| Symbol | Path | Line | Notes |
|---|---|---|---|
| `parse_args()` | `.aitask-scripts/aitask_create.sh` | 126 | Already parses `--auto-merge` / `--no-auto-merge` at 147-148. No change. |
| `BATCH_MODE` / `BATCH_AUTO_MERGE` globals | `.aitask-scripts/aitask_create.sh` | 26, 46 | Already declared. No change. |
| `finalize_draft()` entry | `.aitask-scripts/aitask_create.sh` | 537 | Modify both child and parent paths. |
| Child commit (`ait: Add child task ...`) | `.aitask-scripts/aitask_create.sh` | 585 | Insert helper call AFTER this line, BEFORE `release_child_lock` at 587. |
| Parent commit (`ait: Add task ...`) | `.aitask-scripts/aitask_create.sh` | 644 | Insert helper call immediately after this line, before the final `if silent` echo at 647. |
| `run_auto_merge_if_needed()` | `.aitask-scripts/aitask_create.sh` | 1237 | Existing helper; already reads `file_references` from the on-disk file via `get_file_references` (line 1256). Add interactive prompt branch before the existing warn-or-fold gate at 1287. |
| `run_batch_mode()` --batch --commit wiring | `.aitask-scripts/aitask_create.sh` | 1555, 1591 | Existing call sites — unchanged reference for pattern consistency. |
| `get_file_references()` | `.aitask-scripts/lib/task_utils.sh` | 494 | Unchanged — helper already works for finalized files. |
| `tests/test_auto_merge_file_ref.sh` | 267 lines | 1-267 | Add Test 8 (finalize path); renumber existing syntax check to Test 9. |

## Design

### 1. Wire `run_auto_merge_if_needed` into `finalize_draft`

**Child path** — insert one new call after the commit at line 585, before the release at line 587:

```bash
task_git commit -m "ait: Add child task ${task_id}: ${humanized_name}"

run_auto_merge_if_needed "${parent_num}_${child_num}" "$filepath"

release_child_lock "$parent_num"
trap - EXIT
```

Keeping the call **inside** the child lock matches the pattern at `:1555` in `run_batch_mode`'s child path. The helper's fold step creates its own commit via `aitask_fold_mark.sh --commit-mode fresh`; running under the child lock preserves the invariant that child-scoped writes are serialized per parent.

**Parent path** — insert one new call after the commit at line 644:

```bash
task_git commit -m "ait: Add task ${task_id}: ${humanized_name}"

run_auto_merge_if_needed "$claimed_id" "$filepath"
```

`$claimed_id` is the numeric ID returned by `aitask_claim_id.sh --claim` (scoped in the parent branch starting at line 594). The helper's `new_id="${new_id#t}"` at line 1240 is a no-op on a bare numeric ID, so either `$claimed_id` or `$task_id` would work. Pass the numeric form to match the pattern at `:1591`.

Both insertion points are **after** the creation commit lands, which mirrors the existing `--batch --commit` wiring and keeps the git history readable:
1. `ait: Add (child) task tN: <name>` — the creation commit.
2. `ait: Fold tasks into tN: merge t...` — the auto-merge commit (if any).

### 2. Interactive prompt in `run_auto_merge_if_needed`

Insert a new block immediately after the `[[ ${#cand_ids[@]} -eq 0 ]] && return 0` guard at line 1285, and before the existing `if [[ "$BATCH_AUTO_MERGE" != true ]]; then warn ...` gate at line 1287:

```bash
# Interactive prompt (finalize_draft interactive path): when the user did
# not pass --auto-merge on the CLI but matching candidates were found,
# offer to fold them via fzf. Only fires when BATCH_MODE is false (i.e.,
# not invoked with --batch) and stdin is a TTY (guard against pipes).
if [[ "$BATCH_AUTO_MERGE" != true && "$BATCH_MODE" != true && -t 0 ]]; then
    info "Found ${#cand_ids[@]} pending task(s) that already reference this file:"
    local i
    for ((i = 0; i < ${#cand_ids[@]}; i++)); do
        info "  - t${cand_ids[$i]} (${cand_paths_by_id[${cand_ids[$i]}]}) → ${cand_files[$i]}"
    done
    local merge_choice
    merge_choice=$(printf 'Yes, fold them into this task\nNo, keep separate\n' \
        | fzf --prompt="Auto-merge? " --height=6 --no-info \
              --header="Fold ${#cand_ids[@]} matching task(s) into t${new_id}") || true
    if [[ "$merge_choice" == Yes* ]]; then
        BATCH_AUTO_MERGE=true
    fi
fi
```

Key points:
- `BATCH_MODE != true` ensures `--batch --commit` and `--batch --finalize` paths are untouched (no surprise prompts in scripts). The existing `--auto-merge` CLI flag is orthogonal: if the user sets `BATCH_AUTO_MERGE=true` explicitly, this block is skipped and the helper folds immediately.
- `-t 0` guards against the interactive script being invoked via pipe (e.g., `echo y | aitask_create.sh`) which would break fzf.
- `|| true` after fzf prevents ESCape from failing the whole pipeline under `set -e`. ESC → empty `$merge_choice` → falls through to the existing warn-and-skip branch.
- `BATCH_AUTO_MERGE=true` is a local mutation of a global; since finalize_draft returns shortly after, the state change is effectively scoped to this invocation. No need to restore.
- The info-level candidate listing replaces the existing warn-level duplication (we'd otherwise list twice — once pre-prompt, once in the warn branch). When the user says No, the existing `warn()` at 1288-1293 re-prints the list prefixed with "Found N pending task(s)…" — slight duplication but harmless; matches the informative tone of the existing warn. Alternative: track a `_printed_candidates=true` flag to dedupe the listing. Skipped for simplicity — the duplication is minor and a future follow-up can clean it up.

### 3. Test extension — new Test 8 (finalize path)

Add a new case to `tests/test_auto_merge_file_ref.sh` that exercises the `--batch --finalize <draft> --auto-merge` path. Rename the existing syntax-check case from Test 8 to Test 9.

```bash
# --- Test 8: Finalize-path auto-merge via --batch --finalize ---
echo "--- Test 8: Finalize-path auto-merge ---"
TMPDIR_8="$(setup_project)"
# Step 1: Create A with --commit so there's an existing match.
(cd "$TMPDIR_8/local" && \
    ./.aitask-scripts/aitask_create.sh --batch --commit --name "a8" \
        --desc "first" --file-ref "foo.py" >/dev/null 2>&1)
a8_file=$(find_task_file "$TMPDIR_8/local" a8)
a8_id=$(task_num_from_file "$a8_file")

# Step 2: Create a draft (batch, no --commit) that references the same file.
(cd "$TMPDIR_8/local" && \
    ./.aitask-scripts/aitask_create.sh --batch --name "b8" \
        --desc "second" --file-ref "foo.py" >/dev/null 2>&1)
draft_file=$(ls "$TMPDIR_8/local/aitasks/new"/draft_*_b8.md 2>/dev/null | head -1)

# Step 3: Finalize the draft with --auto-merge.
(cd "$TMPDIR_8/local" && \
    ./.aitask-scripts/aitask_create.sh --batch --finalize "$(basename "$draft_file")" \
        --auto-merge >/dev/null 2>&1)
b8_file=$(find_task_file "$TMPDIR_8/local" b8)
b8_id=$(task_num_from_file "$b8_file")

assert_eq "T8: a8 status is Folded (finalize path)" "Folded" "$(get_field "$a8_file" status)"
assert_eq "T8: a8 folded_into points to b8" "$b8_id" "$(get_field "$a8_file" folded_into)"
assert_contains "T8: b8 folded_tasks contains a8" "$a8_id" "$(get_field "$b8_file" folded_tasks)"
rm -rf "$TMPDIR_8"
```

Renumber the existing Test 8 syntax check to "Test 9: Syntax check".

**Why not test the interactive prompt directly?** fzf requires a real TTY; the test harness runs inside a subshell with stdin redirected, so the `-t 0` guard in the helper will be false and the interactive prompt block will be skipped. The test covers the finalize-wiring path (Test 8) and relies on the `--batch --finalize --auto-merge` explicit-flag path to prove the hook executes. Interactive prompt behavior is covered by manual smoke testing (Verification section).

**Rationale for leaving batch-finalize coverage as the only new case:** the finalize path's new code is exactly two call sites in `finalize_draft` plus an interactive prompt in `run_auto_merge_if_needed`. Test 8 proves the call sites fire and successfully delegate to the existing fold pipeline. The interactive block is guarded on TTY presence, which cannot be reproduced in the harness.

## Implementation sequence

1. **Modify `.aitask-scripts/aitask_create.sh`**:
   - Insert the interactive prompt block in `run_auto_merge_if_needed` between the `return 0` guard at 1285 and the existing warn gate at 1287.
   - Insert `run_auto_merge_if_needed "${parent_num}_${child_num}" "$filepath"` after the child commit at line 585, before `release_child_lock` at 587.
   - Insert `run_auto_merge_if_needed "$claimed_id" "$filepath"` after the parent commit at line 644.
2. **Modify `tests/test_auto_merge_file_ref.sh`**:
   - Add Test 8 as described above (finalize path).
   - Rename existing syntax-check block label to "Test 9: Syntax check".
3. **Syntax & lint checks**:
   - `bash -n .aitask-scripts/aitask_create.sh`
   - `shellcheck .aitask-scripts/aitask_create.sh`
4. **Run tests**:
   - `bash tests/test_auto_merge_file_ref.sh` — all 9 cases must pass.
   - `bash tests/test_file_references.sh` — regression check, no change expected.

## Verification

**Automated:**
- `bash tests/test_auto_merge_file_ref.sh` — PASS, including new Test 8.
- `bash tests/test_file_references.sh` — still PASS.
- `bash -n .aitask-scripts/aitask_create.sh` — clean.
- `shellcheck .aitask-scripts/aitask_create.sh` — no new warnings.

**Manual smoke test (interactive prompt) — user-approved path:**
1. Create task A that references a file: `./.aitask-scripts/aitask_create.sh --batch --commit --name "ref_a" --desc "ref a" --file-ref "README.md"`.
2. Run `./.aitask-scripts/aitask_create.sh --file-ref README.md` (interactive, no `--batch`, no `--auto-merge`).
3. Walk through the interactive prompts (priority, effort, type, status, labels, name, description). Press "Finalize now" at the end.
4. After the commit, the new fzf prompt should appear: "Auto-merge? Fold 1 matching task(s) into tN". Info lines should list `t<A's id> (README.md) → aitasks/t<A's id>_ref_a.md`.
5. Select "Yes, fold them into this task". Verify:
   - A's task file is gone (or marked Folded with `folded_into: N`).
   - New task N has `folded_tasks: [<A's id>]` in its frontmatter.
   - Git log shows two commits: `ait: Add task tN: <name>` followed by `ait: Fold tasks into tN: ...`.

**Manual smoke test (interactive prompt, decline):**
1. Same setup as above.
2. On the fzf prompt, select "No, keep separate" (or press ESC).
3. Verify: A is still Ready, new task N exists standalone with no folded_tasks, and a `warn()` message listed the candidates.

**Manual smoke test (batch finalize + --auto-merge):**
1. Create task A as above.
2. Create a draft: `./.aitask-scripts/aitask_create.sh --batch --name "ref_b" --desc "ref b" --file-ref "README.md"` (no `--commit`).
3. Finalize: `./.aitask-scripts/aitask_create.sh --batch --finalize draft_<timestamp>_ref_b.md --auto-merge`.
4. Verify A was folded into the new finalized task — no prompt (BATCH_MODE=true).

**Manual smoke test (codebrowser flow — the user-visible feature):**
1. `./ait codebrowser`. Open a file already referenced by another pending task.
2. Press `n`. AgentCommandScreen opens. Select "Run in terminal" / "Run in tmux".
3. `aitask_create.sh --file-ref <path>:<range>` launches interactively.
4. Fill the create flow, finalize.
5. After the creation commit, the fzf auto-merge prompt appears. Pick Yes → matching tasks fold into the new one.

**Regression checks:**
- `aitask_create.sh --batch --commit --file-ref foo.py` (no `--auto-merge`) — unchanged: creation commit + warn-only.
- `aitask_create.sh --batch --commit --file-ref foo.py --auto-merge` — unchanged: creation commit + fold commit.
- `aitask_create.sh --batch --finalize draft.md` (no `--auto-merge`) — new behavior: creation commit + warn about matches (same as `--batch --commit`; intentionally consistent).

## Post-implementation (Step 9 reference)

Run `./.aitask-scripts/aitask_archive.sh 540_8` per task-workflow Step 9. The archived plan file is the primary reference for any sibling task that needs to understand the finalize_draft auto-merge contract (e.g., t540_5 board widget, or a future task that changes the interactive prompt UX).
