---
priority: medium
effort: low
depends: [790]
issue_type: test
status: Done
labels: [testing, test_infrastructure]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_7_1m
created_at: 2026-05-25 18:04
updated_at: 2026-05-26 18:58
completed_at: 2026-05-26 18:58
boardidx: 110
---

## Context

Surfaced by t790 triage of pre-existing test failures
(`aiplans/p790_triage_preexisting_test_failures_post_t777.md`, Bucket B).

`tests/test_opencode_setup.sh` Tests 1 and 2 fail with
`expected: '50', got: '44'`. Root cause is a glob-vs-count divergence in the
test itself:

- `expected_skill_count` uses
  `find .opencode/skills -mindepth 2 -maxdepth 2 -name SKILL.md`, counting
  all SKILL.md files (50).
- The packaging and staging loops iterate
  `for skill_dir in "$REPO_DIR/.opencode/skills"/aitask-*/`, copying only
  the 44 `aitask-*`-prefixed dirs.

The 6 unmatched dirs were added by t777's profile-aware skill conversion:

```
.opencode/skills/task-workflow-{default,fast,remote}-/SKILL.md
.opencode/skills/user-file-select-{default,fast,remote}-/SKILL.md
```

These are legitimately not `aitask-*`-prefixed (they are shared closures,
not top-level user-facing skills).

## Approach

Broaden the packaging glob and staging glob in `tests/test_opencode_setup.sh`
so the actual count matches the expected count. Both Test 1 (packaging) and
Test 2 (staging) need parallel updates — same loop pattern is duplicated.

Two reasonable shapes:
- Iterate every `<repo>/.opencode/skills/*/` subdir (excluding the two
  `opencode_*` flat markdowns), which mirrors what `find -mindepth 2
  -maxdepth 2 -name SKILL.md` actually counts.
- Or list the prefixes explicitly: `aitask-*`, `task-workflow-*-`,
  `user-file-select-*-`. Less future-proof — every new profile-variant
  closure would need a fixture update.

First shape preferred (single source of truth, symmetric with the count).

## Out of scope

- Other Bucket A / C failures from t790.
- Renaming the rendered skill dirs to `aitask-*` to satisfy the old glob.
- Skill-render or template-engine changes.

## Verification

- `bash tests/test_opencode_setup.sh` passes all 31 assertions.
- Whole-suite regression loop (p734 §3) shows `test_opencode_setup.sh`
  removed from the FAIL list.
- Adding a new profile-variant skill (e.g., another `*-default-/`) does not
  re-break the test.
