---
Task: t583_1_verification_parser_python_helper.md
Parent Task: aitasks/t583_manual_verification_module_for_task_workflow.md
Sibling Tasks: aitasks/t583/t583_2_*.md through aitasks/t583/t583_9_*.md
Archived Sibling Plans: (none yet — t583_1 is the first child)
Worktree: (current branch)
Branch: (current branch)
Base branch: main
plan_verified:
  - claudecode/opus4_7_1m @ 2026-04-19 09:55
---

# Plan: t583_1 — Verification Parser (Python Helper)

## Context

First child of t583 (manual-verification module for `/aitask-pick`). Foundational state primitive — all subsequent children (t583_2…t583_9) depend on the parser subcommands this task exposes.

This plan was re-verified against the current codebase. Existing patterns (`aitask_stats.py`, `aitask_codemap.sh`/`.py`, `terminal_compat.sh`) are confirmed present and match the plan's approach. One clarification added: the checklist **format** the parser targets is `- [ ]` markdown checkboxes, NOT the numbered prose found in `aitasks/t571/t571_7_*.md`. The `seed` subcommand bridges that gap by generating checkboxes from a plain items file.

## Files to create / modify

**New:**
- `.aitask-scripts/aitask_verification_parse.py` — main logic (all 5 subcommands).
- `.aitask-scripts/aitask_verification_parse.sh` — one-line dispatcher: `exec python3 "$SCRIPT_DIR/aitask_verification_parse.py" "$@"` (with the standard shebang + `SCRIPT_DIR` resolution; see below).
- `tests/test_verification_parse.py` — unittest-based automated test suite (picked up by `tests/run_all_python_tests.sh`).

**Modify (whitelist — 5 touchpoints):**
- `.claude/settings.local.json` — append `"Bash(./.aitask-scripts/aitask_verification_parse.sh:*)"` at end of the `aitask_*.sh` run (insertion-ordered).
- `.gemini/policies/aitasks-whitelist.toml` — append a `[[rule]]` block mirroring the neighbors (insertion-ordered).
- `seed/claude_settings.local.json` — insert **alphabetically** between `aitask_verified_update.sh` and `aitask_web_merge.sh`.
- `seed/geminicli_policies/aitasks-whitelist.toml` — append at end of `aitask_*.sh` run (insertion-ordered).
- `seed/opencode_config.seed.json` — insert **alphabetically** between `aitask_verified_update.sh` and `aitask_web_merge.sh`.

**Codex:** skip (no `.codex/` shell-script whitelist exists; only destructive-command sandbox rules).

## Parser spec (verified unchanged from task file)

### CLI subcommands (argparse subparsers)

- **`parse <task_file>`** — emit `ITEM:<index>:<state>:<line_number>:<text>` per item (1-indexed). `<state>` ∈ `pending|pass|fail|skip|defer` where:
  - `- [ ]` → `pending`
  - `- [x]` → `pass`
  - `- [fail]` → `fail`
  - `- [skip]` → `skip`
  - `- [defer]` → `defer`
- **`set <task_file> <index> <state> [--note <text>]`** — mutate body in place. Flip checkbox to the requested state, then append ` — <STATE_UPPER> YYYY-MM-DD HH:MM[ <note>]` suffix after the item text. Refresh frontmatter `updated_at`. Atomic write via temp file + `os.replace()`.
- **`summary <task_file>`** — one line: `TOTAL:N PENDING:A PASS:B FAIL:C SKIP:D DEFER:E`.
- **`terminal_only <task_file>`** — exit 0 if all items are terminal (`pass|fail|skip`). Otherwise exit 2 with `PENDING:<count>` and/or `DEFERRED:<count>` lines on stdout.
- **`seed <task_file> --items <file>`** — insert a `## Verification Checklist` H2 section at end of body with one `- [ ]` entry per non-blank line in the items file. Error with non-zero exit if such a section already exists.

### Parser rules

- **Section locator regex (case-insensitive, full-line):** `^## (verification( checklist)?|checklist)\s*$`.
- **Scan range:** from the matched H2 until the next H2 (any `^## `) or EOF.
- **Item regex:** `^[ \t]*- \[([ x]|fail|skip|defer)\]\s+(.*)$`. Capture group 1 = state marker, group 2 = item text (including any ` — …` suffix).
- **Suffix parsing:** split the item text on the literal ` — ` (em dash surrounded by spaces); everything after the first occurrence is the state annotation. When re-writing a `set`, strip any existing ` — …` suffix before appending the new one (prevents accumulation across successive `set` calls).

### Frontmatter handling

- Read `---` delimited YAML header via simple line-based parsing (no PyYAML dependency).
- Update only the `updated_at` field. If absent, insert it before the closing `---`. Format: `YYYY-MM-DD HH:MM` (local time — matches existing convention in task files).
- Preserve all other frontmatter fields, comments, and blank lines verbatim.

### Bash wrapper

One-file dispatcher:

```bash
#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec python3 "$SCRIPT_DIR/aitask_verification_parse.py" "$@"
```

No `terminal_compat.sh` helpers are needed — the wrapper is pure dispatch; all error handling lives in the Python script. `chmod +x` both files.

## Reference infrastructure (verified)

- **Python helper pattern:** `.aitask-scripts/aitask_stats.py:1-50` — shebang, stdlib imports, `sys.path.insert(...)` for `./lib` (not needed here since parser is self-contained), constants, `main()` with argparse. Follow this general skeleton.
- **Bash-wrapper + Python pattern:** `.aitask-scripts/aitask_codemap.sh` + `aitask_codemap.py` — note `codemap.sh` is heavier than our wrapper (it pre-parses args and sources libs), but the general `SCRIPT_DIR` + `python3` pattern transfers.
- **`terminal_compat.sh` helpers** (`.aitask-scripts/lib/terminal_compat.sh`): `die`, `warn`, `info`, `sed_inplace`, `portable_date` — available if any bash-side work is added later, but **not needed for the current one-liner wrapper**.

## Implementation order

1. **Write `aitask_verification_parse.py`** with `argparse` subparsers: `parse`, `set`, `summary`, `terminal_only`, `seed`. Share a `_read_task_file(path) -> (frontmatter_lines, body_lines)` helper and an `_iter_checklist_items(body_lines) -> list[(index, state, line_no, text)]` helper. Structure top-level functions (one per subcommand) so the test module can call them directly after importlib-loading the module (mirroring `tests/test_aitask_stats_py.py`).
2. **Write `aitask_verification_parse.sh`** — the one-liner dispatcher above.
3. **`chmod +x`** both files.
4. **Write `tests/test_verification_parse.py`** covering the 7 `TestCase` classes listed under "Automated tests" below. Run `bash tests/run_all_python_tests.sh tests/test_verification_parse.py` and confirm all tests pass before touching whitelists.
5. **Manual smoke test** with a synthetic task file:
   - Create `/tmp/t_syn.md` containing frontmatter with `updated_at: 2020-01-01 00:00` and a body with `## Verification Checklist` plus 5 items covering each state: `- [ ]`, `- [x]`, `- [fail] … — FAIL 2026-04-19 08:00 reason`, `- [skip] …`, `- [defer] …`.
   - Run `parse /tmp/t_syn.md` → expect 5 `ITEM:` lines with correct states.
   - Run `summary /tmp/t_syn.md` → expect `TOTAL:5 PENDING:1 PASS:1 FAIL:1 SKIP:1 DEFER:1`.
   - Run `terminal_only /tmp/t_syn.md` → expect exit 2 with `PENDING:1` and `DEFERRED:1`.
   - Run `set /tmp/t_syn.md 1 pass --note "ok"` → verify `- [x]` + ` — PASS YYYY-MM-DD HH:MM ok` appended, `updated_at` bumped.
   - Run `parse` again; confirm round-trip (no drift in other items).
   - Run `seed /tmp/t_fresh.md --items /tmp/items.txt` on a task file *without* a checklist section → confirm `## Verification Checklist` appended with one `- [ ]` per items line.
6. **Update all 5 whitelist touchpoints** per the file-specific guidance above (alphabetical for `seed/claude_settings.local.json` and `seed/opencode_config.seed.json`, append-at-end for the other three).
7. **Single-commit** strategy: commit the parser, wrapper, test file, and all 5 whitelist files together with message `feature: Add verification parser (t583_1)`.

## Edge cases to handle

- **No `## Verification Checklist` section:** `parse` and `summary` emit `TOTAL:0` (no error); `terminal_only` exits 0; `set` exits non-zero with a clear error; `seed` proceeds to create the section.
- **Malformed checkbox lines in the section:** skip them silently (do not count them as items). Only lines matching the item regex count.
- **Multiple H2 sections with matching names:** use the **first** match only.
- **Existing `— ` suffix on `set` target:** strip before appending the new one. If the suffix uses a different dash (`–` en-dash, `-` hyphen), do NOT strip — only strip the exact `' — '` literal the spec uses.
- **Frontmatter without closing `---`:** error with a clear message; do not silently corrupt.

## Automated tests (in-scope for t583_1)

`tests/test_verification_parse.py` — unittest `TestCase` classes mirroring the style of `tests/test_aitask_stats_py.py` (importlib-loaded module, synthetic task files under `tempfile.TemporaryDirectory`). Picked up automatically by `tests/run_all_python_tests.sh` (pytest-first, unittest fallback).

**Test classes and the behaviors each must cover:**

1. `TestParseSubcommand`
   - Finds the `## Verification Checklist` H2 case-insensitively (`## checklist`, `## Verification`, `## Verification Checklist`).
   - Emits one `ITEM:<idx>:<state>:<line>:<text>` line per checkbox; 1-indexed.
   - Correctly maps `[ ]`/`[x]`/`[fail]`/`[skip]`/`[defer]` → `pending`/`pass`/`fail`/`skip`/`defer`.
   - Skips malformed checkbox lines silently (doesn't count them or crash).
   - Stops at the next `## ` heading.
   - On a file with no checklist section: emits zero `ITEM:` lines, exit 0.
   - On a file with multiple H2s matching the pattern: uses only the first.

2. `TestSummarySubcommand`
   - Emits exactly one `TOTAL:N PENDING:A PASS:B FAIL:C SKIP:D DEFER:E` line with counts matching a hand-built fixture.
   - `TOTAL:0` when no checklist section exists.

3. `TestTerminalOnlySubcommand`
   - Exit 0 when all items are `pass`/`fail`/`skip`.
   - Exit 2 with `PENDING:<n>` on stdout when any `pending` exists.
   - Exit 2 with `DEFERRED:<n>` when any `defer` exists.
   - Exit 2 with both lines when both kinds exist.
   - Exit 0 on an empty-checklist file (no items = vacuously terminal).

4. `TestSetSubcommand`
   - Flips checkbox from `[ ]` to `[x]` for `pass`, `[fail]` for `fail`, etc.
   - Appends ` — PASS YYYY-MM-DD HH:MM` suffix (timestamp format verified via regex).
   - With `--note "reason"`: appends ` — PASS YYYY-MM-DD HH:MM reason`.
   - On a second `set` against the same item: strips the prior ` — …` suffix before appending the new one (no duplication).
   - Only strips the exact ` — ` literal — an item whose text contains a hyphen (` - `) or en-dash (` – `) is preserved untouched.
   - Refreshes frontmatter `updated_at` to a current-time value (assert post-write value differs from pre-write).
   - Preserves all other frontmatter fields and ordering byte-for-byte.
   - Writes atomically: asserts the file exists and is complete even if `os.replace` is simulated (covered by a functional post-condition: final file parses cleanly).
   - Invalid index → exits non-zero; file content unchanged.
   - No checklist section → exits non-zero; file content unchanged.

5. `TestSeedSubcommand`
   - Appends `## Verification Checklist` H2 + one `- [ ]` per non-blank line of the items file.
   - Blank lines in the items file are skipped.
   - If the section already exists → exits non-zero; file content unchanged.
   - Newline handling: ends the file with exactly one trailing `\n` (no extra blank lines).

6. `TestRoundTrip`
   - End-to-end: `seed` → `parse` → `set` (for each of the 4 terminal states + `defer`) → `parse` → `summary` → `terminal_only`. Assert each step matches expected output without drift.

7. `TestFrontmatterEdgeCases`
   - Frontmatter without closing `---` → exits non-zero with a clear error.
   - Frontmatter without `updated_at` → `set` inserts the field before the closing `---`.
   - Body with leading/trailing whitespace preserved.

**Runner:** tests are run via `bash tests/run_all_python_tests.sh` (pytest-first) or individually via `python3 -m unittest tests.test_verification_parse`.

## Manual smoke validation

1. Run the synthetic-file smoke tests above (steps 4.a–4.g).
2. Run `./.aitask-scripts/aitask_verification_parse.sh parse <file>` on one of the t583_* task files (they use `- [ ]` format per their bodies) and confirm the output lines parse cleanly.
3. Confirm the 5 whitelist entries are inserted correctly by visual inspection (diff the 5 files).
4. Confirm both new files are executable (`ls -l .aitask-scripts/aitask_verification_parse.*`).
5. Run `bash tests/run_all_python_tests.sh tests/test_verification_parse.py` → all tests pass.

**Relationship to t583_6:** that task's scope shrinks from "unit tests for the parser + manual-verification plumbing" to just "`issue_type: manual_verification` plumbing + integration tests at the workflow level". The parser-level unit tests now live with the parser. Add a note to t583_6 (during its own implementation, not here) that parser tests are covered by `test_verification_parse.py`.

## Step 9 reminder

Follow `.claude/skills/task-workflow/SKILL.md` Step 9 for post-implementation merge/archival. Commit format: `feature: Add verification parser (t583_1)`. Plan file commits use `ait:` prefix.

## Final Implementation Notes

- **Actual work done:** Created `.aitask-scripts/aitask_verification_parse.py` with all 5 subcommands (`parse`, `set`, `summary`, `terminal_only`, `seed`) using `argparse` subparsers and top-level `cmd_*` functions that can be called directly from tests. Wrote the one-line bash wrapper `aitask_verification_parse.sh`. Added 31 automated unittest cases in `tests/test_verification_parse.py` covering all subcommands, round-trip, edge cases, and frontmatter handling. Added the new script to all 5 whitelist touchpoints (`.claude/settings.local.json`, `.gemini/policies/aitasks-whitelist.toml`, `seed/claude_settings.local.json`, `seed/geminicli_policies/aitasks-whitelist.toml`, `seed/opencode_config.seed.json`).
- **Deviations from plan:** One correction to the plan's whitelist insertion guidance: alphabetically `verification_parse` < `verified_update`, so the new entry was inserted *before* `verified_update` in the two alphabetically-ordered seed files, not between `verified_update` and `web_merge` as originally written. One test (`test_second_set_strips_prior_suffix`) had a defective assertion (`assertNotIn("first", line)` matched the item's own text "first pending item"); corrected to check the annotation segment only (post-split on ` — `) with neutral note strings `note_alpha`/`note_beta`.
- **Issues encountered:** `bash tests/run_all_python_tests.sh tests/test_verification_parse.py` fails because `run_all_python_tests.sh` passes its args to `unittest discover`, which expects a directory, not a file. Worked around by running `python3 -m unittest tests.test_verification_parse` directly. (Not an issue introduced by this task — pre-existing runner limitation.)
- **Key decisions:** Used the em-dash character everywhere internally as the annotation separator — matches the plan's `' — '` literal and avoids confusion with plain hyphens. Wrote files with `os.replace()` to a sibling temp file for atomicity. Used line-based YAML parsing (no PyYAML) for frontmatter. Kept `cmd_*` functions callable with `argparse.Namespace` so tests can drive them via `main(argv)` rather than subprocess.
- **Notes for sibling tasks:**
  - The parser's CLI output format is stable — downstream siblings (t583_3, t583_4, t583_5) should depend on the `ITEM:<idx>:<state>:<line>:<text>`, `TOTAL:...`, and `PENDING:<n>`/`DEFERRED:<n>` contracts documented here.
  - The `set` command updates frontmatter `updated_at` as a side effect; siblings that mutate the same task file in the same workflow step should be aware that every `set` call refreshes this timestamp.
  - `test_verification_parse.py` already covers the parser layer. **t583_6 should not duplicate parser-level tests** — it should cover only the `issue_type: manual_verification` plumbing + workflow-level integration.
  - `seed` refuses to overwrite an existing `## Verification Checklist` section — callers must handle the "already seeded" case explicitly (exit code != 0, file unchanged).
