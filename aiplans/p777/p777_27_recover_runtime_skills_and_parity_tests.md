---
Task: t777_27_recover_runtime_skills_and_parity_tests.md
Parent Task: aitasks/t777_modular_pick_skill.md
Sibling Tasks: aitasks/t777/t777_*_*.md
Archived Sibling Plans: aiplans/archived/p777/p777_*_*.md
Worktree: (none — profile 'fast', working on current branch)
Branch: main
Base branch: main
---

# Plan: t777_27 — Recover pre-rewrite skills + add parity tests

## Context

The t777 redesign converted `aitask-pick/SKILL.md` and the whole
`task-workflow/` closure from static procedural markdown into Jinja
`.md.j2` / `.md` templates with `{% if profile.… %}` wraps. The conversion
tasks (`t777_6`, `t777_7`, `t777_23`) **deleted** the original procedural
text at conversion time. No archived copy survives outside git history at
parent commits `f1b01895` (aitask-pick) and `c46366fc` (task-workflow).

This task lands a **frozen** copy of those originals under `tests/fixtures/`
and a parity test that asserts: for every profile-conditional branch in the
pre-rewrite source, the current `.j2` render preserves the original
behaviour for each branch of each profile key — including the implicit
"ASK / fallback" case when a profile key is undefined.

This is the gating prerequisite for trusting the t777 rewrite and a
hard dependency of follow-up sibling **t777_28** (`.j2` branch-dedup
refactor) — which `depends:` on this one so the parity tests gate the
refactor.

`tests/` is excluded from the release tarball
(`.github/workflows/release.yml:107-120`) and from `install.sh`, so
nothing under `tests/fixtures/` ever ships downstream.

## Phase 1 — Land fixtures (one `chore:` commit, provenance-visible)

Create `tests/fixtures/skills/` (sibling to `tests/golden/` and
`tests/lib/`) with two subtrees:

```
tests/fixtures/skills/
├── README.md                                  # SHA provenance + frozen rule
├── aitask-pick/
│   └── SKILL.md.pre-rewrite                   # from f1b01895
└── task-workflow/
    ├── SKILL.md.pre-rewrite                   # from c46366fc
    ├── planning.md.pre-rewrite
    ├── manual-verification.md.pre-rewrite
    ├── satisfaction-feedback.md.pre-rewrite
    ├── manual-verification-followup.md.pre-rewrite
    ├── remote-drift-check.md.pre-rewrite
    ├── execution-profile-selection.md.pre-rewrite
    └── … (one .pre-rewrite per file in `git ls-tree -r c46366fc -- .claude/skills/task-workflow/`, 25 files total)
```

Extraction commands (verified — `git rev-parse f1b01895`/`c46366fc` resolve;
`git ls-tree -r c46366fc -- .claude/skills/task-workflow/ | wc -l` = 25):

```bash
mkdir -p tests/fixtures/skills/aitask-pick tests/fixtures/skills/task-workflow

git show f1b01895:.claude/skills/aitask-pick/SKILL.md \
  > tests/fixtures/skills/aitask-pick/SKILL.md.pre-rewrite

while IFS= read -r f; do
  base="${f##*/}"
  git show "c46366fc:$f" > "tests/fixtures/skills/task-workflow/${base}.pre-rewrite"
done < <(git ls-tree -r c46366fc -- .claude/skills/task-workflow/ | awk '{print $4}')
```

Write `tests/fixtures/skills/README.md` (concise, ≤ 25 lines):

> Frozen copies of pre-rewrite skill text used by
> `tests/test_skill_parity_runtime_vs_rendered.sh`. Sources:
> `aitask-pick/SKILL.md.pre-rewrite` ← `f1b01895:.claude/skills/aitask-pick/SKILL.md`
> (parent of `b6dabc19 refactor: Convert aitask-pick to template + stubs (t777_6)`);
> `task-workflow/*.pre-rewrite` ← `c46366fc:.claude/skills/task-workflow/*`
> (parent of `70f7daf2 refactor: Stage wrapped profile-check sites …`).
> **Frozen — never edited to match newer behaviour.** They record the
> baseline that the current Jinja-rendered output must preserve.
> Only delete if the rewrite goal itself changes (separate task).

**Commit:** `chore: Recover pre-rewrite skill fixtures for parity testing (t777_27)`

## Phase 2 — Land the parity test

New file: `tests/test_skill_parity_runtime_vs_rendered.sh` (~250 lines).
Patterns mirror `tests/test_skill_render_aitask_pick.sh`
(`assert_eq`/`assert_contains`/`assert_not_contains`, PASS/FAIL counter,
minijinja-availability SKIP guard).

### Assertion table (data-driven; comments cite pre-rewrite line numbers)

Hard-coded bash arrays (or here-doc fed into a parser loop). Each row:
`SKILL|PROFILE|FIXTURE_LINE|KEY|SENTINEL_PRESENT|SENTINEL_ABSENT|NOTE`.

Concrete rows derived from the audit in `p777_21` + the Explore-agent
verification against current rendered output (`.claude/skills/aitask-pick-<p>-/SKILL.md`,
`.claude/skills/task-workflow-<p>-/SKILL.md`):

| Skill | File / line in fixture | Key | `fast` / `remote` sentinel-PRESENT | `default` sentinel-PRESENT (= ASK case) |
|-------|-----------------------|-----|------------------------------------|----------------------------------------|
| aitask-pick | SKILL.md:44 (parent confirm) | `skip_task_confirmation` | `auto-confirming task selection` | `AskUserQuestion` + "Is this the correct task" |
| aitask-pick | SKILL.md:72 (child confirm) | `skip_task_confirmation` | `auto-confirming task selection` (second site) | `AskUserQuestion` (second site) |
| task-workflow | SKILL.md:98 | `default_email` | `Profile '<p>': using email` | `Enter your email to track who is working on this task` |
| task-workflow | SKILL.md:183 | `create_worktree` | `working on current branch` (fast) / `creating worktree` (remote) | `Do you want to work on a new branch and worktree` |
| task-workflow | SKILL.md:198 | `base_branch` | `using base branch` | `Which branch should the new task branch be based on` |
| task-workflow | planning.md:29 | `plan_preference` / `_child` | profile-specific verify/use_current display string | `How would you like to proceed with the plan` |
| task-workflow | planning.md:294 | `post_plan_action` / `_for_child` | `proceeding to implementation` (when value=`start_implementation`) | `Plan saved to` + 4-option `AskUserQuestion` |
| task-workflow | manual-verification-followup.md:19 | `manual_verification_followup_mode` | `Profile '<p>': skipping manual verification follow-up offer` (value=`never`) | manual-verification-followup `AskUserQuestion` text |
| task-workflow | satisfaction-feedback.md:34 | `enableFeedbackQuestions` | feedback-skipped (sentinel-absent of AskUserQuestion) when `false` | satisfaction `AskUserQuestion` text when undefined/`true` |
| task-workflow | remote-drift-check.md:17 | `remote_drift_check` | (silent return — sentinel: absence of drift-check output) when value=`skip` | `Remote drift detected` warning text otherwise |

Coverage target: every profile key from
`p777_21`'s 12-key universe (`skip_task_confirmation`, `default_email`,
`create_worktree`, `base_branch`, `plan_preference`, `plan_preference_child`,
`post_plan_action`, `post_plan_action_for_child`, `plan_verification_required`,
`enableFeedbackQuestions`, `remote_drift_check`,
`manual_verification_followup_mode`) — one row per key per representative
value, including the undefined / ASK case (i.e. the `default` profile).

### Per-row assertion loop

```bash
for ROW in "${ROWS[@]}"; do
  IFS='|' read -r SKILL PROFILE FIXTURE_LINE KEY PRESENT ABSENT NOTE <<<"$ROW"
  # Render the current .j2 closure for this (skill, profile) into a tmpdir.
  # Use the existing helper directly (no `./ait skill ...` indirection).
  RENDER_OUT=$(./.aitask-scripts/aitask_skill_render.sh "$SKILL" \
      --profile "$PROFILE" --agent claude --output-dir "$TMPDIR/render" --force 2>&1)

  # Locate the rendered top-level file for this skill.
  RENDERED_FILE="$TMPDIR/render/skills/${SKILL}-${PROFILE}-/SKILL.md"

  # Assert sentinel presence/absence.
  if [[ -n "$PRESENT" ]]; then
    assert_contains "$SKILL/$PROFILE key=$KEY (fixture:$FIXTURE_LINE) present" \
                    "$PRESENT" "$(<"$RENDERED_FILE")"
  fi
  if [[ -n "$ABSENT" ]]; then
    assert_not_contains "$SKILL/$PROFILE key=$KEY (fixture:$FIXTURE_LINE) absent" \
                        "$ABSENT" "$(<"$RENDERED_FILE")"
  fi
done
```

### Cross-check: every pre-rewrite conditional has at least one render arm

After the per-row loop, a second pass scans each pre-rewrite fixture for
`If the active profile|Profile check[.:]|If the effective action is`
lines. For each match, build the union of sentinels-PRESENT across all 3
profiles for that row and assert that **at least one** of them appears in
**some** profile's render. This catches the failure mode where a
template author deletes both arms by accident.

### Failure messaging

On `assert_contains` failure, print: fixture file + line, the conditional
sentence (head -1 of the fixture line + next 2 lines), the expected
sentinel, and the rendered file path so the developer can `diff` quickly.

### No-leak assertion

Cheap re-affirmation of an existing invariant: every rendered file under
the per-skill tmpdir must contain no `{%` or `{{` tokens. Already covered
by `tests/test_skill_render_aitask_pick.sh` and
`tests/test_skill_render_task_workflow.sh`; replicated here so this test
stands alone.

## Phase 3 — CI / runner wiring

There is **no** `tests/run_all.sh` in this repo (verified). The existing
`test_skill_*.sh` files are run individually (per `CLAUDE.md`'s "Tests are
bash scripts run individually"). Wiring decisions:

1. Document the manual invocation in the test file's header comment
   (`# Run: bash tests/test_skill_parity_runtime_vs_rendered.sh`), matching
   the other `test_skill_*.sh` headers.
2. **Pre-commit / verify hook**: extend `.aitask-scripts/aitask_skill_verify.sh`
   to also run this test when its sibling render tests pass — minimal
   wiring, no new runner. (If touching `aitask_skill_verify.sh` widens
   scope beyond what feels safe in this task, leave it out — the test is
   discoverable through the `test_skill_*.sh` glob and the header docs the
   command. Decide during implementation.)
3. No GitHub Actions wiring needed — there is no CI step that enumerates
   `tests/test_*.sh` today.

## Phase 4 — Self-check (mandatory before commit)

Per task acceptance criterion #4, prove the test actually catches
regressions. Two deliberate breakages, each reverted before final commit:

1. **Template-arm removal:** Temporarily delete the
   `{% if profile.skip_task_confirmation is defined and profile.skip_task_confirmation %}`
   auto-confirm arm in `.claude/skills/aitask-pick/SKILL.md.j2` (one of
   the two sites). Re-run the test. **Expect:** `aitask-pick/fast` and
   `aitask-pick/remote` rows fail with "sentinel-PRESENT missing"; `default`
   row still passes. Revert the edit.
2. **AskUserQuestion text mutation:** Temporarily change the
   AskUserQuestion question wording in the `default` arm of
   `.claude/skills/task-workflow/SKILL.md` (e.g. for `default_email`).
   Re-run the test. **Expect:** `task-workflow/default` row for
   `default_email` fails with "sentinel-PRESENT 'Enter your email …'
   missing". Revert the edit.

Without this self-check the test is a green rubber-stamp. Record both
breakage diffs + the failing test output in Final Implementation Notes
so a future reader can see the test was empirically validated.

## Phase 5 — Commits + archival (Step 9 standard)

Per `task-workflow/SKILL.md` Step 9, no deviations:

1. **Phase 1 commit** (already done): `chore: Recover pre-rewrite skill
   fixtures for parity testing (t777_27)`.
2. **Phase 2 + 3 commit**: `test: Add parity test
   tests/test_skill_parity_runtime_vs_rendered.sh (t777_27)`. Touches the
   new test file and (if Phase 3.2 lands) `.aitask-scripts/aitask_skill_verify.sh`.
3. **Plan commit** via `./ait git`: updated plan file with Final
   Implementation Notes.
4. **Archive**: `./.aitask-scripts/aitask_archive.sh 777_27`.
5. **Push**: `./ait git push`.

Attribution per `code-agent-commit-attribution.md`.
No linked issue.

## Out of scope (mirrors task spec — explicit)

- Any `.j2` template refactoring to reduce branch duplication (that is
  sibling **t777_28**, which depends on this task).
- Touching the runtime-check originals at their old SHAs (we only copy
  them out — `git show … > …`).
- Adding parity coverage for the other converted skills
  (`aitask-explore`, `aitask-fold`, `aitask-qa`, `aitask-pr-import`,
  `aitask-revert`, `aitask-pickrem`, `aitask-pickweb`, `aitask-review`).
  This pilot focuses on the two skills with the deepest profile logic.
- Parity coverage for new files added to the `task-workflow/` closure
  **after** `c46366fc` (`related-task-discovery.md`,
  `task-fold-content.md`, `task-fold-marking.md` — these have no
  pre-rewrite baseline; their behavior is asserted by the existing
  per-skill render tests + goldens, not by this parity test).

## Acceptance criteria (verbatim from task description)

1. `tests/fixtures/skills/aitask-pick/SKILL.md.pre-rewrite` exists and
   byte-matches `git show f1b01895:.claude/skills/aitask-pick/SKILL.md`.
2. `tests/fixtures/skills/task-workflow/*.pre-rewrite` covers all 25 files
   from `c46366fc`.
3. `bash tests/test_skill_parity_runtime_vs_rendered.sh` passes for the
   current rendered output of both skills across `{default, fast, remote}`
   profiles.
4. The two deliberate-break self-checks (Phase 4) both fail before revert.
5. `tests/` is still absent from the release tar command (no regression
   in packaging boundary).
6. `./.aitask-scripts/aitask_skill_verify.sh` and `shellcheck
   .aitask-scripts/aitask_*.sh` still pass.

## Verification (end-to-end, before commit)

```bash
# 1. Fixture byte-match
diff <(git show f1b01895:.claude/skills/aitask-pick/SKILL.md) \
     tests/fixtures/skills/aitask-pick/SKILL.md.pre-rewrite     # exit 0

# 2. Fixture count
ls tests/fixtures/skills/task-workflow/*.pre-rewrite | wc -l   # = 25

# 3. Parity test
bash tests/test_skill_parity_runtime_vs_rendered.sh             # exit 0

# 4. Existing checks unbroken
bash tests/test_skill_render_aitask_pick.sh                     # exit 0
bash tests/test_skill_render_task_workflow.sh                   # exit 0
./.aitask-scripts/aitask_skill_verify.sh                        # exit 0
shellcheck .aitask-scripts/aitask_*.sh                          # exit 0

# 5. Packaging boundary
grep -n "tests/" .github/workflows/release.yml                  # no `tests/` in tar command
```

## Step 9 — Post-Implementation reference

See Phase 5 above for the standard archival sequence.

## Final Implementation Notes

(To be filled in at Step 8 by the implementing agent.)

- **Actual work done:** <summary>
- **Deviations from plan:** <changes from this plan and why>
- **Issues encountered:** <problems found and how resolved>
- **Key decisions:** <technical decisions made during implementation>
- **Upstream defects identified:** <`path:LINE — summary` bullets, or `None`>
- **Notes for sibling tasks:** <hand-off for t777_28 in particular — what
  the parity test's failure messages look like in practice, any rows that
  needed sentinel refinement after the first run>
