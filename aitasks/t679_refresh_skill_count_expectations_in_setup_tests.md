---
priority: low
effort: low
depends: []
issue_type: test
status: Implementing
labels: [testing]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_7_1m
created_at: 2026-04-27 17:25
updated_at: 2026-04-28 00:03
---

The macOS audit (t658) baseline run revealed two tests failing because their hardcoded skill counts have drifted from the actual catalog as new skills were added.

## Failures observed

- `tests/test_gemini_setup.sh` — `FAIL: Global policy has explicit aitask skill entries (expected: '19', got: '20')` and `FAIL: Seed policy has explicit aitask skill entries (expected: '19', got: '20')`. (Two assertions, same root cause.)
- `tests/test_opencode_setup.sh` — `FAIL: Packaged 18 skill wrappers (expected: '18', got: '21')`, `FAIL: Packaged 18 command wrappers (expected: '18', got: '20')`, plus the same two assertions in the staging test. (Four assertions, same root cause.)

## Suggested approach

Two options:

1. **Update the hardcoded numbers** to match the current catalog. Quick fix; will go stale again next time a skill is added.
2. **Compute expectations dynamically** by counting `.claude/skills/*/SKILL.md` (or whatever the test treats as the source of truth) and asserting against the same count after packaging/staging. Self-maintaining.

Option 2 is preferred. The assertion changes from `assert_eq "Packaged 18 skill wrappers" "18" "$count"` to:
```bash
expected=$(find .claude/skills -mindepth 2 -maxdepth 2 -name SKILL.md | wc -l | tr -d ' ')
assert_eq "Packaged $expected skill wrappers" "$expected" "$count"
```

## Verification

After the fix, both tests must pass on macOS. Add a regression check: run `./.aitask-scripts/aitask_setup.sh --add-skill some_test_skill` (or equivalent) in a scratch project and confirm the test counts adjust automatically.
