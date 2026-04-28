---
Task: t695_1_python_resolve_helper.md
Parent Task: aitasks/t695_install_python_if_sys_python_old.md
Sibling Tasks: aitasks/t695/t695_2_venv_python_upgrade.md, aitasks/t695/t695_3_aitask_bin_symlink_path.md, aitasks/t695/t695_4_refactor_python_callers.md
Archived Sibling Plans: aiplans/archived/p695/p695_*_*.md
Worktree: aiwork/t695_1_python_resolve_helper
Branch: aitask/t695_1_python_resolve_helper
Base branch: main
plan_verified:
  - claudecode/opus4_7_1m @ 2026-04-28 11:45
---

# Plan — t695_1: lib/python_resolve.sh helper + $AIT_PYTHON env override

## Context

First child of t695. Pure additive change — introduces a centralized Python
interpreter resolution layer at `.aitask-scripts/lib/python_resolve.sh` that
all subsequent children build on. Must land first.

The framework currently has ~9 TUI launchers using the `${PYTHON:-python3}`
shorthand and ~3 scripts that hardcode `python3`. There is no central place
that defines "which Python should aitasks use", and no way for scripts to
fall back gracefully in remote sandboxes (`aitask-pick-rem` /
`aitask-pick-web`) where `~/.aitask/` doesn't exist.

## Files

- `.aitask-scripts/lib/python_resolve.sh` — NEW. Sourced lib (no whitelist
  entries needed per CLAUDE.md "Adding a New Helper Script", because lib
  files are not invoked directly by skills).
- `tests/test_python_resolve.sh` — NEW. Self-contained bash test using the
  `assert_eq` / `assert_contains` style from existing tests.

## Implementation Steps

### Step 1 — Create the lib file

Path: `.aitask-scripts/lib/python_resolve.sh`

Skeleton:

```bash
#!/usr/bin/env bash
# Python interpreter resolution for the aitasks framework.
# Sourced (not executed). Provides resolve_python, require_python,
# require_modern_python.

if [[ -n "${_AIT_PYTHON_RESOLVE_LOADED:-}" ]]; then return 0; fi
_AIT_PYTHON_RESOLVE_LOADED=1

# shellcheck source=lib/terminal_compat.sh
source "$(dirname "${BASH_SOURCE[0]}")/terminal_compat.sh"

resolve_python() {
  if [[ -n "${_AIT_RESOLVED_PYTHON:-}" ]]; then
    echo "$_AIT_RESOLVED_PYTHON"
    return 0
  fi
  local cand
  for cand in \
    "${AIT_PYTHON:-}" \
    "$HOME/.aitask/bin/python3" \
    "$HOME/.aitask/venv/bin/python" \
    "$(command -v python3 2>/dev/null || true)"; do
    if [[ -n "$cand" && -x "$cand" ]]; then
      _AIT_RESOLVED_PYTHON="$cand"
      echo "$cand"
      return 0
    fi
  done
  return 0   # echo nothing; caller handles empty
}

require_python() {
  local p
  p="$(resolve_python)"
  if [[ -z "$p" ]]; then
    die "No Python interpreter found. Run 'ait setup' locally, or install python3 system-wide for remote use."
  fi
  echo "$p"
}

require_modern_python() {
  local min="${1:?usage: require_modern_python <major.minor>}"
  local p major minor
  p="$(require_python)"
  major="${min%%.*}"
  minor="${min##*.}"
  if ! "$p" -c "import sys; sys.exit(0 if sys.version_info >= ($major, $minor) else 1)" 2>/dev/null; then
    local found
    found="$("$p" --version 2>&1 | awk '{print $2}')"
    die "Python >=$min required (found $found at $p). Run 'ait setup' to install a newer interpreter."
  fi
  echo "$p"
}
```

### Step 2 — Add the unit test

Path: `tests/test_python_resolve.sh`

The test should set `HOME` to a scratch dir to avoid polluting the real
`~/.aitask/`. Lay down stub interpreters (small bash scripts) on a scratch
PATH, source the helper, and assert resolution behavior.

Outline:

```bash
#!/usr/bin/env bash
set -euo pipefail
SCRATCH="$(mktemp -d)"
trap 'rm -rf "$SCRATCH"' EXIT

# Helper: create a stub python that prints a version
make_stub() {
  local name="$1" version="$2"
  cat > "$SCRATCH/bin/$name" <<EOF
#!/usr/bin/env bash
case "\$1" in
  --version) echo "Python $version" ;;
  -c) shift; "$(command -v python3)" -c "$@" ;;  # delegate -c to real python3 for test purposes
  *) echo "stub:$name v$version" ;;
esac
EOF
  chmod +x "$SCRATCH/bin/$name"
}

mkdir -p "$SCRATCH/bin" "$SCRATCH/.aitask/bin" "$SCRATCH/.aitask/venv/bin"

# Test 1: system python3 only
unset AIT_PYTHON _AIT_RESOLVED_PYTHON
make_stub python3 "3.9.0"
HOME="$SCRATCH" PATH="$SCRATCH/bin" \
  bash -c 'source .aitask-scripts/lib/python_resolve.sh; resolve_python' \
  | grep -q "$SCRATCH/bin/python3" && echo "PASS test 1" || { echo "FAIL test 1"; exit 1; }

# Test 2: AIT_PYTHON wins
make_stub aitpy "3.13.0"
HOME="$SCRATCH" AIT_PYTHON="$SCRATCH/bin/aitpy" PATH="$SCRATCH/bin" \
  bash -c 'source .aitask-scripts/lib/python_resolve.sh; resolve_python' \
  | grep -q "aitpy" && echo "PASS test 2" || { echo "FAIL test 2"; exit 1; }

# Test 3: ~/.aitask/bin/python3 wins over system
ln -sf "$SCRATCH/bin/aitpy" "$SCRATCH/.aitask/bin/python3"
HOME="$SCRATCH" PATH="$SCRATCH/bin" \
  bash -c 'unset AIT_PYTHON; source .aitask-scripts/lib/python_resolve.sh; resolve_python' \
  | grep -q ".aitask/bin/python3" && echo "PASS test 3" || { echo "FAIL test 3"; exit 1; }

# Test 4: cache test — second call returns same value even if stub removed
HOME="$SCRATCH" PATH="$SCRATCH/bin" \
  bash -c '
    source .aitask-scripts/lib/python_resolve.sh
    first="$(resolve_python)"
    rm -f "$SCRATCH/.aitask/bin/python3"   # would not affect cached call
    second="$(resolve_python)"
    [[ "$first" == "$second" ]]
  ' && echo "PASS test 4" || { echo "FAIL test 4"; exit 1; }

# Test 5: require_modern_python rejects 3.9
make_stub python3 "3.9.0"
HOME="$SCRATCH" PATH="$SCRATCH/bin" \
  bash -c '
    unset AIT_PYTHON _AIT_RESOLVED_PYTHON
    source .aitask-scripts/lib/python_resolve.sh
    require_modern_python 3.11
  ' 2>&1 | grep -q "Python >=3.11 required" && echo "PASS test 5" || { echo "FAIL test 5"; exit 1; }

echo "All python_resolve tests passed."
```

The exact stubbing approach for `-c` (used by `require_modern_python`) needs
care — the simplest is to make the stub call a real Python (e.g., the host's
`/usr/bin/python3`) for `-c` requests, since the version check is what
matters. Adjust during implementation.

### Step 3 — Verify shellcheck and double-source

Run:

```bash
shellcheck .aitask-scripts/lib/python_resolve.sh
# Source twice in one shell:
bash -c 'source .aitask-scripts/lib/python_resolve.sh; source .aitask-scripts/lib/python_resolve.sh; declare -F resolve_python'
```

The second source must be a no-op (guarded by `_AIT_PYTHON_RESOLVE_LOADED`).

## Verification

- `bash tests/test_python_resolve.sh` exits 0 with all PASSes.
- `shellcheck .aitask-scripts/lib/python_resolve.sh` clean.
- Source the lib in an interactive shell and call `resolve_python` — should
  return either the system `python3` path, or `~/.aitask/bin/python3` if a
  prior setup ran.

## Dependencies / Sequencing

This is the first child. No dependencies on siblings. t695_2 / t695_3 /
t695_4 build on top of this helper.

## Step 9 — Post-Implementation

Standard archival flow. No worktree, no merge step. The lib file ships as
part of the framework so it must be committed in the implementation commit
(not under `aitasks/` / `aiplans/`).

## Final Implementation Notes

- **Actual work done:** Created `.aitask-scripts/lib/python_resolve.sh`
  (72 lines) implementing `resolve_python`, `require_python`, and
  `require_modern_python` exactly as planned. Created
  `tests/test_python_resolve.sh` (187 lines) with 8 tests, all passing.
  Both files pass `shellcheck -e SC1091` (the SC1091 informational about
  the dynamic source path is unfollowable by static shellcheck — it's the
  same situation as every other lib-sourcing script in the framework).
- **Deviations from plan:**
  - **Tests use `/usr/bin/bash --noprofile --norc -c ...` instead of plain
    `bash -c ...`.** The user has rc files that re-invoke `bash`, so a
    plain `bash -c` with a restricted PATH fails to find `bash` again
    inside its own startup. Using the absolute path with `--noprofile
    --norc` skips rc loading entirely. Documented inline in the test.
  - **Sub-PATH includes `/usr/bin:/bin`.** The lib calls `dirname` (in the
    source line) and `awk` (in `require_modern_python`'s version
    extraction), so test subshells need coreutils on PATH. The plan
    proposed PATH=$SCRATCH/bin only — that broke the dirname/awk calls.
    Tests now use `SUBPATH="$SCRATCH/bin:/usr/bin:/bin"` so stubs win for
    `python3` while coreutils stay reachable.
  - **Test 4 (cache stability) writes results to tempfiles instead of using
    command substitution `$(resolve_python)`.** Command substitution runs
    in a subshell, where any `_AIT_RESOLVED_PYTHON` cache is local to the
    subshell and never propagates back. Redirecting to a tempfile lets the
    parent shell pick up the cache between calls so the test actually
    validates caching. Inline comment in the test explains why.
  - **shellcheck `source=` directive uses a relative-from-file path
    (`source=terminal_compat.sh`).** Initially I wrote
    `source=lib/terminal_compat.sh` which made shellcheck look for
    `lib/lib/terminal_compat.sh` (the directive resolves relative to the
    file being checked, which is already in `lib/`). Fixed in-flight.
- **Issues encountered:**
  - The "rc files re-invoke bash" gotcha caused the first test run to fail
    with `bash: command not found` and was non-obvious from the error.
    `man bash` confirms `--noprofile --norc` is the right escape hatch.
  - shellcheck SC1091 is informational ("Not following: dynamic path");
    it's emitted as a warning even with the `# shellcheck source=` hint.
    The framework convention (per `shellcheck .aitask-scripts/aitask_*.sh`
    in CLAUDE.md) doesn't even cover lib files, so this is benign.
- **Key decisions:**
  - Cache via plain shell variable `_AIT_RESOLVED_PYTHON` rather than a
    file-backed cache — caches per-shell, which is exactly what callers
    need (no stale cross-process leak).
  - `resolve_python` echoes empty on miss (return 0) rather than dying;
    `require_python` is the one that dies. This lets callers choose
    soft-fail behavior (skip a Python step gracefully) where appropriate.
- **Upstream defects identified:** None.
- **Notes for sibling tasks:**
  - The lib is now in place and ready for t695_4 to source.
  - t695_2 (venv-Python upgrade) doesn't strictly need the helper, but its
    new `find_modern_python` should agree with the helper's lookup paths
    (`~/.aitask/bin/python3`, `~/.aitask/venv/bin/python`,
    `~/.aitask/python/<ver>/bin/python3`) so that after a fresh setup, the
    helper's first hit is the same interpreter the venv was built on.
  - The test file's "rc files break restricted-PATH `bash -c`" workaround
    is reusable — sibling tests that set PATH should also use
    `/usr/bin/bash --noprofile --norc -c ...`.
  - shellcheck users on this codebase should run `shellcheck -e SC1091
    <file>` (the project's existing convention is the same; SC1091 is a
    known false positive for dynamic source paths).
