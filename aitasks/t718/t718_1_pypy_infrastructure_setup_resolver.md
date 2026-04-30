---
priority: medium
effort: medium
depends: []
issue_type: performance
status: Implementing
labels: [performance, setup, tui]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_7_1m
created_at: 2026-04-30 10:30
updated_at: 2026-04-30 12:26
---

## Context

Parent task **t718** (`aitasks/t718_pypy_optional_runtime_for_tui_perf.md`) introduces opt-in PyPy support for long-running Textual TUIs. Per the parent plan (`aiplans/p718_pypy_optional_runtime_for_tui_perf.md`), this child lands the **infrastructure layer** in isolation — install PyPy, create a sibling venv, expose new resolver functions — without touching any TUI launcher. Exiting this task with green tests means: a user who runs `ait setup --with-pypy` gets PyPy installed at `~/.aitask/pypy_venv/`, but `ait board`, `ait codebrowser`, etc. **still run on CPython** (they get switched in t718_2). This is intentional: it lets the infrastructure be tested in full isolation before any user-visible behavior change.

The codebase is already PyPy 3.11 compatible per `aidocs/python_tui_performance.md` (no PEP 695, no `tomllib`, no `typing.override`). All deps support 3.9+.

## `AIT_USE_PYPY` precedence (established here)

`require_ait_python_fast()` (added in this task) implements:

| `AIT_USE_PYPY` | PyPy installed? | Result |
|----------------|-----------------|--------|
| `1` | Yes | PyPy (forced) |
| `1` | No | `die`: "AIT_USE_PYPY=1 set but PyPy is not installed. Run 'ait setup --with-pypy' first." |
| `0` | (any) | CPython (user override) |
| unset / empty | Yes | PyPy (default once installed) |
| unset / empty | No | CPython (silent — current behavior preserved) |

`require_ait_python` semantics are **unchanged** — only the new `require_ait_python_fast` is PyPy-aware.

## Key Files to Modify

1. `.aitask-scripts/lib/python_resolve.sh`
   - Add constants `AIT_PYPY_PREFERRED="${AIT_PYPY_PREFERRED:-3.11}"` and `PYPY_VENV_DIR="${PYPY_VENV_DIR:-$HOME/.aitask/pypy_venv}"` near the existing `AIT_VENV_PYTHON_MIN` constant. **Single source of truth** — do not duplicate these literals in `aitask_setup.sh` (per `feedback_single_source_of_truth_for_versions.md`).
   - Add `resolve_pypy_python()` mirroring `resolve_python()` (cached in `_AIT_RESOLVED_PYPY`). Resolution order: `$AIT_PYPY` (override) → `$PYPY_VENV_DIR/bin/python` → `command -v pypy3.11` → `command -v pypy3` → empty.
   - Add `require_ait_pypy()` paralleling `require_ait_python` — calls `resolve_pypy_python` and `die`s on miss.
   - Add `require_ait_python_fast()` implementing the precedence table above.

2. `.aitask-scripts/aitask_setup.sh`
   - Add `find_pypy()` paralleling `find_modern_python` (line 378) — looks up `$PYPY_VENV_DIR/bin/python`, `pypy3.11`, `pypy3`. Returns the first usable interpreter that reports `sys.implementation.name == 'pypy'`.
   - Add `install_pypy()` paralleling `install_modern_python` (line 403). Linux: `"$uv_dir/bin/uv" python install pypy@$AIT_PYPY_PREFERRED` (uv treats PyPy as a first-class interpreter family). macOS: `brew install pypy3.11` (with `pypy3` fallback). Both branches symlink the resolved interpreter into `$HOME/.aitask/python/pypy-$AIT_PYPY_PREFERRED/bin/python3` for parallel structure with the CPython install.
   - Add `setup_pypy_venv()` paralleling `setup_python_venv` (line 447). Same dependency set: `'textual>=8.1.1,<9' 'pyyaml==6.0.3' 'linkify-it-py==2.1.0' 'tomli>=2.4.0,<3'` (skip `plotext` for now — not required by t718_2's scope; can be added later if the stats TUI needs it). Skip the `install_python_wrappers` call (PyPy venv has its own bin dir; no global wrapper needed since the resolver finds it directly).
   - **Add a `--with-pypy` CLI flag.** Currently `main()` (line 3107) takes no flags. Insert flag parsing at the top of `main()` (before `detect_os`). Set a global `INSTALL_PYPY=1` if the flag is present. Also add an interactive prompt inside `setup_python_venv` (or a new wrapper) for TTY users: `Install PyPy for faster TUIs (board, codebrowser)? [y/N]` — but only when `INSTALL_PYPY` is not already set by the flag, and only when `[ -t 0 ]`. Either path triggers a call to `setup_pypy_venv` after the regular CPython venv is ready.

3. **Whitelist** — no new helper scripts are introduced in this task (only new functions inside existing scripts), so the 5-touchpoint helper-script whitelist checklist from CLAUDE.md does **not** apply here.

## Reference Files for Patterns

- `find_modern_python` (`.aitask-scripts/aitask_setup.sh:378-400`) — candidate-list lookup pattern.
- `install_modern_python` / `_install_modern_python_macos` / `_install_modern_python_linux` (`.aitask-scripts/aitask_setup.sh:403-444`) — OS-branched installer.
- `setup_python_venv` (`.aitask-scripts/aitask_setup.sh:447-528`) — venv creation, dep install, idempotence, plotext prompt pattern.
- `install_python_wrappers` (`.aitask-scripts/aitask_setup.sh:536-550`) — **do not call this for PyPy**, but useful pattern reference for similar shim work.
- `resolve_python` / `require_ait_python` (`.aitask-scripts/lib/python_resolve.sh:37-89`) — caching, candidate fallback, version assertion.

## Implementation Plan

**Step 1 — Constants and resolver (`lib/python_resolve.sh`)**

Add right after `AIT_VENV_PYTHON_MIN` (line 32):

```bash
AIT_PYPY_PREFERRED="${AIT_PYPY_PREFERRED:-3.11}"
PYPY_VENV_DIR="${PYPY_VENV_DIR:-$HOME/.aitask/pypy_venv}"
```

Add at the bottom of the file:

```bash
resolve_pypy_python() {
    if [[ -n "${_AIT_RESOLVED_PYPY:-}" ]]; then
        echo "$_AIT_RESOLVED_PYPY"
        return 0
    fi
    local cand resolved
    for cand in \
        "${AIT_PYPY:-}" \
        "$PYPY_VENV_DIR/bin/python"; do
        if [[ -n "$cand" && -x "$cand" ]]; then
            # Confirm it really is PyPy (not a misnamed CPython).
            if "$cand" -c "import sys; sys.exit(0 if sys.implementation.name == 'pypy' else 1)" 2>/dev/null; then
                _AIT_RESOLVED_PYPY="$cand"
                echo "$cand"
                return 0
            fi
        fi
    done
    for cand in pypy3.11 pypy3; do
        resolved="$(command -v "$cand" 2>/dev/null || true)"
        if [[ -n "$resolved" && -x "$resolved" ]]; then
            _AIT_RESOLVED_PYPY="$resolved"
            echo "$resolved"
            return 0
        fi
    done
    return 0  # empty output = not found
}

require_ait_pypy() {
    local p
    p="$(resolve_pypy_python)"
    [[ -z "$p" ]] && die "PyPy not found. Run 'ait setup --with-pypy' to install it."
    echo "$p"
}

require_ait_python_fast() {
    case "${AIT_USE_PYPY:-}" in
        1)  # forced PyPy — die if missing
            require_ait_pypy
            return 0 ;;
        0)  # forced CPython
            require_ait_python
            return 0 ;;
    esac
    # Default: prefer PyPy if installed, else CPython
    local p
    p="$(resolve_pypy_python)"
    if [[ -n "$p" ]]; then
        echo "$p"
        return 0
    fi
    require_ait_python
}
```

**Step 2 — Setup helpers (`aitask_setup.sh`)**

After `install_modern_python` (line ~444), add `find_pypy`, `install_pypy` (with macOS/Linux variants), and `setup_pypy_venv`. These mirror the existing functions but key off `$PYPY_VENV_DIR`, `$AIT_PYPY_PREFERRED`, and a `pypy@$AIT_PYPY_PREFERRED` uv argument / `pypy3.11` brew formula.

`setup_pypy_venv` is idempotent in the same way `setup_python_venv` is: if the venv exists and reports `sys.implementation.name == 'pypy'`, skip recreation; otherwise rebuild.

**Step 3 — Flag parsing in `main()`**

Insert at the top of `main()` (line 3107), before `echo ""`:

```bash
INSTALL_PYPY=0
while [[ $# -gt 0 ]]; do
    case "$1" in
        --with-pypy) INSTALL_PYPY=1; shift ;;
        --) shift; break ;;
        *)  shift ;;  # ignore unknown for forward-compat
    esac
done
```

After `setup_python_venv` (line 3155), add:

```bash
if [[ "$INSTALL_PYPY" == "1" ]] || prompt_install_pypy_if_tty; then
    setup_pypy_venv
    echo ""
fi
```

`prompt_install_pypy_if_tty` is a small new function: prints the prompt only if `[ -t 0 ]` and PyPy is not already installed; returns 0 if user types Y/y, else 1.

**Step 4 — Tests / integration verification**

Per CLAUDE.md "Test the full install flow for setup helpers": create a small bash test or shell session that does:

```bash
bash install.sh --dir /tmp/aitt718_1 --force
cd /tmp/aitt718_1
./ait setup --with-pypy
test -x ~/.aitask/pypy_venv/bin/python
~/.aitask/pypy_venv/bin/python -c "import sys; assert sys.implementation.name == 'pypy'; import textual"
AIT_USE_PYPY=1 ./.aitask-scripts/lib/python_resolve.sh  # source-and-call check via a test wrapper
```

The last line will need a small shim — a `tests/test_pypy_resolver.sh` similar to other test scripts, sourcing the lib and calling the new functions. Specifically test the precedence table above — three direct calls covering forced=1 / forced=0 / unset cases.

The integration test script does **not** need to live under the `tests/` runner harness for fresh installs — a manual repro listed in the plan's verification section is acceptable since the test would otherwise need to mutate `~/.aitask/`. Still, a small `tests/test_python_resolve_pypy.sh` for the unit logic of `require_ait_python_fast` (using `_AIT_RESOLVED_PYPY` overrides to fake an installed PyPy) is required.

## Verification Steps

1. `shellcheck .aitask-scripts/aitask_setup.sh .aitask-scripts/lib/python_resolve.sh` passes.
2. `bash tests/test_python_resolve_pypy.sh` (new) passes — covers the precedence table for `require_ait_python_fast`.
3. `bash install.sh --dir /tmp/aitt718_1 --force && cd /tmp/aitt718_1 && ./ait setup --with-pypy` completes without error and `~/.aitask/pypy_venv/bin/python -c 'import textual'` succeeds.
4. Without `--with-pypy`, `bash install.sh --dir /tmp/aitt718_1b --force && cd /tmp/aitt718_1b && ./ait setup` is byte-for-byte unchanged (`diff -ruN` with a baseline run on `main` should show no setup-script-induced differences in `~/.aitask/` apart from new venv timestamp). Smoke test: `~/.aitask/pypy_venv` does **not** exist after a no-flag run.
5. **No TUI launcher script is touched in this task** — `git diff --stat` should not show any of `aitask_board.sh`, `aitask_codebrowser.sh`, `aitask_settings.sh`, `aitask_stats_tui.sh`, `aitask_brainstorm_tui.sh`, `aitask_monitor.sh`, `aitask_minimonitor.sh`. They get updated in t718_2.

## Notes for sibling tasks

- t718_2 will rely on `require_ait_python_fast` from this task. The function's contract (precedence + zero-arg signature) is fixed by this task — do not change it without updating t718_2.
- The interactive `--with-pypy` prompt in `setup_python_venv` is a hint; t718_2 does **not** depend on the user having opted in. The fast-path functions handle the no-PyPy case silently.
- t718_3 (docs) will document the `AIT_USE_PYPY` env var and `--with-pypy` flag — make sure the helper messages printed by `install_pypy` and `setup_pypy_venv` are user-friendly (e.g., final summary line: "PyPy venv ready at $PYPY_VENV_DIR — TUIs will auto-use it").
