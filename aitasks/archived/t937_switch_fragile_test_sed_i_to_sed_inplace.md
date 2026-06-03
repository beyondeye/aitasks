---
priority: low
effort: low
depends: []
issue_type: refactor
status: Done
labels: [macos, bash_scripts, testing]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_8
created_at: 2026-06-03 23:15
updated_at: 2026-06-03 23:20
completed_at: 2026-06-03 23:20
---

Surfaced by the t926 periodic macOS compat audit. **Not a failure** — these work
correctly on macOS today via a fallback — but they are a portability fragility
worth tidying while the audit context is fresh.

## Problem

Two test setups use a bare GNU-style `sed -i 's/.../.../' file` and rely on it
*failing* on BSD/macOS to trigger a `sed -i.bak` fallback:

- `tests/test_fold_mark.sh:204`
- `tests/test_fold_file_refs_union.sh:162`

Pattern:
```bash
sed -i 's/^status: Ready$/status: Folded/' aitasks/t70_x.md aitasks/t71_y.md 2>/dev/null || \
    { sed -i.bak 's/.../.../' ...; rm -f ...bak; }
```

On macOS the first form errors (BSD `sed -i` reads `s/...` as the backup
suffix), the `2>/dev/null ||` swallows it, and the `sed -i.bak` fallback does
the work — so it functions, but it depends on a command erroring by design and
is brittle.

## Suggested fix

Source `.aitask-scripts/lib/terminal_compat.sh` and replace both with the
canonical `sed_inplace 's/.../.../' file...` helper (the documented portable
in-place edit). Removes the error-and-fallback dance and matches the rest of the
codebase. See `aidocs/framework/sed_macos_issues.md` ("The `sed_inplace()`
Helper").

## Verification

`bash tests/test_fold_mark.sh` and `bash tests/test_fold_file_refs_union.sh`
pass on both macOS and Linux with no leftover `.bak` files.
