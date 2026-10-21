---
Task: t1751_stale_lock_test_bsd_wc_l_padding.md
Base branch: main
Output branch: main
---

# t1751 — Trim BSD `wc -l` padding in exact-string count assertions

## Context

BSD `wc -l` (macOS) left-pads its count (`'       1'`), so an exact
`assert_eq "<desc>" "1" "$(… | wc -l)"` fails on macOS even when the count is
right. `aidocs/framework/sed_macos_issues.md` § "`wc -l` Output Whitespace"
documents the trap. The task names two sites in `tests/test_stale_lock.sh`
and asks for a sweep of the whole `tests/` tree first.

## Sweep result (already run on this macOS box)

Two passes, because a log-only filter misses comparators with their own message
format. (A first pass that ran only `assert_eq` files and filtered on the quoted
`got '…'` form missed `test_workflow_phase_prompt_drift.sh`, which compares with
its own `check` helper and prints values without quotes.)

1. **Runtime:** ran **every** `tests/**/*.sh` containing `wc -l` (79 files; live
   tmux suites excluded because `$TMUX` is set here), whatever comparator it
   uses, and scanned the logs for any fail/expected line with a run of ≥3
   spaces before a number. This catches the unquoted form too.
2. **Static:** for every untrimmed `wc -l` in `tests/` (continuations joined),
   traced each captured variable to its uses and classified them as arithmetic
   (`-eq`/`-gt`/`(( ))`: safe) or string (`assert_eq`, `[[ == ]]`, custom
   helpers). Every string consumer is either already `assert_eq_trim`, already
   trimmed with `tr -d`/`xargs`, symmetric (see below), or in the table below.

Eleven comparisons in 8 files fail **only because of padding**:

| file | line(s) | value source |
|---|---|---|
| `tests/test_stale_lock.sh` | 470, 671 | inline `$(find … \| wc -l)` |
| `tests/test_fold_mark.sh` | 791, 1106 | inline `$(printf … \| wc -l)` |
| `tests/test_parallel_admission_cli.sh` | 153 | `$recalls` (captured at 152) |
| `tests/test_pick_own_scoped_commit.sh` | 558 | `$count4b` (captured at 557) |
| `tests/test_run_project_command.sh` | 457 | `$table_sites` (captured at 456) |
| `tests/test_sync_deferral_and_quarantine.sh` | 569, 813 | `$LINES18B`, `$LEFTOVER30` |
| `tests/test_workflow_phase_prompt_drift.sh` | 83–84 | `$bogus` → local `check` (exact `[[ == ]]`, line 42) |
| `tests/test_revert_analyze_batch.sh` | 224 | `$nul_b` — padded **and** genuinely wrong (`1` not `0`), see below |

Left alone on purpose (they pass on macOS):
- arithmetic uses (`-gt`, `$(( ))`) — safe per the doc;
- `test_goengines_benchci.sh:72` and `test_frozen_reopen_live.sh:201,226,482,499,504`
  — both sides come from untrimmed `wc -l`, and BSD pads to a fixed 8-column
  width, so the pad is the same on both sides;
- `test_skill_parity_runtime_vs_rendered.sh:84` and
  `test_skill_render_task_workflow.sh:888` — arithmetic `-ne` / `-lt`.

## Implementation

**`test_workflow_phase_prompt_drift.sh:83`** — `check` is a file-local exact
comparator and the file does not source `tests/lib/asserts.sh`. Trim the count
where it is captured, the same idiom the file's siblings use
(`| wc -l | tr -d ' '`):

```bash
bogus=$(grep -rF -- "Plan preserved to a file somewhere" "$WORKFLOW_DIR" 2>/dev/null | wc -l | tr -d ' ')
```

(The `hits` capture at line 67 only feeds `-ge`, so it stays as it is.)

**The other 10 sites:** change `assert_eq` → `assert_eq_trim` (existing helper,
`tests/lib/asserts.sh:161`, which `xargs`-trims both sides and every one of these
files already sources). No change to the captured value or the expected value.
Multi-line calls keep their `\` continuation shape. Example:

```bash
assert_eq_trim "no .reap residue is left behind" "0" \
    "$(find "$(dirname "$L")" -maxdepth 1 -name "$(basename "$L").gc.reap.*" | wc -l)"
```

`assert_eq_trim` compares exact strings after trimming, so a genuinely wrong
count still fails — no weakening.

`test_revert_analyze_batch.sh:224` also gets `assert_eq_trim` (so its failure
message is honest), but it will **still fail**: it asserts GNU grep's
binary-stream behaviour (`0` matches across a NUL stream) and macOS grep returns
`1`. That is a separate platform defect → follow-up task (Step 8b), not fixed here.

## Out-of-scope failures seen during the sweep (file follow-ups at Step 8b)

Reproduced serially, unrelated to `wc -l`:
- `test_task_git.sh` 13b/13c/13d/15b and `test_task_worktree_helper.sh` 3/5 —
  `/var/…` vs `/private/var/…` realpath mismatch on macOS.
- `test_cd_guard_lint.sh` — `tests/test_scratchpad_spawn_live.sh` has no
  `enter_scratch_cwd` before its first `cd` (line 218).
- `test_fixture_root.sh` — control "old shape leaks all three" gets `0|0`.
- `test_shadow_phase_advisory.sh` — "all 9 capabilities still dispatched" gets
  `1` (`.claude/skills/aitask-shadow-fast-`) and `2` (codex variant); the count
  is already trimmed, so these are real values.
- `test_revert_analyze_batch.sh` NUL-stream control (above).
(`test_crew_git_noninteractive.sh` failed only under parallel load; passes serially — not filed.)
Check for existing tasks covering each before creating.

## Verification

1. `bash tests/test_stale_lock.sh` → `134/134 passed`, rc 0; same under
   `/bin/bash tests/test_stale_lock.sh` (3.2).
2. Each of the other fixed files: run under both shells; the padded FAILs are
   gone (`test_fold_mark.sh`, `test_parallel_admission_cli.sh`,
   `test_pick_own_scoped_commit.sh`, `test_run_project_command.sh`,
   `test_sync_deferral_and_quarantine.sh`, `test_workflow_phase_prompt_drift.sh`
   green;
   `test_revert_analyze_batch.sh` shows only the NUL-control failure, now
   reported as `got '1'`).
3. Non-weakening probe: temporarily run `assert_eq_trim "x" "1" "       2"` via
   a sourced `tests/lib/asserts.sh` → must report FAIL; and temporarily seed a
   second record before `test_stale_lock.sh:671` → that assertion must fail;
   revert the seed. For the `tr -d` site, temporarily change the fabricated
   anchor to one that exists → "fabricated anchor absent" must fail; revert.
4. Re-run both sweep passes after the fix: the runtime scan must report no padded
   value, and the static scan must list no new string consumer.
5. `shellcheck` on the edited test files (no new warnings).

## Step 9

Commit `bug: Trim BSD wc -l padding in count assertions (t1751)`, then archive
via Step 9 of task-workflow.

## Risk

### Code-health risk: low
None identified.

### Goal-achievement risk: low
None identified.
