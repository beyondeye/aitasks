---
Task: t695_4_refactor_python_callers.md
Parent Task: aitasks/t695_install_python_if_sys_python_old.md
Sibling Tasks: aitasks/t695/t695_5_manual_verification_install_python_if_sys_python_old.md
Archived Sibling Plans: aiplans/archived/p695/p695_*_*.md
Worktree: aiwork/t695_4_refactor_python_callers
Branch: aitask/t695_4_refactor_python_callers
Base branch: main
plan_verified:
  - claudecode/opus4_7_1m @ 2026-04-28 16:13
---

# Plan — t695_4: Refactor direct python3 callers to source the helper

## Context

Fourth implementation child of t695. With the resolver helper from t695_1
in place and the venv + symlink from t695_2/t695_3 working, this child
migrates every `.sh` script that invokes Python to source
`lib/python_resolve.sh` and use the helper's resolution functions
instead of hardcoded `python3` or the ad-hoc `${PYTHON:-python3}`
shorthand.

The parent task explicitly states: *"every place we invoke the system
python in the aitasks framework (in scripts, in ait, EVERYWHERE)"*.
Verification against the current codebase showed the original 9-file
scope was incomplete — 17+ additional `.sh` scripts use the same pattern.
Scope expanded (user-confirmed) to cover all of them.

## Design principles (per user direction)

1. **Single canonical resolution path.** Every framework script ends up
   with the same `$PYTHON` value, resolved by the same code in
   `lib/python_resolve.sh`. No per-script venv-detection ladders.
2. **Version constant defined ONCE.** `AIT_VENV_PYTHON_MIN=3.11` lives
   in exactly one file (`lib/python_resolve.sh`). No `.sh` migrated by
   this task hardcodes "3.11" anywhere. `aitask_setup.sh` sources the
   helper to consume the same constant rather than redefining it.
3. **Two compatibility levels — chosen via function name, not numeric
   argument.** Each migrated script calls one of two functions; neither
   takes a version argument:
   - `require_ait_python` — returns the framework Python (≥
     `AIT_VENV_PYTHON_MIN`) or dies. Used by every TUI launcher and any
     script whose downstream `.py` imports `textual` / `yaml` /
     `linkify_it`.
   - `require_python` — returns any python3 found by the resolver, or
     dies if none. Used by the handful of scripts that legitimately run
     in remote `aitask-pickrem` / `aitask-pickweb` sandboxes where the
     framework venv may not exist.

   The version "3.11" never appears in caller scripts — only the function
   name expresses the requirement.

## Helper changes (Step 0 — prerequisite)

Add to `lib/python_resolve.sh`:

```bash
# Framework minimum Python version. The single source of truth — every
# migrated script picks up this constant by sourcing this file. Override
# via env for testing only.
AIT_VENV_PYTHON_MIN="${AIT_VENV_PYTHON_MIN:-3.11}"

# Preferred canonical entry point. Equivalent to
# require_modern_python "$AIT_VENV_PYTHON_MIN" — defined as a separate
# zero-arg function so callers don't repeat the version literal.
require_ait_python() {
    require_modern_python "$AIT_VENV_PYTHON_MIN"
}
```

Insertion point: between the existing function definitions and the
end-of-file. The existing `resolve_python`, `require_python`, and
`require_modern_python` functions stay (the latter remains internal —
not called by migrated scripts).

Update `aitask_setup.sh` to source `lib/python_resolve.sh` near the top
(after `set -euo pipefail`, before the `AIT_VENV_PYTHON_MIN=` line) and
remove its own duplicate `AIT_VENV_PYTHON_MIN=` definition. The setup
script keeps its bootstrap-specific functions (`find_modern_python`,
`install_modern_python`, `setup_python_venv`) — those are
bootstrap-time and cannot use `require_ait_python` (the venv they're
creating doesn't exist yet). But the constant they compare against now
comes from one place.

## Scope decisions (verified during plan-mode)

- **`aitask_setup.sh` python invocations are NOT migrated.** It is the
  bootstrap that creates the venv `python_resolve.sh` resolves to. Its
  existing python3 calls are pre-venv and stay as `python3` (or its
  internal `find_modern_python` result). Setup only changes to source
  the helper for the version constant (Step 0).
- **`install.sh:263` is pre-setup** and stays as `python3` (system) with
  a clarifying comment.
- **Gemini whitelist literal `python3` in `seed/geminicli_policies/...`**
  needs no change — the t695_3 PATH symlink ensures `python3` resolves
  to the framework interpreter.
- **`.py` shebang guards: skipped.** Verification confirmed every `.py`
  file is wrapped by a `.sh` launcher (no direct `./script.py`
  invocations exist anywhere). The wrapper's `require_ait_python`
  already enforces the version. Adding `import sys; sys.version_info`
  guards to the `.py` files would be redundant.
- **`aidocs/benchmarks/bench_archive_formats.py`: skipped.** Standalone
  manual benchmark utility, not invoked from any `.sh`.

## Files to migrate (26 `.sh` scripts)

Every script below ends up with the same idiomatic block at the top
(after `set -euo pipefail` and `SCRIPT_DIR=`):

```bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/aitask_path.sh
source "$SCRIPT_DIR/lib/aitask_path.sh"
# shellcheck source=lib/python_resolve.sh
source "$SCRIPT_DIR/lib/python_resolve.sh"
# shellcheck source=lib/terminal_compat.sh    # if previously sourced
source "$SCRIPT_DIR/lib/terminal_compat.sh"

PYTHON="$(require_ait_python)"   # OR: PYTHON="$(require_python)" — see column
```

Then every existing `python3` / `${PYTHON:-python3}` invocation in the
script body becomes `"$PYTHON"`. The pre-existing venv-detection blocks
(typically lines 8–32) and the standalone import-check blocks are
DELETED — the helper handles resolution; the venv-vs-system fork no
longer exists at the caller level.

The retained import-check pattern (e.g. `aitask_board.sh:22-24`
`$PYTHON -c "import textual"`) stays — it catches the orthogonal "venv
exists but lacks new deps" case (user updated framework but didn't
re-run setup). Convert to `"$PYTHON" -c ...` form.

### Function-choice column

| File | Function |
| ---- | -------- |
| `.aitask-scripts/aitask_verification_parse.sh` | `require_python` (runs in remote sandboxes) |
| `.aitask-scripts/aitask_explain_context.sh` | `require_python` (stdlib + yaml — see note) |
| `.aitask-scripts/aitask_explain_extract_raw_data.sh` | `require_python` (stdlib only) |
| `.aitask-scripts/aitask_codemap.sh` | `require_python` (stdlib only) |
| `.aitask-scripts/aitask_sync.sh` | best-effort: `resolve_python` (may be empty; auto-merge falls back to git behavior) |
| `.aitask-scripts/aitask_board.sh` | `require_ait_python` |
| `.aitask-scripts/aitask_minimonitor.sh` | `require_ait_python` |
| `.aitask-scripts/aitask_settings.sh` | `require_ait_python` |
| `.aitask-scripts/aitask_crew_status.sh` | `require_ait_python` |
| `.aitask-scripts/aitask_crew_runner.sh` | `require_ait_python` |
| `.aitask-scripts/aitask_brainstorm_archive.sh` | `require_ait_python` |
| `.aitask-scripts/aitask_brainstorm_apply_initializer.sh` | `require_ait_python` |
| `.aitask-scripts/aitask_brainstorm_delete.sh` | `require_ait_python` |
| `.aitask-scripts/aitask_brainstorm_init.sh` | `require_ait_python` |
| `.aitask-scripts/aitask_brainstorm_status.sh` | `require_ait_python` |
| `.aitask-scripts/aitask_brainstorm_tui.sh` | `require_ait_python` |
| `.aitask-scripts/aitask_codebrowser.sh` | `require_ait_python` |
| `.aitask-scripts/aitask_crew_dashboard.sh` | `require_ait_python` |
| `.aitask-scripts/aitask_crew_logview.sh` | `require_ait_python` |
| `.aitask-scripts/aitask_crew_report.sh` | `require_ait_python` |
| `.aitask-scripts/aitask_diffviewer.sh` | `require_ait_python` |
| `.aitask-scripts/aitask_monitor.sh` | `require_ait_python` |
| `.aitask-scripts/aitask_stats.sh` | `require_ait_python` |
| `.aitask-scripts/aitask_stats_tui.sh` | `require_ait_python` |
| `.aitask-scripts/lib/launch_modes_sh.sh` | special: defensive `${_AIT_RESOLVED_PYTHON:-python3}` (sourced before resolution) |

> **Note on `aitask_explain_context.sh`:** Its downstream
> `aitask_explain_format_context.py` imports `yaml`. Per the framework
> rule, anything needing pyyaml needs the venv-Python. **Override:**
> mark this `require_ait_python`, not `require_python`. Updated below.
>
> **Corrected:** `aitask_explain_context.sh` → `require_ait_python`.

(The function-choice column above lists `require_python` for that file
in error — implementation should use `require_ait_python` since the
downstream Python imports yaml.)

## Implementation Steps

### Step 0 — Update `lib/python_resolve.sh`

Add the `AIT_VENV_PYTHON_MIN` constant and the `require_ait_python`
function as described above. No changes to `resolve_python`,
`require_python`, or `require_modern_python` (those remain).

### Step 1 — Update `aitask_setup.sh`

1. Source `lib/python_resolve.sh` near the top (after the existing
   `SCRIPT_DIR=` and `VERSION_FILE=` lines, before
   `AIT_VENV_PYTHON_MIN=` at line 15):
   ```bash
   # shellcheck source=lib/python_resolve.sh
   source "$SCRIPT_DIR/lib/python_resolve.sh"
   ```
2. Delete the duplicate `AIT_VENV_PYTHON_MIN=...` line (currently line 15).
   `AIT_VENV_PYTHON_PREFERRED=` (line 16) stays — that's a separate
   bootstrap-only concern.
3. The setup script's own python3 calls and `find_modern_python` /
   `install_modern_python` / `setup_python_venv` flow stay as-is — they
   are pre-venv bootstrap.
4. Remove the dead `check_python_version()` function and
   `PYTHON_VERSION_OK` global (lines 444-510 inclusive). Confirm via
   `grep -rn 'check_python_version\|PYTHON_VERSION_OK' .` that the only
   remaining matches are in `tests/test_version_checks.sh` (handled in
   Step 4).

### Step 2 — Migrate the 25 caller scripts (Group A + B, excluding `lib/launch_modes_sh.sh`)

Apply the migration template above to each script in the function-choice
table. Per-script special cases:

- **`aitask_verification_parse.sh`** is currently 4 lines total. Final shape:
  ```bash
  #!/usr/bin/env bash
  set -euo pipefail
  SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  # shellcheck source=lib/aitask_path.sh
  source "$SCRIPT_DIR/lib/aitask_path.sh"
  # shellcheck source=lib/python_resolve.sh
  source "$SCRIPT_DIR/lib/python_resolve.sh"
  PYTHON="$(require_python)"
  exec "$PYTHON" "$SCRIPT_DIR/aitask_verification_parse.py" "$@"
  ```

- **`aitask_sync.sh`** uses Python only as a best-effort auto-merge helper
  (sets `_MERGE_PYTHON=""` if no python is found and falls back to git
  behavior). Replace `_init_merge_python()` with:
  ```bash
  _init_merge_python() {
      _MERGE_PYTHON="$(resolve_python)"   # may be empty; that's fine
  }
  ```

- **`aitask_crew_status.sh:15`** has a typo:
  `VENV_PYTHON="$HOME/.aitask/venv/bin"` (missing `/python`). Migration
  removes this variable entirely so the typo disappears.

### Step 3 — Special case: `lib/launch_modes_sh.sh`

This file is sourced by other scripts at top-of-file (often before
`python_resolve.sh` is sourced). Use a defensive lookup:

```bash
_ait_launch_modes_compute_pipe() {
    local dir="${AIT_LAUNCH_MODES_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}"
    local pycmd="${_AIT_RESOLVED_PYTHON:-python3}"
    "$pycmd" -c "
import sys
sys.path.insert(0, '$dir')
from launch_modes import launch_modes_pipe
sys.stdout.write(launch_modes_pipe())
"
}
```

This works in both cases: cached path if available, system `python3` (now
the t695_3 symlink) otherwise.

### Step 4 — Update `tests/test_version_checks.sh`

Tests 2-7 (lines ~59-176) exercise the dead `check_python_version` /
`PYTHON_VERSION_OK`. Delete them. Test 1 (`check_bash_version`) stays.

After deletion: re-number remaining tests if the harness uses test
counters in its summary. Add a one-line top-of-file comment noting that
earlier python-version tests were removed at t695_4. Keep filename.

### Step 5 — `install.sh:263` audit (no behavior change)

Add a clarifying comment above the existing line:

```bash
# NOTE: Pre-setup invocation. Helper at .aitask-scripts/lib/python_resolve.sh
# is not yet usable because no AIT-resolved Python exists. System python3
# only needs pyyaml here, which install.sh ensures via earlier prerequisites.
if python3 "$INSTALL_DIR/.aitask-scripts/aitask_install_merge.py" "$mode" "$src" "$dest" 2>/dev/null; then
```

### Step 6 — Smoke test

Add `tests/test_python_resolution_fallback.sh` that verifies:
1. With `~/.aitask/` mocked away (HOME=/tmp/scratch), `resolve_python`
   returns the system python3 path (whatever PATH lookup yields).
2. `aitask_verification_parse.sh` runs against `/dev/null` without
   crashing in the stripped environment.
3. After sourcing `python_resolve.sh`, `AIT_VENV_PYTHON_MIN` is defined
   (not empty) — guards against the constant accidentally being lost in
   the move.

Style: follow existing test conventions with `assert_eq`/`assert_contains`
helpers used in other `tests/test_*.sh` files.

### Step 7 — Lint

Run `shellcheck` on every modified script. Add the
`# shellcheck source=lib/<helper>.sh` directive comments before each new
`source` statement (already in the migration template).

```bash
shellcheck .aitask-scripts/aitask_*.sh \
           .aitask-scripts/lib/python_resolve.sh \
           .aitask-scripts/lib/launch_modes_sh.sh
```

## Verification

- `grep -rn '\${PYTHON:-' .aitask-scripts/` returns zero results.
- `grep -rn '\b3\.11\b' .aitask-scripts/` returns matches only in
  `lib/python_resolve.sh` (and possibly `aitask_setup.sh:16` for
  `AIT_VENV_PYTHON_PREFERRED`'s default of 3.13 — that's a different
  constant; verify by reading).
- `grep -rn 'check_python_version\|PYTHON_VERSION_OK' .` returns no
  results outside git history.
- `bash tests/test_python_resolution_fallback.sh` passes.
- `bash tests/test_version_checks.sh` passes (Test 1 only).
- `shellcheck` clean on all modified scripts.
- Manual: launch board, brainstorm, settings, codebrowser, monitor,
  stats, diffviewer TUIs after migration — verify they still work
  locally.
- Manual: run `aitask_verification_parse.sh` against a sample task in a
  remote-sandbox-like env (no `~/.aitask/`) — verify graceful behavior
  using system python3.

## Dependencies / Sequencing

t695_1 + t695_2 + t695_3 all merged (confirmed via git log). Helpers
exist; PATH symlink in place. This child can land directly.

## Step 9 — Post-Implementation

Standard archival flow per task-workflow SKILL.md. After this child
commits, the parent t695 can be considered complete pending the
aggregate manual-verification sibling t695_5.

## Notes for sibling tasks (read by t695_5 manual verification)

- The aggregate manual verification sibling tests TUI flows on real
  macOS-3.9 + Debian-11 hosts that automated tests cannot exercise.
- After this child commits:
  - Every Python invocation in the framework — except `aitask_setup.sh`
    pre-venv calls (bootstrap), `install.sh` (pre-setup), and
    `bench_archive_formats.py` (standalone benchmark) — goes through
    `lib/python_resolve.sh`.
  - The version "3.11" appears exactly once: in
    `lib/python_resolve.sh:AIT_VENV_PYTHON_MIN`. Caller scripts pick the
    requirement level by function name (`require_ait_python` vs
    `require_python`), not by repeating the literal.
  - The `${PYTHON:-python3}` shorthand should now appear in zero
    `.aitask-scripts/*.sh` files. Future PRs reintroducing it should be
    flagged in review.

## Final Implementation Notes

- **Actual work done:** Migrated 25 caller scripts plus `lib/launch_modes_sh.sh` to source `lib/python_resolve.sh` and use `require_ait_python` (TUIs / venv-deps) or `require_python` (stdlib-only). Added `AIT_VENV_PYTHON_MIN=3.11` constant + `require_ait_python()` helper to `lib/python_resolve.sh`. Updated `aitask_setup.sh` to consume the constant from the helper (single source of truth) and removed dead `check_python_version()` + `PYTHON_VERSION_OK` (≈70 lines). Pruned 6 dead-code test cases from `tests/test_version_checks.sh`. Added `tests/test_python_resolution_fallback.sh` (4 cases, all pass). Net diff: ~230 insertions, ~541 deletions across 30 files.
- **Deviations from plan:** None of substance. The migration table's note about `aitask_explain_context.sh` (column listed `require_python` but the override below it specified `require_ait_python` since downstream imports yaml) was applied correctly during implementation. The function-choice column was the source of truth for the override decision, not the table cell.
- **Issues encountered:** (1) Smoke test Test 2 initially used `env -i ... command -v python3` to find the system Python — `command` is a bash builtin and `env -i` strips bash, so the lookup returned empty and the test silently skipped. Fixed by iterating `/usr/bin/python3` and `/bin/python3` directly. (2) Subtle die() ordering concern in `aitask_setup.sh`: sourcing `python_resolve.sh` (which transitively sources `terminal_compat.sh`) defines a die() before setup.sh's own `die()` definition at line 23 — setup's die() correctly overrides the helper's, preserving the `[ait] Error:` formatted output. Verified by running `aitask_setup.sh --help`.
- **Key decisions:** Per user direction during plan-verify, replaced the per-script version-arg pattern (`require_modern_python 3.11` repeated) with a single zero-arg `require_ait_python` function. Version literal "3.11" lives in exactly one place (`lib/python_resolve.sh:AIT_VENV_PYTHON_MIN`). The two compatibility levels are now expressed by function name (`require_ait_python` vs `require_python`) — debugging python-version issues now starts and ends at one file. Excluded `aitask_setup.sh`'s pre-venv python3 calls (bootstrap), `install.sh:263` (pre-setup), and `aidocs/benchmarks/bench_archive_formats.py` (standalone) from migration. Skipped defensive `import sys; sys.version_info` guards in `.py` files since none are invoked directly — every `.py` is wrapped by a `.sh` launcher whose `require_ait_python` already enforces version.
- **Upstream defects identified:** None.
- **Notes for sibling tasks:** When t695_5 (manual verification) runs, the TUI flows to verify on real macOS-3.9 / Debian-11 hosts include: board, minimonitor, settings, brainstorm_tui, codebrowser, crew_dashboard, diffviewer, monitor, stats_tui, crew_logview. Each will fail loudly (`die "Python >=3.11 required"`) on a sandbox with only system 3.9 — that's the expected behavior, and the prompt to "Run 'ait setup'" tells the user how to recover. Plain-stdlib scripts (verification_parse, codemap, sync, explain_extract_raw_data, explain_context) should continue working on system python3 in remote sandboxes.
