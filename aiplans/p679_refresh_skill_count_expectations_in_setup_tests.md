---
Task: t679_refresh_skill_count_expectations_in_setup_tests.md
Base branch: main
plan_verified: []
---

# Plan — t679: Refresh skill count expectations in setup tests

## Context

The macOS audit (t658) baseline run flagged six failing assertions in two
setup-test scripts. All failures share one root cause: the tests hard-code
expected counts (skills, commands, activate_skill rules) that have drifted as
the catalog grew.

- `tests/test_opencode_setup.sh` — expects `18` skill wrappers and `18`
  command wrappers; the source dirs now hold `21` and `20` respectively.
- `tests/test_gemini_setup.sh` — expects `19` `activate_skill` entries in
  both the seed policy and the merged global policy; the seed file now has
  `20`.

Per the task description, the self-maintaining option is preferred: derive
expected values from the source-of-truth files at test runtime so the tests
stop drifting whenever the catalog grows.

### Cross-agent gap discovered during planning (NOT in scope)

While inspecting counts, two skills surfaced as un-ported across agent trees
(claude is the source of truth per CLAUDE.md "WORKING ON SKILLS / CUSTOM
COMMANDS"):

| Skill | `.claude/skills` | `.opencode/skills` | `.agents/skills` (codex) | `.opencode/commands` | `.gemini/commands` | gemini policy `activate_skill` |
|---|:-:|:-:|:-:|:-:|:-:|:-:|
| `aitask-add-model` | ✓ | — | — | — | — | — |
| `aitask-qa` | ✓ | ✓ | ✓ | — | ✓ | — |
| (other 20 `aitask-*`) | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |

`.gemini/skills/` is intentionally empty (consolidated into `.agents/skills/`
per `tests/test_gemini_setup.sh:41`).

**Decision:** keep t679 narrow (test-only). Spawn a follow-up task to port
the two missing skills to all non-claude agent trees. See "Follow-up task"
section at the end of this plan.

## Files to modify

- `tests/test_opencode_setup.sh`
- `tests/test_gemini_setup.sh`

No source code changes — these are test-only adjustments.

## Implementation

### 1. `tests/test_opencode_setup.sh`

Right after the `REPO_DIR` definition (around line 33), once before any
assertion uses them, derive the expected counts from the upstream source
directories:

```bash
expected_skill_count=$(find "$REPO_DIR/.opencode/skills" -mindepth 2 -maxdepth 2 -name "SKILL.md" -type f | wc -l | tr -d ' ')
expected_command_count=$(find "$REPO_DIR/.opencode/commands" -type f -name "*.md" | wc -l | tr -d ' ')
```

Then replace the four hard-coded `18` assertions:

- Line 53 — `assert_eq "Packaged 18 skill wrappers" "18" "$skill_count"`
  becomes
  `assert_eq "Packaged $expected_skill_count skill wrappers" "$expected_skill_count" "$skill_count"`.
- Line 56 — `assert_eq "Packaged 18 command wrappers" "18" "$command_count"`
  becomes
  `assert_eq "Packaged $expected_command_count command wrappers" "$expected_command_count" "$command_count"`.
- Line 85 — `assert_eq "Staged 18 wrappers to metadata" "18" "$staged_count"`
  becomes
  `assert_eq "Staged $expected_skill_count wrappers to metadata" "$expected_skill_count" "$staged_count"`.
- Line 88 — `assert_eq "Staged 18 command wrappers" "18" "$staged_command_count"`
  becomes
  `assert_eq "Staged $expected_command_count command wrappers" "$expected_command_count" "$staged_command_count"`.

The "expected = source-count, actual = staged-count" assertion is still
meaningful: it verifies the staging pipeline copied every source file
without loss.

### 2. `tests/test_gemini_setup.sh`

The activate_skill rules in the merged global policy come straight from the
seed policy file at `seed/geminicli_policies/aitasks-whitelist.toml`. That
file is the source of truth.

Once near the top of the file (e.g. just after `REPO_DIR=…` around line 33),
derive the expected count from the seed file:

```bash
expected_activate_skill_count=$(grep -c '^toolName = "activate_skill"$' "$REPO_DIR/seed/geminicli_policies/aitasks-whitelist.toml" | tr -d ' ')
```

Then replace the two hard-coded `19` assertions:

- Line 269 — `assert_eq "Global policy has explicit aitask skill entries" "19" "$global_activate_skill_count"`
  becomes
  `assert_eq "Global policy has explicit aitask skill entries" "$expected_activate_skill_count" "$global_activate_skill_count"`.
- Line 315 — `assert_eq "Seed policy has explicit aitask skill entries" "19" "$seed_activate_skill_count"`
  becomes
  `assert_eq "Seed policy has explicit aitask skill entries" "$expected_activate_skill_count" "$seed_activate_skill_count"`.

The seed-against-itself check is now tautological-looking but documents the
intent: both seed and merged-global policies should have the same number of
explicit activate_skill rules.

## Verification

Run both tests:

```bash
bash tests/test_opencode_setup.sh
bash tests/test_gemini_setup.sh
```

Both must report `0 failed` for all assertions.

Spot-check the dynamic counts match reality:

```bash
find .opencode/skills -mindepth 2 -maxdepth 2 -name SKILL.md | wc -l   # currently 21
find .opencode/commands -type f -name "*.md" | wc -l                   # currently 20
grep -c '^toolName = "activate_skill"$' seed/geminicli_policies/aitasks-whitelist.toml   # currently 20
```

These numbers will drift as the catalog grows — which is exactly the point.
The tests will follow without further edits.

## Follow-up task (created during Step 8/9)

After t679 commits, create one standalone follow-up task via
`./.aitask-scripts/aitask_create.sh --batch` covering both porting gaps:

- **Title:** "Port aitask-add-model and aitask-qa wrappers to non-claude
  agent trees"
- **issue_type:** `chore`
- **priority:** medium (low if the user prefers)
- **labels:** `claude-code-skills`
- **Description should include:**
  - The gap table from the Context section above.
  - For each skill, the specific touchpoints to add:
    - `aitask-add-model`: create wrappers under `.opencode/skills/`,
      `.opencode/commands/`, `.agents/skills/`, `.gemini/commands/`; add
      `[[rule]] toolName = "activate_skill" / argsPattern = "aitask-add-model"`
      to `seed/geminicli_policies/aitasks-whitelist.toml` (mirror existing
      entries near line where the alphabetical position is). Adapt from
      `.claude/skills/aitask-add-model/` per the porting guidance in
      `CLAUDE.md` "WORKING ON SKILLS / CUSTOM COMMANDS".
    - `aitask-qa`: create wrappers under `.opencode/commands/` and add the
      activate_skill entry to the gemini policy file. The opencode skill,
      codex skill, and gemini command already exist.
  - Verification: re-run `bash tests/test_opencode_setup.sh` and
    `bash tests/test_gemini_setup.sh` — counts should grow by 1 (gemini)
    and by 2 (opencode skills/commands) and the dynamic assertions should
    still pass.

## Step 9 (Post-Implementation)

Standard archival flow per `task-workflow/SKILL.md` Step 9: commit changes,
update plan, archive task, push. The follow-up task creation above happens
between Step 8 (Commit changes) and Step 9 (Archive).

## Final Implementation Notes

- **Actual work done:** Two test files made self-maintaining.
  `tests/test_opencode_setup.sh` now derives `expected_skill_count` and
  `expected_command_count` from the upstream `.opencode/skills/aitask-*/SKILL.md`
  and `.opencode/commands/*.md` source dirs at the top of the file (just
  after `REPO_DIR` definition), and uses those variables in all four
  packaging/staging assertions (former lines 53, 56, 85, 88).
  `tests/test_gemini_setup.sh` derives `expected_activate_skill_count` from
  `seed/geminicli_policies/aitasks-whitelist.toml` near the top of the file
  and uses it in the global-policy and seed-policy assertions (former lines
  269, 315).
- **Deviations from plan:** None. Implemented exactly as planned. The
  gemini-test variable was placed at the top of the file (after `REPO_DIR`)
  rather than inside Test 8, since the plan flagged that as the cleaner
  option.
- **Issues encountered:** None.
- **Key decisions:**
  - Kept the "expected = source-count, actual = staged-count" assertion
    structure because it still verifies the staging pipeline copied every
    source file without loss — the test is not tautological.
  - Cross-agent skill porting gap (aitask-add-model, aitask-qa) deferred to
    a follow-up task (see "Follow-up task" section above) per user
    direction during planning. t679 stays test-only.
- **Upstream defects identified:** None. The "Cross-agent gap" surfaced
  during planning is a porting omission, not an upstream defect that seeded
  the symptom — t679's symptom (test count drift) was caused by the tests
  hard-coding numbers, not by the missing wrappers. The follow-up task
  tracks the porting work directly.

## Verification (run results)

- `bash tests/test_opencode_setup.sh` → 31 passed, 0 failed.
- `bash tests/test_gemini_setup.sh` → 57 passed, 0 failed.
- Live counts at implementation time: 21 opencode skills, 20 opencode
  commands, 20 gemini activate_skill entries — assertions now match these
  dynamically.
