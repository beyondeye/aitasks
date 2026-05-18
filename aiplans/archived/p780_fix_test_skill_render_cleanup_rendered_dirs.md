---
Task: t780_fix_test_skill_render_cleanup_rendered_dirs.md
Worktree: (none — current branch)
Branch: main
Base branch: main
---

# Plan: Verify and close t780 (cleanup of rendered output dirs)

## Summary

t780 was filed during t777_4's Step 8b review as a follow-up to a defect
acknowledged in t777_3's archived plan: `tests/test_skill_render.sh`'s
`cleanup()` allegedly removed authoring dirs but **not** rendered output
dirs, leaving Claude-discovered scratch skills behind after every test run.

Investigation shows the defect does **not** exist in current code. The fix
was already in place since the file was authored in commit 62ac349b
(t777_2). The task's "Suggested fix" code is byte-identical to the code
already present at `tests/test_skill_render.sh:72-80`.

## Diagnosis

The cleanup function is:

```bash
cleanup() {
    rm -rf "$TMP_DIR"
    # Remove any scratch skill dirs (template authoring dirs + rendered output dirs).
    # shellcheck disable=SC2115
    rm -rf "$PROJECT_DIR"/.claude/skills/"${TEST_SKILL_PREFIX}"* \
           "$PROJECT_DIR"/.gemini/skills/"${TEST_SKILL_PREFIX}"* \
           "$PROJECT_DIR"/.agents/skills/"${TEST_SKILL_PREFIX}"* \
           "$PROJECT_DIR"/.opencode/skills/"${TEST_SKILL_PREFIX}"*
}
```

`TEST_SKILL_PREFIX="_t777_2_test_"` and the glob `${TEST_SKILL_PREFIX}*`
expands to `_t777_2_test_*`. That glob already matches **both** classes of
directory:

- Authoring dirs: `_t777_2_test_basic`, `_t777_2_test_rec_a`, ...
- Rendered output dirs: `_t777_2_test_basic-fast-`,
  `_t777_2_test_basic-_t777_2_test_profile-`, `_t777_2_test_rec_a-fast-`,
  ...

All rendered output dirs share the `_t777_2_test_` prefix (the trailing
hyphen convention from t777_3 appends `-<profile>-` to the original skill
name; it does not rewrite the prefix), so they are caught by the same
glob as the authoring dirs.

The t780 description likely conflated the diagnosis from t777_3's plan with
the actual on-disk reality. The relevant code path may have been incorrect
in an intermediate development state before t777_2 landed, but it has been
correct in every committed revision.

## Empirical verification

1. Pre-run disk state — clean:
   ```
   ls .claude/skills/ .agents/skills/ .gemini/skills/ .opencode/skills/ \
       2>/dev/null | grep -E '^_t777_2_test_|-$'
   # (no output)
   ```
2. `bash tests/test_skill_render.sh` → `PASS: 31, FAIL: 0, SKIP: 0, TOTAL: 31`.
3. Post-run disk state — still clean (same grep, no output).
4. The verification command from t780's "Verification" section
   (`ls .claude/skills/ | grep -- '-$'`) returns zero matches.

The Claude Code skill listing visible in mid-test `<system-reminder>`
snapshots reflects the transient state between scratch-dir creation
(`mkdir -p ".claude/skills/$SK1"`) and the `EXIT` trap firing
(`trap cleanup EXIT`). Once the trap completes, those entries vanish.

## Resolution

Close as already-fixed. No code changes are made. This plan file is the
artifact-of-record.

## Final Implementation Notes

- **Actual work done:** No code changes. Investigation, empirical
  reproduction attempt (test passed with no leftover dirs), plan
  documentation, archival.
- **Deviations from plan:** None — the plan itself documents the no-op
  resolution.
- **Issues encountered:** Mid-test `<system-reminder>` skill snapshots
  briefly listed scratch skills (e.g. `_t777_2_test_basic-fast-`),
  initially suggesting the bug was live. Direct disk inspection after the
  trap fired confirmed they were transient — the harness had snapshotted
  the skill tree before the test's `EXIT` trap completed.
- **Key decisions:** Per user direction, closed as already-fixed rather
  than adding redundant defensive `rm -rf` lines that would only
  re-target the same dirs the existing glob already catches.
- **Upstream defects identified:** None.
