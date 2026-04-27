---
Task: t658_full_audit_of_bash_script_for_macos_compatibility.md
Base branch: main
plan_verified: []
---

# t658 — Full audit of bash scripts for macOS compatibility

## Context

`aidocs/sed_macos_issues.md` records that targeted macOS-portability sweeps were last done in tasks **t186, t209, t211, t213**. Since then ~76 production scripts in `.aitask-scripts/` and ~98 bash tests in `tests/` have continued to evolve. The host running this task is macOS arm64 (Darwin 24.6, bash 5.3 from brew, GNU coreutils available as `gdate`, etc.) — the user explicitly asked for the audit to be run on macOS so the test suite can flag regressions that Linux CI would miss. Goal: confirm every shell script obeys the BSD-portable rules in `CLAUDE.md` / `aidocs/sed_macos_issues.md`, run the full bash test suite on this Mac, fix anything that fails for macOS-portability reasons, and append the new findings to the audit log.

## Findings from Pre-Plan Static Sweep

A repo-wide grep against the known macOS-portability footguns turned up a small, well-contained fix list (full triage in Phase B):

| Footgun | Sites | Status |
|---|---|---|
| `#!/bin/bash` shebangs | 0 (188/188 .sh files use `#!/usr/bin/env bash`; the few `#!/bin/bash` strings in tests are inside heredoc fixtures) | ✓ clean |
| `sed -i` without `''` | 3 unguarded calls in `tests/test_archive_no_overbroad_add.sh` (lines 148, 257, 364) — fail on BSD sed. 2 calls in `tests/test_fold_mark.sh:233` and `tests/test_fold_file_refs_union.sh:193` already have a `\|\| sed -i.bak` fallback (works but inconsistent with rest of repo) | **fix needed** |
| `grep -P` / `-oP` / `\K` / lookaround | 0 production occurrences | ✓ clean |
| Plain `date -d` in production scripts | 5 sites in `aitask_verified_update.sh`, `aitask_plan_verified.sh` (×2 helpers), `aitask_explain_context.sh` — all already wrapped in `if date --version` / `if date -d "1 hour ago"` GNU-detection branches with BSD `date -j` / `date -v` fallbacks | ✓ functional but **inconsistent** with the `portable_date()` helper in `lib/terminal_compat.sh` |
| `mktemp --suffix=` | 0 occurrences | ✓ clean |
| `base64 -d` / `--decode` | 1 site in `lib/repo_fetch.sh:36` — already inside the `_rf_base64_decode()` portable wrapper | ✓ clean |
| `sed \U` / `\L` / `/pattern/a` / grouped `{ ... ; N ; ... }` | 0 occurrences | ✓ clean |
| `wc -l` flowing into string compares | Production scripts use `wc -l` in arithmetic contexts (`-gt`, `$((...))`) which are macOS-safe; existing trims (`\| tr -d ' '`, `\| xargs`) are present where strings are needed. To verify per-site in Phase B. | review |

The repo is in good shape — earlier sweeps caught most issues. The audit's main payload is therefore the **dynamic** half: running every bash test on macOS to surface anything the static rules don't catch.

## Plan

### Phase A — Establish the macOS test baseline

A1. Build a tiny driver `tests/run_all_bash_tests.sh` (one-shot, **not** committed — kept under `/tmp` for the duration of the task) that:
- Iterates every `tests/test_*.sh` in lexicographic order.
- Runs each under `bash <file>` with a per-test timeout (e.g. 120s) and captures stdout+stderr to `/tmp/t658_baseline/<basename>.log`.
- Records `PASS|FAIL|TIMEOUT|SKIP` plus wall time into a TSV `/tmp/t658_baseline/summary.tsv`.
- Continues on failure (no `set -e` propagation).
- Refuses to run if `pwd` is not a clean worktree (the tests cd into temp dirs but a few inspect `aitasks/` directly, so the suite must start from main).

A2. Run `bash tests/run_all_python_tests.sh` separately (out of scope but a quick sanity check that the Python harness is healthy too).

A3. Snapshot the baseline:
- Total: pass / fail / timeout counts.
- For each FAIL, classify into:
  - **(a) macOS-portability bug** — fix in Phase C.
  - **(b) preexisting / environmental** (network, missing tool, race, expects Linux-only path) — log in plan, do not fix as part of this audit.
  - **(c) flaky** — re-run once; if still flaky, log and skip.

### Phase B — Static audit (confirm Phase 0 sweep, deep-dive `wc -l`)

B1. Re-run the eight static greps from the pre-plan sweep, in plan-mode read-only form, against the current tree. (Helps catch anything added between sweep time and implementation start.)

B2. **Deep-dive on `wc -l`**: walk every site listed in the table above and confirm the destination context is arithmetic (`[[ ... -gt ... ]]`, `(( ... ))`, `$((...))`) or already trimmed. Any site that does `[[ "$count" == "<number>" ]]` or `assert_eq "<number>" "$count"` is a real bug. Track in a fix list.

B3. Spot-check the five "guarded `date -d`" sites for correctness: each must return the same epoch on both macOS and Linux for representative inputs (`2026-04-27`, `1 hour ago`, `48 hours ago`). The cleanup to `portable_date()` in B4 is contingent on this matching.

B4. **Optional consistency cleanup** (only if Phase C is otherwise small): replace the five hand-rolled `date --version` branches with calls to `portable_date()` from `lib/terminal_compat.sh`. This is **not** a bug fix — flag in commit message as `refactor:` if applied. If Phase C grows, defer this to a follow-up task.

### Phase C — Fix

C1. **Fix the three unguarded `sed -i` calls** in `tests/test_archive_no_overbroad_add.sh`. Replacement strategy: source `lib/terminal_compat.sh` near the top (pattern already used in many tests) and switch to `sed_inplace`. Verify by re-running the test on macOS — must pass. (The two already-guarded `sed -i ... \|\| sed -i.bak` patterns in `test_fold_mark.sh` / `test_fold_file_refs_union.sh` are working correctly; convert them to `sed_inplace` only as a B4-style consistency cleanup, not as a bugfix.)

C2. **Fix any (a)-category test failures from Phase A.** Each fix must be minimal, scoped to the specific portability gap (BSD tool, bash 3.2 vs 5.x, etc.), and verified by re-running the affected test on macOS.

C3. Fix any real `wc -l` string-compare bugs identified in B2 (probably none, but listed for completeness).

### Phase D — Re-run tests

D1. Re-run the bash test driver from A1. Required outcome: zero NEW failures vs. baseline; all (a)-category failures from baseline now pass.

D2. Diff `/tmp/t658_baseline/summary.tsv` vs the post-fix run. Embed a compact PASS/FAIL delta into the plan's Final Implementation Notes.

### Phase E — Update audit log

E1. Append a `## Files Fixed in t658` section to `aidocs/sed_macos_issues.md` with one row per fix (file, line, issue, fix). Mirrors the format of t186/t209/t211/t213 sections.

E2. If Phase B4 was executed, add a subsection under E1 (or a separate `## Refactors in t658`) noting the `portable_date()` consolidation.

### Phase 9 — Post-implementation

Follow Step 9 of `task-workflow/SKILL.md`: commit (single feature commit per fix is overkill — bundle as one `chore: macOS-compat audit (t658)` plus a separate `ait:` commit for the plan file), no worktree to clean (profile said current branch), then `aitask_archive.sh 658`.

## Critical Files

- `tests/test_archive_no_overbroad_add.sh` — three unguarded `sed -i` calls.
- `aidocs/sed_macos_issues.md` — append new findings section.
- (conditional, B4) `.aitask-scripts/aitask_verified_update.sh`, `.aitask-scripts/aitask_plan_verified.sh`, `.aitask-scripts/aitask_explain_context.sh` — `date -d` consolidation onto `portable_date()`.
- (conditional, C2) any test files surfaced by the Phase A baseline run.

## Functions / Helpers to Reuse

- `sed_inplace` — `lib/terminal_compat.sh:84`; portable `sed -i` shim.
- `portable_date` — `lib/terminal_compat.sh:91`; portable `date -d` shim (auto-routes to `gdate` on macOS).
- `_rf_base64_decode` — `lib/repo_fetch.sh:33`; portable `base64 -d`.

## Verification

End-to-end:

```bash
# Baseline (before any fix)
mkdir -p /tmp/t658_baseline
bash /tmp/t658_runner.sh > /tmp/t658_baseline/summary.tsv

# Post-fix
mkdir -p /tmp/t658_postfix
bash /tmp/t658_runner.sh > /tmp/t658_postfix/summary.tsv

# Delta
diff <(awk '{print $1, $2}' /tmp/t658_baseline/summary.tsv) \
     <(awk '{print $1, $2}' /tmp/t658_postfix/summary.tsv)
```

Pass criterion: post-fix has ≥ baseline PASS count, no regressions, every (a)-category failure now PASSes.

Spot-check the three `sed -i` fixes individually:

```bash
bash tests/test_archive_no_overbroad_add.sh
```

Must print `All tests passed` (or equivalent) on macOS.
