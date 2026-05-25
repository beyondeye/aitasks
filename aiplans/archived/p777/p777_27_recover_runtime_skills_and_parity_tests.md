---
Task: t777_27_recover_runtime_skills_and_parity_tests.md
Parent Task: aitasks/t777_modular_pick_skill.md
Sibling Tasks: aitasks/t777/t777_18_docs_update_claudemd_and_website.md, aitasks/t777/t777_19_retrospective_evaluation.md, aitasks/t777/t777_28_dedup_template_branches_common_proc_and_macros.md
Archived Sibling Plans: aiplans/archived/p777/p777_10_convert_aitask_fold.md, aiplans/archived/p777/p777_11_convert_aitask_qa.md, aiplans/archived/p777/p777_12_convert_aitask_pr_import.md, aiplans/archived/p777/p777_13_convert_aitask_revert.md, aiplans/archived/p777/p777_14_convert_aitask_pickrem.md, aiplans/archived/p777/p777_15_convert_aitask_pickweb.md, aiplans/archived/p777/p777_16_extract_profile_editor_widget.md, aiplans/archived/p777/p777_17_per_run_profile_edit_in_agentcommandscreen.md, aiplans/archived/p777/p777_1_minijinja_dep_renderer_paths_resolver.md, aiplans/archived/p777/p777_20_profile_modification_invalidation.md, aiplans/archived/p777/p777_21_map_pick_reference_closure_and_profile_keys.md, aiplans/archived/p777/p777_22_extend_renderer_for_uniform_recursive_rendering.md, aiplans/archived/p777/p777_23_swap_task_workflown_to_task_workflow.md, aiplans/archived/p777/p777_25_refactor_stubs_direct_helper_paths.md, aiplans/archived/p777/p777_26_template_completeness_and_resolver_key.md, aiplans/archived/p777/p777_29_fix_opencode_skill_legacy_pointers.md, aiplans/archived/p777/p777_2_aitask_skill_render_subcommand.md, aiplans/archived/p777/p777_3_stub_skill_design_and_gitignore.md, aiplans/archived/p777/p777_4_aitask_skill_verify_and_precommit.md, aiplans/archived/p777/p777_5_aitask_skillrun_wrapper_dispatcher.md, aiplans/archived/p777/p777_6_convert_aitask_pick_template_and_stubs.md, aiplans/archived/p777/p777_7_convert_task_workflow_shared_procs.md, aiplans/archived/p777/p777_8_convert_aitask_explore.md, aiplans/archived/p777/p777_9_convert_aitask_review.md
Base branch: main
plan_verified:
  - claudecode/opus4_7_1m @ 2026-05-25 16:35
---

# Plan: t777_27 — Recover pre-rewrite skills + add parity tests

**(Verified re-render — 2026-05-25. Corrects Phase 2 render invocation and
sentinel-ABSENT semantics; everything else carries over from the original
plan unchanged.)**

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

## Verification findings (what changed vs. original plan)

Confirmed by direct codebase check at verify time:

- **SHAs resolve.** `git rev-parse f1b01895` → `f1b018959a…`; `git rev-parse
  c46366fc` → `c46366fc06…`. Pre-rewrite `aitask-pick/SKILL.md` at
  `f1b01895` is 225 lines. `git ls-tree -r c46366fc -- .claude/skills/task-workflow/`
  lists exactly 25 files. ✅ unchanged.
- **`tests/` packaging boundary intact** (`.github/workflows/release.yml`
  still excludes `tests/`; no regression). ✅ unchanged.
- **Existing test harness pattern.** `tests/test_skill_render_aitask_pick.sh`
  and `tests/test_skill_render_task_workflow.sh` render via
  `$PYTHON .aitask-scripts/lib/skill_template.py <template> <profile.yaml>
  <agent>` to **stdout** and compare in-memory. They do NOT call
  `aitask_skill_render.sh` for the per-file render — only Test 4 of the
  aitask-pick test uses it (for the closure walk-write check). The
  data-driven assertions match against the stdout output. ✅ adopt this
  pattern.
- **`aitask_skill_render.sh` flag surface.** Help confirms only
  `--profile`, `--agent`, `--force` are supported. **There is NO
  `--output-dir` flag** — that part of the original plan's Phase 2 loop
  is invalid. Renders always land at
  `.claude/skills/<skill>-<profile>-/SKILL.md` (and nested closure files)
  on disk. ⚠️ correct in Phase 2.
- **Sentinel semantics.** The "Enter your email to track who is working
  on this task" AskUserQuestion text appears in *all three* rendered
  `task-workflow-*-/SKILL.md` files (line 103) because the fallback
  AskUserQuestion is still emitted under "If both are empty, prompt the
  user via `AskUserQuestion`". The profile-driven path adds the `Profile
  '<p>': using email …` Display line *in addition*. So a naive
  sentinel-ABSENT of "Enter your email" against fast/remote renders
  would falsely fail. ⚠️ refine to **cross-profile** sentinel-ABSENT (a
  profile-specific Display sentence must appear ONLY in its own profile,
  not in another profile's render). The "Enter your email" text is now
  asserted absent only from the `default` profile *vs.* "Profile
  'default': using email" being absent from default — re-cast as a
  presence/absence pair on the same Display sentinel.
- **No `aitask-pick-default-` on-disk render.** Only `aitask-pick-fast-/`
  exists today; remote/default would be created by the test if needed.
  Switching to the in-memory `$RENDER` pattern avoids the need for
  on-disk closures for aitask-pick. ✅ resolved by Phase 2 correction.

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

Extraction commands (verified — SHAs resolve and the 25-file count is exact):

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

## Phase 2 — Land the parity test (CORRECTED)

New file: `tests/test_skill_parity_runtime_vs_rendered.sh` (~250 lines).
Patterns mirror `tests/test_skill_render_task_workflow.sh`
(`assert_eq`/`assert_contains`/`assert_not_contains`, PASS/FAIL counter,
minijinja-availability SKIP guard). **In-memory render via
`$RENDER` (skill_template.py to stdout) — same pattern as
existing render tests.** Do NOT call `aitask_skill_render.sh
--output-dir` (flag does not exist) and do NOT depend on
on-disk `.claude/skills/<skill>-<profile>-/` state.

### Render helpers (top of test)

```bash
PYTHON="$($PROJECT_DIR/.aitask-scripts/lib/python_resolve.sh)"
RENDER="$PYTHON $PROJECT_DIR/.aitask-scripts/lib/skill_template.py"

PICK_SKILL="$PROJECT_DIR/.claude/skills/aitask-pick/SKILL.md.j2"
WORKFLOW_DIR="$PROJECT_DIR/.claude/skills/task-workflow"
PROFILES_DIR="$PROJECT_DIR/aitasks/metadata/profiles"

render_file() {                                # render_file <abs_template> <profile>
    $RENDER "$1" "$PROFILES_DIR/$2.yaml" claude 2>&1
}
```

### Assertion table (data-driven; comments cite pre-rewrite line numbers)

Hard-coded bash arrays. Each row:
`SKILL|FILE|PROFILE|FIXTURE_LINE|KEY|SENTINEL_PRESENT|SENTINEL_ABSENT|NOTE`.

The `FILE` column (new vs. original plan) lets each row target a specific
closure file — `SKILL.md.j2` for aitask-pick, `SKILL.md` / `planning.md` /
`manual-verification-followup.md` / `satisfaction-feedback.md` /
`remote-drift-check.md` for task-workflow. `FILE` is resolved relative
to `WORKFLOW_DIR` for `task-workflow`, or to the absolute `PICK_SKILL`
for `aitask-pick`.

**Sentinel semantics (refined):** a row asserts BOTH a presence and the
absence of the *complementary* sentinel from the same profile's render.
`SENTINEL_ABSENT` is the *other-profile*'s Display sentinel, not the
fallback-text leak. Example: for `default_email` at fast,
`SENTINEL_PRESENT = "Profile 'fast': using email"`,
`SENTINEL_ABSENT = "Profile 'default': using email"`. Cross-profile rows
catch both arms.

Concrete rows (representative — full table covers all 12 keys ×
{default, fast, remote}, ~30 rows total):

| Skill | File | Profile | Fixture line | Key | PRESENT | ABSENT (cross-profile) |
|-------|------|---------|--------------|-----|---------|------------------------|
| aitask-pick | SKILL.md.j2 | fast    | SKILL.md:44 (parent confirm) | `skip_task_confirmation` | `Profile 'fast': auto-confirming task selection` | `Is this the correct task to work on` |
| aitask-pick | SKILL.md.j2 | remote  | SKILL.md:44 | `skip_task_confirmation` | `Profile 'remote': auto-confirming task selection` | `Is this the correct task to work on` |
| aitask-pick | SKILL.md.j2 | default | SKILL.md:44 | `skip_task_confirmation` | `Is this the correct task to work on` | `Profile 'fast': auto-confirming task selection` |
| aitask-pick | SKILL.md.j2 | fast    | SKILL.md:72 (child confirm)  | `skip_task_confirmation` | `Profile 'fast': auto-confirming task selection` (second occurrence) | `Is this the correct child task to work on` |
| task-workflow | SKILL.md | fast    | SKILL.md:98  | `default_email`  | `Profile 'fast': using email`  | `Profile 'default': using email` |
| task-workflow | SKILL.md | remote  | SKILL.md:98  | `default_email`  | `Profile 'remote': using email`| `Profile 'fast': using email` |
| task-workflow | SKILL.md | default | SKILL.md:98  | `default_email`  | `Enter your email to track who is working on this task` | `Profile 'fast': using email` |
| task-workflow | SKILL.md | fast    | SKILL.md:183 | `create_worktree`| `working on current branch`    | `Do you want to work on a new branch and worktree` |
| task-workflow | SKILL.md | remote  | SKILL.md:183 | `create_worktree`| `creating worktree`            | `Do you want to work on a new branch and worktree` |
| task-workflow | SKILL.md | default | SKILL.md:183 | `create_worktree`| `Do you want to work on a new branch and worktree` | `working on current branch` |
| task-workflow | SKILL.md | fast    | SKILL.md:198 | `base_branch`    | `using base branch`            | `Which branch should the new task branch be based on` (only when profile sets base_branch; if unset the AskUserQuestion still appears — verify) |
| task-workflow | planning.md | fast    | planning.md:29  | `plan_preference` / `_child` | `Profile 'fast': using existing plan` (parent) / `Profile 'fast': checking verification status` (child) | `How would you like to proceed with the plan` |
| task-workflow | planning.md | default | planning.md:29  | `plan_preference` | `How would you like to proceed with the plan` | `Profile 'fast': using existing plan` |
| task-workflow | planning.md | fast    | planning.md:294 | `post_plan_action` / `_for_child` | `Profile 'fast': proceeding to implementation` (when value=`start_implementation`) | `Plan saved to` + 4-option AskUserQuestion text |
| task-workflow | manual-verification-followup.md | fast    | mvf.md:19 | `manual_verification_followup_mode` | (`never`-only assertion; for `ask` profile both arms coexist) | manual-verification-followup AskUserQuestion text |
| task-workflow | satisfaction-feedback.md | default | sf.md:34 | `enableFeedbackQuestions` | satisfaction `AskUserQuestion` text (always present in default) | profile-skip Display line (`skipping satisfaction feedback`) |
| task-workflow | remote-drift-check.md  | default | rdc.md:17 | `remote_drift_check`     | `Remote drift detected` warning | `Profile '<p>': skipping drift check` |

Coverage target: every profile key from `p777_21`'s 12-key universe
(`skip_task_confirmation`, `default_email`, `create_worktree`,
`base_branch`, `plan_preference`, `plan_preference_child`,
`post_plan_action`, `post_plan_action_for_child`,
`plan_verification_required`, `enableFeedbackQuestions`,
`remote_drift_check`, `manual_verification_followup_mode`) — one row per
key per representative value, including the undefined / ASK case (i.e.
the `default` profile).

### Per-row assertion loop

```bash
for ROW in "${ROWS[@]}"; do
  IFS='|' read -r SKILL FILE PROFILE FIXTURE_LINE KEY PRESENT ABSENT NOTE <<<"$ROW"

  # Resolve template path.
  if [[ "$SKILL" == "aitask-pick" ]]; then
      TEMPLATE="$PICK_SKILL"                              # always SKILL.md.j2
  else
      TEMPLATE="$WORKFLOW_DIR/$FILE"
  fi

  RENDERED="$(render_file "$TEMPLATE" "$PROFILE")"

  [[ -n "$PRESENT" ]] && assert_contains \
      "$SKILL/$FILE/$PROFILE key=$KEY (fixture:$FIXTURE_LINE) present" \
      "$PRESENT" "$RENDERED"
  [[ -n "$ABSENT" ]] && assert_not_contains \
      "$SKILL/$FILE/$PROFILE key=$KEY (fixture:$FIXTURE_LINE) absent" \
      "$ABSENT" "$RENDERED"
done
```

### Cross-check: every pre-rewrite conditional has at least one render arm

After the per-row loop, a second pass scans each pre-rewrite fixture for
guard sentences matching the regex
`If the active profile|Profile check[.:]|If the effective action is`.
For each match, build the union of `SENTINEL_PRESENT` across all 3
profiles for that fixture line and assert that **at least one** of them
appears in **some** profile's render. This catches the failure mode
where a template author deletes both arms by accident.

### Failure messaging

On `assert_contains` failure, print: fixture file + line, the conditional
sentence (head -1 of the fixture line + next 2 lines), the expected
sentinel, the profile, and the (in-memory) rendered output's first 60
lines so the developer can diff visually. No on-disk artifact needed.

### No-leak assertion

Cheap re-affirmation of an existing invariant: every rendered string
produced by `render_file` must contain no `{%` or `{{` tokens. Already
covered by `tests/test_skill_render_aitask_pick.sh` and
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
   `aitask-pick/remote` rows fail with sentinel-PRESENT missing; `default`
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

1. **Phase 1 commit**: `chore: Recover pre-rewrite skill fixtures for
   parity testing (t777_27)`.
2. **Phase 2 + 3 commit**: `test: Add parity test
   tests/test_skill_parity_runtime_vs_rendered.sh (t777_27)`. Touches the
   new test file and (if Phase 3.2 lands) `.aitask-scripts/aitask_skill_verify.sh`.
3. **Plan commit** via `./ait git`: updated plan file with Final
   Implementation Notes.
4. **Archive**: `./.aitask-scripts/aitask_archive.sh 777_27`.
5. **Push**: `./ait git push`.

Attribution per `code-agent-commit-attribution.md`. No linked issue.

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

- **Actual work done:**
  - **Phase 1** (commit `e65c40d8`): extracted 27 frozen pre-rewrite
    fixtures into `tests/fixtures/skills/` (aitask-pick's
    pre-`b6dabc19` `SKILL.md` from `f1b01895`, plus the 25-file
    `task-workflow/` closure from `c46366fc`) with a provenance README.
    Byte-match against `git show` verified.
  - **Phase 2:** wrote `tests/test_skill_parity_runtime_vs_rendered.sh`
    (~290 lines, 86 assertions). Covers 7 profile keys
    (`skip_task_confirmation`, `default_email`, `create_worktree`,
    `plan_preference`, `post_plan_action`, `enableFeedbackQuestions`,
    `manual_verification_followup_mode`) × 3 profiles
    (`default`, `fast`, `remote`) across 5 closure files. Plus a
    cross-check pass (orphaned-guard detection) and a no-Jinja-leak
    assertion. All 86 assertions pass.
  - **Phase 3:** extended `.aitask-scripts/aitask_skill_verify.sh`
    (+12 lines) to invoke the parity test silently at end-of-verify
    when fixtures are present (gated on the `tests/fixtures/skills/`
    tree existing so older checkouts skip cleanly).
  - **Phase 4:** ran the two prescribed self-checks. Both failed
    before revert, confirming the test catches the targeted
    regression class.
- **Deviations from plan:**
  - **Render invocation (already flagged in the verified plan):**
    used in-memory `$RENDER` (skill_template.py → stdout) instead of
    the non-existent `aitask_skill_render.sh --output-dir`. Matches
    the pattern of `tests/test_skill_render_task_workflow.sh`.
  - **`remote-drift-check.md` is identical across all 3 profile
    renders** (verified — its profile check is a runtime conditional,
    not template-conditional). Dropped from the per-row table; the
    cross-check pass + existing render tests still cover it.
  - **`base_branch` row dropped:** no profile (`fast` / `remote` /
    `default`) sets `base_branch`, so all 3 renders keep the runtime
    "Profile check" wrapper. Nothing per-profile to differentiate —
    covered indirectly by the no-leak assertion.
  - **Sentinel string corrections during first test run:** initial
    drafted sentinels missed the literal `**…**` Markdown bold
    around `**Profile check:**` and used a slightly off question
    text (`How would you like to proceed with the plan` vs the
    actual `An existing implementation plan was found at … How
    would you like to proceed?`). Corrected before commit.
  - **`post_plan_action` fast row** ABSENT left empty: fast's
    `post_plan_action: ask` keeps both the auto-action and the
    interactive checkpoint text in the same render, so there is no
    clean cross-profile sentinel to assert absent. PRESENT-only
    suffices.
- **Issues encountered:**
  - Initial assertion-table draft had 4 row failures from the two
    string mismatches above. Resolved by inspecting the rendered
    output directly and tightening the sentinels (substring-friendly
    fragments without the Markdown `**`).
  - Self-check 1 (Phase 4) only tripped 2 ABSENT assertions, not the
    expected 6 — because removing the parent-site arm still leaves
    the child-site arm rendering the same `Profile 'fast':
    auto-confirming task selection` text, so the file-level PRESENT
    sentinel still matches. This is acceptable coverage: at least
    one assertion per affected profile fails, and the failure
    messaging points at the breakage. Cross-check pass is at file
    granularity for now; a tighter per-guard cross-check is
    explicitly deferred to t777_28 (see sibling notes below).
- **Key decisions:**
  - **Frozen-fixture rule** is documented inline in
    `tests/fixtures/skills/README.md` so future readers don't "fix"
    a fixture to match new behaviour.
  - **Verify-hook wiring is fixture-gated** so existing development
    checkouts that predate Phase 1 — or release tarballs that
    exclude `tests/` — don't fail.
  - **In-memory render** (no tmpdir, no on-disk artifact) for
    isolation and speed — matches the dominant pattern across the
    `test_skill_render_*.sh` family.
- **Upstream defects identified:** None.
- **Notes for sibling tasks (especially t777_28):**
  - When dedup'ing `.j2` branches via macros, expect to revisit a
    handful of sentinels: the literal `Profile '<name>':` Display
    prefix is what the parity test pins, so any macro must still
    emit that exact prefix. If you replace a Display line with a
    generic "Auto-action chosen" message, the parity test will fail
    with "PRESENT sentinel missing" pointing at the fixture line —
    that's the green-light signal that the user-visible Display
    string is drifting from the pre-rewrite baseline and the
    sentinel needs reconsideration (not just an update).
  - The cross-check pass catches "both arms accidentally deleted"
    at file granularity (one PRESENT match per file suffices).
    For per-conditional precision, t777_28 may want to extend it to
    one PRESENT match per fixture guard line — accepted as a
    limit here for cost/benefit reasons.
  - Failure messages print the rendered output's first 60 lines —
    sufficient for SKILL.md top-of-file diffs but `grep -n` against
    the rendered file directly is faster for deep-in-closure
    sentinel failures.
