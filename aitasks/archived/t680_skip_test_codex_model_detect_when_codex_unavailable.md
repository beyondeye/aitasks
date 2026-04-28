---
priority: low
effort: low
depends: []
issue_type: test
status: Done
labels: [testing, bash_scripts]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_7_1m
created_at: 2026-04-27 17:25
updated_at: 2026-04-28 11:02
completed_at: 2026-04-28 11:02
boardidx: 30
---

The macOS audit (t658) baseline run found `tests/test_codex_model_detect.sh` failing on hosts where Codex CLI isn't installed, with `ERROR: codex CLI not found in PATH` and exit 1. The test should detect missing tooling and skip with a non-error exit, the way `test_multi_session_primitives.sh` skips runtime assertions when tmux is absent.

## Reference pattern

`tests/test_multi_session_primitives.sh:130`:
```bash
if ! command -v tmux >/dev/null 2>&1; then
    echo "SKIP: tmux not installed — skipping runtime assertions"
else
    ...
fi
```

## Suggested approach

Wrap the body of `tests/test_codex_model_detect.sh` in `if command -v codex >/dev/null 2>&1; then ... else echo "SKIP: codex CLI not installed"; exit 0; fi` (or equivalent).

## Verification

- On a host without `codex`: test prints SKIP and exits 0.
- On a host with `codex`: test runs and passes (presumed — the existing assertions were not regressed by t658).
