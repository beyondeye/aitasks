---
Task: t777_8_convert_aitask_explore.md
Parent Task: aitasks/t777_modular_pick_skill.md
Sibling Tasks: aitasks/t777/t777_10_convert_aitask_fold.md, aitasks/t777/t777_11_convert_aitask_qa.md, aitasks/t777/t777_12_convert_aitask_pr_import.md, aitasks/t777/t777_13_convert_aitask_revert.md, aitasks/t777/t777_14_convert_aitask_pickrem.md, aitasks/t777/t777_15_convert_aitask_pickweb.md, aitasks/t777/t777_16_extract_profile_editor_widget.md, aitasks/t777/t777_17_per_run_profile_edit_in_agentcommandscreen.md, aitasks/t777/t777_18_docs_update_claudemd_and_website.md, aitasks/t777/t777_19_retrospective_evaluation.md, aitasks/t777/t777_20_profile_modification_invalidation.md, aitasks/t777/t777_9_convert_aitask_review.md
Archived Sibling Plans: aiplans/archived/p777/p777_1_minijinja_dep_renderer_paths_resolver.md, aiplans/archived/p777/p777_21_map_pick_reference_closure_and_profile_keys.md, aiplans/archived/p777/p777_22_extend_renderer_for_uniform_recursive_rendering.md, aiplans/archived/p777/p777_23_swap_task_workflown_to_task_workflow.md, aiplans/archived/p777/p777_25_refactor_stubs_direct_helper_paths.md, aiplans/archived/p777/p777_26_template_completeness_and_resolver_key.md, aiplans/archived/p777/p777_2_aitask_skill_render_subcommand.md, aiplans/archived/p777/p777_3_stub_skill_design_and_gitignore.md, aiplans/archived/p777/p777_4_aitask_skill_verify_and_precommit.md, aiplans/archived/p777/p777_5_aitask_skillrun_wrapper_dispatcher.md, aiplans/archived/p777/p777_6_convert_aitask_pick_template_and_stubs.md, aiplans/archived/p777/p777_7_convert_task_workflow_shared_procs.md
Base branch: main
plan_verified:
  - claudecode/opus4_7_1m @ 2026-05-19 13:30
---

# Plan: t777_8 — Convert `aitask-explore` to template + stubs (4 agents)

## Context

`aitask-explore` is the next per-skill conversion in the t777 templated-dispatch
refactor (siblings t777_8..t777_15). The pilot (t777_6, `aitask-pick`)
established the full pattern and t777_25/t777_26 hardened it: stubs call the
direct helper scripts (not `./ait skill ...`), templates must NOT re-resolve
profile at runtime, and stub resolver-key uses the short name (`explore`, not
`aitask-explore`). The shared procedure closure was templated in t777_7.

The conversion lets `aitask-explore` use baked-in profile values for its sole
profile key (`explore_auto_continue`) instead of re-reading the profile YAML at
runtime — eliminating the Step 3b "Select Execution Profile" round-trip.

## Decision: direct conversion, not staged

Pilot lesson #2 (`feedback_stage_under_parallel_name`) staged `aitask-pickn`
because the pilot's own workflow ran on `aitask-pick`. **`aitask-explore` is
NOT driving this conversion** (`aitask-pick` is). Editing in place is safe;
no parallel `aitask-exploren` stage is needed. A user running `/aitask-explore`
in a second session during the brief window between commit and re-render is the
only failure mode — accepted as negligible.

## Critical Files

**Created / replaced (5 framework files):**
- `.claude/skills/aitask-explore/SKILL.md.j2` *(new)* — entry-point template
- `.claude/skills/aitask-explore/SKILL.md` *(replace with canonical stub per
  §3b, `<agent_literal>=claude`)*
- `.agents/skills/aitask-explore/SKILL.md` *(replace with canonical stub per
  §3b, `<agent_literal>=codex`)*
- `.gemini/commands/aitask-explore.toml` *(replace with canonical stub per §3c)*
- `.opencode/commands/aitask-explore.md` *(replace with canonical stub per §3d)*

**Test infrastructure (created):**
- `tests/test_skill_render_aitask_explore.sh` *(new)* — adapted from
  `tests/test_skill_render_aitask_pick.sh` (same 5-test structure)
- `tests/golden/skills/aitask-explore/SKILL-<profile>-<agent>.md` — 12 golden
  files (3 profiles × 4 agents), flat directory layout (per t777_6 pilot)

**Read-only references:**
- `.claude/skills/aitask-explore/SKILL.md` *(existing — source for the template)*
- `.claude/skills/aitask-pick/SKILL.md.j2` *(reference for Jinja conventions)*
- `aidocs/stub-skill-pattern.md` *(canonical stub bodies §3b-§3d, conventions
  §3f, template completeness §3j, pilot findings)*
- `tests/test_skill_render_aitask_pick.sh` *(model for the new test script)*
- `.aitask-scripts/aitask_skill_verify.sh:72` *(already maps
  `aitask-explore → explore` — no edit needed)*

## Template authoring (`.claude/skills/aitask-explore/SKILL.md.j2`)

Source: copy current `.claude/skills/aitask-explore/SKILL.md`, then apply these
six edits:

1. **Frontmatter** — `name: aitask-explore-{{ profile.name }}`.

2. **Delete "## Arguments (Optional)" section** (current lines 6–13). The
   `--profile <name>` parsing is handled by the stub Step 1; the rendered body
   never re-resolves the profile (§3j).

3. **Delete Step 3b "Select Execution Profile"** (current lines 186–194).
   Profile is baked in at render time. Forbidden tokens per §3j MUST NOT
   appear after this deletion: `aitask_scan_profiles.sh`,
   `Execute the Execution Profile Selection Procedure`,
   `Select Execution Profile`, `refresh execution profile`.

4. **Wrap Step 4 profile check on `explore_auto_continue`** (current lines
   196–204) in Jinja conditionals. Use the same `is defined and` guard
   convention as the pick template:
   ```jinja
   {# ---------- explore_auto_continue ---------- #}{% if profile.explore_auto_continue is defined and profile.explore_auto_continue %}
   - Display: "Profile '{{ profile.name }}': continuing to implementation"
   - Skip the AskUserQuestion below and proceed directly to the handoff
   {% else %}{# explore_auto_continue: when false / undefined #}
   - Use `AskUserQuestion`:
     - Question: "Task created successfully. How would you like to proceed?"
     - Header: "Proceed"
     - Options:
       - "Continue to implementation" (description: "Start implementing the task now via the standard workflow")
       - "Save for later" (description: "Task saved — pick it up later with /aitask-pick <N>")
   {% endif %}{# ---------- end explore_auto_continue ---------- #}
   ```
   Follow the inline-comment placement rule from
   `feedback_authoring_docs_in_aidocs` / `aidocs/skill_authoring_conventions.md`:
   separator-on-same-line as `{% if %}`, inline labels on `{% else %}` /
   `{% endif %}`, to keep render output diff-clean.

5. **Bake in profile values at Step 5 handoff:**
   - `active_profile`: `{ name: {{ profile.name }} }`
   - `active_profile_filename`: `{{ profile.name }}.yaml`
   - Drop the parenthetical "(or null if no profile)" — profile is mandatory.
   - The handoff path stays `.claude/skills/task-workflow/SKILL.md` — the
     dep-walker rewrites it per-agent at render time (§3i).

6. **Scan body for stray `{{` / `{%`** outside Jinja directives. The current
   `aitask-explore` text contains no literal templating examples, but verify
   with `grep -n '{{\|{%' .claude/skills/aitask-explore/SKILL.md` against the
   pre-conversion file. Wrap any hits in `{% raw %}…{% endraw %}`.

## Stubs (4 files, byte-for-byte canonical from §3b-§3d)

Each stub uses `aitask-explore` for `<skill_short_name>` and `explore` for
`<resolver_key>`. Per-agent `<agent_literal>` values:
`claude`/`codex`/`gemini`/`opencode`. Use the existing `aitask-pick` stubs as
templates — substitute the slug + resolver key only:
- `.claude/skills/aitask-explore/SKILL.md` ← copy from
  `.claude/skills/aitask-pick/SKILL.md`, replace `aitask-pick`→`aitask-explore`
  and ` pick` (resolver call) → ` explore`.
- `.agents/skills/aitask-explore/SKILL.md` ← copy from
  `.agents/skills/aitask-pick/SKILL.md`, same substitutions.
- `.gemini/commands/aitask-explore.toml` ← copy from
  `.gemini/commands/aitask-pick.toml`, same substitutions (also update the
  `description` field to match the explore frontmatter description).
- `.opencode/commands/aitask-explore.md` ← copy from
  `.opencode/commands/aitask-pick.md`, same substitutions (also update the
  `description` field).

## Test script (`tests/test_skill_render_aitask_explore.sh`)

Adapt `tests/test_skill_render_aitask_pick.sh` line-for-line:

- `TEMPLATE=".claude/skills/aitask-explore/SKILL.md.j2"`
- `GOLDEN_DIR="tests/golden/skills/aitask-explore"`
- Test 2 (profile-conditional sanity) checks the `explore_auto_continue`
  branches — fast (`false`) renders the AskUserQuestion text; create a
  one-off test fixture or use a synthetic profile if you want to assert the
  `true` branch (cleanest: copy `fast.yaml`, override `explore_auto_continue: true`
  in `aitasks/metadata/profiles/local/` for the assertion, or simply assert
  current-profile values). **Decision**: assert against the live profiles
  only (matches the pick test):
  - `fast` (`explore_auto_continue: false`) → renders AskUserQuestion text
    "Task created successfully. How would you like to proceed?"
  - `default` (key absent → false) → same AskUserQuestion text
  - `remote` (key absent → false) → same AskUserQuestion text
  - All three: NO `continuing to implementation` text
  - This still proves the Jinja conditional renders the `{% else %}` arm and
    that the wrap is syntactically valid. The `{% if %}` arm is exercised by
    `./ait skill verify` (which renders without error against all profiles)
    plus a focused `assert_contains` after temporarily rendering against a
    synthetic profile. **Drop the synthetic-profile assertion** — `verify`
    + render-without-error covers it. Pick-test parity is the priority.
- Test 4 (cross-agent ref rewrites) checks `task-workflow-fast-/SKILL.md` is
  reachable from the rendered entry-point under each of the 4 agent roots —
  identical structure to the pick test, just substitute `aitask-explore`.
- Test 5 (stub markers) checks all 4 stubs contain
  `aitask_skill_resolve_profile.sh explore`,
  `aitask_skill_render.sh aitask-explore`,
  the canonical Read-and-follow marker, and the correct `--agent` literal +
  per-agent rendered-variant path.

## Goldens (12 files, flat dir)

Generated by rendering `aitask-explore` for each of the 3 profiles ×
4 agents:

```bash
for p in default fast remote; do
  for a in claude codex gemini opencode; do
    "$PYTHON" .aitask-scripts/lib/skill_template.py \
      .claude/skills/aitask-explore/SKILL.md.j2 \
      aitasks/metadata/profiles/${p}.yaml ${a} \
      > tests/golden/skills/aitask-explore/SKILL-${p}-${a}.md
  done
done
```

All 12 are committed. Subsequent template edits regenerate them and
`tests/test_skill_render_aitask_explore.sh` enforces empty diffs.

## Implementation Steps (in execution order)

1. **Author template** — copy current SKILL.md → SKILL.md.j2, apply the 6
   edits above. Verify with one manual render
   (`$PYTHON .aitask-scripts/lib/skill_template.py … fast.yaml claude`).
2. **Write 4 stubs** by copying from pick equivalents (above mapping).
3. **Replace the old per-agent surfaces** (delete then write new content; or
   just overwrite — the four files already exist):
   - `.claude/skills/aitask-explore/SKILL.md` *(overwrite ~22-line wrapper)*
   - `.agents/skills/aitask-explore/SKILL.md` *(overwrite)*
   - `.gemini/commands/aitask-explore.toml` *(overwrite)*
   - `.opencode/commands/aitask-explore.md` *(overwrite)*
4. **Generate goldens** — `mkdir -p tests/golden/skills/aitask-explore`; run
   the 3×4 render loop above to produce all 12 files.
5. **Render the full closure** for each agent so the live dispatch works:
   ```bash
   for a in claude codex gemini opencode; do
     ./.aitask-scripts/aitask_skill_render.sh aitask-explore \
       --profile fast --agent "$a" --force
   done
   ```
   (Also render `default` and `remote` so all three are on disk.)
6. **Write the test script** by copying from
   `tests/test_skill_render_aitask_pick.sh` and substituting paths.
7. **Run tests**:
   ```bash
   bash tests/test_skill_render_aitask_explore.sh
   ./.aitask-scripts/aitask_skill_verify.sh
   ```
   Both MUST be green before committing.
8. **Grep for stragglers**:
   ```bash
   grep -rn 'aitask-explore' .claude/skills/aitask-explore/ \
     .agents/skills/aitask-explore/ \
     .gemini/commands/aitask-explore.toml \
     .opencode/commands/aitask-explore.md \
     tests/test_skill_render_aitask_explore.sh
   ```
   Confirm only intended occurrences.

## Verification (end-to-end)

1. `bash tests/test_skill_render_aitask_explore.sh` — exits 0, all 12 golden
   diffs empty, profile-branch and stub-marker assertions pass.
2. `./.aitask-scripts/aitask_skill_verify.sh` — exits 0 (renders all 4 agents
   for all 3 profiles, validates stub format).
3. **Forbidden-token scan** on every rendered golden:
   ```bash
   for f in tests/golden/skills/aitask-explore/*.md; do
     for tok in 'aitask_scan_profiles.sh' \
                'Execute the Execution Profile Selection Procedure' \
                'Select Execution Profile' 'refresh execution profile'; do
       grep -F "$tok" "$f" && echo "FORBIDDEN: $tok in $f" && exit 1
     done
   done
   ```
4. **Stub-dispatch dry-run** (optional manual check, post-merge): invoking
   `/aitask-explore` in Claude Code reads the stub, renders fast variant,
   dispatches via Read-and-follow. The test script's Test 4 already exercises
   the render+rewrite layer on disk; live dispatch is exercised by the user
   the next time they pick up aitask-explore.

## Step 9 (Post-Implementation)

Per `task-workflow/SKILL.md` Step 9. Code commit message:
`refactor: Convert aitask-explore to template + stubs (t777_8)`. Plan commit
via `./ait git`. Archive with `./.aitask-scripts/aitask_archive.sh 777_8`.
Push with `./ait git push`. No linked issue.

## Notes for sibling tasks (t777_9..t777_15)

This conversion is a clean reuse of the pilot pattern with one profile key
(`explore_auto_continue`) and the canonical Jinja wrap. Sibling conversions
with similar single-key surfaces can copy this plan + bump the slug.

## Final Implementation Notes

- **Actual work done:** Authored `.claude/skills/aitask-explore/SKILL.md.j2`
  from the existing `aitask-explore/SKILL.md` (deleted Step 0 "Arguments
  (Optional)" and Step 3b "Select Execution Profile"; wrapped Step 4's
  `explore_auto_continue` check in `{% if profile.explore_auto_continue is
  defined and profile.explore_auto_continue %}…{% else %}…{% endif %}`
  following the inline-comment placement convention; baked profile values
  into Step 5 handoff). Replaced all 4 per-agent stubs
  (`.claude/skills/aitask-explore/SKILL.md`,
  `.agents/skills/aitask-explore/SKILL.md`,
  `.gemini/commands/aitask-explore.toml`,
  `.opencode/commands/aitask-explore.md`) with canonical stub bodies from
  `aidocs/stub-skill-pattern.md` §3b-§3d, resolver key `explore`. Generated
  12 goldens at `tests/golden/skills/aitask-explore/`. Authored
  `tests/test_skill_render_aitask_explore.sh` (5 tests, 118 assertions)
  adapted from the pick equivalent.
- **Deviations from plan:** None substantive. Test 2's `assert_not_contains`
  initially false-positive'd on the Notes-section phrase "continuing to
  implementation"; tightened the forbidden substring to
  `': continuing to implementation` (apostrophe-colon-prefixed) which only
  appears in the rendered `{% if %}` branch.
- **Issues encountered:** None.
- **Key decisions:**
  - Direct conversion (not staged under `aitask-exploren`): the pilot's
    parallel-name staging applied because `aitask-pick` drove its own
    conversion. Here `aitask-pick` is driving — `aitask-explore` is dormant,
    so in-place edits are safe.
  - Test 2 asserts the `{% else %}` arm across all 3 live profiles (none have
    `explore_auto_continue: true`); the `{% if %}` arm is exercised
    structurally by `./ait skill verify` rendering without error against
    every profile.
- **Upstream defects identified:** None.

## Verification Results (2026-05-19)

- `bash tests/test_skill_render_aitask_explore.sh` → **118/118 PASS**.
- `./.aitask-scripts/aitask_skill_verify.sh` → **OK** (2 templates × 4
  agents — aitask-pick + aitask-explore).
- Forbidden-token scan on all 12 goldens → clean (no
  `aitask_scan_profiles.sh`, `Execute the Execution Profile Selection
  Procedure`, `Select Execution Profile`, or `refresh execution profile`).
