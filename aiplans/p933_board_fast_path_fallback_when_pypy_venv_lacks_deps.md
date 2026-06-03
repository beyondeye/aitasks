---
Task: t933_board_fast_path_fallback_when_pypy_venv_lacks_deps.md
Worktree: (none — profile 'fast', working on current branch)
Branch: main
Base branch: main
---

# Plan: Install-time validation of venv Python deps (t933)

## Context

`ait board` crashes at startup (from the TUI switcher and directly) on a machine
whose PyPy venv exists but is missing the board's runtime deps. Reproduced here:

- The board routes through the PyPy fast-path (`ait board` → `aitask_board.sh` →
  `require_ait_python_fast`), which prefers `~/.aitask/pypy_venv` whenever that
  venv exists and is PyPy — without checking that its deps import.
- This machine's `~/.aitask/pypy_venv` has **none** of `textual`/`pyyaml`/
  `linkify_it`; the CPython venv has all of them. So `aitask_board.sh`'s import
  guard `die`s with "Missing Python packages…", which in a switcher pane looks
  like a crash.
- The half-built PyPy venv is consistent with `ait setup` aborting between venv
  creation (`aitask_setup.sh:568`) and the dep-install line (`:573`) — the
  macOS/BSD setup crashes fixed in t931/t932.

**Chosen direction (per user):** fix this at **install time**, not at runtime.
`ait setup` must **always verify that all required Python deps are present in
both venvs** — the CPython venv always, and the PyPy venv whenever it exists —
and repair them. No runtime resolver/board changes.

Two gaps make today's `ait setup` insufficient:
1. **No post-install dep validation** for either venv — a partial install is
   never detected.
2. **An existing PyPy venv is never revalidated on a plain `ait setup`.**
   `setup_pypy_venv` only runs under `--with-pypy` or the fresh-install TTY
   prompt (`prompt_install_pypy_if_tty` returns 1 when the venv dir already
   exists, `:582`). So a broken existing PyPy venv is never touched/repaired.

## Approach

Make `ait setup` self-healing for venv deps:
1. **Single source of truth** for the dep specs (today duplicated inline at
   `:573` and `:654`), reused for both `pip install` and post-install validation.
2. **Post-install validation + repair** in each venv setup function — validating
   **both** (a) that every module imports, and (b) that the installed
   **version satisfies the pip spec** (e.g. `textual>=8.2.7,<9`), not just that
   the package is present.
3. **Always revalidate an existing PyPy venv** on every `ait setup`.
4. If the PyPy venv's deps can't be repaired, **remove the PyPy venv** so the
   (unchanged) fast-path resolver naturally falls back to the CPython venv —
   guaranteeing a working board without any runtime code.

All edits are in `.aitask-scripts/aitask_setup.sh` plus one new test. No changes
to `lib/python_resolve.sh` or `aitask_board.sh`.

## Changes — `.aitask-scripts/aitask_setup.sh`

### 1. Canonical dep arrays (single source of truth)

Define near the other top-level constants (after `python_resolve.sh` is sourced;
functions see these as globals). The two venvs share a common core; CPython adds
`minijinja` + `segno`. Parallel `*_IMPORTS` arrays give the import names to verify
(`pyyaml`→`yaml`, `linkify-it-py`→`linkify_it`).

```bash
# pip install specs — single source of truth (was duplicated at the two
# pip-install sites). PyPy gets COMMON only; CPython gets COMMON + EXTRA.
AIT_PIP_SPECS_COMMON=('textual>=8.2.7,<9' 'pyyaml==6.0.3' 'linkify-it-py==2.1.0' 'tomli>=2.4.0,<3' 'pexpect>=4.9,<5')
AIT_PIP_SPECS_CPYTHON_EXTRA=('minijinja>=2.0,<3' 'segno>=1.5,<2' 'plotext==5.3.2')
# Import names to verify (parallel to what each venv actually installs).
AIT_IMPORTS_COMMON=(textual yaml linkify_it tomli pexpect)
AIT_IMPORTS_CPYTHON_EXTRA=(minijinja segno plotext)
```

`plotext` is now a **required, version-pinned** CPython dep (was an interactive
opt-in) — installed and validated like every other dep. It stays **CPython-only**:
the PyPy venv is the board-only fast path and never uses plotext, and forcing it
there risks an install failure if no PyPy wheel exists (which would trigger the
PyPy-venv removal path). The interactive plotext prompt is removed (see §3).

### 2. Validation helpers (importability **and** version)

Add near the other helpers. Two complementary checks: importability (catches the
exact board failure — module not importable) and version-range compliance
(catches an installed-but-wrong-version package).

```bash
# verify_venv_imports <python> <module>... — populate global `missing_imports`
# with the modules that fail to import under the given interpreter.
verify_venv_imports() {
    local py="$1"; shift
    missing_imports=()
    local mod
    for mod in "$@"; do
        "$py" -c "import $mod" 2>/dev/null || missing_imports+=("$mod")
    done
}

# verify_venv_specs <python> <pip-spec>... — populate global `bad_specs` with
# distributions that are missing OR whose installed version violates the spec.
# Uses pip's vendored packaging (no extra dependency — pip is in every venv);
# importlib.metadata.version() resolves the distribution name from each spec
# (e.g. pyyaml, linkify-it-py), independent of the import name.
verify_venv_specs() {
    local py="$1"; shift
    bad_specs=()
    local out
    out="$("$py" - "$@" <<'PY' 2>/dev/null
import sys
try:
    from packaging.requirements import Requirement
except ImportError:
    from pip._vendor.packaging.requirements import Requirement
from importlib.metadata import version, PackageNotFoundError
for spec in sys.argv[1:]:
    req = Requirement(spec)
    try:
        inst = version(req.name)
    except PackageNotFoundError:
        print(f"{req.name} (missing)"); continue
    if not req.specifier.contains(inst, prereleases=True):
        print(f"{req.name} {inst} (need {req.specifier})")
PY
)" || out=""
    [[ -n "$out" ]] && while IFS= read -r line; do bad_specs+=("$line"); done <<< "$out"
}
```

### 3. CPython venv — install from arrays + validate (fatal on failure)

In `setup_python_venv`:
- **Remove the interactive plotext opt-in** — the `install_plotext` prompt block
  (`:635-643`) and the conditional `if [[ "$install_plotext" == true ]] … else …`
  install block (`:662-667`). plotext is now installed unconditionally via the
  CPython array.
- Replace the inline spec at `:654` with
  `"${AIT_PIP_SPECS_COMMON[@]}" "${AIT_PIP_SPECS_CPYTHON_EXTRA[@]}"` (which now
  includes plotext); keep the `textual_before/after` diff logic.
- After the install, validate **importability + versions** with one retry, then
  `die` if still bad — the framework cannot run without its core venv:

```bash
verify_venv_imports "$VENV_DIR/bin/python" "${AIT_IMPORTS_COMMON[@]}" "${AIT_IMPORTS_CPYTHON_EXTRA[@]}"
verify_venv_specs   "$VENV_DIR/bin/python" "${AIT_PIP_SPECS_COMMON[@]}" "${AIT_PIP_SPECS_CPYTHON_EXTRA[@]}"
if [[ ${#missing_imports[@]} -gt 0 || ${#bad_specs[@]} -gt 0 ]]; then
    warn "CPython venv deps need repair (missing: ${missing_imports[*]:-none}; version: ${bad_specs[*]:-none}). Retrying..."
    "$VENV_DIR/bin/pip" install --quiet "${AIT_PIP_SPECS_COMMON[@]}" "${AIT_PIP_SPECS_CPYTHON_EXTRA[@]}"
    verify_venv_imports "$VENV_DIR/bin/python" "${AIT_IMPORTS_COMMON[@]}" "${AIT_IMPORTS_CPYTHON_EXTRA[@]}"
    verify_venv_specs   "$VENV_DIR/bin/python" "${AIT_PIP_SPECS_COMMON[@]}" "${AIT_PIP_SPECS_CPYTHON_EXTRA[@]}"
    [[ ${#missing_imports[@]} -gt 0 || ${#bad_specs[@]} -gt 0 ]] && \
        die "CPython venv still bad (missing: ${missing_imports[*]:-none}; version: ${bad_specs[*]:-none}). Check pip/network and re-run 'ait setup'."
fi
```

### 4. PyPy venv — install from arrays + validate (remove venv on failure)

Restructure `setup_pypy_venv` so the **revalidate-existing** path is cheap (no
`find_pypy`/`install_pypy` when the venv is already a valid PyPy venv), then
always install + validate deps; if deps can't be made to import, remove the venv
so the fast-path falls back to CPython:

```bash
setup_pypy_venv() {
    local pypy_cmd="" have_valid_venv=false impl=""
    if [[ -x "$PYPY_VENV_DIR/bin/python" ]]; then
        impl="$("$PYPY_VENV_DIR/bin/python" -c 'import sys; print(sys.implementation.name)' 2>/dev/null)" || impl=""
        [[ "$impl" == "pypy" ]] && have_valid_venv=true
    fi
    if [[ "$have_valid_venv" == true ]]; then
        info "PyPy virtual environment already exists at $PYPY_VENV_DIR"
    else
        pypy_cmd="$(find_pypy)"
        if [[ -z "$pypy_cmd" ]]; then
            info "No PyPy $AIT_PYPY_PREFERRED found. Installing one..."
            install_pypy
            pypy_cmd="$(find_pypy)"
            [[ -z "$pypy_cmd" ]] && die "PyPy install completed but interpreter still not found."
        fi
        info "Using PyPy for venv: $pypy_cmd ($("$pypy_cmd" --version 2>&1 | head -1))"
        rm -rf "$PYPY_VENV_DIR"
        mkdir -p "$(dirname "$PYPY_VENV_DIR")"
        "$pypy_cmd" -m venv "$PYPY_VENV_DIR"
    fi

    info "Installing/upgrading Python deps into PyPy venv..."
    "$PYPY_VENV_DIR/bin/pip" install --quiet --upgrade pip
    "$PYPY_VENV_DIR/bin/pip" install --quiet "${AIT_PIP_SPECS_COMMON[@]}"

    verify_venv_imports "$PYPY_VENV_DIR/bin/python" "${AIT_IMPORTS_COMMON[@]}"
    verify_venv_specs   "$PYPY_VENV_DIR/bin/python" "${AIT_PIP_SPECS_COMMON[@]}"
    if [[ ${#missing_imports[@]} -gt 0 || ${#bad_specs[@]} -gt 0 ]]; then
        warn "PyPy venv deps need repair (missing: ${missing_imports[*]:-none}; version: ${bad_specs[*]:-none}). Retrying..."
        "$PYPY_VENV_DIR/bin/pip" install --quiet "${AIT_PIP_SPECS_COMMON[@]}"
        verify_venv_imports "$PYPY_VENV_DIR/bin/python" "${AIT_IMPORTS_COMMON[@]}"
        verify_venv_specs   "$PYPY_VENV_DIR/bin/python" "${AIT_PIP_SPECS_COMMON[@]}"
    fi
    if [[ ${#missing_imports[@]} -gt 0 || ${#bad_specs[@]} -gt 0 ]]; then
        warn "PyPy venv deps could not be installed (missing: ${missing_imports[*]:-none}; version: ${bad_specs[*]:-none}). Removing $PYPY_VENV_DIR so the board uses the CPython venv. Re-run 'ait setup --with-pypy' to retry."
        rm -rf "$PYPY_VENV_DIR"
        return 0
    fi
    success "PyPy venv ready at $PYPY_VENV_DIR — TUIs will auto-use it (set AIT_USE_PYPY=0 to override)."
}
```

This subsumes the old exists/impl branch (`:556-569`) — the recreate-on-bad-impl
case is now the `else` (rm + recreate) path.

### 5. `main()` — always revalidate an existing PyPy venv

Change the gate (`:3005`) so an existing PyPy venv is repaired on every
`ait setup`, while the fresh-install TTY prompt still only fires when no venv
exists (`prompt_install_pypy_if_tty` already returns 1 if the dir exists, so it
isn't reached when the dir clause is true — no double prompt):

```bash
if [[ "$INSTALL_PYPY" == "1" ]] || [[ -d "$PYPY_VENV_DIR" ]] || prompt_install_pypy_if_tty; then
    setup_pypy_venv
    echo ""
fi
```

### 6. Docs — reflect plotext as a required, pinned dep (current-state only)

plotext is documented as "optional / prompted" in several places. Update the
current-state docs to say it's installed and pinned like the other deps and drop
the prompt wording (per `documentation_conventions.md`). Historical records
(`CHANGELOG.md`, `CHANGELOG_HUMANIZED.md`, `website/content/blog/*`) are **not**
edited.

- `website/content/docs/commands/setup-install.md` (`:29`, `:49`) — remove the
  "prompts `Install plotext…?`" / "re-run and answer `y`" wording; list plotext
  as an always-installed pinned dep.
- `website/content/docs/tuis/stats/_index.md` (`:22`) — drop "optional" + prompt
  sentence; plotext is always present in the CPython venv.
- `website/content/docs/installation/_index.md` (`:123`) — move plotext out of
  the "optional … when enabled" parenthetical into the pinned dep list.
- `website/content/docs/commands/board-stats.md` (`:84`) — drop "optional … when
  prompted".
- `aidocs/framework/python_tui_performance.md` (`:28`) — drop "optional" before
  `plotext==5.3.2`.
- `aidocs/framework/tui_conventions.md` (`:32`) — already accurate ("installed
  only in the CPython venv"); no change needed beyond confirming it doesn't call
  plotext optional.

Defensive runtime fallbacks for a missing plotext (`stats/panes/base.py`
placeholder, `aitask_stats_tui.sh` import guard) are left as-is — harmless now
that plotext is guaranteed, and still graceful if a user removes it manually.

## Test — `tests/test_setup_verify_venv_imports.sh` (new)

`aitask_setup.sh` supports `--source-only` (tail: `[[ "${1:-}" == "--source-only" ]] && return 0`),
so source it and unit-test both validators against bash stub interpreters
(pattern from `tests/test_python_resolve_pypy.sh`, `tests/lib/asserts.sh`):

`verify_venv_imports`:
- Stub python where `import sys`/`import textual` succeed → `missing_imports` empty.
- Stub python where a given module exits 1 → that module appears in `missing_imports`.
- Mixed set → only the absent modules are collected, in order.

`verify_venv_specs` (version validation):
- Stub python whose stdin-script run prints nothing → `bad_specs` empty (all in range).
- Stub that prints `textual 7.0.0 (need >=8.2.7,<9)` → `bad_specs` carries it.
- Stub that prints `segno (missing)` → `bad_specs` carries the missing line.

Stubs special-case the two invocation shapes the helpers use: `-c "import <mod>"`
(exit 0/1 from a manifest) and `-` (read script from stdin; echo a canned
problem-list, simulating the importlib.metadata/packaging output) — deterministic
and independent of host site-packages.

Heavier end-to-end repair behavior (gate revalidation, venv removal) is covered
by the manual verification below; the existing `test_setup_python_install.sh`
integration test (gated by `AIT_RUN_INTEGRATION_TESTS=1`) continues to cover real
venv builds.

## Verification

1. **Repro → repair (the reported bug).** With the current broken PyPy venv in
   place, run plain `ait setup` (no flags). Expect: it detects the existing PyPy
   venv, reinstalls + validates its deps, and reports success — then `ait board`
   (and the TUI switcher → Board) launches on PyPy without crashing.
2. **CPython validation fatal-path.** Confirm a CPython venv missing a core dep
   (or holding an out-of-range version) is detected and reinstalled; if
   unrepairable, setup dies with a clear message naming the missing/version-bad
   distributions.
3. **PyPy unrepairable → fallback.** Simulate a PyPy venv whose deps can't
   install; confirm setup removes `~/.aitask/pypy_venv` and the board then runs on
   CPython (resolver returns the CPython venv when no PyPy venv exists).
4. **Fast path intact when healthy.** On a complete PyPy venv, `ait setup` reports
   "already exists" + success with no recreate, and `ait board` uses PyPy.
5. **plotext now unconditional.** `ait setup` no longer prompts for plotext, and
   `~/.aitask/venv/bin/python -c "import plotext"` succeeds after a plain setup.
6. **Unit + lint:** `bash tests/test_setup_verify_venv_imports.sh`;
   `shellcheck .aitask-scripts/aitask_setup.sh`. Hugo build of the website if docs
   changed: `cd website && hugo build --gc --minify`.

See **Step 9 (Post-Implementation)** of the task-workflow for archival/merge.

## Out of scope / follow-ups

- Pushing the dep list to a shared `requirements`-style file consumed by `seed/`
  too — kept within `aitask_setup.sh` for now; note in Final Implementation Notes
  if worth a separate single-source-of-truth task.
- No runtime resolver/board fallback is added (explicitly per user direction).

## Risk

### Code-health risk: medium
- Touches the load-bearing `ait setup` install flow and adds a destructive
  `rm -rf "$PYPY_VENV_DIR"` on the unrepairable-PyPy path. · severity: medium · → mitigation: rm is tightly guarded (only after two failed dep installs into the dedicated pypy_venv dir, never the CPython venv); manual verification step 3.
- `setup_pypy_venv` restructure changes the existing/recreate branching. · severity: low · → mitigation: behavior preserved (valid venv → reuse; otherwise recreate); manual verification step 4 + shellcheck.
- Dep-spec arrays replace two inline lists — must stay in sync with what each venv installs. · severity: low · → mitigation: single source of truth removes the prior duplication rather than adding to it.
- plotext promoted from opt-in to always-installed: enlarges the base install and makes it a hard dep of `ait setup` succeeding. · severity: low · → mitigation: pinned (`==5.3.2`, existing version), CPython-only, widely available wheel; current-state docs updated to match.

### Goal-achievement risk: low
- Approach directly delivers the user's ask (always validate both venvs at
  install time, repair, and guarantee a working board) and resolves the
  reproduced crash on `ait setup` re-run. · severity: low · → mitigation: manual verification step 1.

## Final Implementation Notes

- **Actual work done:** Implemented exactly as planned in `.aitask-scripts/aitask_setup.sh`:
  single-source dep arrays (`AIT_PIP_SPECS_COMMON`/`AIT_PIP_SPECS_CPYTHON_EXTRA` +
  parallel `AIT_IMPORTS_*`), two validators (`verify_venv_imports`,
  `verify_venv_specs`), CPython post-install validate+retry+die, PyPy
  cheap-revalidate/validate+retry/remove-on-failure, and the `main()` gate now
  revalidates an existing PyPy venv on every `ait setup`. plotext promoted to a
  required pinned dep (opt-in prompt removed). Added
  `tests/test_setup_verify_venv_imports.sh` (8 tests) and updated 5 current-state
  docs.
- **Deviations from plan:** None structurally. One addition surfaced during
  testing (see below): both validators got an explicit `return 0`.
- **Issues encountered:** Smoke-testing under `set -euo pipefail` revealed that
  `verify_venv_specs`'s final statement (`[[ -n "$out" ]] && while …`) returns 1
  when there are no bad specs — and since `setup_python_venv`/`setup_pypy_venv`
  call the helper as a bare command under `set -e`, that would have aborted setup
  on the (common) all-deps-valid path. Fixed by ending both helpers with
  `return 0` (result is communicated via the global arrays, not the exit code).
  Verified the fix survives `set -e` to the end.
- **Key decisions:**
  - Version validation uses `importlib.metadata.version()` (keyed on the
    distribution name parsed from each pip spec — so `pyyaml`/`linkify-it-py`
    resolve correctly) + `pip._vendor.packaging.requirements.Requirement` as a
    dependency-free fallback when top-level `packaging` is absent (it is, in the
    venv). Confirmed range checks work positive and negative.
  - Two complementary checks kept separate: imports (by import name) catch the
    exact board failure mode (not-importable); specs (by dist name) catch
    installed-but-wrong-version.
  - PyPy unrepairable → `rm -rf "$PYPY_VENV_DIR"` so the unchanged fast-path
    resolver (`resolve_pypy_python` returns empty when the dir is gone) falls back
    to the CPython venv. No runtime resolver/board changes (per user direction).
  - plotext stays CPython-only — the PyPy venv is the board-only fast path and
    never uses plotext; forcing it there risks a no-PyPy-wheel install failure
    that would trigger venv removal.
- **Upstream defects identified:** None.
- **Verification:** `bash tests/test_setup_verify_venv_imports.sh` → 8/8;
  `bash tests/test_python_resolve_pypy.sh` (untouched resolver) → 9/9 regression;
  `bash -n` clean; no new shellcheck findings in the added code. Confirmed the
  validators flag the real broken `~/.aitask/pypy_venv` (all 5 common deps
  missing), so a re-run of `ait setup` repairs it. Full end-to-end `ait setup` +
  `ait board` launch is the user's manual verification step.
