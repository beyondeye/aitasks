---
Task: t777_6_convert_aitask_pick_template_and_stubs.md
Parent Task: aitasks/t777_modular_pick_skill.md
Sibling Tasks: aitasks/t777/t777_*_*.md
Parent Plan: aiplans/p777_modular_pick_skill.md
Base branch: main
Plan revised: 2026-05-19 (verify-mode refresh; t777_24 gate PASSED; t777_25/26 conventions applied)
Depends: [t777_5, t777_21, t777_22, t777_7]
plan_verified:
  - claudecode/opus4_7 @ 2026-05-18 08:52
  - claudecode/opus4_7_1m @ 2026-05-19 11:36
---

# Plan: t777_6 — Convert `aitask-pick` (PILOT) across all 4 agents

## Context

Pilot conversion of `aitask-pick` from a static SKILL.md into a Jinja
`SKILL.md.j2` template + 4 per-agent stubs. Proves the cross-agent
template + stub-dispatch model end-to-end. Phase 1–4 landed 2026-05-18 as
the parallel-name `aitask-pickn` (per
`feedback_stage_under_parallel_name`). Phase 4b (manual verification gate
via sibling **t777_24**) **PASSED 2026-05-19** on all 7 checks.
**t777_25** (direct helper paths) and **t777_26** (template completeness
+ resolver-key alignment) shipped 2026-05-19 and already edited the
staged `aitask-pickn` artifacts. The pilot is now ready for **Phase 5
atomic rename** and **Phase 6 docs append**.

Phase 5 swaps the live `aitask-pick/*` artifacts for the staged
`aitask-pickn/*` artifacts in a single commit, then re-renders + re-tests
the new live name. Phase 6 documents pilot lessons in
`aidocs/stub-skill-pattern.md`.

After this task lands, **t777_23** (follow-up, already filed) renames the
referenced procedure tree `task-workflown/` → `task-workflow/` and
re-points the template's body references; that swap is out of scope here.

## Verified state (2026-05-19)

- **t777_24 gate**: `aitasks/archived/t777/t777_24_*.md` — Done
  2026-05-19 10:15. All 7 checklist items PASS (fast/parent,
  default/interactive, fast/child, remote dry-run, stub markers, claude
  rendered closure, original `/aitask-pick` regression).
- **Staged `aitask-pickn/*`**: all 5 source files present.
  - `.claude/skills/aitask-pickn/SKILL.md.j2` (207 lines, t777_26 applied:
    Step 0/0a deleted, profile baked in at render time)
  - `.claude/skills/aitask-pickn/SKILL.md` (Claude stub, ~906 bytes;
    direct-helper render call; resolver key = `pick`)
  - `.agents/skills/aitask-pickn/SKILL.md` (Codex stub, ~905 bytes)
  - `.gemini/commands/aitask-pickn.toml` (Gemini stub, ~957 bytes)
  - `.opencode/commands/aitask-pickn.md` (OpenCode stub, ~909 bytes)
- **Test script**: `tests/test_skill_render_aitask_pickn.sh` (198 lines,
  incl. t777_25/26 tightening — direct-helper-path assertion + short-key
  resolver assertion).
- **Goldens**: single dir `tests/golden/skills/aitask-pickn/`, 12 files
  named `SKILL-<profile>-<agent>.md`. **Plan correction:** the earlier
  draft assumed per-combo subdirs `aitask-pickn-<p>-<a>/`; reality is one
  flat dir. Phase 5 step 4 simplifies to a single `mv`.
- **Live `aitask-pick/*` to delete**: 4 files unchanged from pre-pilot
  (`.claude/skills/aitask-pick/SKILL.md` 225 lines, 3 agent stubs).
- **Extra `aitask-pickn` references** discovered (NOT in earlier plan;
  added to Phase 5 below):
  - `aidocs/stub-skill-pattern.md:50, :143` — paired `aitask-pick`/`aitask-pickn`
    mentions in t777_26's resolver-key prose. Drop the `/aitask-pickn`
    half post-rename.
  - `.aitask-scripts/aitask_skill_verify.sh:71` — `aitask-pick|aitask-pickn)`
    case alias resolving to `pick`. Drop the `|aitask-pickn` alias.

## Scope of the remaining work (3 phases)

### Phase 5 — Atomic rename `aitask-pickn` → `aitask-pick`

Single commit, executed in this exact order so no intermediate state
leaves a broken slash-command name on disk.

1. **Delete the 4 live `aitask-pick` artifacts** (the static stubs being
   replaced by the templated pipeline):
   - `.claude/skills/aitask-pick/SKILL.md`
   - `.agents/skills/aitask-pick/SKILL.md`
   - `.gemini/commands/aitask-pick.toml`
   - `.opencode/commands/aitask-pick.md`

2. **Move the 4 staged `aitask-pickn` stubs + template into the
   `aitask-pick` locations**:
   - `.claude/skills/aitask-pickn/SKILL.md.j2` → `.claude/skills/aitask-pick/SKILL.md.j2`
   - `.claude/skills/aitask-pickn/SKILL.md` → `.claude/skills/aitask-pick/SKILL.md`
   - `.agents/skills/aitask-pickn/SKILL.md` → `.agents/skills/aitask-pick/SKILL.md`
   - `.gemini/commands/aitask-pickn.toml` → `.gemini/commands/aitask-pick.toml`
   - `.opencode/commands/aitask-pickn.md` → `.opencode/commands/aitask-pick.md`

3. **String-replace `aitask-pickn` → `aitask-pick` inside every moved
   file** (use `sed_inplace` per project convention — never `sed -i`).
   This rewrites:
   - Frontmatter `name: aitask-pickn-{{ profile.name }}` →
     `name: aitask-pick-{{ profile.name }}` in `.j2`.
   - Stub `render` call args and stub `Read` target paths.
   - All internal references (resolver-key prose, comments).
   - Stays: every `task-workflown/` reference in the `.j2` body (t777_23
     reverts those separately).

4. **Move the goldens dir** (single `mv`, no per-combo loop needed):
   - `tests/golden/skills/aitask-pickn/` → `tests/golden/skills/aitask-pick/`
   - Inner files (`SKILL-<profile>-<agent>.md`) keep their names —
     `aitask-pickn` does not appear in filenames there.

5. **Rename and rewrite the test script**:
   - `mv tests/test_skill_render_aitask_pickn.sh
       tests/test_skill_render_aitask_pick.sh`
   - String-replace `aitask-pickn` → `aitask-pick` and `aitask_pickn` →
     `aitask_pick` inside the moved file. Verify `GOLDEN_DIR` line now
     reads `tests/golden/skills/aitask-pick`.

6. **Drop the `aitask-pickn` alias from the verify script**:
   - `.aitask-scripts/aitask_skill_verify.sh:71` — change
     `aitask-pick|aitask-pickn)` to `aitask-pick)`. The alias was only
     needed while both names co-existed during Phase 1–4b.

7. **Clean up the `aitask-pickn` mentions in
   `aidocs/stub-skill-pattern.md`** (lines 50 and 143):
   - Drop the `/aitask-pickn` half of the paired mention so docs reflect
     post-rename reality (e.g. `` `aitask-pick`/`aitask-pickn` `` →
     `` `aitask-pick` ``). Surrounding prose unchanged.

8. **Delete now-empty staged dirs** (only after every `mv` succeeded):
   - `rmdir .claude/skills/aitask-pickn`
   - `rmdir .agents/skills/aitask-pickn`
   - (No directories existed for `.gemini/commands/aitask-pickn.toml` or
     `.opencode/commands/aitask-pickn.md` — those are files, not dirs.)
   - Locally rendered trees `.claude/skills/aitask-pickn-*-/` etc. are
     gitignored; `rm -rf` them as housekeeping but do not stage anything.

9. **Re-render all 12 (profile × agent) combos under the new name** to
   produce the on-disk per-profile dirs the stubs target:
   ```bash
   for p in default fast remote; do
     for a in claude codex gemini opencode; do
       ./.aitask-scripts/aitask_skill_render.sh aitask-pick \
         --profile "$p" --agent "$a" --force
     done
   done
   ```
   These outputs (`<root>/skills/aitask-pick-<p>-/SKILL.md` plus closure)
   are gitignored — they are NOT staged. Their job is to make
   `./ait skill verify` green on this branch and to make a live
   `/aitask-pick` dispatch actually work post-merge.

10. **Run goldens + verify** — both must be green before committing:
    ```bash
    bash tests/test_skill_render_aitask_pick.sh
    ./.aitask-scripts/aitask_skill_verify.sh
    ```
    If either fails, do NOT commit — diagnose and fix (see "Failure
    modes" below) before re-running.

### Phase 6 — Append pilot findings to `aidocs/stub-skill-pattern.md`

Append a new top-level section `## Pilot findings (t777_6)` at the end
of the file (current end of file is §3j, "Template completeness",
lines 155–209 per t777_26's edit). Five bullets, ≤ 1 paragraph each:

1. **Uniform recursive rendering works.** `aitask_skill_render.sh`'s
   walk-write traversed the 22-file `task-workflown/` closure across 12
   (profile × agent) renders without manual intervention. Reference-rewrite
   regex (`FULL_PATH_REF_RE`) and BFS visited-set are the supported
   public interface — do not reinvent. See
   `feedback_golden_file_tests_for_template_engines` for the testing
   contract.

2. **Stage under `<skill>n` for in-use skills.** The live `aitask-pick`
   ran every step of this task's own workflow. Editing it in place
   would have wedged mid-pick. The parallel-name stage gives a full
   golden + manual-verification cycle before the atomic rename. This is
   the canonical procedure for future skill conversions
   (t777_8..15 should follow it). Canonical entry:
   `feedback_stage_under_parallel_name`.

3. **Golden-file tests are mandatory.** `./ait skill verify` and "renders
   without error" catch fewer regressions than committed goldens; the
   template engine can silently shift output (whitespace, comment
   placement, conditional bodies). 12 goldens caught the t777_26
   profile-resolution mismatch the moment it landed.

4. **Entry-point templates use `.md.j2`; referenced procedures keep
   `.md`.** The walk-write infrastructure assumes a single `.md.j2`
   per skill at the entry point. Referenced procedures (manual-verification.md,
   planning.md, etc.) MUST be plain `.md` files — even when they contain
   `{% if profile.… %}` wraps. The render closure handles both shapes;
   double-suffix `.md.j2` on a procedure file confuses the walker.

5. **Per-agent tool mapping lives in prereq files, never in template
   body.** Resist the temptation to add `{% if agent == "claude" %}
   AskUserQuestion … {% elif agent == "codex" %} request_user_input …
   {% endif %}` branches inside the template body. They balloon the
   template and obscure intent. Keep per-agent tool-name mapping in
   per-agent prereq files that the rendered body Reads-and-follows.

### Phase 7 — Step 9 (Post-Implementation)

Follow the standard `task-workflow/SKILL.md` Step 9 sequence — no
deviations:

- **Code commit** (regular `git`, code files only): single commit
  message `refactor: Convert aitask-pick to template + stubs (t777_6)`.
  Touches the 5 moved framework files, 1 renamed test file + its
  goldens dir mv, plus `.aitask-scripts/aitask_skill_verify.sh` and
  `aidocs/stub-skill-pattern.md`. Attribution per
  `code-agent-commit-attribution.md`.
- **Plan commit** (via `./ait git`): updated plan file with Final
  Implementation Notes.
- **Archive**: `./.aitask-scripts/aitask_archive.sh 777_6`.
- **Push**: `./ait git push`.

No linked issue.

## Failure modes (Phase 5 diagnosis cookbook)

If `tests/test_skill_render_aitask_pick.sh` fails after Phase 5:
- **Diff shows leftover `aitask-pickn` token** in a rendered output →
  string-replace in step 3 missed a site. Re-run with `grep -rn aitask-pickn
  .claude/ .agents/ .gemini/ .opencode/ tests/` to find it.
- **`GOLDEN_DIR` mismatch** in the test script → step 5 string-replace
  missed the path constant. Re-check `tests/test_skill_render_aitask_pick.sh:73`.
- **Render exit non-zero** with `template not found` → step 9 ran before
  step 2 (template `mv`) landed. Re-order; never commit partial state.

If `./.aitask-scripts/aitask_skill_verify.sh` fails:
- **Slug `aitask-pickn` unknown** → step 6 alias drop happened, but a
  stub or template still references `aitask-pickn`. `grep -rn
  aitask-pickn .claude/ .agents/ .gemini/ .opencode/` will pinpoint it.

## Verification (end-to-end)

1. `bash tests/test_skill_render_aitask_pick.sh` — exits 0, every
   golden diff empty (12 combos × file-level diff).
2. `./.aitask-scripts/aitask_skill_verify.sh` — exits 0.
3. `grep -rn aitask-pickn -- . | grep -v '^./aitasks/' | grep -v
   '^./aiplans/' | grep -v '^./.claude/projects/'` returns empty (no
   stragglers outside task/plan/transcript bookkeeping).
4. `git status` — staged: the 9 moved files, the renamed test script,
   the moved goldens dir, the 2 edited helper/docs files. NOT staged:
   any rendered `<root>/skills/aitask-pick-<p>-/` trees (gitignored).
5. Post-merge live dispatch: a fresh `/aitask-pick 777_6` (or any other
   open task) in Claude Code renders + dispatches identically to the
   pre-Phase-5 behavior. (User-driven; not blocking — t777_24 already
   green-lit this.)

## Step 9 (Post-Implementation) reference

Per `task-workflow/SKILL.md` Step 9, see Phase 7 above.

## Partial Implementation Notes (Phase 1-4 landed 2026-05-18)

[Retained from prior plan — preserves the audit trail; do not delete.]

- **Actual work done:**
  - Phase 1: smoke-checked the t777_22 renderer by rendering
    `task-workflown/SKILL.md` against fast/claude. The
    `default_email: userconfig` branch fires inline — render
    infrastructure works.
  - Phase 2: authored `.claude/skills/aitask-pickn/SKILL.md.j2`
    (copied from live `aitask-pick/SKILL.md`). Three edits:
    frontmatter `name: aitask-pickn-{{ profile.name }}`, plus
    `{% if profile.skip_task_confirmation is defined and
    profile.skip_task_confirmation %}` wraps at lines 44 and 72.
    Cross-skill references rewritten from `task-workflow/` to
    `task-workflown/` per the user's hand-off-target decision.
  - Phase 3: wrote 4 per-agent stubs (claude/codex/gemini/opencode)
    using `aidocs/stub-skill-pattern.md` §3b/§3c/§3d.
  - Phase 4: rendered 12 (profile × agent) combos. Dep-walker
    produced full closures (entry-point + 22-file task-workflown
    closure under each agent root). 12 golden files under
    `tests/golden/skills/aitask-pickn/`.
    `tests/test_skill_render_aitask_pickn.sh` (64 assertions) PASS.
    `./ait skill verify` reports `OK`. Existing
    `tests/test_skill_render_task_workflown.sh` 50/50 PASS.

- **Deviations from plan:**
  - Phase 1 standalone smoke test via `./ait skill render
    task-workflown` failed: the renderer requires a `SKILL.md.j2`
    entry-point, and `task-workflown` is reached only via dep-walker
    from a calling template. Substituted by invoking
    `lib/skill_template.py` directly to render the procedure file
    standalone. Phase 4's walk-write covered the dep-walker
    end-to-end.
  - Test 4 (cross-agent reference rewrites) initially failed:
    single-file `render_skill` does not rewrite references —
    rewriting is a `walk-write` property. Adapted Test 4 to invoke
    `./ait skill render` and read the on-disk per-profile output.

- **Issues encountered:**
  - Default-profile render initially raised strict-undefined for
    `profile.skip_task_confirmation` (absent from `default.yaml`).
    Fixed by guarding with `is defined and` per the t777_7 wrap
    convention.

- **Phase 5 + 6 deferred.** Phase 4b (manual end-to-end verification
  gate) blocks Phase 5 (atomic rename). Manual-verification sibling
  task **t777_24** filed with the 7-item checklist. **t777_24
  completed 2026-05-19 with all 7 checks PASS — gate is now open.**

- **Upstream defects identified (Phase 1–4):**
  Two bugs surfaced from a live `/aitask-pickn 741` run shared by the
  user. Both filed as separate sibling tasks; **both landed 2026-05-19**:
  - `aidocs/stub-skill-pattern.md:36,70,103` — `./ait skill render ...`
    instead of `./.aitask-scripts/aitask_skill_render.sh ...`. Filed as
    **t777_25** (direct-helper-paths refactor). ✓ Archived.
  - `.claude/skills/aitask-pickn/SKILL.md.j2:8-24,191` — template
    re-resolves profile at runtime. Filed as **t777_26**
    (template-completeness + resolver-key alignment). ✓ Archived.

- **Notes for sibling tasks (per-skill conversions t777_8..15):**
  Three patterns established by this pilot, codified in t777_25/26's
  scope:
  1. Stubs call `./.aitask-scripts/aitask_skill_*.sh` directly — not
     via `./ait skill ...`.
  2. **Delete** Step 0 / Step 0a / Step 3b at template-author time so
     rendered body contains no runtime profile resolution. (Updated
     from the earlier "wrap with `{% if not profile %}`" guidance —
     dead-code deletion preferred.)
  3. Stub Step 1 resolver lookup uses the short name (`pick`), not
     the full slash command name (`aitask-pick`).

  All eight conversion tasks (`t777_8..15`) now depend on `t777_26` so
  they inherit the corrected pattern from the updated
  `aidocs/stub-skill-pattern.md`.

## Final Implementation Notes (Phase 5 + Phase 6 landed 2026-05-19)

- **Actual work done:**
  - Phase 5 atomic rename executed in a single working pass: deleted the
    4 live `aitask-pick` stubs, moved the 5 staged `aitask-pickn`
    artifacts (template + 4 stubs) into the `aitask-pick` locations,
    string-replaced `aitask-pickn`/`aitask_pickn` → `aitask-pick`/`aitask_pick`
    in every moved file, moved `tests/golden/skills/aitask-pickn/` →
    `tests/golden/skills/aitask-pick/` (and patched the 12 golden files
    in-place to clear the `aitask-pickn` tokens), renamed
    `tests/test_skill_render_aitask_pickn.sh` →
    `tests/test_skill_render_aitask_pick.sh`, dropped the
    `aitask-pick|aitask-pickn)` alias from
    `.aitask-scripts/aitask_skill_verify.sh:71`, and cleaned up the two
    paired `aitask-pick`/`aitask-pickn` mentions in
    `aidocs/stub-skill-pattern.md:50,143` plus the stale test-script
    reference at the bottom of that file. Deleted now-empty staged dirs
    (`.claude/skills/aitask-pickn/`, `.agents/skills/aitask-pickn/`).
    Re-rendered all 12 (profile × agent) combos under the new name.
  - Phase 6 documentation: appended a new `## Pilot findings (t777_6)`
    section to `aidocs/stub-skill-pattern.md` with five lessons —
    uniform recursive rendering works, stage-under-`<skill>n` is
    canonical for in-use skills, golden-file tests are mandatory,
    entry-point `.md.j2` vs procedure `.md` convention, per-agent tool
    mapping stays in prereq files (never in template body).
  - Re-ran `bash tests/test_skill_render_aitask_pick.sh` (116/116 PASS)
    and `./.aitask-scripts/aitask_skill_verify.sh` (OK). Confirmed only
    remaining `aitask-pickn` reference outside task/plan/transcript
    bookkeeping is the intentional historical mention in the new pilot
    findings section (describing the staging pattern itself).

- **Deviations from plan:**
  - Plan's Phase 5 step 4 said "single `mv`" for the goldens dir, but
    the 12 golden files themselves still contained `aitask-pickn`
    tokens — caught immediately by the first test run (12 failures).
    Fixed with an in-place `sed` pass on every file in
    `tests/golden/skills/aitask-pick/*.md`. Plan now reflects this two-step.
  - Verify script alias drop landed cleanly with one `sed` edit (no
    edge cases — single occurrence).

- **Issues encountered:**
  - Initial test run after Phase 5 step 9 (re-render) produced 12 golden
    diffs because the `mv tests/golden/skills/aitask-pickn → aitask-pick`
    preserved file *names* but the *content* still had the old token.
    The plan's diagnosis cookbook ("Diff shows leftover `aitask-pickn`
    token in a rendered output") covered this exact failure mode, and
    the fix was the documented `grep -rn aitask-pickn …` + sed pass.

- **Key decisions:**
  - Kept `task-workflown` references intact in the rendered closure.
    The `.j2` template body still points at `.claude/skills/task-workflown/`
    procedures; t777_23 reverts this when it renames `task-workflown` →
    `task-workflow`. This means the goldens currently reference
    `task-workflown-<profile>-/SKILL.md` rendered closures — which is
    correct for the current intermediate state.
  - The historical `aitask-pickn` mention retained in
    `aidocs/stub-skill-pattern.md`'s new pilot-findings section is
    intentional — it documents what the staging-pattern memory
    (`feedback_stage_under_parallel_name`) actually looked like in
    practice. Removing it would make the lesson unreadable.

- **Upstream defects identified:** None.

- **Notes for sibling tasks (per-skill conversions t777_8..15):**
  Phase 5's golden-file content patch (step beyond the `mv`) is now part
  of the conversion playbook. When `<skill>n` → `<skill>` atomic rename
  fires, do BOTH:
  1. `mv tests/golden/skills/<skill>n → tests/golden/skills/<skill>`
  2. `sed -i 's/<skill>n/<skill>/g; s/<skill_under>n/<skill_under>/g'
     tests/golden/skills/<skill>/*.md`

  Otherwise the first post-rename test run produces N×M golden-diff
  failures (where N = profiles, M = agents). Already captured in the
  refreshed pilot-findings section as part of the golden-file lesson.

  All five lessons in §"Pilot findings (t777_6)" of
  `aidocs/stub-skill-pattern.md` are required reading before starting
  any of t777_8..15.

## Follow-up: t777_23 (already filed, depends on this task)

After t777_6 lands and manual verification passes, t777_23:
1. Renames `.claude/skills/task-workflown/` → `.claude/skills/task-workflow/`
   (overwriting the live, untouched copy).
2. Updates `aitask-pick/SKILL.md.j2`'s body references from
   `.claude/skills/task-workflown/...` back to
   `.claude/skills/task-workflow/...`.
3. Re-renders all 12 combos, re-runs goldens (which now reference
   `task-workflow-<p>-` paths), commits.

This 2-step landing is the cost of the user's "Reference `task-workflown/`
(staged)" decision, in exchange for full Jinja-branch exercise in the
pilot.
