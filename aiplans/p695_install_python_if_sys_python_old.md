---
Task: t695_install_python_if_sys_python_old.md
Base branch: main
plan_verified: []
---

# Plan — t695: Install newer Python for venv if system Python is too old

## Context

On macOS the system Python is typically 3.9.x, which is now too old for several
of aitasks's TUI dependencies (the user reported `linkify-it-py` failing in the
venv). The framework already has partial scaffolding:

- `${PYTHON:-python3}` env-var fallback in ~9 TUI launchers.
- `aitask_setup.sh::check_python_version()` enforces a 3.9+ floor and offers
  `brew install python@3` on macOS if missing.
- `setup_python_venv()` creates `~/.aitask/venv/` with `textual`, `pyyaml`,
  `linkify-it-py`, `tomli` pinned.
- `install_cli_tools()` (called early in `ait setup`) lays down `python3` via
  apt/dnf/pacman/brew per OS.

What's missing — and what this task adds — is a deliberate split between the
**system Python** (3.9+ baseline; only used by `install.sh`'s pre-setup merge
step) and the **venv Python** (must be ≥3.11 to support the TUI deps), plus a
**resilient resolution layer** so scripts running in remote sandboxes
(`aitask-pick-rem`, `aitask-pick-web` — where `~/.aitask/` doesn't exist) can
still find a usable interpreter without crashing.

User-confirmed design choices (resolved across two plan-mode Q&A rounds):

1. **System Python floor stays at 3.9+**; only the venv interpreter is upgraded.
2. **Discovery layer = lib helper (`lib/python_resolve.sh`) sourced by every
   Python-invoking script**, with a `~/.aitask/bin/python3` symlink as the
   fast path for local setups. The helper resolves in priority:
   `$AIT_PYTHON` → `~/.aitask/bin/python3` → `~/.aitask/venv/bin/python` →
   system `python3` → empty. Cached per shell. This works on local installs
   (returns venv-Python) and on remote sandboxes (falls back to system
   `python3`) without forking script logic.
3. **Linux auto-install — strictly local, no sudo, no system-wide changes**:
   download `astral-sh/uv` (a small static binary, ~30MB) into
   `~/.aitask/uv/bin/uv`, then run `uv python install 3.13` which fetches a
   prebuilt python-build-standalone interpreter into uv's managed area. We
   then symlink the chosen interpreter into a stable path
   (`~/.aitask/python/3.13/bin/python3`) for venv creation. The system
   `python3` is **not** touched. Distro package managers (`apt`/`dnf`/
   `pacman`) are deliberately *not* used because they require sudo and
   modify the user's system — keeping the whole flow inside `~/.aitask/`
   matches macOS's brew-install pattern in spirit (user-scoped tooling)
   while staying portable across distros.
4. **macOS auto-install**: re-use the existing `brew install python@3.13`
   flow already in `check_python_version()`.
5. **Split into 4 implementation children + 1 aggregate manual verification
   sibling.**

The venv-Python floor will be **3.11+** (broad ecosystem support; matches
`brew install python@3.13`, `apt install python3.11`, and uv's default
distributions). Configurable via `AIT_VENV_PYTHON_MIN` env var.

## Overall Approach

### t695_1 — `lib/python_resolve.sh` helper + `$AIT_PYTHON` env override

Pure additive change — introduces the resolution layer ahead of any
behavior change. Safe to land first; nothing depends on it yet.

Critical files:
- `.aitask-scripts/lib/python_resolve.sh` (new — sourced lib, no whitelisting)

Behavior:
- Function `resolve_python()` returns the first executable Python in priority
  order: `$AIT_PYTHON` → `~/.aitask/bin/python3` → `~/.aitask/venv/bin/python`
  → `command -v python3`. Empty stdout if none. Caches in
  `_AIT_RESOLVED_PYTHON` for the lifetime of the shell.
- Function `require_python()` calls `resolve_python()` and `die`s with a
  clear error if empty (suggests running `ait setup` locally, or installing
  a system `python3` for remote use).
- Function `require_modern_python <min_version>` validates the resolved
  interpreter meets `<min_version>` (using
  `python3 -c "import sys; sys.exit(0 if sys.version_info >= (M, m) else 1)"`)
  and offers a clear error message identifying which fallback was used and
  what's missing. For TUI launchers that need linkify/textual.
- Standard `_AIT_PYTHON_RESOLVE_LOADED` double-source guard.
- All output via `info()`/`warn()`/`die()` from `terminal_compat.sh`.

### t695_2 — venv-Python upgrade flow in `setup_python_venv()` (macOS + Linux)

Modifies the existing setup function to install a newer Python when none
is available, then build the venv on top of it.

Critical files:
- `.aitask-scripts/aitask_setup.sh` (modify `setup_python_venv()`,
  `check_python_version()`, possibly extract a new
  `install_modern_python()` helper)

Behavior:
- New constant `AIT_VENV_PYTHON_MIN="3.11"` near the top of `aitask_setup.sh`,
  overridable via env var.
- New helper `find_modern_python <min_version>` searches PATH for
  `python3.13`, `python3.12`, `python3.11` (or whatever ≥ min) and returns
  the highest available; empty if none.
- New helper `install_modern_python` (OS-dispatched via `detect_os()`):
  - **macOS**: re-use the brew flow currently in `check_python_version()`
    lines 395–428 — extract it for reuse and adapt to install
    `python@3.13` (or whichever satisfies `AIT_VENV_PYTHON_MIN`). User-space
    via Homebrew; no system-wide changes.
  - **Linux (Debian/Ubuntu/WSL/Fedora/Arch/unknown)**: strictly local,
    no sudo. Download the static `uv` binary from
    `https://github.com/astral-sh/uv/releases/latest` (or use the official
    `curl -LsSf https://astral.sh/uv/install.sh | sh` redirected to a
    framework-managed dir) into `~/.aitask/uv/bin/uv`. Run `uv python
    install 3.13` to fetch a python-build-standalone interpreter into uv's
    managed dir, then symlink the chosen interpreter into
    `~/.aitask/python/3.13/bin/python3` for stable lookup. The system
    `python3` is never modified.
  - Distro package managers (`apt install python3.13`, etc.) are
    **intentionally not used** — they require sudo and modify the user's
    system. Keeping all framework Python tooling in `~/.aitask/` matches
    the user-scoped spirit of macOS's brew flow and is portable across
    distros.
- `setup_python_venv()` flow:
  1. Try `find_modern_python`. If found → use it for venv creation.
  2. Else → call `install_modern_python` (interactive prompt with
     auto-accept on `--yes` flag respect — match existing patterns).
  3. After install, re-run `find_modern_python`. If still empty → abort with
     clear error.
  4. Create `~/.aitask/venv/` using the resolved interpreter (existing
     code path, just parameterized).
- `check_python_version()`'s 3.9 floor stays — it's the floor for
  `aitask_install_merge.py` (which runs from `install.sh` before the venv
  exists) and bash-bootstrap callers.

### t695_3 — `~/.aitask/bin/python3` symlink + PATH integration

The fast path for local setups. After this lands, scripts (and
shebang-driven `.py` files) automatically resolve to the venv-Python via
PATH without sourcing the helper.

Critical files:
- `.aitask-scripts/aitask_setup.sh` (modify `setup_python_venv()` and
  `ensure_path_in_profile()`)

Behavior:
- After successful venv creation, create:
  ```bash
  mkdir -p "$HOME/.aitask/bin"
  ln -sf "$VENV_DIR/bin/python" "$HOME/.aitask/bin/python3"
  ln -sf "$VENV_DIR/bin/python" "$HOME/.aitask/bin/python"
  ```
- Extend `ensure_path_in_profile()` to also export `~/.aitask/bin` to PATH,
  placed **before** `~/.local/bin` so the framework's interpreter wins over
  the system one.
- Setup output prints a one-liner explaining the new PATH entry on first
  install ("Added ~/.aitask/bin to your PATH; reload your shell or
  re-source your rc file to use `python3` from the framework venv").

### t695_4 — Refactor direct `python3` callers to source the helper

Migrates every script that currently invokes Python to use the helper, so
remote-sandbox flows resolve gracefully.

Critical files (modify, all in `.aitask-scripts/`):

| File | Current | After |
| ---- | ------- | ----- |
| `aitask_verification_parse.sh:4` | `exec python3 …` | source helper, `exec "$(resolve_python)" …` |
| `aitask_explain_context.sh:245`  | `python3 …`      | source helper, `"$(resolve_python)" …` |
| `aitask_board.sh:14,37`          | `${PYTHON:-python3}` | source helper, use cached `$_AIT_RESOLVED_PYTHON` |
| `aitask_minimonitor.sh:14,53`    | `${PYTHON:-python3}` | same |
| `aitask_settings.sh:14`          | `${PYTHON:-python3}` | same |
| `aitask_crew_status.sh:21`       | `${PYTHON:-python3}` | same |
| `aitask_crew_runner.sh:21`       | `${PYTHON:-python3}` | same |
| `aitask_brainstorm_archive.sh:24`| `${PYTHON:-python3}` | same |
| `aitask_sync.sh:39-44`           | venv-then-python3 fallback | replace with helper (which already does this) |

Audit (no edits unless an issue surfaces):
- `install.sh:263` — `python3 ./.aitask-scripts/aitask_install_merge.py` runs
  **before** `ait setup`, so the helper isn't yet sourceable. Keep as
  `python3` (system) and add a clarifying comment. The merge script only
  needs `pyyaml`, which install.sh ensures via earlier prerequisites.
- `seed/geminicli_policies/aitasks-whitelist.toml:471` — already uses literal
  `python3`. The PATH symlink keeps the literal name correct, so no change.
- 13 `.py` files with `#!/usr/bin/env python3` shebangs — only matter when
  invoked as executables. Once the PATH symlink is in place, shebangs
  resolve to venv-Python on local installs. For remote sandboxes, shebangs
  resolve to system python3 (which won't have textual/linkify) — so any
  `.py` file invoked directly must guard imports with a clear error
  message. Audit and fix per child task.

### Aggregate manual verification sibling (offered after child plans commit)

Will be created via the `manual-verification-followup` flow. Covers:

- macOS with system Python 3.9: full `bash install.sh --dir /tmp/scratchXY`
  → `cd /tmp/scratch695; ait setup` → verify brew install path → board TUI
  loads → URLs are linkified.
- Debian 11 / Ubuntu 22.04 with old python3: setup downloads uv into
  `~/.aitask/uv/`, runs `uv python install 3.13`, builds venv on top →
  board TUI loads. Verify nothing was sudo-installed system-wide.
- Remote sandbox simulation: in a directory without `~/.aitask/`, run a
  Python-invoking workflow script (e.g., `aitask_verification_parse.sh`
  on a sample input) and verify it falls back to system `python3`
  without crashing.
- Verify all TUI launchers (board, monitor, brainstorm, codebrowser,
  settings) load `linkify_it`, `textual`, `yaml` without error.

## Critical files to read during implementation

| Purpose                                  | Path                                                   |
| ---------------------------------------- | ------------------------------------------------------ |
| OS detection                             | `.aitask-scripts/aitask_setup.sh:21-69` (`detect_os`)  |
| Existing brew install flow               | `.aitask-scripts/aitask_setup.sh:372-432` (`check_python_version`) |
| Venv creation                            | `.aitask-scripts/aitask_setup.sh:435-511` (`setup_python_venv`) |
| Existing `${PYTHON:-python3}` pattern    | `.aitask-scripts/aitask_board.sh:14,37`                |
| PATH profile management                  | `.aitask-scripts/aitask_setup.sh:516+` (`ensure_path_in_profile`) |
| Lib helper style + double-source guard   | `.aitask-scripts/lib/terminal_compat.sh:1-30, 80-96`   |
| Test pattern (per CLAUDE.md t624 lesson) | `tests/test_release_tarball.sh` (uses `bash install.sh --dir /tmp/...`) |
| uv install reference                     | https://github.com/astral-sh/uv (install script + `uv python install`) |

## Verification

Per-child verification:

- **t695_1**: stub-PATH unit test — lay down fake `python3.X` binaries in a
  scratch PATH and verify resolver picks the highest. Test cache behavior
  (call resolver twice, second is no-op). Test `$AIT_PYTHON` override wins.
- **t695_2**: integration test runs `bash install.sh --dir /tmp/scratchXY`
  end-to-end with a controlled environment (e.g., system `python3` aliased
  to 3.9) and verifies that after setup, `~/.aitask/venv/bin/python -V`
  returns ≥3.11, and that `python -c "import linkify_it"` succeeds.
- **t695_3**: verify `~/.aitask/bin/python3 -V` returns the venv-Python
  version, and that adding `~/.aitask/bin` to PATH makes shell `python3`
  resolve to it.
- **t695_4**: each refactored script gets a smoke test (e.g., run
  `aitask_verification_parse.sh` on a fixture and verify it produces
  expected output without crashing on various Python availability
  scenarios). Run with `AIT_PYTHON` unset / set / pointing at missing
  binary.
- **Aggregate manual sibling**: covers anything the unit/integration tests
  can't (TUI rendering, real brew/apt install paths, real macOS-3.9 host).

## Step 9 (Post-Implementation)

Per the standard task-workflow Step 9 — after the last child commits and the
aggregate verification sibling completes, archive the parent and run any
linked-issue/PR cleanup. No special branch/worktree was created (profile
`fast` set `create_worktree: false`), so the worktree-cleanup sub-step is a
no-op. Build verification (`verify_build`) runs whatever the project config
defines; check at archival time.

## Touchpoints checklist (per CLAUDE.md "Adding a New Helper Script")

`lib/python_resolve.sh` is sourced (not invoked directly) — **no whitelist
entries needed** for any of the 5 touchpoints. No new top-level scripts in
`.aitask-scripts/` are introduced by this plan. The uv binary download
in t695_2 places the binary under `~/.aitask/uv/`, not in
`.aitask-scripts/`, so it doesn't need whitelisting either.
