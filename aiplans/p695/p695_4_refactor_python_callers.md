---
Task: t695_4_refactor_python_callers.md
Parent Task: aitasks/t695_install_python_if_sys_python_old.md
Sibling Tasks: aitasks/t695/t695_1_python_resolve_helper.md, aitasks/t695/t695_2_venv_python_upgrade.md, aitasks/t695/t695_3_aitask_bin_symlink_path.md
Archived Sibling Plans: aiplans/archived/p695/p695_*_*.md
Worktree: aiwork/t695_4_refactor_python_callers
Branch: aitask/t695_4_refactor_python_callers
Base branch: main
---

# Plan — t695_4: Refactor direct python3 callers to source the helper

## Context

Fourth and final implementation child of t695. Migrates every script that
invokes Python to source `lib/python_resolve.sh` (created in t695_1) and
use the cached `$_AIT_RESOLVED_PYTHON` (or the function `resolve_python`)
instead of hardcoded `python3` or the `${PYTHON:-python3}` shorthand.

The motivation is remote-sandbox resilience: scripts in the task-workflow
(e.g., `aitask_verification_parse.sh`) may run inside `aitask-pick-rem` /
`aitask-pick-web` sandboxes where `~/.aitask/` doesn't exist. The helper
falls back to system `python3` cleanly in those environments. Without
this migration, hardcoded `python3` calls work coincidentally in remote
envs (where system python3 IS what we want) and the symlink-based
local case from t695_3 — but the contract is implicit. Making it
explicit via the helper eliminates an entire class of "framework not
bootstrapped" crashes and unifies the resolution path.

## Files to Modify

| File | Current | After |
| ---- | ------- | ----- |
| `.aitask-scripts/aitask_verification_parse.sh:4` | `exec python3 …` | source helper, `exec "$PYTHON" …` |
| `.aitask-scripts/aitask_explain_context.sh:245` | `python3 …`      | source helper, `"$PYTHON" …` |
| `.aitask-scripts/aitask_board.sh:14,37` | `${PYTHON:-python3}` | source helper, `$PYTHON` |
| `.aitask-scripts/aitask_minimonitor.sh:14,53` | same | same |
| `.aitask-scripts/aitask_settings.sh:14` | same | same |
| `.aitask-scripts/aitask_crew_status.sh:21` | same | same |
| `.aitask-scripts/aitask_crew_runner.sh:21` | same | same |
| `.aitask-scripts/aitask_brainstorm_archive.sh:24` | same | same |
| `.aitask-scripts/aitask_sync.sh:39-44` | venv-then-python3 fallback | replace with helper (which encapsulates the same fallback) |

## Implementation Steps

### Step 1 — Migration template

For each script in the table, the change pattern is:

```bash
# After existing shebang and `set -euo pipefail`:
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/python_resolve.sh
source "$SCRIPT_DIR/lib/python_resolve.sh"
PYTHON="$(resolve_python)"
[[ -z "$PYTHON" ]] && die "No Python interpreter found. Run 'ait setup'."
```

Then replace `python3` / `${PYTHON:-python3}` invocations with `"$PYTHON"`.

For TUI launchers that REQUIRE the venv-Python (linkify, textual deps —
board, minimonitor, settings, brainstorm, crew_status, crew_runner), use
`require_modern_python "$AIT_VENV_PYTHON_MIN"` instead of plain
`resolve_python`. Note: if `AIT_VENV_PYTHON_MIN` is only defined in
`aitask_setup.sh`, the launcher will need to either source a config snippet
or hardcode the value (`require_modern_python 3.11`). Hardcoded is fine —
this is internal coupling, not user-facing.

For scripts that just need basic Python (verification_parse,
explain_context, sync), `resolve_python` (no version requirement) is
sufficient — they may legitimately run in remote sandboxes with system
python3.

### Step 2 — Existing import-check guards

TUI launchers like `aitask_board.sh:24` already have an import-check
pattern:

```bash
if ! "$PYTHON" -c "import linkify_it" 2>/dev/null; then
  die "linkify-it-py not installed in venv. Run 'ait setup'."
fi
```

Keep this pattern — it's the runtime guard for "venv-Python doesn't have
the deps" (e.g., the user updated the framework but didn't re-run setup,
so the venv exists but lacks new deps). This guard is complementary to
`require_modern_python` (version) and remains useful even after the
migration.

### Step 3 — Audit `.py` shebangs

The 13 `.py` files with `#!/usr/bin/env python3` shebangs:

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

For each, determine: is it invoked directly (`./script.py`) or always
wrapped by a `.sh` launcher? Use:

```bash
grep -rn '\.aitask-scripts/.*\.py' . --include='*.sh' --include='*.md' \
  | grep -v 'python.*\.py'   # exclude lines where it's already a python arg
```

For files invoked directly (chmod +x and called by name), the t695_3 PATH
symlink makes shebang resolution work on local installs. For remote
sandboxes, shebang falls back to system python3 — which won't have
textual/linkify. So any directly-invoked `.py` that imports those deps
should add a defensive guard at the top:

```python
import sys
if sys.version_info < (3, 11):
    sys.stderr.write(
        f"Python >=3.11 required (found {sys.version}). Run 'ait setup'.\n"
    )
    sys.exit(2)
```

Apply only to `.py` files that import textual/linkify/yaml. Plain stdlib
scripts can stay unguarded.

### Step 4 — install.sh:263 audit (no code change)

Add a clarifying comment above the existing line:

```bash
# NOTE: Pre-setup invocation. Helper at .aitask-scripts/lib/python_resolve.sh
# is not yet usable because no AIT-resolved Python exists. System python3
# only needs pyyaml here, which install.sh ensures via earlier prerequisites.
python3 ./.aitask-scripts/aitask_install_merge.py
```

No behavior change.

### Step 5 — seed/geminicli_policies/aitasks-whitelist.toml:471 audit

The literal `python3` in the commandPrefix continues to work because
the t695_3 PATH symlink ensures `python3` resolves to the framework
interpreter. No change needed; just document in the PR description.

### Step 6 — Smoke tests

`tests/test_python_resolution_fallback.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail
SCRATCH="$(mktemp -d)"
trap 'rm -rf "$SCRATCH"' EXIT

# Simulate remote sandbox: HOME points at empty dir, PATH has only system python3
export HOME="$SCRATCH"
export PATH="/usr/bin:/bin"

# Sanity: helper resolves to system python3
result="$(bash -c 'source .aitask-scripts/lib/python_resolve.sh; resolve_python')"
[[ "$result" == "/usr/bin/python3" ]] || { echo "FAIL helper fallback"; exit 1; }

# verification_parse.sh runs against a fixture without crashing on missing ~/.aitask
# (assuming the fixture-runner exists; otherwise just verify --help / dry-run path)
./.aitask-scripts/aitask_verification_parse.sh --help >/dev/null \
  || { echo "FAIL verification_parse --help"; exit 1; }

echo "Fallback tests passed."
```

Adapt to whatever entrypoint/dry-run flag exists per script.

## Verification

- `bash tests/test_python_resolution_fallback.sh` passes.
- `shellcheck .aitask-scripts/aitask_*.sh` clean for every modified script.
- Manual: launch board, brainstorm, settings TUIs after migration — verify
  they still work locally.
- Manual: run `aitask_verification_parse.sh` against a sample task in a
  remote-sandbox-like env (no `~/.aitask/`) — verify graceful behavior
  (uses system python3 if available, dies with clear error if not).

## Dependencies / Sequencing

- t695_1 must be in place — this child sources the helper from t695_1.
- Ideally t695_2 and t695_3 are also merged so local testing uses the
  venv-Python end-to-end. But the migration itself can land on top of just
  t695_1 — the helper's fallback chain works without venv.

## Step 9 — Post-Implementation

Standard archival flow. After this child commits, the parent t695 can be
considered complete pending the aggregate manual-verification sibling.

## Notes for sibling tasks (read by aggregate manual verification)

- The aggregate manual verification sibling tests TUI flows on real
  macOS-3.9 + Debian-11 hosts that this automated test cannot.
- After this child commits, every Python invocation in the framework goes
  through `resolve_python` (or via PATH symlink for shebang-driven `.py`
  files). The two paths converge on the same interpreter on local
  installs and gracefully fall back on remote sandboxes.
