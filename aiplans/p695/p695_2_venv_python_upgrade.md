---
Task: t695_2_venv_python_upgrade.md
Parent Task: aitasks/t695_install_python_if_sys_python_old.md
Sibling Tasks: aitasks/t695/t695_3_aitask_bin_symlink_path.md, aitasks/t695/t695_4_refactor_python_callers.md, aitasks/t695/t695_5_manual_verification_install_python_if_sys_python_old.md
Archived Sibling Plans: aiplans/archived/p695/p695_1_python_resolve_helper.md
Base branch: main
plan_verified:
  - claudecode/opus4_7_1m @ 2026-04-28 12:34
---

# Plan — t695_2: venv-Python upgrade flow in setup_python_venv (macOS + Linux)

## Context

Second child of t695. The heart of the user's reported fix.

Today, `setup_python_venv()` in `.aitask-scripts/aitask_setup.sh` builds the
framework venv on top of *whatever* `python3` happens to be in PATH. On macOS
that's typically the system 3.9.x, which the `linkify-it-py` dependency does
not support — so `ait setup` fails on a stock macOS install.

After this child lands, every fresh `ait setup` produces a venv backed by a
Python ≥ `AIT_VENV_PYTHON_MIN` (default 3.11) regardless of how old the
system Python is. macOS upgrades go through Homebrew's `python@3.13`. Linux
upgrades go strictly user-scoped: `~/.aitask/uv/` (the [astral-sh/uv]
installer redirected via `UV_INSTALL_DIR` + `INSTALLER_NO_MODIFY_PATH=1`),
which then fetches a python-build-standalone interpreter under `~/.aitask/`.
**No sudo. No apt/dnf modifications.**

This child does NOT yet wire up the `~/.aitask/bin/python3` symlink (that's
t695_3) and does NOT refactor any callers (t695_4). Scope is contained to
`setup_python_venv()` and supporting helpers in `aitask_setup.sh`.

## Files

- `.aitask-scripts/aitask_setup.sh` — modify `setup_python_venv()`
  (lines 435–511), add `find_modern_python()` and `install_modern_python()`
  helpers, add `AIT_VENV_PYTHON_MIN` / `AIT_VENV_PYTHON_PREFERRED`
  constants near the top.
- `tests/test_setup_find_modern_python.sh` — NEW. Unit-level test using
  stub interpreters on a scratch PATH. Always runs.
- `tests/test_setup_python_install.sh` — NEW. Heavy end-to-end test
  (`bash install.sh` → `./ait setup`) that actually installs Python via
  brew/uv. **Gated behind `AIT_RUN_INTEGRATION_TESTS=1`** so default test
  runs are not slowed by network downloads / brew installs.
- `aitasks/t695/t695_4_refactor_python_callers.md` — append a single
  one-line note under `## Notes for sibling tasks` flagging that the
  now-dead `check_python_version()` / `PYTHON_VERSION_OK` cleanup
  belongs in t695_4. Content-only edit (see Step 5).

## Pre-flight verification (already done)

- `aitask_setup.sh` is shellcheck-clean for errors (4 SC2015 info-level
  warnings only, all pre-existing).
- `AIT_VENV_PYTHON_MIN` / `AIT_VENV_PYTHON_PREFERRED` / `UV_INSTALL_DIR` /
  `INSTALLER_NO_MODIFY_PATH` are not used anywhere in the repo — no
  collision.
- `aitask_setup.sh --source-only` (line 3089) returns early so tests can
  source it and call helpers directly. Existing tests
  (`tests/test_version_checks.sh:37`) already use this.
- `OS` is a global set by `detect_os()` invoked from `main()` at line 3009;
  `setup_python_venv` runs at 3049, so `OS` is in scope.
- The `info`/`warn`/`die`/`success` helpers used below are defined inline
  in `aitask_setup.sh` lines 14–18 (not the `terminal_compat.sh` ones).
- t695_1's `.aitask-scripts/lib/python_resolve.sh` ships `resolve_python`
  with candidate order `$AIT_PYTHON → ~/.aitask/bin/python3 →
  ~/.aitask/venv/bin/python → command -v python3`. Our new lookup paths
  align: we additionally probe `~/.aitask/python/<ver>/bin/python3` (the
  uv-installed location) so the next setup run finds the just-installed
  interpreter without going through PATH.

## Implementation Steps

### Step 1 — Add config constants

Just after line 11 (the `REPO=` line) in `aitask_setup.sh`:

```bash
AIT_VENV_PYTHON_MIN="${AIT_VENV_PYTHON_MIN:-3.11}"
AIT_VENV_PYTHON_PREFERRED="${AIT_VENV_PYTHON_PREFERRED:-3.13}"
```

Both honour pre-existing env overrides so power users can pin a different
minimum/preferred version without editing the script.

### Step 2 — Add `find_modern_python <min_version>`

Place it just before `check_python_version()` (line 372 today). Searches a
fixed list of locations for a Python ≥ `min_version`. Echoes the absolute
path on success or empty on failure. Always returns 0 (caller checks empty
output).

```bash
# Resolve a Python interpreter that meets $min_version (e.g. "3.11").
# Echoes the absolute path or empty. Always returns 0.
find_modern_python() {
    local min="${1:-$AIT_VENV_PYTHON_MIN}"
    local major="${min%%.*}" minor="${min##*.}"
    local cand resolved candidates=(
        "$HOME/.aitask/bin/python3"
        "$HOME/.aitask/python/$AIT_VENV_PYTHON_PREFERRED/bin/python3"
        "$HOME/.aitask/venv/bin/python"
        python3.13 python3.12 python3.11 python3
    )
    for cand in "${candidates[@]}"; do
        if [[ "$cand" == /* ]]; then
            resolved="$cand"
        else
            resolved="$(command -v "$cand" 2>/dev/null || true)"
        fi
        [[ -z "$resolved" || ! -x "$resolved" ]] && continue
        if "$resolved" -c "import sys; sys.exit(0 if sys.version_info >= ($major, $minor) else 1)" 2>/dev/null; then
            echo "$resolved"
            return 0
        fi
    done
    return 0   # echo nothing
}
```

The defensive `python3` candidate at the tail covers the case where the
system `python3` is *already* modern (e.g., Arch, recent Debian) — no
install needed. The interpreter version is verified by running `-c
"import sys..."` so spoofed names (e.g., a `python3.11` symlink that
actually points at 3.9) are rejected.

### Step 3 — Add `install_modern_python` (OS-dispatched)

Place it just after `find_modern_python`. The dispatcher routes on `$OS`
(set globally by `detect_os()`):

```bash
install_modern_python() {
    case "$OS" in
        macos) _install_modern_python_macos ;;
        *)     _install_modern_python_linux ;;   # debian/arch/fedora/wsl/linux-unknown
    esac
}

_install_modern_python_macos() {
    if ! command -v brew >/dev/null 2>&1; then
        die "Homebrew not found. Install from https://brew.sh and re-run 'ait setup'."
    fi
    info "Installing python@$AIT_VENV_PYTHON_PREFERRED via Homebrew..."
    brew install "python@$AIT_VENV_PYTHON_PREFERRED" \
        || brew upgrade "python@$AIT_VENV_PYTHON_PREFERRED" \
        || die "brew install python@$AIT_VENV_PYTHON_PREFERRED failed."
    hash -r   # refresh bash command cache so newly-linked python3.13 is visible
}

_install_modern_python_linux() {
    local uv_dir="$HOME/.aitask/uv"
    if [[ ! -x "$uv_dir/bin/uv" ]]; then
        info "Downloading uv (astral-sh/uv) into $uv_dir (user-scoped, no sudo)..."
        if ! command -v curl >/dev/null 2>&1; then
            die "curl is required to download uv. Install curl and re-run 'ait setup'."
        fi
        UV_INSTALL_DIR="$uv_dir" \
        INSTALLER_NO_MODIFY_PATH=1 \
            sh -c 'curl -LsSf https://astral.sh/uv/install.sh | sh' \
            || die "uv install failed."
    fi
    info "Installing Python $AIT_VENV_PYTHON_PREFERRED via uv..."
    "$uv_dir/bin/uv" python install "$AIT_VENV_PYTHON_PREFERRED" \
        || die "uv python install $AIT_VENV_PYTHON_PREFERRED failed."
    local installed
    installed="$("$uv_dir/bin/uv" python find "$AIT_VENV_PYTHON_PREFERRED" 2>/dev/null)"
    [[ -z "$installed" || ! -x "$installed" ]] && \
        die "uv reported Python $AIT_VENV_PYTHON_PREFERRED installed but interpreter is not executable: ${installed:-<empty>}"
    mkdir -p "$HOME/.aitask/python/$AIT_VENV_PYTHON_PREFERRED/bin"
    ln -sf "$installed" "$HOME/.aitask/python/$AIT_VENV_PYTHON_PREFERRED/bin/python3"
    info "Python $AIT_VENV_PYTHON_PREFERRED installed at $installed (symlinked at ~/.aitask/python/$AIT_VENV_PYTHON_PREFERRED/bin/python3)."
    hash -r
}
```

Notes:
- The `UV_INSTALL_DIR` + `INSTALLER_NO_MODIFY_PATH=1` env vars are
  documented at <https://docs.astral.sh/uv/configuration/installer/>;
  verify the spelling at implementation time and adjust if astral-sh
  has renamed them.
- macOS: existing code at line 405 uses `brew install python@3` (whatever
  Homebrew calls "latest"); this new path uses `python@3.13` (pinned).
  The two formulae can co-exist on the system.

### Step 4 — Refactor `setup_python_venv()`

**Three coordinated changes** in the function (lines 435–511 today):

1. **Replace the find-python-cmd preamble** (lines 436–455) with a
   `find_modern_python` call + auto-install fallback.
2. **Delete the `check_python_version "$python_cmd"` call and the
   `PYTHON_VERSION_OK` recheck** (lines 458–463). After this child,
   `find_modern_python` guarantees ≥ `AIT_VENV_PYTHON_MIN` ≥ 3.9, so the
   downstream re-detect logic is unreachable / dead.
3. **Update the existing-venv version check** (lines 469–477) so that an
   old 3.9-based venv is recreated when `AIT_VENV_PYTHON_MIN` is now
   3.11. Currently it hardcodes 3.9 (`venv_minor -ge 9`); change to
   `AIT_VENV_PYTHON_MIN`'s minor.

The full replacement for lines 436–488 (preamble through venv-creation
block) reads:

```bash
setup_python_venv() {
    local python_cmd
    python_cmd="$(find_modern_python "$AIT_VENV_PYTHON_MIN")"
    if [[ -z "$python_cmd" ]]; then
        info "No Python >=$AIT_VENV_PYTHON_MIN found. Installing one (user-scoped)..."
        install_modern_python
        python_cmd="$(find_modern_python "$AIT_VENV_PYTHON_MIN")"
        [[ -z "$python_cmd" ]] && \
            die "Modern Python install completed but interpreter still not found. Aborting venv setup."
    fi
    info "Using Python for venv: $python_cmd ($("$python_cmd" --version 2>&1))"

    # Parse the configured minimum into major/minor for the existing-venv check
    local min_major="${AIT_VENV_PYTHON_MIN%%.*}"
    local min_minor="${AIT_VENV_PYTHON_MIN##*.}"

    if [[ -d "$VENV_DIR" ]]; then
        local venv_ver=""
        venv_ver="$("$VENV_DIR/bin/python" -c 'import sys; print("{}.{}".format(*sys.version_info[:2]))' 2>/dev/null)" || venv_ver=""
        if [[ -n "$venv_ver" ]]; then
            local venv_major venv_minor
            venv_major="$(echo "$venv_ver" | cut -d. -f1)"
            venv_minor="$(echo "$venv_ver" | cut -d. -f2)"
            if [[ "$venv_major" -gt "$min_major" ]] || \
               { [[ "$venv_major" -eq "$min_major" ]] && [[ "$venv_minor" -ge "$min_minor" ]]; }; then
                info "Python virtual environment already exists at $VENV_DIR (Python $venv_ver)"
            else
                warn "Existing venv uses Python $venv_ver (< $AIT_VENV_PYTHON_MIN). Recreating..."
                rm -rf "$VENV_DIR"
                mkdir -p "$(dirname "$VENV_DIR")"
                "$python_cmd" -m venv "$VENV_DIR"
            fi
        else
            info "Python virtual environment already exists at $VENV_DIR"
        fi
    else
        info "Creating Python virtual environment at $VENV_DIR..."
        mkdir -p "$(dirname "$VENV_DIR")"
        "$python_cmd" -m venv "$VENV_DIR"
    fi
```

**Lines 489–511 (plotext prompt + pip install block) are unchanged.** The
package list stays:

```bash
"$VENV_DIR/bin/pip" install --quiet --upgrade pip
"$VENV_DIR/bin/pip" install --quiet 'textual>=8.1.1,<9' 'pyyaml==6.0.3' 'linkify-it-py==2.1.0' 'tomli>=2.4.0,<3'
```

### Step 5 — Defer `check_python_version()` / `PYTHON_VERSION_OK` cleanup to t695_4

After Step 4 lands, `check_python_version` (lines 372–432) and the
`PYTHON_VERSION_OK` global (line 371) become **fully dead**:
- They are no longer called from `setup_python_venv`.
- They have no other callers in `aitask_setup.sh`.
- `install.sh:263` invokes `python3` directly for the
  `aitask_install_merge.py` step (no version check, no helper sourced).
- `tests/test_version_checks.sh` still exercises the function — that
  test stays as long as the function exists.

**Decision:** **leave the function in place in t695_2** but explicitly
delegate the cleanup to **t695_4** (`refactor_python_callers`).

t695_4 is the natural home because:
- Its scope is "every Python caller in the framework migrates to
  `lib/python_resolve.sh`'s `resolve_python` / `require_modern_python`".
- After t695_4 finishes, no caller in the framework needs the 3.9
  floor that `check_python_version` enforces — `require_modern_python`
  supersedes it.
- t695_4 also owns the matching update to `tests/test_version_checks.sh`
  (rename or replace its python-version coverage with tests against the
  new helper).

**Sub-step in this plan:** as part of Step 4, append a one-line note to
the `## Notes for sibling tasks` section of
`aitasks/t695/t695_4_refactor_python_callers.md`:

```
- `check_python_version()` and the `PYTHON_VERSION_OK` global in
  `.aitask-scripts/aitask_setup.sh` (lines ~371–432) are dead after
  t695_2; remove them as part of this task. Update or delete the
  matching coverage in `tests/test_version_checks.sh`.
```

That note lands as a content-only edit (no frontmatter changes), so it
does not need a separate `aitask_update.sh --batch` invocation —
include it in the same `./ait git commit` that lands the plan-file
update during Step 8 (alongside any plan-file Final Implementation
Notes).

Optionally, also append a `# DEPRECATED: dead after t695_2 — removal in
t695_4` comment above `check_python_version` so anyone reading
`aitask_setup.sh` between t695_2 and t695_4 immediately sees the
status. Single line, no behaviour change.

### Step 6 — Unit test for `find_modern_python` (always runs)

Path: `tests/test_setup_find_modern_python.sh`

Pattern: source `aitask_setup.sh --source-only`, mirror the
`test_version_checks.sh` style. Stub interpreters are tiny bash scripts
that fake `--version` and `-c "import sys; sys.exit(...)"`.

Outline:

```bash
#!/usr/bin/env bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

PASS=0; FAIL=0; TOTAL=0
assert_eq() { ... }            # copy from test_version_checks.sh
assert_contains() { ... }

source "$PROJECT_DIR/.aitask-scripts/aitask_setup.sh" --source-only
set +euo pipefail

OS="linux"
SCRATCH="$(mktemp -d)"
trap 'rm -rf "$SCRATCH"' EXIT
mkdir -p "$SCRATCH/bin" "$SCRATCH/home/.aitask/python/3.13/bin"

# Stub generator — reports VERSION via --version and via -c sys.version_info exit code
make_stub() {
    local path="$1" version="$2"
    local major="${version%%.*}" minor
    minor="$(echo "$version" | cut -d. -f2)"
    cat > "$path" <<EOF
#!/usr/bin/env bash
case "\$1" in
  --version) echo "Python $version" ;;
  -c)
    shift
    # Crude but sufficient: parse "($MAJOR, $MINOR)" out of the assertion
    if echo "\$1" | grep -qE 'sys.version_info >= \\(([0-9]+), ([0-9]+)\\)'; then
        req_major="\$(echo "\$1" | sed -E 's/.*>= \\(([0-9]+), [0-9]+\\).*/\\1/')"
        req_minor="\$(echo "\$1" | sed -E 's/.*>= \\([0-9]+, ([0-9]+)\\).*/\\1/')"
        if [[ $major -gt \$req_major ]] || { [[ $major -eq \$req_major ]] && [[ $minor -ge \$req_minor ]]; }; then
            exit 0
        else
            exit 1
        fi
    fi
    ;;
esac
EOF
    chmod +x "$path"
}

# Test 1 — no candidates → empty
PATH="$SCRATCH/bin" HOME="$SCRATCH/home" out="$(find_modern_python 3.11)"
assert_eq "no candidates returns empty" "" "$out"

# Test 2 — python3.13 stub on PATH → returned
make_stub "$SCRATCH/bin/python3.13" "3.13.1"
PATH="$SCRATCH/bin" HOME="$SCRATCH/home" out="$(find_modern_python 3.11)"
assert_contains "python3.13 picked up via PATH" "python3.13" "$out"

# Test 3 — python3.11 stub that lies (reports 3.9) → rejected
make_stub "$SCRATCH/bin/python3.11" "3.9.0"
rm -f "$SCRATCH/bin/python3.13"
PATH="$SCRATCH/bin" HOME="$SCRATCH/home" out="$(find_modern_python 3.11)"
assert_eq "spoofed python3.11 reporting 3.9 is rejected" "" "$out"

# Test 4 — uv-style ~/.aitask/python/3.13/bin/python3 takes priority over PATH
make_stub "$SCRATCH/bin/python3.13" "3.13.1"           # PATH candidate
make_stub "$SCRATCH/home/.aitask/python/3.13/bin/python3" "3.13.2"
AIT_VENV_PYTHON_PREFERRED=3.13 \
PATH="$SCRATCH/bin" HOME="$SCRATCH/home" out="$(find_modern_python 3.11)"
assert_contains "uv-installed path preferred over PATH" ".aitask/python/3.13/bin/python3" "$out"

echo ""
echo "=== Results: $PASS/$TOTAL passed, $FAIL failed ==="
[[ $FAIL -eq 0 ]] || exit 1
```

This unit test never runs `brew`, `curl`, or real Python — safe and fast
on every dev machine.

### Step 7 — Integration test (gated)

Path: `tests/test_setup_python_install.sh`

Per CLAUDE.md "Test the full install flow for setup helpers", this test
runs `bash install.sh --dir <scratch>` then `./ait setup` end-to-end.
**It is heavy (downloads brew formulae or uv; minutes-scale)** so it
gates on an opt-in env var:

```bash
#!/usr/bin/env bash
set -euo pipefail

if [[ -z "${AIT_RUN_INTEGRATION_TESTS:-}" ]]; then
    echo "SKIP: set AIT_RUN_INTEGRATION_TESTS=1 to run full install integration test"
    exit 0
fi

SCRATCH="$(mktemp -d /tmp/scratch695_XXXXXX)"
trap 'rm -rf "$SCRATCH"' EXIT

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Run install.sh into scratch dir
bash "$PROJECT_DIR/install.sh" --dir "$SCRATCH"

# Run ait setup via stdin redirect — relies on the existing `[[ -t 0 ]]`
# auto-accept paths in check_python_version (line 396) and the optional
# plotext prompt (line 491). NO --yes flag exists.
HOME="$SCRATCH/fakehome" PATH="/usr/bin:/bin" \
    "$SCRATCH/ait" setup < /dev/null

# Assert venv exists and Python >= 3.11
ver="$("$SCRATCH/fakehome/.aitask/venv/bin/python" -c 'import sys; print("{}.{}".format(*sys.version_info[:2]))')"
ver_major="${ver%%.*}"; ver_minor="${ver##*.}"
if ! { [[ "$ver_major" -gt 3 ]] || { [[ "$ver_major" -eq 3 ]] && [[ "$ver_minor" -ge 11 ]]; }; }; then
    echo "FAIL: venv Python is $ver (expected >= 3.11)"
    exit 1
fi

# Assert critical deps import
"$SCRATCH/fakehome/.aitask/venv/bin/python" -c "import linkify_it; import textual; import yaml"

# On Linux: assert uv was used (since system python is likely 3.9 on CI)
if [[ "$(uname)" == "Linux" ]]; then
    [[ -x "$SCRATCH/fakehome/.aitask/uv/bin/uv" ]] && \
        [[ -L "$SCRATCH/fakehome/.aitask/python/3.13/bin/python3" ]] || {
            echo "Note: Linux integration host had a modern system Python; uv path not exercised."
        }
fi

echo "PASS: integration test"
```

**Key decision: NO `--yes` flag is added to `ait setup` in this child.**
That would expand scope; the existing `[[ -t 0 ]]` auto-accept paths
(lines 396, 491) already give us non-interactive behaviour when stdin
is redirected from `/dev/null`. If a future caller needs an explicit
flag, that's a separate task.

## Verification

- `bash tests/test_setup_find_modern_python.sh` exits 0 with all PASSes
  (always runs).
- `AIT_RUN_INTEGRATION_TESTS=1 bash tests/test_setup_python_install.sh`
  exits 0 on a Linux dev host (and on macOS if brew is available).
- `shellcheck .aitask-scripts/aitask_setup.sh` is at least no worse than
  baseline (currently 4 SC2015 info-level warnings; new helpers should
  not add errors). Ignore SC1091 ("not following dynamic source") if it
  surfaces — that's the project convention.
- `bash tests/test_version_checks.sh` still passes (we did not break
  `check_python_version`'s contract; we just stopped calling it from
  `setup_python_venv`).
- Manual on macOS Sequoia (system python 3.9.x):
  `rm -rf ~/.aitask/venv && ait setup < /dev/null` →
  brew installs `python@3.13`, venv built on 3.13, `linkify_it` imports.
- Manual on Debian 11 (system python 3.9.x):
  `rm -rf ~/.aitask/venv ~/.aitask/uv ~/.aitask/python && ait setup < /dev/null` →
  uv downloaded under `~/.aitask/uv`, python 3.13 installed under
  `~/.aitask/python/3.13/`, venv built on 3.13, **no sudo prompts**.
- `git status` after run: only intended changes
  (`aitask_setup.sh`, two new test files, plus `aiplans/p695/...`).

## Dependencies / Sequencing

- t695_1 (`lib/python_resolve.sh`) is already merged. This child does not
  source the helper but its `find_modern_python` lookup paths align with
  `resolve_python`'s candidates so subsequent `ait` invocations
  consistently land on the same interpreter.
- t695_3 (`~/.aitask/bin/python3` symlink) lands next; this child's
  lookup already probes `~/.aitask/bin/python3` so once t695_3 is in
  place, that becomes the first hit.
- t695_4 (refactor remaining python callers) lands last.

## Step 9 — Post-Implementation

Standard archival flow per `task-workflow/SKILL.md` Step 9. No worktree
to remove (profile `fast` works on `main` directly). The integration
test runs in a scratch dir, so nothing on the dev machine needs cleanup
beyond what each test's `trap` already handles.

The Final Implementation Notes section appended to this plan during
Step 8 should call out:
- **Notes for sibling tasks:** that `find_modern_python` is now the
  single source of truth for "which python should the venv use", that
  `check_python_version` is dead in `aitask_setup.sh` and a future
  cleanup target, and that the unit-test stub-PATH pattern in
  `tests/test_setup_find_modern_python.sh` is reusable for siblings.
- Any deviation from this plan, especially if the uv installer's env
  var contract has changed by the time of implementation.

## Final Implementation Notes

- **Actual work done:** Implemented Steps 1-7 of the plan as written.
  - `.aitask-scripts/aitask_setup.sh`: added `AIT_VENV_PYTHON_MIN`
    (3.11) and `AIT_VENV_PYTHON_PREFERRED` (3.13) constants near the
    top, added `find_modern_python()`, `install_modern_python()` +
    `_install_modern_python_macos` (brew) +
    `_install_modern_python_linux` (uv user-scoped) helpers, and
    refactored `setup_python_venv()` per Step 4 (replaced preamble,
    deleted the `check_python_version` call + `PYTHON_VERSION_OK`
    recheck, updated existing-venv version check to use the
    configured minimum). Added `# DEPRECATED: dead after t695_2 —
    removal in t695_4` comment above `check_python_version`.
  - `tests/test_setup_find_modern_python.sh`: 6 unit tests
    (unsatisfiable min, PATH lookup, spoofed version rejection,
    uv-installed path priority, framework bin/python3 priority, min
    enforcement). All pass.
  - `tests/test_setup_python_install.sh`: gated end-to-end test that
    runs `install.sh` → `ait setup` and asserts venv Python ≥ 3.11
    and that `linkify_it`/`textual`/`yaml` import. Skips by default;
    runs only when `AIT_RUN_INTEGRATION_TESTS=1`.
  - `aitasks/t695/t695_4_refactor_python_callers.md`: appended a
    sibling-task note flagging the dead `check_python_version()` /
    `PYTHON_VERSION_OK` for t695_4 cleanup.
- **Deviations from plan:**
  - **Test 1 (unsatisfiable min) replaces the "no candidates" framing
    in the original outline.** On any host where system `python3`
    exists in `/usr/bin/`, restricting `PATH` to a stub-only directory
    breaks the stub itself (the stub uses `/usr/bin/grep` and
    `/usr/bin/sed`). Including `/usr/bin:/bin` in `PATH` then made
    "no candidates available" untestable because the trailing
    `python3` candidate would always find the system interpreter.
    Reframed Test 1 to use `min=99.0` (no candidate can satisfy) and
    Test 6 to use `min=4.0`. Same coverage, robust to host state.
  - **Test PATH includes `/usr/bin:/bin`** (per the t695_1 plan's
    "Sub-PATH includes /usr/bin:/bin" note). The function calls
    `command -v` and the stubs invoke `grep`/`sed` — restricting
    `PATH` to `$SCRATCH/bin` only silently breaks them.
  - **System Python on this dev host is 3.14.3, not 3.13.** The
    initial Test 6 used `min=3.14` expecting rejection; bumped to
    `min=4.0` after discovering this. (Not a plan defect — just a
    fact-on-the-ground that affected test calibration.)
  - **No `--yes` flag added** (as planned). The integration test
    relies on stdin redirection to `/dev/null`, which the existing
    `[[ -t 0 ]]` auto-accept paths handle correctly.
- **Issues encountered:**
  - First run of the unit test failed Tests 4 and 5 silently because
    `PATH=$SCRATCH/bin` (from the original outline) made the stub
    interpreters unable to find `grep`/`sed`. Diagnosed by adding
    debug prints and tracing — confirmed the t695_1 plan's note about
    needing `/usr/bin:/bin` in test PATH. Fixed.
  - `aitask_setup.sh --source-only` returns early (line 3089). Tests
    that source it inherit `set -euo pipefail` from line 2; tests
    must `set +euo pipefail` after sourcing to use loose-mode
    helpers like `assert_eq` / `assert_contains`.
- **Key decisions:**
  - **Dead-code cleanup deferred to t695_4** (per user request during
    plan review): `check_python_version()` and `PYTHON_VERSION_OK`
    remain in place with a `# DEPRECATED` comment, and a one-line
    sibling-task note in `aitasks/t695/t695_4_refactor_python_callers.md`
    flags the cleanup. This keeps the t695_2 diff focused and
    routes the cleanup through the natural refactor task.
  - **`find_modern_python` candidate order** intentionally agrees
    with `lib/python_resolve.sh` (t695_1) for `~/.aitask/bin`,
    `~/.aitask/venv`, system `python3` — and adds
    `~/.aitask/python/<ver>/bin/python3` for the uv path. After a
    fresh `ait setup` followed by t695_3 (symlink), all callers
    consistently land on the same interpreter.
  - **Integration test gated behind `AIT_RUN_INTEGRATION_TESTS=1`**
    rather than running by default. The test downloads brew formulae
    (~30s+ on macOS) or uv + a python-build-standalone tarball
    (~minutes on Linux) — too heavy for default `bash tests/...`
    iteration loops.
- **Upstream defects identified:** None.
- **Notes for sibling tasks:**
  - `find_modern_python` is the single source of truth for "which
    Python should the venv use" — t695_3 and t695_4 should not
    re-implement the version check.
  - `check_python_version()` and `PYTHON_VERSION_OK` are dead and
    must be removed in t695_4 (note already in that task file).
  - The stub-PATH unit-test pattern in
    `tests/test_setup_find_modern_python.sh` is reusable. Two
    gotchas to remember when copying it: (1) include
    `/usr/bin:/bin` in `PATH` so stubs can find `grep`/`sed`; (2)
    after `source aitask_setup.sh --source-only`, run
    `set +euo pipefail` so test assertions don't abort on first
    failure.
  - The uv installer env-var contract used here is
    `UV_INSTALL_DIR` + `INSTALLER_NO_MODIFY_PATH=1` (verified
    against the docs at the time of implementation). If astral-sh
    renames either, adjust `_install_modern_python_linux` accordingly.
