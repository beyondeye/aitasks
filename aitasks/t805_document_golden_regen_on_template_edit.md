---
priority: medium
effort: low
depends: []
issue_type: documentation
status: Ready
labels: [documentation]
created_at: 2026-05-19 22:32
updated_at: 2026-05-19 22:32
---

## Context

Documentation gap surfaced during t777_9 implementation. Goldens at
`tests/golden/skills/<skill>/SKILL-<profile>-<agent>.md` are byte-for-byte
snapshots of rendered template output. Any edit to a `.md.j2` (or to any
file in its render closure — task-workflow procedures, etc.) that shifts
rendered bytes will fail Test 1's `assert_eq`. The regenerate-and-diff
cycle is also the **point** of goldens (memory:
`feedback_golden_file_tests_for_template_engines`) — the diff is the audit
signal on every template edit.

Neither doc CLAUDE.md points to spells this out as a workflow rule:

- `aidocs/skill_authoring_conventions.md:206-212` — mentions golden diffs
  but scoped to the narrow "Jinja comment convention should be
  render-neutral" scenario.
- `aidocs/stub-skill-pattern.md:233-238` (Pilot Finding #3) — says
  goldens are mandatory (commit them), but framed as a one-time
  conversion-time decision, not an ongoing workflow rule.

Result: future template edits could land without golden regen, silently
diverging goldens from rendered output. Loud failure happens at the next
`bash tests/test_skill_render_*.sh` run, but a contributor unfamiliar with
the convention might mistakenly regenerate the goldens blindly to "fix the
test" rather than reviewing the diff.

## Key Files to Modify

- `aidocs/skill_authoring_conventions.md` — add a new subsection (under
  the existing render-neutrality paragraph) titled approximately "When
  you edit a `.md.j2` (or any file in its closure)" with:
  - The regenerate-and-diff command (3×4 render loop).
  - The rationale: the diff is the audit signal — review it, don't
    rubber-stamp it.
  - Pointer to the test scripts (`tests/test_skill_render_*.sh`) for
    enforcement.
- `aidocs/stub-skill-pattern.md` — extend Pilot Finding #3 with the
  operational rule: "Goldens must be regenerated and committed alongside
  *any* edit to a `.md.j2` or closure file, not just at conversion
  time." Or add a new bullet near it.
- (Optional, evaluate during impl) `CLAUDE.md` "Working on Skills /
  Custom Commands" section: add a one-line pointer if the rule fits
  there better than (or in addition to) `aidocs/`.

## Implementation Plan

1. **Drift audit first** — before writing the documentation, verify the
   premise. For every committed `.md.j2` template + closure, regenerate
   goldens and `git diff` to check whether any committed goldens have
   already drifted from current rendered output. Scope:
   - `tests/golden/skills/aitask-pick/` (12 files, from t777_6)
   - `tests/golden/skills/aitask-explore/` (12 files, from t777_8)
   - `tests/golden/skills/aitask-review/` (12 files, from t777_9)
   - `tests/golden/procs/` (procedure goldens, if any)
   Approach: a small `--check` mode for the existing regen loop that
   regenerates to a temp dir and diffs against committed goldens; report
   per-file PASS/DRIFT. **If drift is found**, treat each drifted file as
   a separate finding: investigate which template edit caused it, decide
   whether to update the golden (intended drift) or revert the template
   (unintended drift). Surface findings as bullets in this task's Final
   Implementation Notes — separate fix-up tasks if the drift count > 3
   or if intent is unclear per-case.
2. **Write the documentation** — once drift state is known and any
   real drifts are reconciled, add the workflow rule:
   - New subsection in `aidocs/skill_authoring_conventions.md` (suggested
     placement: immediately after the existing render-neutrality
     paragraph).
   - Extension to `aidocs/stub-skill-pattern.md` Pilot Finding #3.
   - Optional CLAUDE.md cross-reference.
3. **Capture command snippets** — the docs should include the exact
   regenerate command for entry-point templates and for procedure
   templates (they live in different dirs). Reuse the loop from t777_8's
   `tests/test_skill_render_aitask_explore.sh` / t777_9's review test.
4. **Add a `make-style` helper (optional, evaluate at impl time)** —
   `.aitask-scripts/aitask_skill_regenerate_goldens.sh <skill>` that
   bundles the 3×4 render loop and prints a clear diff summary. If the
   helper is added, doc the rule as "run this script, review the diff,
   commit if intended." Defer the helper if it adds complexity without
   clear benefit — the inline loop is short enough.

## Reference Files for Patterns

- `aidocs/skill_authoring_conventions.md:206-212` (existing
  render-neutrality paragraph — model for the new subsection)
- `aidocs/stub-skill-pattern.md:211-262` (Pilot Findings section — model
  for extending Finding #3)
- `tests/test_skill_render_aitask_review.sh` (Test 1's `assert_eq` loop
  is the enforcement; the regenerate command is the inverse)
- Memory: `feedback_golden_file_tests_for_template_engines`

## Verification Steps

1. After drift audit: report all drift findings (or "no drift") in this
   task's Final Implementation Notes. If drifts were found and
   reconciled, list each file and the resolution (golden updated /
   template reverted / both).
2. After doc edits: re-render goldens for all 3 converted skills (pick,
   explore, review) and confirm no new drift was introduced by the
   ongoing audit work.
3. `./.aitask-scripts/aitask_skill_verify.sh` → OK (3 templates × 4
   agents).
4. `bash tests/test_skill_render_aitask_review.sh`, `aitask_pick.sh`,
   `aitask_explore.sh` (and any procs/ test if added) → all green.
5. Manually review the new subsection / Finding extension for clarity:
   does a fresh contributor reading just the doc know exactly what to do
   after editing a `.md.j2`? Specifically:
   - The exact regenerate command.
   - The expectation that they'll review (not rubber-stamp) the diff.
   - When goldens-and-template should land in the same commit.

## Notes

- This is purely a documentation task plus a one-time drift audit;
  effort is medium-to-low. The audit could surface real bugs in
  committed goldens — escalate to fix-up tasks if findings exceed
  3 files or cross multiple templates with unclear intent.
- Pattern is now established across 3 conversions (pick/explore/review).
  Document the rule before the next sibling conversion (t777_10 fold)
  picks up the same template-edit cycle.
