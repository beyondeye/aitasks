---
priority: high
effort: medium
depends: [t777_26]
issue_type: test
status: Ready
labels: [tests, t777, skill-templates]
created_at: 2026-05-23 23:39
updated_at: 2026-05-25 14:59
---

# Goal

Recover the pre-rewrite text of `aitask-pick/SKILL.md` and the full `task-workflow/` closure (the 25 markdown files that existed before the t777 conversion), park them as test-only fixtures, and add parity tests that compare the current `.j2`-rendered output to the original procedural text for **every supported profile value, including the implicit "ASK" fallback** that fires when a profile key is undefined.

This is the gating prerequisite for trusting the t777 rewrite: without a stored copy of the runtime-check originals there is no way to assert that the per-profile rendered SKILL.md preserves the original behaviour for each branch of each profile key.

# Why a separate task

t777_6 (aitask-pick conversion) and t777_7 + t777_23 (task-workflow conversion) both **deleted** the original files at conversion time. No archived copy exists outside git history. Recovering them as fixtures, and adding the parity tests that consume them, are out-of-scope for those already-Done tasks but are needed before any further refactoring of the `.j2` templates lands (see follow-up sibling t777_28).

# Source SHAs (do not lose these)

- `aitask-pick` pre-rewrite SKILL.md: parent commit `f1b01895` (just before `b6dabc19 refactor: Convert aitask-pick to template + stubs (t777_6)`). Path at that SHA: `.claude/skills/aitask-pick/SKILL.md` — 225 lines, 11,256 bytes, branches on `skip_task_confirmation` at two sites (parent-task and child-task confirmation).
- `task-workflow` pre-rewrite closure: parent commit `c46366fc` (just before `70f7daf2 refactor: Stage wrapped profile-check sites under task-workflown (t777_7)`). Path at that SHA: `.claude/skills/task-workflow/` — 25 markdown files, ~161 KB total. SKILL.md is 609 lines / 44 KB; 6 sub-procedures are profile-aware (`planning.md`, `manual-verification.md`, `satisfaction-feedback.md`, `manual-verification-followup.md`, `remote-drift-check.md`, `execution-profile-selection.md`); the remaining 18 are static.

# Implementation outline

## 1. Land the fixtures

Create `tests/fixtures/skills/` (sibling to existing `tests/golden/` and `tests/lib/`). `tests/` is excluded from the release tarball at `.github/workflows/release.yml:107-120` and from `install.sh`, so nothing under it ever ships downstream.

Two subtrees:

```
tests/fixtures/skills/
├── aitask-pick/
│   └── SKILL.md.pre-rewrite                 # from f1b01895
└── task-workflow/
    ├── SKILL.md.pre-rewrite                 # from c46366fc
    ├── planning.md.pre-rewrite
    ├── manual-verification.md.pre-rewrite
    ├── satisfaction-feedback.md.pre-rewrite
    ├── manual-verification-followup.md.pre-rewrite
    ├── remote-drift-check.md.pre-rewrite
    ├── execution-profile-selection.md.pre-rewrite
    └── ... (one .pre-rewrite per file in the c46366fc closure)
```

Extraction commands (commit them as a single `chore:` commit so the provenance is obvious):

```bash
git show f1b01895:.claude/skills/aitask-pick/SKILL.md \
  > tests/fixtures/skills/aitask-pick/SKILL.md.pre-rewrite

mkdir -p tests/fixtures/skills/task-workflow
for f in $(git ls-tree -r c46366fc -- .claude/skills/task-workflow/ | awk '{print $4}'); do
  base="${f##*/}"
  git show "c46366fc:$f" > "tests/fixtures/skills/task-workflow/${base}.pre-rewrite"
done
```

Add a short `tests/fixtures/skills/README.md` explaining the SHA provenance and the rule that these files are **frozen** (never edited to match newer behaviour — they are the recorded baseline, only deleted if the rewrite goal itself changes).

## 2. Land the parity tests

New test file: `tests/test_skill_parity_runtime_vs_rendered.sh`. Pattern mirrors the existing `tests/test_skill_render_aitask_pick.sh` (golden diffs + branch-fired asserts + no-`{%`/`{{` leak).

For each `(skill, profile)` pair where `skill ∈ {aitask-pick, task-workflow}` and `profile ∈ {default, fast, remote}`:

1. Render the current `.j2` via the existing helper (`$PYTHON .aitask-scripts/lib/skill_template.py …`).
2. Identify each profile-conditional site in the pre-rewrite fixture (e.g., "If the active profile has `skip_task_confirmation` set to `true` …"). For the active profile value, determine which branch should fire:
   - true/value-set branch → assert the rendered output contains the **action sentences** from that branch and does NOT contain the AskUserQuestion text.
   - false/undefined branch (the "ASK" case) → assert the rendered output contains the **AskUserQuestion** text and does NOT contain the auto-action sentences.
3. Cross-check that no profile-conditional sentence from the pre-rewrite source is silently dropped: for each "If the active profile" guard sentence in the fixture, exactly one of its branches must appear (verbatim or with documented substitution) in the rendered output.

Make the assertion driver data-driven: a small table mapping `(skill, profile_key, profile_value) → (sentinel_that_must_appear, sentinel_that_must_be_absent)`. Comments in the table cite the source line in the pre-rewrite fixture.

Coverage target: every profile key listed in the pre-rewrite `profiles.md.pre-rewrite` reference table (`skip_task_confirmation`, `default_email`, `create_worktree`, `base_branch`, `plan_preference`, `plan_preference_child`, `post_plan_action`, `plan_verification_required`, `enableFeedbackQuestions`, `remote_drift_check`, `manual_verification_followup_mode`, plus aitask-pick's keys). At least one row per key per representative value, including the undefined / ASK case.

## 3. Wire into CI / pre-commit

Add the new test to whatever runner enumerates `tests/test_skill_*.sh` today (check `tests/run_all.sh` or equivalent; if missing, document the manual `bash tests/test_skill_parity_runtime_vs_rendered.sh` invocation in the test file's header comment).

## 4. Verify it actually catches regressions

Before merging, deliberately break the test in two ways and confirm a failure:
- Temporarily remove one `{% if %}` arm from `aitask-pick/SKILL.md.j2` (e.g., the auto-confirm action for `skip_task_confirmation=true`). The parity test must fail for `fast`/`remote` profiles.
- Temporarily change the AskUserQuestion text in a default-branch render. The parity test must fail for `default`.

Revert both before commit. Without this self-check, the test is just a green rubber-stamp.

# Out of scope (explicitly)

- Any `.j2` template refactoring to reduce branch duplication — that is sibling task **t777_28**, which `depends:` on this one so the parity tests gate the refactor.
- Touching the runtime-check originals at their old SHAs (we only copy them out).
- Adding parity coverage for the other already-converted skills (`aitask-explore`, `aitask-fold`, `aitask-qa`, `aitask-pr-import`, `aitask-revert`). If desired, file as a follow-up; this task focuses on the two pilot skills with the deepest profile logic.

# Acceptance criteria

- `tests/fixtures/skills/aitask-pick/SKILL.md.pre-rewrite` exists and byte-matches `git show f1b01895:.claude/skills/aitask-pick/SKILL.md`.
- `tests/fixtures/skills/task-workflow/*.pre-rewrite` covers all 25 files from `c46366fc`.
- `bash tests/test_skill_parity_runtime_vs_rendered.sh` passes for the current rendered output of both skills across `{default, fast, remote}` profiles.
- The two deliberate-break self-checks (Step 4) both fail before revert.
- `tests/` is still absent from the release tar command (no regression in packaging boundary).
- `./.aitask-scripts/aitask_skill_verify.sh` and `shellcheck .aitask-scripts/aitask_*.sh` still pass.
