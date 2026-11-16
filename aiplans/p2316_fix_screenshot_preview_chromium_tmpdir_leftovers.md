---
Task: t2316_fix_screenshot_preview_chromium_tmpdir_leftovers.md
Base branch: main
Output branch: main
---

# t2316 — Chromium preview: private short TMPDIR, no leftovers

## Context

`website/screenshots/svg_export.py:render_png` runs headless Chromium for PNG
previews. Two defects, both reproduced in this session:

1. **Leftovers.** Chromium creates
   `org.chromium.Chromium.chromium_chrome_url_fetcher_.XXXXXX` directories in the
   **environment `$TMPDIR`** (4 of 5 renders leaked one), outside the private
   `--user-data-dir` that `render_png` already cleans up. The tmpdir guard flags
   them as `TMPDIR LEFTOVERS`.
2. **Abort under a long `$TMPDIR`.** Reproduced with a 161-char TMPDIR:
   `FATAL:chrome/browser/process_singleton_posix.cc:315 Socket path too long:
   $TMPDIR/org.chromium.Chromium.XXXXXX/SingletonSocket` → SIGABRT. Isolated:
   long TMPDIR + short user-data-dir aborts; short TMPDIR + long user-data-dir
   renders fine. So the trigger is `$TMPDIR` length alone (108-byte `sun_path`).
   The aborted run also leaks an `org.chromium.Chromium.XXXXXX` dir.

The current `ExportError` message hides Chromium's stderr, so the abort reads
as a bare "died with SIGABRT".

**The repeated Chromium core dumps the user reported are this defect.** Their
core carries the identical FATAL line, for
`<session scratchpad>/tmpcheck/ait_shots_chrome_…/org.chromium.Chromium.…/SingletonSocket`
(167 chars). This session's isolation run makes their "inferred" point proven:
the same render works when `TMPDIR` is short. Every abort writes a
systemd-coredump, so long-`TMPDIR` runs (agent scratchpads) leave cores as well
as failed previews. The fix below measures the socket path and moves Chromium's
`TMPDIR` to a short private dir, so no Chromium launched by `render_png` can
reach that abort.

## Implementation

### 1. `website/screenshots/svg_export.py`

Add near `_BROWSERS`:

```python
#: Chromium binds ``$TMPDIR/org.chromium.Chromium.XXXXXX/SingletonSocket``; a
#: Unix socket path holds at most 107 bytes (``sun_path`` is 108 with the NUL).
_SOCKET_TAIL = len("/org.chromium.Chromium.XXXXXX/SingletonSocket")
_SUN_PATH_MAX = 107
#: Short base used when the caller's temp dir is too long for that socket.
_SHORT_TMP_FALLBACK = "/tmp"


def _socket_fits(scratch: str) -> bool:
    # sun_path is a BYTE limit: measure the encoded path, not its characters.
    return len(os.fsencode(scratch)) + _SOCKET_TAIL <= _SUN_PATH_MAX


def _chrome_scratch_dir() -> str:
    """A fresh private dir for one Chromium run, short enough for its socket.

    Made under ``tempfile.gettempdir()`` when the resulting socket path fits,
    else under ``_SHORT_TMP_FALLBACK``. Raises :class:`ExportError`, leaving
    nothing behind, when neither fits: Chromium would only abort on it. The
    caller removes the returned dir."""
    import tempfile

    scratch = tempfile.mkdtemp(prefix="ait_shots_chrome_")
    if _socket_fits(scratch):
        return scratch
    os.rmdir(scratch)
    try:
        short = tempfile.mkdtemp(prefix="ait_shots_chrome_", dir=_SHORT_TMP_FALLBACK)
    except OSError as exc:
        raise ExportError(
            f"temp dir {scratch!r} is too long for Chromium's socket and no "
            f"scratch dir could be made in {_SHORT_TMP_FALLBACK}: {exc}") from exc
    if not _socket_fits(short):
        os.rmdir(short)
        raise ExportError(f"no temp dir short enough for Chromium's socket "
                          f"(tried {scratch!r} and {short!r})")
    return short
```

- Measure the actual created path rather than precomputing from the base, so
  the random-suffix length is never assumed. `_SOCKET_TAIL` is ASCII, so its
  character length is its byte length.
- Every failure exit removes the directory it made, and it raises **before**
  any Chromium launch (in `render_png` the helper runs before the `try/finally`
  and before `subprocess.run`).

Rewrite the Chromium branch of `render_png`:

```python
if browser:
    scratch = _chrome_scratch_dir()
    try:
        profile = os.path.join(scratch, "profile")
        os.mkdir(profile)
        # Chromium's own temp files (url-fetcher dirs, the singleton socket)
        # go to $TMPDIR: point it at the scratch dir so they are removed with
        # it and the socket path stays short.
        env = {**os.environ, "TMPDIR": scratch}
        argv = [... same as today, --user-data-dir={profile} ...]
        try:
            subprocess.run(argv, capture_output=True, timeout=timeout, check=True, env=env)
        except subprocess.CalledProcessError as exc:
            raise ExportError(f"{browser} could not render {svg_path}: {exc}"
                              f"{_last_line(exc.stderr)}") from exc
        except (OSError, subprocess.SubprocessError) as exc:
            raise ExportError(f"{browser} could not render {svg_path}: {exc}") from exc
    finally:
        shutil.rmtree(scratch, ignore_errors=True)
```

- `import os` at module top; drop the local `import tempfile` from `render_png`.
- `_last_line(stderr: bytes | None) -> str`: last non-empty decoded
  (`errors="replace"`) line as `" — <line>"`, or `""`. This makes a socket-path
  abort self-explaining (`… — FATAL:… Socket path too long: …`).
- `ignore_errors=True`: a lingering Chromium helper must not turn a successful
  render into an exception; the dir lives under a private name either way.
- Behaviour for the rsvg-convert path and the PNG/return contract is unchanged;
  `cli.py:150` (the only other caller) needs no change.

### 2. `tests/test_screenshots_svgpost.py` — `PreviewTests`

Add `import subprocess` / `from unittest import mock` as needed, and a helper
that patches **both** `os.environ["TMPDIR"]` (what Chromium reads) and
`tempfile.tempdir` (what `gettempdir()` caches) to a given dir.

- `test_a_preview_leaves_nothing_in_tmpdir` (skipUnless a Chromium-family
  browser is on PATH): private `base = tempfile.mkdtemp(dir="/tmp")` (short, so
  the non-fallback branch runs; removed via `addCleanup(shutil.rmtree, …)`),
  render the cropped SVG **three times** (the pre-fix leak is intermittent),
  assert `renderer != "rsvg-convert"` and `os.listdir(base) == []`.
- `test_a_long_tmpdir_falls_back_to_a_short_scratch_dir` (same skip): `long`
  = a dir whose path is > 100 chars under a private `/tmp` base; patch
  `sx._SHORT_TMP_FALLBACK` to a second private short `/tmp` dir; render; assert
  a valid PNG of the viewBox size, `os.listdir(long) == []` and
  `os.listdir(fallback) == []`.
- `test_scratch_dir_choice` (no browser needed): with a long `tempfile.tempdir`
  `_chrome_scratch_dir()` returns a path under the patched fallback and leaves
  nothing in the long dir; with a short one it returns a path under it.
- `test_a_non_ascii_temp_dir_is_measured_in_bytes` (no browser needed): build a
  dir under a private `/tmp` base whose name is `n` × `é`, with `n` computed so
  that the scratch path's **character** length passes the budget and its
  **byte** length fails it. The test asserts both preconditions, so the fixture
  proves its own shape. Assert the helper returns a path under the patched
  short fallback and leaves the non-ASCII dir empty.
- `test_no_short_dir_raises_before_launching_chromium` (no browser needed,
  deterministic): long `tempfile.tempdir`, `sx._SHORT_TMP_FALLBACK` = a
  non-existent path under a private base, `shutil.which` patched in `sx` to
  report `chromium`, `sx.subprocess.run` patched with a `mock.Mock`. Assert
  `render_png` raises `ExportError`, `run` was **never called**, and the long
  dir is empty.
- `test_a_too_long_fallback_raises_and_cleans_up` (no browser needed): both
  `tempfile.tempdir` and the fallback are long existing dirs. Assert
  `ExportError` and both dirs empty.

The SVG/PNG files themselves go in a separate `TemporaryDirectory` (not in the
watched dir). The file runs unittest-style without subprocess bodies, so the
t1207 counter opt-in does not apply.

## Verification

- `python3 -m pytest tests/test_screenshots_svgpost.py -v` — all pass.
- **Pre-fix control** (no stash): copy the pre-fix `website/screenshots/` and the
  new test file into a scratch mirror (`<scratch>/website/screenshots`,
  `<scratch>/tests/`) and run the new tests there, **once** (each pre-fix
  long-TMPDIR run deliberately aborts Chromium and writes one more core dump).
  Expected: long-TMPDIR test fails (SIGABRT ExportError, now with no stderr
  tail since that is pre-fix); leftover test fails with url-fetcher dirs
  (probabilistic, 3 renders); the four helper tests error (no helper /
  pre-fix code launches Chromium; the no-short-dir test sees `run` called).
- Mutant check (isolated scratch copy, not the live file): revert
  `_socket_fits` to `len(scratch)` → the non-ASCII test fails; restore the
  `except OSError: return scratch` shape → the no-short-dir test fails.
- Post-fix: `coredumpctl list chromium --since <start of verification>` shows
  no new Chromium cores from the post-fix runs.
- `bash tests/run_shell_test.sh`-style guard: run
  `bash tests/run_all_python_tests.sh --test-dir <dir with only this module>` (or
  the full suite) and confirm no `org.chromium.*` in `TMPDIR LEFTOVERS`.
- Re-run the session's repro script under a 161-char TMPDIR: renders, leaves
  nothing.
- Full suite: `bash tests/run_all_python_tests.sh` — last line `PASSED`.

## Step 9 (Post-Implementation)

Commit code (`bug: … (t2316)`), plan via `./ait git`, archive per the workflow.

## Risk

### Code-health risk: low
- Single function in a docs-tooling module, one caller (`cli.py`), unchanged
  contract; the new env override is scoped to the Chromium subprocess.
  · severity: low · → mitigation: none needed
- The fallback writes under hardcoded `/tmp`, which the tmpdir guard cannot
  see. · severity: low · → mitigation: none needed (the dir is always removed in
  `finally`; tests point the fallback at a private dir and assert it is empty)

### Goal-achievement risk: low
- The pre-fix leak is intermittent, so the leftover test alone is a weak red.
  · severity: low · → mitigation: none needed (three renders per test + the
  deterministic long-TMPDIR red + the scratch pre-fix control above)
