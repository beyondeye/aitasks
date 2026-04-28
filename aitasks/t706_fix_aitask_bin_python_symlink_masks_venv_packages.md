---
priority: high
effort: medium
depends: []
issue_type: bug
status: Ready
labels: [ait_setup, ait_dispatcher]
created_at: 2026-04-28 18:00
updated_at: 2026-04-28 18:00
---

## Symptom

`ait board` (and any other TUI that calls `require_ait_python`) fails on a fresh setup with:

```
Error: Missing Python packages: textual pyyaml linkify-it-py. Run 'ait setup' to install all dependencies.
```

The error persists even after re-running `ait setup`. The framework venv at `~/.aitask/venv/` *does* have textual/pyyaml/linkify-it-py installed correctly — but the resolver picks the `~/.aitask/bin/python3` symlink, which silently bypasses the venv's site-packages.

Additionally, every `ait <cmd>` invocation prints noisy arithmetic-syntax errors from `ait:94-95` because the update-check cache file got populated with raw JSON tokens.

## Root cause #1 — Bin symlink masks venv site-packages

`aitask_setup.sh:574-577` (introduced by t695_3, commit `709380a5`) creates:

```
~/.aitask/bin/python3 → ~/.aitask/venv/bin/python → python3.13 → /opt/homebrew/opt/python@3.13/bin/python3.13
```

`lib/python_resolve.sh:39-48` orders candidates as:

1. `$AIT_PYTHON`
2. `$HOME/.aitask/bin/python3`        ← **picked first**
3. `$HOME/.aitask/venv/bin/python`
4. system `python3`

When Python launches via the `bin/python3 → venv/bin/python` chain, `sys.executable` canonicalizes through both symlink hops to `/opt/homebrew/opt/python@3.13/bin/python3.13`. Python's venv detection then looks for `pyvenv.cfg` adjacent to that path — but `pyvenv.cfg` lives only at `~/.aitask/venv/pyvenv.cfg`. So Python uses the **system** site-packages instead of the venv's. textual/pyyaml/linkify-it-py are not in system site-packages → import fails.

Verified directly:
- `~/.aitask/venv/bin/python -c "import textual"` → 8.2.4 ✓ (sys.executable=`~/.aitask/venv/bin/python`)
- `~/.aitask/bin/python3   -c "import textual"` → ModuleNotFoundError ✗ (sys.executable=`/opt/homebrew/.../python3.13`)

`ait setup` recreates the same broken symlink each run, which is why re-running it does not fix the problem.

### Fix

Replace the symlinks at `~/.aitask/bin/{python,python3}` with a small wrapper script:

```bash
#!/usr/bin/env bash
exec "$HOME/.aitask/venv/bin/python" "$@"
```

Invoking `venv/bin/python` directly (rather than via a symlink chain) preserves `pyvenv.cfg` discovery, and the wrapper still satisfies the PATH-injection design from `lib/aitask_path.sh` introduced by t695_3.

`aitask_setup.sh` must:
- Detect existing broken symlinks at `~/.aitask/bin/{python,python3}` and replace them (one-time migration on already-installed users).
- Write the wrapper script with `chmod +x`.
- Add a regression test (extension of `tests/test_setup_python_install.sh`) that asserts `~/.aitask/bin/python3 -c "import sys; print(sys.executable)"` matches the venv path, not the system path.

Re-evaluate whether `lib/python_resolve.sh`'s candidate order should reverse to prefer `venv/bin/python` over `bin/python3` — defense-in-depth even after the wrapper fix.

## Root cause #2 — Update-check cache parser is fragile

`ait:135-138` parses GitHub's releases API:

```bash
latest_version="$(curl ... | grep '"tag_name"' | head -1 \
  | sed 's/.*"tag_name": *"v\?\([^"]*\)".*/\1/')"
```

If the API returns an error response, an empty body, or anything where the sed substitution does not match, the entire JSON line passes through unchanged. That value is then written to `~/.aitask/update_check` (`ait:142`). On the next invocation, `read -r cached_time cached_version < "$cache_file"` (`ait:118`) loads the corrupted line — `cached_version` ends up holding `"tag_name": "v0.18.1",` (or similar). `version_gt` then splits on `.` and runs `((n1 > n2))` on tokens like `"tag_name": "v0` → arithmetic syntax errors at `ait:94-95`.

Observed cache content on the affected system: `~/.aitask/update_check` contains a literal JSON fragment instead of a numeric version.

### Fix

- Validate `latest_version` against `^[0-9]+(\.[0-9]+)*$` before writing the cache (`ait:140`). On mismatch, fall back to the timestamp-only update.
- Validate `cached_version` against the same regex after `read` (`ait:118-119`). On mismatch, ignore the cache and treat it as stale (and overwrite with a clean entry next refresh).
- One-time cleanup: if the existing cache fails validation, unlink it.
- Regression test: feed `version_gt` and the cache-read path with corrupted inputs and assert the script exits cleanly with no arithmetic errors.

## Why this surfaced now

Both failures stem from the t695 series (commits `fb3b0c41`, `09ee8ae1`, `709380a5`, `82ce8d98`). t695_3 introduced the bin symlink layer. Before t695_3, `python_resolve.sh` would have fallen back to `venv/bin/python` directly. Existing users who upgrade through `ait setup` will all hit this on next TUI launch.

The update-check noise is a separate latent bug — it became visible during this investigation because the noisy stderr appears immediately before the package-error die.

## Acceptance

- After `ait setup`, `~/.aitask/bin/python3 --version` succeeds and `~/.aitask/bin/python3 -c "import textual, yaml, linkify_it"` succeeds.
- `ait board` launches the TUI cleanly with no missing-package error and no arithmetic-syntax noise.
- Cache file at `~/.aitask/update_check` is robust against corrupt entries (auto-recovers on next run).
- New tests in `tests/test_setup_python_install.sh` cover both regressions.

## Suggested split (during planning)

Two logically independent fixes; consider splitting into two child tasks:
1. `aitask_setup.sh` wrapper-script migration + python_resolve preference + regression test.
2. `ait` update-check input validation + cache-recovery + regression test.
