---
Task: t777_9_convert_aitask_review.md
Parent Task: aitasks/t777_modular_pick_skill.md
Sibling Tasks: aitasks/t777/t777_10_convert_aitask_fold.md, aitasks/t777/t777_11_convert_aitask_qa.md, aitasks/t777/t777_12_convert_aitask_pr_import.md, aitasks/t777/t777_13_convert_aitask_revert.md, aitasks/t777/t777_14_convert_aitask_pickrem.md, aitasks/t777/t777_15_convert_aitask_pickweb.md, aitasks/t777/t777_16_extract_profile_editor_widget.md, aitasks/t777/t777_17_per_run_profile_edit_in_agentcommandscreen.md, aitasks/t777/t777_18_docs_update_claudemd_and_website.md, aitasks/t777/t777_19_retrospective_evaluation.md, aitasks/t777/t777_20_profile_modification_invalidation.md
Archived Sibling Plans: aiplans/archived/p777/p777_1_minijinja_dep_renderer_paths_resolver.md, aiplans/archived/p777/p777_21_map_pick_reference_closure_and_profile_keys.md, aiplans/archived/p777/p777_22_extend_renderer_for_uniform_recursive_rendering.md, aiplans/archived/p777/p777_23_swap_task_workflown_to_task_workflow.md, aiplans/archived/p777/p777_25_refactor_stubs_direct_helper_paths.md, aiplans/archived/p777/p777_26_template_completeness_and_resolver_key.md, aiplans/archived/p777/p777_2_aitask_skill_render_subcommand.md, aiplans/archived/p777/p777_3_stub_skill_design_and_gitignore.md, aiplans/archived/p777/p777_4_aitask_skill_verify_and_precommit.md, aiplans/archived/p777/p777_5_aitask_skillrun_wrapper_dispatcher.md, aiplans/archived/p777/p777_6_convert_aitask_pick_template_and_stubs.md, aiplans/archived/p777/p777_7_convert_task_workflow_shared_procs.md, aiplans/archived/p777/p777_8_convert_aitask_explore.md
Base branch: main
plan_verified:
  - claudecode/opus4_7_1m @ 2026-05-19 16:45
---

# Plan: t777_9 — Convert `aitask-review` to template + stubs (4 agents)

## Context

`aitask-review` is the next per-skill conversion in the t777 templated-dispatch
refactor (siblings t777_8..t777_15). The pilot (t777_6, `aitask-pick`)
established the full pattern; t777_8 (`aitask-explore`, just completed)
re-validated it. The shared procedure closure was templated in t777_7.

The conversion lets `aitask-review` use baked-in profile values for its two
profile keys (`review_default_modes`, `review_auto_continue`) instead of
re-reading the profile YAML at runtime — eliminating the Step 0a "Select
Execution Profile" round-trip.

**Verification findings (vs. original high-level plan):**
- `.claude/skills/aitask-review/SKILL.md` is still the fat (non-template)
  original (293 lines, two `**Profile check:**` blocks at lines 113 & 237).
- `.agents/skills/aitask-review/SKILL.md`, `.gemini/commands/aitask-review.toml`,
  `.opencode/commands/aitask-review.md` exist as pre-templating wrappers and
  will be overwritten with canonical stubs.
- Resolver-key mapping already wired:
  `.aitask-scripts/aitask_skill_verify.sh:75` maps `aitask-review → review`.
- Test/golden infra precedent: t777_8 produced
  `tests/test_skill_render_aitask_explore.sh` + 12 goldens at
  `tests/golden/skills/aitask-explore/`. Mirror exactly for review (golden
  files are mandatory per `feedback_golden_file_tests_for_template_engines`).
- `review_action` exists in `aitasks/metadata/profiles/remote.yaml` but is
  NOT referenced in `.claude/skills/aitask-review/SKILL.md` — pickrem-only
  today. **Out of scope** for this task (templating, not new behavior).

## Decision: direct conversion, not staged

Per pilot lesson #2 (`feedback_stage_under_parallel_name`), parallel-name
staging applies when the conversion is driven by the skill being converted.
**`aitask-review` is NOT driving this conversion** (`aitask-pick` is). Editing
in place is safe; no `aitask-reviewn` stage.

## Critical Files

**Created / replaced (5 framework files):**
- `.claude/skills/aitask-review/SKILL.md.j2` *(new)* — entry-point template
- `.claude/skills/aitask-review/SKILL.md` *(replace with canonical stub per
  `aidocs/stub-skill-pattern.md` §3b, `<agent_literal>=claude`)*
- `.agents/skills/aitask-review/SKILL.md` *(replace with canonical stub per
  §3b, `<agent_literal>=codex`)*
- `.gemini/commands/aitask-review.toml` *(replace with canonical stub per §3c)*
- `.opencode/commands/aitask-review.md` *(replace with canonical stub per §3d)*

**Test infrastructure (created):**
- `tests/test_skill_render_aitask_review.sh` *(new)* — adapted from
  `tests/test_skill_render_aitask_explore.sh`
- `tests/golden/skills/aitask-review/SKILL-<profile>-<agent>.md` — 12 golden
  files (3 profiles × 4 agents), flat directory layout

**Read-only references:**
- `.claude/skills/aitask-review/SKILL.md` *(existing — source for template)*
- `.claude/skills/aitask-explore/SKILL.md.j2` *(reference for Jinja conventions)*
- `.claude/skills/aitask-explore/SKILL.md` *(reference for canonical Claude stub)*
- `.agents/skills/aitask-explore/SKILL.md` *(reference for Codex stub)*
- `.gemini/commands/aitask-explore.toml` *(reference for Gemini stub)*
- `.opencode/commands/aitask-explore.md` *(reference for OpenCode stub)*
- `aidocs/stub-skill-pattern.md` *(canonical bodies §3b-§3d, conventions §3f,
  template completeness §3j)*
- `aidocs/skill_authoring_conventions.md` *(Jinja inline-comment convention)*
- `tests/test_skill_render_aitask_explore.sh` *(model for the new test script)*

## Template authoring (`.claude/skills/aitask-review/SKILL.md.j2`)

Source: copy current `.claude/skills/aitask-review/SKILL.md`, then apply
these seven edits:

1. **Frontmatter** — `name: aitask-review-{{ profile.name }}`.

2. **Delete "## Arguments (Optional)" section** (current lines 6–12). The
   `--profile <name>` parsing is handled by the stub Step 1; the rendered
   body never re-resolves the profile (§3j).

3. **Delete Step 0a "Select Execution Profile"** (current lines 16–21).
   Profile is baked in at render time. Forbidden tokens per §3j MUST NOT
   appear after this deletion: `aitask_scan_profiles.sh`,
   `Execute the Execution Profile Selection Procedure`,
   `Select Execution Profile`, `refresh execution profile`.

4. **Wrap Step 1b profile check on `review_default_modes`** (current lines
   113–122) in Jinja conditionals:
   ```jinja
   {# ---------- review_default_modes ---------- #}{% if profile.review_default_modes is defined and profile.review_default_modes %}
   - Auto-select these modes: `{{ profile.review_default_modes }}`. Display: "Profile '{{ profile.name }}': using review guides: {{ profile.review_default_modes }}"
   - Skip the AskUserQuestion below
   {% else %}{# review_default_modes: when unset / empty #}
   Present the modes in the script's pre-sorted order via `AskUserQuestion` multiSelect: "Select review guides to apply:"
   - Each option: label = `name` field from script output, description = `description` field from script output
   - Since `AskUserQuestion` supports max 4 options, implement pagination:
     - Show up to 3 modes per page + "Show more modes" if additional modes exist
     - On the last page, show up to 4 modes
     - Accumulate selections across pages before proceeding
   {% endif %}{# ---------- end review_default_modes ---------- #}
   ```
   Note: the existing **Profile check:** narrative wrapper around the block
   is removed (replaced by the Jinja conditional).

5. **Wrap Step 5 profile check on `review_auto_continue`** (current lines
   235–253) in Jinja conditionals. The current block has the profile check
   inside Step 5 *before* the "If single task" / "If multiple tasks"
   sub-branches; wrap so the `{% if %}` arm covers the auto-continue
   message + handoff, and the `{% else %}` arm covers the AskUserQuestion
   sub-branches:
   ```jinja
   {# ---------- review_auto_continue ---------- #}{% if profile.review_auto_continue is defined and profile.review_auto_continue %}
   Display: "Profile '{{ profile.name }}': continuing to implementation".
   Skip the AskUserQuestion below and proceed directly to the handoff
   (Step 6). For single-task review, the created task is the handoff target;
   for parent+children review, hand off the first child task automatically.
   {% else %}{# review_auto_continue: when false / undefined #}
   **If single task was created:**

   Use `AskUserQuestion`: "Task created successfully. How would you like to proceed?"
   - "Continue to implementation" (description: "Start implementing the fixes now via the standard workflow")
   - "Save for later" (description: "Task saved — pick it up later with /aitask-pick <N>")

   **If multiple tasks (parent + children) were created:**

   Use `AskUserQuestion`: "Tasks created. How would you like to proceed?"
   - "Pick one to start" (description: "Select a child task to implement now")
   - "Save all for later" (description: "Tasks saved — pick them up later with /aitask-pick <parent_N>")

   **If "Pick one to start":** Use `AskUserQuestion` to let the user select which child task, then hand off that child.

   **If "Save for later" / "Save all for later":**
   - Inform user: "Tasks saved. Run `/aitask-pick <N>` when you want to implement."
   - End the workflow.
   {% endif %}{# ---------- end review_auto_continue ---------- #}
   ```
   Follow the inline-comment convention from
   `aidocs/skill_authoring_conventions.md`: separator-on-same-line as
   `{% if %}`, inline labels on `{% else %}` / `{% endif %}`, render-neutral.

6. **Bake in profile values at Step 6 handoff** (current lines 261–276):
   - `active_profile`: `{ name: {{ profile.name }} }` (replace the
     "execution profile loaded in Step 0a (or null if no profile)" prose).
   - `active_profile_filename`: `{{ profile.name }}.yaml` (replace the
     scanner-output prose).
   - Drop the parenthetical "(or null if no profile)" — profile is mandatory.
   - The handoff path stays `.claude/skills/task-workflow/SKILL.md` — the
     dep-walker rewrites it per-agent at render time (§3i).

7. **Scan body for stray `{{` / `{%`** outside Jinja directives. Wrap any
   hits in `{% raw %}…{% endraw %}`. Pre-conversion check:
   `grep -nE '\{\{|\{%' .claude/skills/aitask-review/SKILL.md`.

## Stubs (4 files, byte-for-byte canonical from §3b-§3d)

Each stub uses `aitask-review` for `<skill_short_name>` and `review` for
`<resolver_key>`. Per-agent `<agent_literal>`:
`claude`/`codex`/`gemini`/`opencode`. Copy from the explore stubs and
substitute the slug + resolver key:

- `.claude/skills/aitask-review/SKILL.md` ← copy from
  `.claude/skills/aitask-explore/SKILL.md`, replace
  `aitask-explore`→`aitask-review` and ` explore`→` review` (the resolver-key
  invocations), and update the `description:` frontmatter to
  "Review code using configurable review guides, then create tasks from findings."
- `.agents/skills/aitask-review/SKILL.md` ← copy from
  `.agents/skills/aitask-explore/SKILL.md`, same substitutions + description.
- `.gemini/commands/aitask-review.toml` ← copy from
  `.gemini/commands/aitask-explore.toml`, same substitutions + description.
- `.opencode/commands/aitask-review.md` ← copy from
  `.opencode/commands/aitask-explore.md`, same substitutions + description.

## Test script (`tests/test_skill_render_aitask_review.sh`)

Adapt `tests/test_skill_render_aitask_explore.sh` line-for-line:

- `TEMPLATE=".claude/skills/aitask-review/SKILL.md.j2"`
- `GOLDEN_DIR="tests/golden/skills/aitask-review"`
- Test 2 (profile-conditional sanity): the live profiles
  (`default`/`fast`/`remote`) have neither `review_default_modes` nor
  `review_auto_continue` set, so all three render the `{% else %}` arms.
  Assertions:
  - Each profile renders: "Select review guides to apply:" (else arm of
    review_default_modes) and "Task created successfully. How would you
    like to proceed?" (else arm of review_auto_continue).
  - None of the live profile renders contain `': continuing to implementation`
    (apostrophe-colon prefix — same Notes-section caveat learned in t777_8).
  - None contain `: using review guides:` (the profile auto-select banner).
  - The `{% if %}` arms are exercised structurally by `./ait skill verify`
    (which renders without error against every profile).
- Test 4 (cross-agent ref rewrites): assert
  `task-workflow-<profile>-/SKILL.md` is reachable under each of the 4
  agent roots from the rendered entry-point — identical structure to the
  explore test, substitute `aitask-review`.
- Test 5 (stub markers): each of the 4 stubs contains
  `aitask_skill_resolve_profile.sh review`,
  `aitask_skill_render.sh aitask-review`,
  the canonical Read-and-follow marker, and the correct `--agent` literal
  + per-agent rendered-variant path.

## Goldens (12 files, flat dir)

Generate via:
```bash
for p in default fast remote; do
  for a in claude codex gemini opencode; do
    "$PYTHON" .aitask-scripts/lib/skill_template.py \
      .claude/skills/aitask-review/SKILL.md.j2 \
      aitasks/metadata/profiles/${p}.yaml ${a} \
      > tests/golden/skills/aitask-review/SKILL-${p}-${a}.md
  done
done
```
(Reuse the `$PYTHON` resolution from the explore test — the file
`.aitask-scripts/lib/python_resolve.sh` provides it.) All 12 are committed.

## Implementation Steps (in execution order)

1. **Author template** — copy `.claude/skills/aitask-review/SKILL.md` →
   `SKILL.md.j2`, apply the 7 edits above. Verify with one manual render:
   ```bash
   $PYTHON .aitask-scripts/lib/skill_template.py \
     .claude/skills/aitask-review/SKILL.md.j2 \
     aitasks/metadata/profiles/fast.yaml claude | head -40
   ```
2. **Write 4 stubs** by copying from explore equivalents (mapping above).
3. **Overwrite the old per-agent surfaces** (all 4 files already exist):
   - `.claude/skills/aitask-review/SKILL.md`
   - `.agents/skills/aitask-review/SKILL.md`
   - `.gemini/commands/aitask-review.toml`
   - `.opencode/commands/aitask-review.md`
4. **Generate goldens** — `mkdir -p tests/golden/skills/aitask-review`; run
   the 3×4 render loop to produce all 12 files.
5. **Render the full closure** for each agent so live dispatch works:
   ```bash
   for a in claude codex gemini opencode; do
     ./.aitask-scripts/aitask_skill_render.sh aitask-review \
       --profile fast --agent "$a" --force
   done
   ```
   (Also render `default` and `remote` so all three are on disk.)
6. **Write the test script** by copying from
   `tests/test_skill_render_aitask_explore.sh` and substituting paths.
7. **Run tests**:
   ```bash
   bash tests/test_skill_render_aitask_review.sh
   ./.aitask-scripts/aitask_skill_verify.sh
   ```
   Both MUST be green before committing.
8. **Grep for stragglers**:
   ```bash
   grep -rn 'aitask-review' .claude/skills/aitask-review/ \
     .agents/skills/aitask-review/ \
     .gemini/commands/aitask-review.toml \
     .opencode/commands/aitask-review.md \
     tests/test_skill_render_aitask_review.sh
   ```
   Confirm only intended occurrences.

## Verification (end-to-end)

1. `bash tests/test_skill_render_aitask_review.sh` — exits 0, all 12 golden
   diffs empty, profile-branch and stub-marker assertions pass.
2. `./.aitask-scripts/aitask_skill_verify.sh` — exits 0 (renders all 4
   agents for all 3 profiles, validates stub format, asserts 3 templates
   total — pick + explore + review).
3. **Forbidden-token scan** on every rendered golden:
   ```bash
   for f in tests/golden/skills/aitask-review/*.md; do
     for tok in 'aitask_scan_profiles.sh' \
                'Execute the Execution Profile Selection Procedure' \
                'Select Execution Profile' 'refresh execution profile'; do
       grep -F "$tok" "$f" && echo "FORBIDDEN: $tok in $f" && exit 1
     done
   done
   ```
4. **Stub-dispatch dry-run** (manual, post-merge): invoking `/aitask-review`
   in Claude Code reads the stub, renders the appropriate profile variant,
   dispatches via Read-and-follow. The test script's Test 4 already exercises
   the render+rewrite layer on disk.

## Step 9 (Post-Implementation)

Per `task-workflow/SKILL.md` Step 9. Code commit message:
`refactor: Convert aitask-review to template + stubs (t777_9)`. Plan commit
via `./ait git`. Archive with `./.aitask-scripts/aitask_archive.sh 777_9`.
Push with `./ait git push`. No linked issue.

## Notes for sibling tasks (t777_10..t777_15)

This conversion follows the same pattern as t777_8 (aitask-explore). The
only review-specific wrinkle is that two profile keys must be wrapped
instead of one, both with the same `is defined and <key>` guard pattern.
Future skill conversions with N profile keys can apply the same Jinja
wrap N times.

## Out of scope (deferred)

- `review_action` (in `remote.yaml`, not currently consumed by
  `aitask-review/SKILL.md`) — pickrem-only today. Integrating
  `review_action` into aitask-review would add new behavior, not just
  template existing behavior. Defer to a follow-up task if/when needed.

## Final Implementation Notes

- **Actual work done:** Authored `.claude/skills/aitask-review/SKILL.md.j2`
  from the existing `aitask-review/SKILL.md` (deleted "## Arguments
  (Optional)" section and Step 0a "Select Execution Profile"; wrapped Step
  1b's `review_default_modes` check and Step 5's `review_auto_continue`
  check in `{% if profile.<key> is defined and profile.<key> %}…{% else
  %}…{% endif %}` following the inline-comment placement convention; baked
  profile values into Step 6 handoff as `{ name: {{ profile.name }} }` /
  `{{ profile.name }}.yaml`). Replaced all 4 per-agent surfaces with
  canonical stubs from `aidocs/stub-skill-pattern.md` §3b-§3d, resolver
  key `review`. Generated 12 goldens at
  `tests/golden/skills/aitask-review/`. Authored
  `tests/test_skill_render_aitask_review.sh` (124 assertions across 5
  test groups) adapted from the explore equivalent — count is higher than
  explore's 118 because Test 2 adds extra assertions for the second
  profile key (`review_default_modes` else-arm fires, if-arm does not).
- **Deviations from plan:** None substantive. The apostrophe-colon
  forbidden-substring discipline (`': continuing to implementation`)
  carried over from t777_8 — no false-positive on Notes-section prose.
- **Issues encountered:** None.
- **Key decisions:**
  - Direct conversion (not staged under `aitask-reviewn`): per pilot
    lesson, parallel-name staging applies when the converted skill is
    driving its own conversion. `aitask-pick` drives here; review is
    dormant, so in-place edits are safe.
  - Tests assert the `{% else %}` arms for both profile keys across all
    three live profiles (none set either key); the `{% if %}` arms are
    exercised structurally by `./ait skill verify`.
  - `review_action` (pickrem-only profile key) deferred — not currently
    referenced in aitask-review/SKILL.md; templating-only conversion does
    not introduce new behavior.
- **Upstream defects identified:** None.
- **Notes for sibling tasks:** Pattern is now stable across three
  conversions (pick / explore / review). N-key surfaces wrap each key in
  its own Jinja block with the same `is defined and <key>` guard.
  Future siblings (fold/qa/pr-import/revert/pickrem/pickweb) can copy
  this plan verbatim, substituting slug, resolver key, and the specific
  profile keys.

## Verification Results (2026-05-19)

- `bash tests/test_skill_render_aitask_review.sh` → **124/124 PASS**.
- `./.aitask-scripts/aitask_skill_verify.sh` → **OK** (3 templates × 4
  agents — aitask-pick + aitask-explore + aitask-review).
- Forbidden-token scan on all 12 goldens → clean (no
  `aitask_scan_profiles.sh`, `Execute the Execution Profile Selection
  Procedure`, `Select Execution Profile`, or `refresh execution profile`).
