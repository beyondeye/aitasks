---
Task: t1030_1_frontmatter_cli_scaffold.md
Parent Task: aitasks/t1030_task_attachments_support.md
Sibling Tasks: aitasks/t1030/t1030_2_local_backend_cache_index.md, aitasks/t1030/t1030_3_archive_gc_fold_rebind.md
Archived Sibling Plans: (none yet — t1030_1 is the first child)
Worktree: (none — profile 'fast' works on the current branch)
Branch: main
Base branch: main
plan_verified:
  - claudecode/opus4_8 @ 2026-06-28 12:55
---

# Plan — t1030_1 Frontmatter + CLI scaffold

## Context

Parent **t1030** adds framework-managed file attachments (screenshots, PDFs,
logs) to aitasks, content-addressed by SHA-256 so a task references a blob by
hash, never by path/URL (design: `aidocs/task_attachments_design.md`). This
first child lands **only the pure, headless, unit-testable primitives** —
YAML list-of-mappings reading, SHA-256 hashing, hash/shard/cache path helpers —
plus a working **read-only** `ait attach ls`. **No blob storage** (that is
t1030_2; archive/gc is t1030_3). The split exists to extract and test the
reusable units in isolation before any storage logic, per the framework's
testability-first decomposition. The helper signatures and the
`read_yaml_mappings` output contract established here are the stable interface
t1030_2 / t1030_3 build on, so they are documented at their definition sites.

## Verification of assumptions (verify path — 2026-06-28)

Confirmed against the current tree before finalizing:
- **No `aitask_attach.sh` / `lib/attachment_utils.sh` exist yet** — clean slate.
- **`ait` dispatcher** is a flat `case "${1:-help}"` (~line 188+) with arms of the
  form `create)       shift; exec "$SCRIPTS_DIR/aitask_create.sh" "$@" ;;`.
- **`lib/yaml_utils.sh`** `read_yaml_list()` lives at lines **95–141** (block/inline
  parse loop to model the new reader on); double-source guard `_AIT_YAML_UTILS_LOADED`.
- **`aitask_projects.sh`** `main()` verb dispatcher at lines **941–987** + `show_help`.
- **`lib/terminal_compat.sh`** provides `die() warn() info() success()` (die exits 1,
  warn→stderr).
- **`resolve_task_file()`** (`lib/task_utils.sh:554`) resolves **both** parent and
  child IDs and echoes the path (or `die`s). **`aitask_query_files.sh resolve`
  rejects child IDs** (`Invalid task number: '1030_1'`), so `cmd_list` MUST use
  `resolve_task_file` from `task_utils.sh`, not the query-files verb.
- **Test scaffold** (`tests/lib/test_scaffold.sh::setup_fake_aitask_repo`) already
  copies `yaml_utils.sh`; `tests/lib/asserts.sh` provides
  `assert_eq`/`assert_contains`/`assert_exit_zero` and maintains PASS/FAIL/TOTAL.
  **`attachment_utils.sh` is NOT in `./ait`'s source-on-startup chain** (only
  `aitask_attach.sh` sources it) → it does **not** need a `test_scaffold.sh` entry.

## Step 1 — Dispatcher arm in `ait`

In the flat `case` (~line 188+), add an arm alphabetically (right after `applink)`):
```bash
attach)       shift; exec "$SCRIPTS_DIR/aitask_attach.sh" "$@" ;;
```
(No change to the update-check skip-list at the top — `attach` does real work and
is fine triggering the normal update check.)

## Step 2 — `lib/attachment_utils.sh` (NEW, pure helpers)

`#!/usr/bin/env bash`, `set -euo pipefail`, double-source guard
(`[[ -n "${_AIT_ATTACHMENT_UTILS_LOADED:-}" ]] && return 0`). All helpers are
pure (no task/repo state):

- `attachment_sha256 <file>` → prints `sha256:<64hex>`. **Encapsulate the CLI
  choice in ONE function**: try `openssl dgst -sha256`, fall back to `sha256sum`,
  then `shasum -a 256`; strip the filename/format noise from each tool's output,
  lowercase, prepend `sha256:`. `die` if no hashing tool is available.
- `attachment_validate_hash <hash>` → exit 0 iff `^sha256:[0-9a-f]{64}$` (BSD-safe
  `grep -qE`); non-zero otherwise (no output — it is a predicate).
- `attachment_shard_path <hash>` → strip `sha256:` prefix, validate via
  `attachment_validate_hash` (else `die`), print `<first2hex>/<remaining62hex>`.
- `attachment_cache_path <hash>` → `${XDG_CACHE_HOME:-$HOME/.cache}/ait/attachments/<hash>`
  (keep the full `sha256:`-prefixed hash as the cache key, per design §5).

## Step 3 — `read_yaml_mappings` in `lib/yaml_utils.sh`

Add `read_yaml_mappings <file> <field>` (additive — leave `read_yaml_field`/
`read_yaml_list`/`join_yaml_flow_lists` untouched). **Read-only** here
(append/remove is t1030_2). Parse a **block-style list of mappings** (the
`attachments:` field, schema in design §3). This child establishes the **stable
parser contract** siblings build on, so the format below is **escaping-free by
construction** and documented at the function top.

- **Block scanning.** Scan frontmatter only when the file opens with `---` (mirror
  `read_yaml_field`'s detection); start collecting after the `<field>:` line. Each
  list item begins at a `  - <key>: <val>` line; subsequent deeper-indented
  `    <key>: <val>` lines belong to the same item. A line that dedents to the
  field level (or another top-level key, or the closing `---`) ends the list.
- **Comments (both forms in design §3 — REQUIRED).**
  - **Full-line comments** (`^[[:space:]]*#…`, e.g. `# backend-specific resolution
    hints…`) and blank lines inside the block are skipped entirely.
  - **Inline trailing comments** (` #…` to end of line — a `#` preceded by
    whitespace, *outside* quotes) are stripped from the scalar value. This is the
    canonical case `backend: local         # one of: local | s3 | …` from the
    schema; without it, `backend` would wrongly parse as `local … # one of …`.
  - A `#` **not** preceded by whitespace, or one **inside** a quoted value, is
    literal (e.g. a filename `bug #3.png` must survive). After comment-strip,
    trim trailing whitespace from the value.
- **Quoting.** If a value is wrapped in matching `"…"` or `'…'`, strip the quotes
  (so `name: "login screen.png"` → `login screen.png`); a `#` inside quotes is
  literal (no inline-comment strip inside the quoted span). Unquoted values are
  taken verbatim after the inline-comment strip + trim.
- **Output contract — newline-delimited records, NO inline `;`/escaping (documented
  in a comment block at the function top — siblings depend on it):**
  - Emit **one `key=value` line per present field**, in **schema order**
    `hash, name, mime, size, added_at, backend, url`. Only keys present on the
    item are emitted (no synthesized empties).
  - **Attachments are separated by a single blank line.** Consumers accumulate
    `key=value` lines into a record until a blank line, then start the next.
  - **Consumers split each line on the FIRST `=` only** → the key never contains
    `=`; the value may freely contain `=`, `;`, spaces, or any shell-significant
    text with **no escaping**. (This replaces the earlier `key=val;key=val`
    single-line idea, which was ambiguous for names/URLs containing `;` or `=`.)
  - YAML single-line scalars cannot contain a newline, so a value never spans
    lines — the blank-line record separator is unambiguous. (A literal newline in
    a filename is out of scope and documented as unsupported.)
  - Missing field → emit nothing, exit 0. `url: null` is preserved verbatim as
    `url=null`.

## Step 4 — `aitask_attach.sh` (NEW)

Verb dispatcher modeled on `aitask_projects.sh main()`:
- Header: `#!/usr/bin/env bash`, `set -euo pipefail`, `SCRIPT_DIR=…`; source
  `lib/terminal_compat.sh`, `lib/yaml_utils.sh`, `lib/task_utils.sh`,
  `lib/attachment_utils.sh`.
- `main()` `case` on verb: `add ls get rm move gc help` (+ `""|--help|-h`→`show_help`).
- **`cmd_list` (`ls`)** — the one functional verb: take a task id arg, resolve via
  `resolve_task_file <id>` (handles parent + child), run
  `read_yaml_mappings <file> attachments`, accumulate each blank-line-delimited
  record into key/value pairs (split on first `=`), and print an aligned table
  (`name · short-hash(first 12 of hex) · size · backend`). Empty/no field →
  print `No attachments.`
- **Validate each row's `hash` before display (concern #3).** `hash` is required
  by the schema, so for every parsed record call `attachment_validate_hash` on its
  `hash` (absent `hash` ⇒ treat as invalid). On failure, **fail loudly** — `die`
  with a message naming the offending row (e.g. its `name`/index and the bad
  value) — rather than shortening/displaying a malformed hash. The reader stays a
  pure parser (emits what is present); validation is the consumer's job, done here
  with the in-scope helper so bad frontmatter surfaces as a clear error. (Document
  that t1030_2/t1030_3 consumers should likewise validate via the shared helper.)
- **`cmd_add/cmd_get/cmd_remove/cmd_move/cmd_gc`** — stubs:
  `die "ait attach <verb>: implemented in t1030_2 / t1030_3 (storage not yet available)"`.
- **`show_help`** — list the full design §6 surface, marking `add/get/rm/move/gc`
  as "(not yet implemented)".
- `main "$@"` at end.

## Step 5 — Tests `tests/test_attach_scaffold.sh` (NEW)

Use `tests/lib/test_scaffold.sh` + `tests/lib/asserts.sh`; own `PASS/FAIL/TOTAL`
and results summary; `mktemp -d` + `trap 'rm -rf' EXIT`. Source
`attachment_utils.sh` and `yaml_utils.sh` directly from `$PROJECT_DIR/.aitask-scripts/lib`.
Cover:
- **sha256 known vector:** empty input → `sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`.
- **shard split:** a known hash → `<2>/<62>`; assert the first segment is 2 chars.
- **`attachment_validate_hash` reject cases:** bad length, missing `sha256:` prefix,
  uppercase hex → non-zero (via `assert_exit_nonzero`); valid → `assert_exit_zero`.
- **`attachment_cache_path`** respects `XDG_CACHE_HOME` override.
- **`read_yaml_mappings`** on fixtures with **0 / 1 / 2** attachments. The 1/2-item
  fixtures use the **exact design §3 block** so the contract is proven against the
  canonical shape, exercising every edge case the contract promises:
  - **Inline trailing comment** — `backend: local   # one of: …` → record yields
    `backend=local` (comment stripped, no trailing space), **not** the commented
    string (regression guard for concern #2).
  - **Full-line comment** (`# backend-specific resolution hints…`) between fields →
    skipped, does not break record accumulation.
  - **`url: null`** → preserved verbatim as `url=null`.
  - **Value containing `;`/`=`/spaces with NO escaping** — a `name: "report; v=2.png"`
    (quoted) round-trips intact when the consumer splits on first `=` (regression
    guard for concern #1: the old `;`-joined format would have mangled this).
  - **Literal `#` in an unquoted name** — `name: bug#3.png` survives (the `#` is
    not whitespace-preceded, so it is not a comment).
  - Assert: blank-line record separation yields the right record count, and
    first-`=`-split key/value contents per field.
- **`ait attach ls <task>` end-to-end** against a fixture task with an
  `attachments:` block (run the real `aitask_attach.sh` so the dispatcher + table
  path is exercised); the empty case → `No attachments.`; and a **malformed-hash
  row** (e.g. `hash: sha256:nope`) → `ait attach ls` exits non-zero with a clear
  error and does NOT print a row (concern #3 guard).
- **Stub verbs** print the not-yet-implemented notice and exit non-zero.
- **`bash -n`** syntax check on `aitask_attach.sh`, `lib/attachment_utils.sh`,
  `lib/yaml_utils.sh`.

## Verification

- `shellcheck .aitask-scripts/aitask_attach.sh .aitask-scripts/lib/attachment_utils.sh .aitask-scripts/lib/yaml_utils.sh` — clean.
- `bash tests/test_attach_scaffold.sh` — all PASS.
- Manual: create a fixture task with an `attachments:` block (design §3) and run
  `ait attach ls <task>` → prints the entries; `ait attach add/get/rm/move/gc`
  print the not-yet-implemented notice; `ait attach help` lists the full surface.

## Step 9 (Post-Implementation)

Standard cleanup/archival/merge per `task-workflow` Step 9. As the **first child**,
write thorough **Final Implementation Notes** — especially the exact
`read_yaml_mappings` output contract and the `attachment_utils.sh` helper
signatures — they are the primary reference for t1030_2 and t1030_3.

## Risk

### Code-health risk: low
- Touches the widely-sourced `lib/yaml_utils.sh`, but the change is **purely
  additive** (a new `read_yaml_mappings` function; existing readers untouched) and
  guarded by the double-source guard, so regression risk to existing callers is
  negligible · severity: low · → mitigation: covered by the regression-style tests in Step 5
- New surface (`aitask_attach.sh`, `attachment_utils.sh`, one dispatcher arm) is
  isolated and follows established patterns (`aitask_projects.sh` dispatcher,
  `read_yaml_list` parse loop) · severity: low · → mitigation: none needed

### Goal-achievement risk: low
- The block-style list-of-mappings parser (`read_yaml_mappings`) is the one
  non-trivial unit and it sets the **stable contract** siblings build on, so a
  weak format or unhandled edge case would propagate. Addressed in this revision:
  the output format is **escaping-free by construction** (newline-delimited
  `key=value`, split on first `=`, blank-line record separator) and **both** comment
  forms + quoting are handled explicitly · severity: low · → mitigation: fully covered by the design-§3-shaped fixtures in Step 5 (inline comment, full-line comment, `;`/`=`/space-in-value, literal `#`, `url: null`) — no separate task warranted
- `ait attach ls` validates each row's `hash` via the in-scope
  `attachment_validate_hash`, so malformed frontmatter fails loudly instead of
  displaying wrong data · severity: low · → mitigation: malformed-hash test in Step 5
- Scope is well-defined by design §3/§6 with a known SHA-256 test vector and stable
  helper signatures; storage is explicitly out of scope · severity: low · → mitigation: none needed
