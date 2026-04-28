---
priority: low
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [bash_scripts, ait_setup]
assigned_to: daelyasy@hotmail.com
created_at: 2026-04-28 19:08
updated_at: 2026-04-28 22:08
---

## Symptom

`bash tests/test_python_resolve.sh` fails immediately on Apple Silicon Macs (and any system without `/usr/bin/bash`):

```
tests/test_python_resolve.sh: line 101: /usr/bin/bash: No such file or directory
```

The test hard-codes `/usr/bin/bash` in 8 places (lines 97, 106, 115, 127, 142, 152, 161, 176). On macOS Apple Silicon, system bash 3.2 is no longer shipped at `/usr/bin/bash` — the modern brew-installed bash 5.x lives at `/opt/homebrew/bin/bash`. Linux distributions and Intel Macs have `/usr/bin/bash`, so the test passes there.

This is a pre-existing test-infra bug, not introduced by t706 — it was discovered while running the test as part of t706's verification checklist.

## Root cause

`tests/test_python_resolve.sh` was authored against an environment where `/usr/bin/bash` existed. The hard-coded path defeats the standard PATH-based resolution that picks up brew-bash on macOS.

The test uses `--noprofile --norc` flags to control the subshell environment cleanly, which is the correct intent — but the path itself should not be hard-coded.

## Fix

Replace all 8 occurrences of `/usr/bin/bash` with one of:

- **Preferred:** A test-local variable resolved once at the top of the file:
  ```bash
  TEST_BASH="$(command -v bash)"
  [[ -z "$TEST_BASH" ]] && { echo "No bash on PATH"; exit 2; }
  ```
  Then use `"$TEST_BASH" --noprofile --norc -c "..."` in each test case.

- **Alternative:** `${BASH:-bash}` — `$BASH` is set by every running bash to its own interpreter path. This is less explicit but requires no extra setup.

The first form is more readable and consistent with how `REAL_PY` is already resolved at the top of the file (line 42).

## Verification

After the fix, on macOS Apple Silicon:

```bash
bash tests/test_python_resolve.sh
# Expected: Tests: 8  Pass: 8  Fail: 0
```

Also verify on Linux (or any system with `/usr/bin/bash`) that the test still passes — `command -v bash` will resolve to whichever bash is on PATH there.

## Acceptance

- All 8 hard-coded `/usr/bin/bash` references replaced.
- `bash tests/test_python_resolve.sh` passes on Apple Silicon macOS.
- Test still passes on Linux / Intel macOS.
- No behavioral change — only the bash binary path used for the subshells is changed.

## Related

- Discovered during t706 (commit `48e83639`) verification — the t706 task was scoped to the bin-wrapper and update-check fixes; this is its dropped-out test-infra issue.
