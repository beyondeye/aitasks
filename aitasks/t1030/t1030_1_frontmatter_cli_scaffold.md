---
priority: medium
effort: medium
depends: []
issue_type: feature
status: Implementing
labels: [task_attachments]
assigned_to: dario-e@beyond-eye.com
anchor: 1030
created_at: 2026-06-28 12:07
updated_at: 2026-06-28 12:28
---

Scaffold the `attachments:` frontmatter schema and the `ait attach` CLI surface — **no actual blob storage yet** (that is t1030_2). This child lands the pure, headless, unit-testable units (YAML list-of-mappings parsing, SHA-256 hashing, hash/shard path helpers) and a working read-only `ait attach ls`.

Design spec: `aidocs/task_attachments_design.md` §3 (frontmatter schema), §6 (CLI surface). Coordination note in the parent (t1030) and `aidocs/unified_artifact_design.md` §10 (attachments are the immutable, inline-hash degenerate case — inline storage is *safe because immutable*).

## Context
First of three children of t1030 (local-only attachment v1). It exists to extract and test the reusable primitives in isolation before any storage logic, per the framework's testability-first decomposition. Subsequent siblings build storage (t1030_2) and archive/gc (t1030_3) on top of these primitives. The adapter seam is deliberately built generalizable so t1076_1 can later promote `attachment_backend` → `artifact_backend` without re-plumbing.

## Key Files to Modify / Create
- **`ait`** (repo root, flat `case` dispatcher ~lines 187–330): add one arm `attach) shift; exec "$SCRIPTS_DIR/aitask_attach.sh" "$@" ;;` (place it alphabetically near other subcommands).
- **`.aitask-scripts/aitask_attach.sh`** (NEW): internal verb dispatcher modeled on `aitask_projects.sh` `main()`. Verbs: `add ls get rm move gc` + `help`. In THIS child only `ls` and `help` are functional; `add/get/rm/move/gc` print a "implemented in t1030_2/t1030_3" notice via `die`/`warn` (real impls land in siblings). Source `lib/terminal_compat.sh`, `lib/yaml_utils.sh`, `lib/task_utils.sh`, `lib/attachment_utils.sh`.
- **`.aitask-scripts/lib/attachment_utils.sh`** (NEW): portable helpers —
  - `attachment_sha256 <file>` → prints `sha256:<64hex>`. Portability: prefer `openssl dgst -sha256` then fall back to `sha256sum` / `shasum -a 256` (see `aidocs/framework/shell_conventions.md` + `sed_macos_issues.md`). Encapsulate the CLI choice in one helper.
  - `attachment_shard_path <hash>` → `<first2hex>/<remaining62hex>` (strip the `sha256:` prefix first; validate 64 hex chars, else `die`).
  - `attachment_cache_path <hash>` → `${XDG_CACHE_HOME:-$HOME/.cache}/ait/attachments/<hash>`.
  - `attachment_validate_hash <hash>` → exit 0 if `sha256:<64hex>`.
- **`.aitask-scripts/lib/yaml_utils.sh`**: add `read_yaml_mappings <file> <field>` — parse a block-style list-of-mappings (the `attachments:` field) and emit one record per attachment in a stable, parseable form (recommended: one line per attachment of `key=val;key=val;…`, or emit per-field lines grouped by index). Must handle: missing field (emit nothing, exit 0), the exact schema in design §3 (`hash`, `name`, `mime`, `size`, `added_at`, `backend`, `url`), and `url: null`. Keep `read_yaml_field`/`read_yaml_list` untouched. NOTE: writing/appending a mapping is t1030_2's concern — this child only READS.
- **`tests/test_attach_scaffold.sh`** (NEW): unit tests.

## Reference Files for Patterns
- `.aitask-scripts/aitask_projects.sh` `main()` (~lines 939–989) — verb dispatcher + `show_help`.
- `.aitask-scripts/lib/yaml_utils.sh` `read_yaml_list()` (~lines 92–141) — block/inline list parsing to extend from.
- `.aitask-scripts/lib/terminal_compat.sh` — `die/warn/info/success`.
- `tests/test_claim_id.sh`, `tests/lib/test_scaffold.sh` (`setup_fake_aitask_repo`, ~lines 13–30), `tests/lib/asserts.sh` (`assert_eq`/`assert_contains`/`assert_exit_zero`, maintain `PASS/FAIL/TOTAL`).
- `aidocs/framework/shell_conventions.md` (shebang, `set -euo pipefail`, source-on-startup ↔ test-scaffold rule, platform CLI encapsulation) and `aidocs/framework/aitasks_extension_points.md` (adding a new helper script + dispatcher arm).

## Implementation Plan
1. Add the `attach)` arm to `ait`.
2. Write `lib/attachment_utils.sh` (hash, shard, cache, validate helpers) with `set -euo pipefail` and the source-on-startup guard convention.
3. Extend `lib/yaml_utils.sh` with `read_yaml_mappings`.
4. Write `aitask_attach.sh`: `main()` verb dispatch; `cmd_list` (= `ls`) resolves the task file (via `task_utils`/`aitask_query_files.sh resolve`), reads `attachments:` via `read_yaml_mappings`, prints a table (name, hash short, size, backend); empty → "No attachments." Stub the storage verbs.
5. Write `tests/test_attach_scaffold.sh`: sha256 known-vector (`echo -n "" | sha256` → `e3b0c442...`), shard-path split, hash validation reject cases, `read_yaml_mappings` on a fixture task with 0/1/2 attachments, and `ait attach ls` end-to-end on a fixture.

## Verification Steps
- `shellcheck .aitask-scripts/aitask_attach.sh .aitask-scripts/lib/attachment_utils.sh` (and yaml_utils.sh) — clean.
- `bash tests/test_attach_scaffold.sh` — all PASS.
- Manual: create a fixture task with an `attachments:` block (design §3) and run `ait attach ls <task>` — prints the entries; storage verbs print the not-yet-implemented notice.

## Notes for sibling tasks
- The `read_yaml_mappings` output contract and `attachment_utils.sh` helper signatures established here are consumed by t1030_2 (add/get/rm) and t1030_3 (gc/archive). Keep them stable; document the output format at the top of `read_yaml_mappings`.
- `attachment_validate_hash` + shard path are the canonical hash-handling units — reuse them everywhere; do not re-derive shard logic inline.
