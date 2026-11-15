---
Task: t2308_fix_cd_guard_lint_and_brainstorm_list_help.md
Base branch: main
Output branch: main
---

# t2308 — Fix the cd-guard lint violation and `ait brainstorm list --help`

## Context

Two small defects found during t2305:

1. `tests/test_cd_guard_lint.sh` fails 1/92 on the live tree because
   `tests/test_issue_update_ledger.sh:231` (`run_bg()`) has
   `( cd "$REPO" && … ; echo "$?" > rc ) &`. The `&&` chain continues past `;`,
   so `tests/lib/cd_guard_scan.py` classifies it `unconfined-andchain`.
2. `ait brainstorm list --help` runs `aitask_brainstorm_status.sh --list --help`,
   whose `--help` branch always prints `status`'s usage
   (`Usage: ait brainstorm status <task_num>`), not help for `list`.

## Implementation

### 1. `tests/test_issue_update_ledger.sh` — `run_bg()` (≈line 229)

Replace the `&&`-chained subshell with the scanner's accepted **guarded** form
(`cd "$X" || exit 1` followed by a real terminator), keeping the rc capture:

```bash
run_bg() {  # <tag> <args…>
    local tag="$1"; shift
    (
        cd "$REPO" || exit 1
        PATH="$IFX_BIN:$PATH" STUB_LOG="$TMP/par.log" "$IFX_UPDATE" "$@" \
            > "$TMP/par_$tag.out" 2> "$TMP/par_$tag.err"
        echo "$?" > "$TMP/par_$tag.rc"
    ) &
}
```

A failed `cd` leaves no `.rc` file; the existing per-writer check
(`cat "$TMP/par_$n.rc"` == 0) then fails, so the failure stays loud.

### 2. `.aitask-scripts/aitask_brainstorm_status.sh` — list-specific help

- Add `show_list_help()`:
  ```
  Usage: ait brainstorm list

  List all brainstorm sessions (task number, status, ...).

  Equivalent to: ait brainstorm status --list

  Example:
    ait brainstorm list
  ```
- Before the parse loop, pre-scan the args for `--list` (order-independent, so
  `status --help --list` and `list --help` both answer for list mode):
  ```bash
  WANTS_LIST=false
  for _a in "$@"; do [[ "$_a" == "--list" ]] && WANTS_LIST=true; done
  ```
- In the `--help|-h)` branch: `if $WANTS_LIST; then show_list_help; else show_help; fi; exit 0`.
- `status --help` (no `--list`) is unchanged.

No dispatcher (`ait`) change is needed: `list` already execs the status script
with `--list` first.

### 3. Test — new `tests/test_brainstorm_list_help.sh`

Self-contained, same scaffold as `tests/test_brainstorm_apply_help.sh`
(`scratch_cwd.sh` + `enter_scratch_cwd`, `asserts.sh`, top-level assertions,
`run` capture helper). Cases:
- `ait brainstorm list --help` and `-h`: exit 0, contains
  `Usage: ait brainstorm list`, does **not** contain
  `Usage: ait brainstorm status <task_num>`.
- `aitask_brainstorm_status.sh --help --list` (flag order reversed): list usage.
- Control: `ait brainstorm status --help` still shows
  `Usage: ait brainstorm status <task_num>` (proves the new branch is selective,
  not a global swap).

## Verification

- `bash tests/test_cd_guard_lint.sh` → 92/92 pass.
- `bash tests/test_issue_update_ledger.sh` → all pass (parallel-writer block intact).
- `bash tests/test_brainstorm_list_help.sh` → all pass; pre-fix (mentally /
  against the old script) the `list --help` "does not contain status usage"
  assertion fails.
- `bash tests/test_brainstorm_cli.sh` → still passes (status/list behaviour).
- `shellcheck .aitask-scripts/aitask_brainstorm_status.sh tests/test_brainstorm_list_help.sh tests/test_issue_update_ledger.sh`.
- Docs: `website/content/docs/tuis/brainstorm/reference.md:203` already says every
  subcommand accepts `--help`; after the fix that is true for `list` too — no doc edit.

## Step 9 (Post-Implementation)

Commit code + test (`bug: … (t2308)`), then archive per the shared workflow Step 9.

## Risk

### Code-health risk: low
None identified.

### Goal-achievement risk: low
None identified.

## Final Implementation Notes
- **Actual work done:** As planned. `run_bg()` in `tests/test_issue_update_ledger.sh` now uses the scanner-accepted guarded form (`cd "$REPO" || exit 1` in a multi-line subshell). `aitask_brainstorm_status.sh` gained `show_list_help()` and a pre-scan for `--list`, so `--help`/`-h` answers for list mode in any flag order. New `tests/test_brainstorm_list_help.sh` (13 assertions: `list --help`/`-h`, reversed `--help --list`, `status --help`/`-h` control).
- **Deviations from plan:** None. The new test's `run` helper discards stderr (no assertion reads it), which avoids an SC2034 unused-variable warning.
- **Issues encountered:** None. Pre-fix control: running the HEAD version of the status script with `--list --help` printed `Usage: ait brainstorm status <task_num>`, so the new "does not show status usage" assertions would have failed before the fix.
- **Key decisions:** Fixed `list --help` in the status script rather than the `ait` dispatcher, so `ait brainstorm status --list --help` gets the same answer. A failed `cd` in `run_bg` writes no `.rc` file, so the existing per-writer rc check still fails loudly.
- **Verification:** `test_cd_guard_lint.sh` 92/92, `test_issue_update_ledger.sh` 141/141, `test_brainstorm_list_help.sh` 13/13, `test_brainstorm_cli.sh` 38/38, `test_brainstorm_apply_help.sh` 136/136; shellcheck clean at warning level on the new test (pre-existing SC2034 `U11` in `test_issue_update_ledger.sh:438` is unrelated).
- **Upstream defects identified:** None
