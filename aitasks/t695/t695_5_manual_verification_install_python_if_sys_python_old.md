---
priority: medium
effort: medium
depends: [t695_4]
issue_type: manual_verification
status: Ready
labels: [verification, manual]
verifies: [695_1, 695_2, 695_3, 695_4]
created_at: 2026-04-28 11:31
updated_at: 2026-04-28 11:31
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

## Verification Checklist

- [ ] [t695_1] Source `.aitask-scripts/lib/python_resolve.sh` in an interactive shell and call `resolve_python` — verify it returns either the system `python3` or `~/.aitask/bin/python3` if a prior setup ran
- [ ] [t695_1] Run `bash tests/test_python_resolve.sh` and verify all 5 stub-PATH tests pass (system fallback, AIT_PYTHON override, ~/.aitask/bin precedence, cache, require_modern_python rejection)
- [ ] [t695_1] Verify double-source guard: `bash -c 'source lib/python_resolve.sh; source lib/python_resolve.sh; declare -F resolve_python'` — second source must be a no-op
- [ ] [t695_2] On a macOS host with system Python 3.9: run `ait setup` from a scratch dir → verify brew install path triggers (`brew install python@3.13` runs, no sudo prompt) → verify `~/.aitask/venv/bin/python -V` returns ≥3.11
- [ ] [t695_2] On a Debian 11 (or Ubuntu 22.04) host with system Python 3.9: run `ait setup` → verify uv is downloaded into `~/.aitask/uv/bin/uv` (NO sudo prompts during the entire flow) → verify `uv python install 3.13` runs → verify `~/.aitask/python/3.13/bin/python3` symlink exists → verify `~/.aitask/venv/bin/python -V` returns ≥3.11
- [ ] [t695_2] Verify `~/.aitask/venv/bin/python -c "import linkify_it; import textual; import yaml"` exits 0 on both macOS and Linux test hosts
- [ ] [t695_2] Verify nothing was sudo-installed system-wide on Linux: `which python3.13` should NOT find an apt-installed binary; only the uv-managed one in `~/.aitask/`
- [ ] [t695_3] Verify `~/.aitask/bin/python3` symlink exists and resolves to `~/.aitask/venv/bin/python` after setup completes
- [ ] [t695_3] Open a fresh shell after setup, run `which python3` — verify it resolves to `~/.aitask/bin/python3` (PATH precedence over /usr/bin/python3)
- [ ] [t695_3] Run `python3 -c "import linkify_it"` in a fresh shell — verify it succeeds without manually sourcing the venv
- [ ] [t695_3] Re-run `ait setup` and confirm shell rc file does not gain duplicate `~/.aitask/bin` PATH entries (idempotency)
- [ ] [t695_4] Launch the board TUI (`ait board`) on a local install — verify URLs in task cards are linkified (this is the original bug from the user's task description)
- [ ] [t695_4] Launch brainstorm, settings, codebrowser, minimonitor TUIs — verify each loads without ImportError for textual/linkify/yaml
- [ ] [t695_4] Simulate a remote sandbox: `HOME=/tmp/empty PATH=/usr/bin:/bin bash -c 'source .aitask-scripts/lib/python_resolve.sh; resolve_python'` — verify it returns the system `python3` path (no crash on missing `~/.aitask/`)
- [ ] [t695_4] Run `aitask_verification_parse.sh --help` (or equivalent dry-run) in a stripped HOME env — verify it does not crash
- [ ] [t695_4] Verify a TUI launcher in a stripped HOME env (e.g. `HOME=/tmp/empty ait board --help`) dies with a clear "Run 'ait setup'" error rather than a Python ImportError
- [ ] [overall] Run a full end-to-end task pick on a fresh macOS install with system Python 3.9: `bash install.sh --dir /tmp/scratch695fresh` → `cd /tmp/scratch695fresh && ./ait setup` → confirm setup completes without errors → run `ait pick` and verify board loads
