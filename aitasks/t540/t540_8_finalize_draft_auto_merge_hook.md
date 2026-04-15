---
priority: medium
effort: low
depends: []
issue_type: feature
status: Ready
labels: [aitask-create]
created_at: 2026-04-15 11:31
updated_at: 2026-04-15 11:31
---

Wire `run_auto_merge_if_needed` into the interactive `finalize_draft` commit path so that any invocation of `aitask_create.sh --file-ref <path>` (interactive or `--batch --finalize`) triggers the same auto-merge detection that `--batch --commit --auto-merge` already has.

## Background / Why

t540_3 added `run_auto_merge_if_needed` and wired it into the two `--batch --commit` create paths (`aitask_create.sh:1379-1396` child, `1412-1428` parent). The interactive `finalize_draft` path was explicitly left out of scope because the flag is consumed at draft time, so the helper can't read `BATCH_FILE_REFS` at finalize time — it must re-read `file_references` from the finalized task file.

t540_4 (just landed) wires the codebrowser `n` keybinding to launch `aitask_create.sh --file-ref <path>` in interactive mode. That means the codebrowser flow today creates the task standalone, even if another pending task already references the same file. The user must manually edit the AgentCommandScreen command string to add `--batch --commit --auto-merge`, which bypasses the interactive flow.

This task closes that gap by hooking auto-merge into `finalize_draft` so the codebrowser flow (and any other interactive `--file-ref` use) gets auto-merge detection without flag juggling.

## Depends on (already landed)

- **t540_3** — provides `run_auto_merge_if_needed` helper + `--auto-merge` / `--no-auto-merge` flags + `BATCH_AUTO_MERGE` state.
- **t540_4** — provides the codebrowser `n` keybinding that makes interactive `--file-ref` use a real workflow.
- **t540_1** — provides `get_file_references` helper that can read back the finalized task's frontmatter.

## Scope

In scope:
- Call `run_auto_merge_if_needed <new_task_id> <new_task_file>` at the end of `finalize_draft()` in `aitask_create.sh`, right after the creation commit lands.
- Gate on `BATCH_AUTO_MERGE=true`. Default stays `false` (warn-but-skip) to preserve current behavior for users not opting in.
- Optionally offer an interactive "auto-merge?" fzf prompt when `file_references` is non-empty and candidate matches exist — gated by a new `--interactive-auto-merge` flag or a `userconfig.yaml` preference. **Decision deferred to plan time.**

Out of scope:
- Codebrowser-native candidate picker (would bypass `aitask_create.sh` entirely).
- Fold-time `file_references` union — that's t540_7.
- Changing the default of `BATCH_AUTO_MERGE` from `false` to `true`.

## Key files

- `.aitask-scripts/aitask_create.sh`:
  - `finalize_draft()` (search for the function definition around line 1780-1823 in current main) — add the helper call after the creation commit and before the function returns.
  - `run_auto_merge_if_needed()` (already defined ~line 1220+) — verify it reads `file_references` from the finalized file via `get_file_references` so it works on the finalize path without relying on `BATCH_FILE_REFS`.
  - `parse_args()` (~line 119) — possibly add `--interactive-auto-merge` flag (TBD at plan time).

- `tests/test_auto_merge_file_ref.sh` — extend with a finalize-path test:
  1. Create a draft with `aitask_create.sh --file-ref foo.py` (no `--commit`).
  2. Create another task A with `--file-ref foo.py --commit` so there's a match.
  3. Finalize the draft with `aitask_create.sh --batch --finalize <draft_id> --auto-merge`.
  4. Assert A was folded into the new task.

## Reference material

- `aiplans/archived/p540/p540_3_auto_merge_on_file_ref.md` — complete implementation notes for the helper, including the deferred-scope reasoning for `finalize_draft`. Especially §"Scope (locked after verification)" and "Key decisions".
- `aiplans/archived/p540/p540_4_codebrowser_create_from_selection.md` — codebrowser integration that makes this task user-visible.

## Verification

- `bash tests/test_auto_merge_file_ref.sh` — all existing tests pass + the new finalize-path test passes.
- `bash tests/test_file_references.sh` — no regression.
- `shellcheck .aitask-scripts/aitask_create.sh` — no new warnings.
- Manual smoke test via codebrowser: open a file already referenced by another pending task, press `n`, walk through the interactive create, and verify the other task is auto-merged (with `--auto-merge` passed) or warned about (default).
