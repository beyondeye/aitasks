---
Task: t1030_1_frontmatter_cli_scaffold.md
Parent Task: aitasks/t1030_task_attachments_support.md
Sibling Tasks: aitasks/t1030/t1030_2_local_backend_cache_index.md, aitasks/t1030/t1030_3_archive_gc_fold_rebind.md
Archived Sibling Plans: (none yet — t1030_1 is the first child)
Worktree: aiwork/t1030_1_frontmatter_cli_scaffold
Branch: aitask/t1030_1_frontmatter_cli_scaffold
Base branch: main
---

# Plan — t1030_1 Frontmatter + CLI scaffold

Land the **pure, headless, unit-testable primitives** (YAML list-of-mappings
read, SHA-256, hash/shard/cache path helpers) and a working read-only
`ait attach ls`. **No blob storage** — that is t1030_2.

Design: `aidocs/task_attachments_design.md` §3 (schema), §6 (CLI surface).
The full spec (Context / Key Files / Reference patterns / Verification) lives in
the task file `aitasks/t1030/t1030_1_frontmatter_cli_scaffold.md` — read it first.

## Step 1 — Dispatcher arm in `ait`
- In `ait` (flat `case`, ~lines 187–330) add, alphabetically:
  `attach)       shift; exec "$SCRIPTS_DIR/aitask_attach.sh" "$@" ;;`

## Step 2 — `lib/attachment_utils.sh` (NEW, pure helpers)
- `#!/usr/bin/env bash`, `set -euo pipefail`, source-on-startup guard
  (`aidocs/framework/shell_conventions.md`).
- `attachment_sha256 <file>` → `sha256:<64hex>`. Encapsulate the CLI choice in
  ONE function: try `openssl dgst -sha256`, fall back `sha256sum`, then
  `shasum -a 256`. Strip filename, prepend `sha256:`.
- `attachment_validate_hash <hash>` → exit 0 iff matches `^sha256:[0-9a-f]{64}$`.
- `attachment_shard_path <hash>` → strip prefix, validate, print `<2>/<62>`.
- `attachment_cache_path <hash>` →
  `${XDG_CACHE_HOME:-$HOME/.cache}/ait/attachments/<hash>`.

## Step 3 — `read_yaml_mappings` in `lib/yaml_utils.sh`
- Add `read_yaml_mappings <file> <field>`; extend the block-parse approach of
  `read_yaml_list()` (~lines 92–141). **Read-only** here (append/remove is
  t1030_2).
- Output contract (document at the function top — siblings depend on it):
  one line per attachment, `key=val;key=val;…`, fields in schema order
  (`hash;name;mime;size;added_at;backend;url`). Missing field → no output,
  exit 0. Handle `url: null`.

## Step 4 — `aitask_attach.sh` (NEW)
- Verb dispatcher modeled on `aitask_projects.sh` `main()` (~lines 939–989):
  `add ls get rm move gc help`. Source `terminal_compat.sh`, `yaml_utils.sh`,
  `task_utils.sh`, `attachment_utils.sh`.
- `cmd_list` (`ls`): resolve task file (`aitask_query_files.sh resolve <id>` or
  task_utils), `read_yaml_mappings` the `attachments:` field, print a table
  (name · short-hash · size · backend); empty → "No attachments."
- `cmd_add/cmd_get/cmd_remove/cmd_move/cmd_gc`: `die "implemented in
  t1030_2/t1030_3"` placeholders.
- `show_help` lists the full §6 surface (mark unimplemented verbs).

## Step 5 — Tests `tests/test_attach_scaffold.sh` (NEW)
- Use `tests/lib/test_scaffold.sh` + `tests/lib/asserts.sh`; keep PASS/FAIL/TOTAL.
- sha256 known vector: empty input → `e3b0c44298fc1c149afbf4c8996fb924...`.
- shard split, `attachment_validate_hash` reject cases (bad len, no prefix).
- `read_yaml_mappings` on a fixture with 0 / 1 / 2 attachments (incl. `url: null`).
- `ait attach ls <task>` end-to-end against a fixture task.

## Verification
- `shellcheck .aitask-scripts/aitask_attach.sh .aitask-scripts/lib/attachment_utils.sh .aitask-scripts/lib/yaml_utils.sh` clean.
- `bash tests/test_attach_scaffold.sh` — all PASS.
- Manual: fixture task with an `attachments:` block (design §3) → `ait attach ls`
  prints entries; storage verbs print the not-yet-implemented notice.

## Step 9 (Post-Implementation)
Standard cleanup/archival/merge per `task-workflow` Step 9. As the first child,
write thorough **Final Implementation Notes** (esp. the `read_yaml_mappings`
output contract and `attachment_utils.sh` signatures) — they are the primary
reference for t1030_2 and t1030_3.
