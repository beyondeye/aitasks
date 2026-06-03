---
priority: high
effort: medium
depends: []
issue_type: bug
status: Implementing
labels: [aitask_board, pypy, crash_recovery, ait_setup, bash_scripts]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-06-03 17:30
updated_at: 2026-06-03 17:31
---

## Problem

`ait board` crashes at startup when launched from the TUI switcher (and directly) on a machine whose PyPy venv exists but is missing the board's runtime dependencies. The board appears to "crash at start" — in a freshly-spawned tmux switcher pane the error flashes and the window exits.

## Root cause

The board routes through the PyPy fast-path:

- The TUI switcher launches the board via the `ait board` command (`.aitask-scripts/lib/tui_registry.py:18`) → `.aitask-scripts/aitask_board.sh`.
- `aitask_board.sh` resolves its interpreter via `require_ait_python_fast` (`.aitask-scripts/lib/python_resolve.sh`).
- `require_ait_python_fast` → `resolve_pypy_python` **prefers `~/.aitask/pypy_venv/bin/python` whenever that venv exists and reports `sys.implementation.name == 'pypy'`**. It only checks that the interpreter *is* PyPy — it does **not** verify that the board's runtime deps (`textual`, `pyyaml`, `linkify_it`) are importable, and there is **no fallback** to the working CPython venv (`~/.aitask/venv`).
- When the PyPy venv lacks those deps, `aitask_board.sh`'s own import guard fires and `die`s with "Missing Python packages: textual pyyaml linkify-it-py. Run 'ait setup'…". In an interactive shell that's a clear message; in a spawned switcher pane it reads as a crash.

Observed on this machine: `~/.aitask/pypy_venv` has **none** of `textual` / `pyyaml` / `linkify_it`, while `~/.aitask/venv` (CPython) has all of them (textual 8.2.7). So the board *could* run fine on the CPython venv, but the fast-path never falls back.

## Why the PyPy venv is half-built

`setup_pypy_venv` (`.aitask-scripts/aitask_setup.sh`) *does* install these deps (`aitask_setup.sh:573`) — but only **after** creating the venv directory (`:568`). If `ait setup` aborts between those two steps, the result is a created-but-depless PyPy venv with nothing to detect or repair it on subsequent launches. This is consistent with the macOS/BSD `ait setup` portability crashes just fixed in t931/t932.

## Two distinct gaps to address

1. **Runtime resolver has no integrity check / no fallback.** `resolve_pypy_python` should not be trusted as "fast python" unless the board's deps actually import; otherwise the fast-path should gracefully fall back to the CPython venv (`require_ait_python`) rather than letting the launcher `die`. Consider an importable-deps probe in the fast-path (or in `aitask_board.sh`: on missing deps under PyPy, retry with `AIT_USE_PYPY=0` before dying).

2. **Setup leaves an unrecoverable state.** A mid-install crash yields a depless PyPy venv. Consider: install deps into a temp/secondary location and only promote on success, or re-validate venv deps on `setup_pypy_venv` re-run (the existing "already exists" branch at `:558` still reaches the unconditional pip line, so a re-run repairs it — but nothing triggers a re-run automatically).

## Suggested fix direction

Primary: make the board fast-path degrade gracefully — verify (or probe) board deps under the resolved PyPy interpreter, and fall back to the CPython venv when they're missing, instead of dying. This restores a working board even with a broken/partial PyPy venv. Emit a one-line warning so the user knows to re-run `ait setup --with-pypy` to restore the fast path.

Secondary (hardening): make `setup_pypy_venv` resilient to partial installs so it doesn't leave a depless venv behind.

## Affected files

- `.aitask-scripts/lib/python_resolve.sh` — `resolve_pypy_python`, `require_ait_python_fast`
- `.aitask-scripts/aitask_board.sh` — import guard / fallback retry
- `.aitask-scripts/aitask_setup.sh` — `setup_pypy_venv` install ordering/validation

## Reproduction

1. `~/.aitask/pypy_venv` exists but lacks `textual`/`pyyaml`/`linkify_it` (e.g. interrupted `ait setup --with-pypy`).
2. Launch `ait board` (or pick "Board" from the TUI switcher `j`).
3. Board dies with "Missing Python packages" instead of falling back to the CPython venv.

Immediate workaround: `AIT_USE_PYPY=0 ait board`, or `rm -rf ~/.aitask/pypy_venv`, or re-run `ait setup --with-pypy`.

## Out of scope / related (not folded)

- t729 (manual-verification checklist for PyPy install on macOS) — adjacent but a verification chore, not this fallback fix.
- t926 (periodic macOS-compat audit) — broad audit; this is a specific runtime-robustness bug.

## Notes

Tested on macOS (Darwin 24.6.0). The fast-path scoping decision (board-only PyPy) is documented in `aidocs/framework/python_tui_performance.md`; see also `aidocs/framework/shell_conventions.md` for the source-on-startup conventions around `python_resolve.sh`.
