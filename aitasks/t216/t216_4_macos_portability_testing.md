---
priority: medium
effort: low
depends: [t216_3, 216_1]
issue_type: test
status: Ready
labels: [aitask_board]
created_at: 2026-02-23 15:51
updated_at: 2026-02-23 15:51
---

## Context

Parent task t216 adds a new `ait sync` bash script (`aiscripts/aitask_sync.sh`). This child task verifies the script works correctly on macOS, covering known portability issues between Linux and macOS.

Depends on t216_1 (the sync script must exist before testing).

## Key Files to Modify

- **Modify (if needed):** `aiscripts/aitask_sync.sh` — fix any portability issues
- **Modify (if needed):** `tests/test_sync.sh` — add macOS-specific test adjustments

## Reference Files for Patterns

- `aidocs/sed_macos_issues.md` — comprehensive portability guide for sed, grep, wc, mktemp, base64
- `aiscripts/lib/terminal_compat.sh` — `sed_inplace()` and other portable helpers
- `CLAUDE.md` — shell conventions section documenting all portability rules

## Test Areas

1. **`timeout` command** — macOS doesn't ship `timeout` by default (requires `brew install coreutils`). Test the fallback bash watchdog mechanism when `timeout` is not in PATH.
2. **`sed` portability** — if the script uses `sed`, verify BSD sed compatibility. Must use `sed_inplace()` from `terminal_compat.sh` instead of `sed -i`.
3. **`grep` portability** — verify no `-P` (PCRE) flag, no `\K`, no lookahead/lookbehind. Use `-oE` instead.
4. **`wc -l` padding** — macOS `wc -l` pads with leading spaces. Verify numeric comparisons use arithmetic context (e.g., `-gt`), not string comparison (e.g., `== "0"`).
5. **`mktemp`** — if used, verify no `--suffix` flag. Use template pattern: `mktemp "${TMPDIR:-/tmp}/prefix_XXXXXX.ext"`.
6. **`base64`** — if used, verify cross-platform decode flag handling (`-d` vs `-D`).
7. **Git operations** — verify `git pull --rebase`, `git rebase --abort`, `git push` work on macOS git version.
8. **`bash` version** — verify no bash 4+ features (associative arrays `declare -A`, `${var^}` case modification). The shebang `#!/usr/bin/env bash` picks up homebrew bash 5.x if installed, but some users may have stock bash 3.2.
9. **Run test suite** — execute `bash tests/test_sync.sh` on macOS and fix any failures.

## Verification Steps

1. Run `shellcheck aiscripts/aitask_sync.sh` on macOS
2. Run `bash tests/test_sync.sh` on macOS — all tests should pass
3. Manual test: `./ait sync --batch` and `./ait sync` on macOS
4. Verify the `timeout` fallback works by temporarily hiding `timeout` from PATH
