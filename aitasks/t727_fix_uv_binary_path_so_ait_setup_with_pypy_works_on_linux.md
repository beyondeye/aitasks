---
priority: high
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [ait_setup, python, installation]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-04-30 15:38
updated_at: 2026-04-30 15:38
---

## Symptom

Running `ait setup --with-pypy` on Linux fails with:

```
[ait] Downloading uv (astral-sh/uv) into /home/<user>/.aitask/uv...
downloading uv 0.11.8 x86_64-unknown-linux-gnu
installing to /home/<user>/.aitask/uv
  uv
  uvx
everything's installed!
[ait] Installing PyPy 3.11 via uv...
.aitask-scripts/aitask_setup.sh: line 505: /home/<user>/.aitask/uv/bin/uv: No such file or directory
[ait] Error: uv python install pypy@3.11 failed.
```

## Root Cause

uv 0.11.8's installer places the `uv` and `uvx` binaries directly inside `$UV_INSTALL_DIR` — i.e., `~/.aitask/uv/uv` and `~/.aitask/uv/uvx`. There is no `bin/` subdirectory.

`.aitask-scripts/aitask_setup.sh` references `$uv_dir/bin/uv` at six sites across two near-duplicate functions:

- `_install_modern_python_linux` — lines 423, 434, 437
- `_install_pypy_linux` — lines 494, 505, 508

Both functions also duplicate an 11-line "download uv if missing → run uv python install" block. The bug is identical in both copies; only the PyPy path is exercised in this report because the user already had a system Python 3.11+, so `_install_modern_python_linux` was skipped.

## Verification

```bash
$ ls /home/ddt/.aitask/uv/
uv  uvx
$ /home/ddt/.aitask/uv/uv --version
uv 0.11.8 (x86_64-unknown-linux-gnu)
$ ls /home/ddt/.aitask/uv/bin/
ls: cannot access '/home/ddt/.aitask/uv/bin/': No such file or directory
```

The binary works at the actual install location.

## Fix Scope

1. **Correct the path.** Replace `$uv_dir/bin/uv` with `$uv_dir/uv` at all six call sites in `.aitask-scripts/aitask_setup.sh` (lines 423, 434, 437, 494, 505, 508). After the fix, the existing `~/.aitask/uv/uv` binary from the failed run is detected by the corrected `[[ ! -x "$uv_dir/uv" ]]` check, so the user can re-run `ait setup --with-pypy` with no manual cleanup.

2. **Single source of truth — extract `_ensure_uv()` helper.** The 11-line uv install/check block is duplicated verbatim between `_install_modern_python_linux` and `_install_pypy_linux`. Per the project's "single source of truth for cross-script constants" rule, extract a small helper (in `aitask_setup.sh` or a new `lib/uv_resolve.sh`) that:
   - Locates an existing usable `uv` binary, or downloads one into `~/.aitask/uv` if absent.
   - Echoes the absolute path to the `uv` binary on stdout.
   - Both install functions then call `local uv_bin; uv_bin="$(_ensure_uv)"` and use `"$uv_bin"` everywhere.

   This prevents recurrence of the path bug and keeps the install layout decision in one place.

3. **Tighten the test guard.** `tests/test_setup_python_install.sh:67` reads:
   ```bash
   if [[ "$(uname)" == "Linux" ]] && [[ -x "$FAKE_HOME/.aitask/uv/bin/uv" ]]; then
       echo "uv was installed at $FAKE_HOME/.aitask/uv/bin/uv"
       ...
   ```
   The guard references the same wrong path; when the binary is not present at that path the entire branch silently no-ops instead of failing. Update the assertion to:
   - Use the correct path (`$FAKE_HOME/.aitask/uv/uv`).
   - Fail (not silently skip) when the binary is missing on a Linux host that took the uv path.

4. **Add a fast unit-level guard.** Add a non-integration test (no AIT_RUN_INTEGRATION_TESTS gate) that asserts the post-install layout the helper expects — e.g., a small bash test that stubs the uv installer to drop a fake `uv` script at the location the installer actually uses, then calls `_ensure_uv` and asserts the returned path is executable. This catches future drift if uv's installer relocates binaries again.

## Out of Scope

- Adding a `pypy` label (no existing `pypy` label; the existing `python` and `installation` labels are sufficient).
- Reworking `find_pypy()` or the PyPy venv setup (those work correctly once uv is reachable — confirmed by reading the post-install symlink path at `aitask_setup.sh:511-513`).
- Mac path (`_install_pypy_macos` uses brew, not uv).

## Verification Steps After Implementation

1. `bash tests/test_setup_python_install.sh` (with `AIT_RUN_INTEGRATION_TESTS=1`) on a Linux host without system Python 3.11+ — must complete without the path error.
2. `ait setup --with-pypy` on the reporter's machine (existing `~/.aitask/uv/uv` already in place) must complete successfully and create `~/.aitask/pypy_venv` with a working PyPy interpreter.
3. `bash tests/test_python_resolve_pypy.sh` continues to pass.

## Reference

- Reporter run output: see ait setup transcript on 2026-04-30 — uv 0.11.8 installer logs `installing to /home/ddt/.aitask/uv` followed by `uv` and `uvx` (no bin/ subdir).
- AIT_PYPY_PREFERRED is correctly defined once at `lib/python_resolve.sh:37` (single source of truth — leave alone).
