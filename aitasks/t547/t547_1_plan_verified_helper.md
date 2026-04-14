---
priority: medium
effort: medium
depends: []
issue_type: feature
status: Implementing
labels: [task_workflow, aitask_pick]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-04-14 16:11
updated_at: 2026-04-14 16:28
---

## Context

Parent task t547 introduces verification tracking in plan file metadata so the task-workflow can skip re-verification when enough fresh verifications already exist. This child delivers the foundational bash helper that the workflow will call.

The parent plan (`aiplans/p547_plan_verify_on_off_in_task_workflow.md`) describes the full architecture. This child implements the `plan_verified` YAML list parsing/writing and the `decide` subcommand that returns a structured decision report — so the skill markdown can stay trivial (parse 8 key/value lines, branch on one DECISION line).

## Key Files to Modify

- **NEW** `.aitask-scripts/aitask_plan_verified.sh` — helper script
- `.aitask-scripts/aitask_plan_externalize.sh` `build_header()` function (~line 248) — add `plan_verified: []` to the emitted header
- **NEW** `tests/test_plan_verified.sh` — helper tests

## Reference Files for Patterns

- `.aitask-scripts/aitask_plan_externalize.sh` — reference for YAML header parsing with `^---$` delimiters and rebuild patterns. Look at `build_header()` for how headers are currently constructed.
- `.aitask-scripts/aitask_query_files.sh` — reference for structured `KEY:value` output that workflow can parse (`PLAN_FILE:<path>`, `NOT_FOUND`, etc.)
- `.aitask-scripts/aitask_scan_profiles.sh` — another example of structured pipe-delimited output
- `aidocs/sed_macos_issues.md` — macOS BSD sed / wc / mktemp portability rules that MUST be followed
- `.aitask-scripts/lib/terminal_compat.sh` — provides `die()`, `warn()`, `info()`, `sed_inplace()` helpers. Source it in the new script.
- `tests/test_plan_externalize.sh` — pattern for testing bash scripts with `assert_eq`/`assert_contains`
- `tests/test_terminal_compat.sh` — similar test pattern

## Implementation Plan

### Step 1: Create the helper script

Create `.aitask-scripts/aitask_plan_verified.sh` with standard header (`#!/usr/bin/env bash`, `set -euo pipefail`, source `terminal_compat.sh`, double-sourcing guard `_AIT_PLAN_VERIFIED_LOADED`).

Implement three subcommands via a case dispatcher:

#### `read <plan_file>`
- Verify the plan file exists (`die` if not)
- Extract the YAML header block (lines between the first two `^---$` lines)
- Find the `plan_verified:` key
- Parse each following list item line (`  - <agent> @ <timestamp>`) until the indentation drops
- Emit one `<agent>|<timestamp>` line per entry to stdout
- If the field is missing, emit nothing and exit 0 (no entries)
- If the field is `plan_verified: []` (inline empty), emit nothing
- Tolerate malformed entries (skip silently; do not crash)

#### `append <plan_file> <agent>`
- Verify the plan file exists
- Generate current timestamp: `date '+%Y-%m-%d %H:%M'`
- If `plan_verified:` key is missing from header: insert `plan_verified:` followed by the new entry immediately before the closing `---` of the header
- If `plan_verified: []` (inline empty): replace with multi-line list containing the new entry
- If `plan_verified:` has existing entries: append the new entry as a new list item after the last entry
- Use `sed_inplace()` from `terminal_compat.sh` for macOS portability
- No stdout output on success; die with a message on failure

#### `decide <plan_file> <required> <stale_after_hours>`
- Verify `required` and `stale_after_hours` are positive integers (`die` if not)
- If plan file does not exist: emit `TOTAL:0`, `FRESH:0`, `STALE:0`, `LAST:NONE`, `REQUIRED:<R>`, `STALE_AFTER_HOURS:<H>`, `DISPLAY:No plan file found.`, `DECISION:VERIFY` and exit 0
- Call `read` internally to get all entries
- Compute the staleness cutoff as a Unix timestamp: `$(date -d "<H> hours ago" +%s)` on Linux; use `date -v-<H>H +%s` on macOS — detect which with `date -d @0 &>/dev/null`
- Parse each entry's timestamp to a Unix timestamp; compare to the cutoff
  - Entries with timestamp >= cutoff are FRESH
  - Entries with timestamp < cutoff are STALE
- Track the most recent entry (LAST)
- Compute:
  - `TOTAL = FRESH + STALE`
  - If `TOTAL == 0`: `DECISION=VERIFY`, DISPLAY=`No prior verifications found — entering verify mode.`
  - Elif `FRESH >= required`: `DECISION=SKIP`, DISPLAY=`Plan has <FRESH> fresh verification(s) (most recent: <LAST>). Skipping verification.`
  - Else: `DECISION=ASK_STALE`, DISPLAY=`Plan has <TOTAL> verification(s) (<FRESH> fresh, <STALE> stale). Required: <required>.`
- Emit all 8 `KEY:value` lines in the order specified in the parent plan

### Step 2: Update `aitask_plan_externalize.sh` `build_header()`

Find the `build_header()` function (around line 248). Add a line emitting `plan_verified: []` after the `Base branch:` line (before the closing `---`). Apply to both parent and child header branches.

### Step 3: Create tests

Create `tests/test_plan_verified.sh` following the `test_plan_externalize.sh` pattern. Use a temp directory (`mktemp -d`). Test cases:

- `read` with plan file missing `plan_verified` field → empty output
- `read` with `plan_verified: []` → empty output
- `read` with multiple entries → correct `agent|timestamp` output per line
- `read` with malformed entry interleaved → malformed skipped, valid entries returned
- `append` into a header with no `plan_verified` field → field inserted with the new entry
- `append` into `plan_verified: []` → list populated with the new entry
- `append` into existing populated list → new entry appended
- `decide` with no plan file → `DECISION:VERIFY`
- `decide` with 0 entries in plan → `DECISION:VERIFY`
- `decide` with 1 fresh entry and required=1 → `DECISION:SKIP`
- `decide` with 1 fresh entry and required=2 → `DECISION:ASK_STALE`
- `decide` with 1 stale entry and required=1 → `DECISION:ASK_STALE` (fresh=0)
- `decide` with 2 fresh entries and required=1 → `DECISION:SKIP`
- `decide` with 1 fresh + 1 stale entry and required=1 → `DECISION:SKIP`
- `decide` with 1 fresh + 1 stale entry and required=2 → `DECISION:ASK_STALE`
- `decide` verifies that the DISPLAY line is emitted and readable

For staleness testing, use fixed timestamps: a FRESH entry 1 hour ago, a STALE entry 48 hours ago, with `stale_after_hours=24`.

### Step 4: Make the script executable

`chmod +x .aitask-scripts/aitask_plan_verified.sh`

## Verification Steps

1. Run tests: `bash tests/test_plan_verified.sh` — all cases must pass
2. Run lint: `shellcheck .aitask-scripts/aitask_plan_verified.sh` — no errors
3. Manually verify `build_header()` update by running `./.aitask-scripts/aitask_plan_externalize.sh <any_ready_task>` on a fresh test task and checking the emitted plan file contains `plan_verified: []`
4. Verify `read` on an existing plan file without `plan_verified` field returns empty output
5. Verify `append` on such a plan file inserts the field correctly
6. Verify `decide` output format matches the schema exactly (8 lines, correct order)

## Notes for sibling tasks

The `decide` subcommand is the API surface that Child 3 (workflow integration) will consume. The KEY:value output format is stable and documented in the parent plan. Child 3 only needs to parse these lines and branch on `DECISION:`.
