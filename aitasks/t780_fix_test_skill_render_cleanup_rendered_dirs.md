---
priority: medium
effort: low
depends: []
issue_type: bug
status: Ready
labels: [aitask_pick]
created_at: 2026-05-17 16:44
updated_at: 2026-05-17 16:44
---

## Origin

Spawned from t777_4 during Step 8b review. Defect pre-existed t777_4 and was acknowledged in t777_3's archived plan ("Upstream defects identified") with a one-line fix proposal; tracked as its own task here so the fix actually lands.

## Upstream defect

- `tests/test_skill_render.sh:75-80 cleanup()` — `cleanup()` removes scratch *authoring* dirs (`.claude/skills/_t777_2_test_*`, etc.) but does NOT remove rendered *output* dirs (`.claude/skills/_t777_2_test_*-fast-/`, `.claude/skills/_t777_2_test_basic-_t777_2_test_profile-/`, etc.). After every run of `tests/test_skill_render.sh`, those rendered dirs are left on disk. They are gitignored (matched by the `.claude/skills/*-/` glob from t777_3), so git is unaffected, but Claude Code auto-discovers them as skills (visible in `/help` skill listings as `_t777_2_test_basic-fast-`, `_t777_2_test_rec_a-fast-`, etc.).

## Diagnostic context

The defect surfaced during t777_4 implementation: running `bash tests/test_skill_render.sh` to confirm no-regression made the leftover rendered dirs visible in Claude's skill list, where they collide visually with real skills. The new `tests/test_skill_verify.sh` works around the symptom by pre-cleaning `_t777_2_test_*` in its own startup (in addition to `_t777_4_test_*`), but the root-cause fix is in `test_skill_render.sh`'s `cleanup()`.

## Suggested fix

Extend `cleanup()` in `tests/test_skill_render.sh` to also wipe rendered output dirs alongside the authoring dirs. Concretely:

```bash
cleanup() {
    rm -rf "$TMP_DIR"
    # Authoring dirs (already present)
    # shellcheck disable=SC2115
    rm -rf "$PROJECT_DIR"/.claude/skills/"${TEST_SKILL_PREFIX}"* \
           "$PROJECT_DIR"/.gemini/skills/"${TEST_SKILL_PREFIX}"* \
           "$PROJECT_DIR"/.agents/skills/"${TEST_SKILL_PREFIX}"* \
           "$PROJECT_DIR"/.opencode/skills/"${TEST_SKILL_PREFIX}"*
}
```

Confirm by running the test, then `ls .claude/skills/ | grep -- '-$'` — should return zero matches.

Optionally extend `cleanup_with_profile()` (line 144) likewise, although it already inherits via the wrapped `cleanup()` call.

## Verification

1. `bash tests/test_skill_render.sh` — still 32/32 PASS.
2. After test run, `ls .claude/skills/ .agents/skills/ .gemini/skills/ .opencode/skills/ 2>/dev/null | grep -- '-$'` returns empty.
3. Claude Code skill list no longer shows scratch test-skill entries.
