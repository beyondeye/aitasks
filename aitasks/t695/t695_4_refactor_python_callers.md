---
priority: medium
effort: medium
depends: [t695_3]
issue_type: refactor
status: Ready
labels: [ait_setup, installation, python]
created_at: 2026-04-28 11:27
updated_at: 2026-04-28 13:19
---

## Context

This is child 4 of t695. With the resolver helper from t695_1 in place and the venv + symlink from t695_2/t695_3 working locally, this child migrates every script that invokes Python to source `lib/python_resolve.sh` and use `$(resolve_python)` (or the cached `$_AIT_RESOLVED_PYTHON`) instead of hardcoded `python3` or the `${PYTHON:-python3}` shorthand.

The motivation, per the user's note: scripts in the task-workflow (e.g., `aitask_verification_parse.sh`) may run inside `aitask-pick-rem` or `aitask-pick-web` sandboxes where `~/.aitask/` doesn't exist. The helper falls back to system `python3` cleanly in those environments, so this migration eliminates an entire class of "framework not bootstrapped" crashes.

## Key Files to Modify

| File | Current | After |
| ---- | ------- | ----- |
| `.aitask-scripts/aitask_verification_parse.sh:4` | `exec python3 ...` | source helper, `exec "$(resolve_python)" ...` |
| `.aitask-scripts/aitask_explain_context.sh:245` | `python3 ...` | source helper, `"$(resolve_python)" ...` |
| `.aitask-scripts/aitask_board.sh:14,37` | `${PYTHON:-python3}` | source helper, use cached `$_AIT_RESOLVED_PYTHON` |
| `.aitask-scripts/aitask_minimonitor.sh:14,53` | `${PYTHON:-python3}` | same |
| `.aitask-scripts/aitask_settings.sh:14` | `${PYTHON:-python3}` | same |
| `.aitask-scripts/aitask_crew_status.sh:21` | `${PYTHON:-python3}` | same |
| `.aitask-scripts/aitask_crew_runner.sh:21` | `${PYTHON:-python3}` | same |
| `.aitask-scripts/aitask_brainstorm_archive.sh:24` | `${PYTHON:-python3}` | same |
| `.aitask-scripts/aitask_sync.sh:39-44` | venv-then-python3 fallback | replace with helper (which already does the fallback chain) |

## Reference Files for Patterns

- `.aitask-scripts/lib/python_resolve.sh` (created in t695_1) — the helper to source.
- `.aitask-scripts/lib/terminal_compat.sh` — pattern for sourcing libs at top of script: `source "$(dirname "$0")/lib/terminal_compat.sh"`. Apply the same to python_resolve.sh.

## Implementation Plan

1. **Migration template** — for each script in the table above, the change pattern is:
   ```bash
   # At top of script, after shebang and `set -euo pipefail`:
   SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
   # shellcheck source=lib/python_resolve.sh
   source "$SCRIPT_DIR/lib/python_resolve.sh"
   PYTHON="$(resolve_python)"
   [[ -z "$PYTHON" ]] && die "No Python interpreter found. Run 'ait setup'."
   ```
   Then replace `python3` / `${PYTHON:-python3}` invocations with `"$PYTHON"`.
   
   For TUI launchers that need linkify/textual (board, minimonitor, settings, brainstorm), use `require_modern_python "$AIT_VENV_PYTHON_MIN"` — they need not just any python, but the venv-Python with deps installed. The existing import-check (e.g., `aitask_board.sh:24` `$PYTHON -c "import linkify_it"`) becomes the de-facto venv guard; keep it.
   
   For scripts that just need basic Python (verification_parse, explain_context, sync), `resolve_python` (no version requirement) is sufficient since they may legitimately run in remote sandboxes with system python3.

2. **Audit shebangs in the 13 `.py` files** with `#!/usr/bin/env python3`:
   - `.aitask-scripts/aitask_explain_process_raw_data.py`
   - `.aitask-scripts/aitask_codemap.py`
   - `.aitask-scripts/aitask_explain_format_context.py`
   - `.aitask-scripts/aitask_verification_parse.py`
   - `.aitask-scripts/board/aitask_merge.py`
   - `.aitask-scripts/board/aitask_board.py`
   - `.aitask-scripts/agentcrew/agentcrew_status.py`
   - `.aitask-scripts/diffviewer/diffviewer_app.py`
   - `.aitask-scripts/logview/logview_app.py`
   - `.aitask-scripts/stats/stats_app.py`
   - `.aitask-scripts/settings/settings_app.py`
   - `.aitask-scripts/aitask_stats.py`
   - `aidocs/benchmarks/bench_archive_formats.py`
   
   Determine which are invoked directly (chmod +x and `./script.py`) vs. always wrapped by a `.sh` launcher. For those invoked directly, the PATH symlink from t695_3 makes shebang resolution work on local installs. For remote sandboxes, document that direct invocation requires system python3 OR add a defensive import guard at the top of each `.py` file:
   ```python
   import sys
   if sys.version_info < (3, 11):
       sys.stderr.write(f"Python ≥3.11 required (found {sys.version}). Run 'ait setup'.\n")
       sys.exit(2)
   ```
   Apply this guard only to `.py` files that import textual/linkify/yaml. Plain stdlib scripts can stay unguarded.

3. **install.sh:263 audit** — the merge step `python3 ./.aitask-scripts/aitask_install_merge.py` runs BEFORE `ait setup`, so the helper isn't sourceable. Leave as `python3` (system) and add a clarifying comment:
   ```bash
   # NOTE: Pre-setup invocation. Helper at .aitask-scripts/lib/python_resolve.sh
   # is not yet usable because no AIT-resolved Python exists. System python3
   # only needs pyyaml here, which install.sh ensures via earlier prerequisites.
   python3 ./.aitask-scripts/aitask_install_merge.py
   ```

4. **`seed/geminicli_policies/aitasks-whitelist.toml:471` audit** — already uses literal `python3 .aitask-scripts/aitask_explain_process_raw_data.py`. Once the PATH symlink is in place, `python3` resolves to the venv-Python automatically. No change needed; document in PR.

5. **Smoke tests** — add `tests/test_python_resolution_fallback.sh`:
   - With `~/.aitask/` mocked away (set `HOME=/tmp/scratchXX`) and `PATH` including only system python3, source the helper and verify `resolve_python` returns the system path.
   - Run `aitask_verification_parse.sh` against a fixture in this stripped environment — verify it doesn't crash.
   - Run a TUI launcher (e.g., `aitask_board.sh --help` or whatever non-interactive subcommand exists) — verify it dies with the expected "Run 'ait setup'" error rather than a Python crash.

## Verification Steps

- `bash tests/test_python_resolution_fallback.sh` passes.
- `shellcheck .aitask-scripts/aitask_*.sh` clean for every modified script.
- Manual: launch board, brainstorm, settings TUIs after migration — verify they still work locally.
- Manual: run `aitask_verification_parse.sh` against a sample task in a remote-sandbox-like env (no `~/.aitask/`) — verify graceful behavior.

## Dependencies

- t695_1 must be in place (the helper itself).
- Ideally t695_2 and t695_3 are also merged so local testing uses the venv-Python end-to-end. But this child can technically be developed against just t695_1 — the helper's fallback chain works without venv.

## Notes for sibling tasks

- The aggregate manual verification sibling (created next) covers TUI flows on real macOS-3.9 + Debian-11 hosts that this automated test cannot.
- Keep the existing import-check pattern in TUI launchers (e.g., `aitask_board.sh:24` `$PYTHON -c "import linkify_it"`) — it's the runtime guard for "venv-Python doesn't have the deps".
- `check_python_version()` and the `PYTHON_VERSION_OK` global in `.aitask-scripts/aitask_setup.sh` (lines ~373–435 after t695_2) are dead code — no callers remain after t695_2. Remove them as part of this task and update or delete the matching coverage in `tests/test_version_checks.sh`. The `# DEPRECATED` comment above `check_python_version` flags this in-source.
- **Source `lib/aitask_path.sh` in every migrated script.** t695_3 ships this lib and sources it from the `ait` dispatcher only. Skill-direct calls to `.aitask-scripts/aitask_*.sh` bypass the dispatcher, so each Python-invoking script must source `lib/aitask_path.sh` explicitly near its top (right next to `lib/python_resolve.sh`). This keeps shebang-based `python3` resolution scoped to aitasks subprocesses without touching the user's interactive shell rc. Pattern:
  ```bash
  SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  # shellcheck source=lib/aitask_path.sh
  source "$SCRIPT_DIR/lib/aitask_path.sh"
  # shellcheck source=lib/python_resolve.sh
  source "$SCRIPT_DIR/lib/python_resolve.sh"
  ```
