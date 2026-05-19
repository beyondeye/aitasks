---
Task: t777_10_convert_aitask_fold.md
Parent Task: aitasks/t777_modular_pick_skill.md
Sibling Tasks: aitasks/t777/t777_11_convert_aitask_qa.md, aitasks/t777/t777_12_convert_aitask_pr_import.md, aitasks/t777/t777_13_convert_aitask_revert.md, aitasks/t777/t777_14_convert_aitask_pickrem.md, aitasks/t777/t777_15_convert_aitask_pickweb.md, aitasks/t777/t777_16_extract_profile_editor_widget.md, aitasks/t777/t777_17_per_run_profile_edit_in_agentcommandscreen.md, aitasks/t777/t777_18_docs_update_claudemd_and_website.md, aitasks/t777/t777_19_retrospective_evaluation.md, aitasks/t777/t777_20_profile_modification_invalidation.md
Archived Sibling Plans: aiplans/archived/p777/p777_1_minijinja_dep_renderer_paths_resolver.md, aiplans/archived/p777/p777_21_map_pick_reference_closure_and_profile_keys.md, aiplans/archived/p777/p777_22_extend_renderer_for_uniform_recursive_rendering.md, aiplans/archived/p777/p777_23_swap_task_workflown_to_task_workflow.md, aiplans/archived/p777/p777_25_refactor_stubs_direct_helper_paths.md, aiplans/archived/p777/p777_26_template_completeness_and_resolver_key.md, aiplans/archived/p777/p777_2_aitask_skill_render_subcommand.md, aiplans/archived/p777/p777_3_stub_skill_design_and_gitignore.md, aiplans/archived/p777/p777_4_aitask_skill_verify_and_precommit.md, aiplans/archived/p777/p777_5_aitask_skillrun_wrapper_dispatcher.md, aiplans/archived/p777/p777_6_convert_aitask_pick_template_and_stubs.md, aiplans/archived/p777/p777_7_convert_task_workflow_shared_procs.md, aiplans/archived/p777/p777_8_convert_aitask_explore.md, aiplans/archived/p777/p777_9_convert_aitask_review.md
Base branch: main
plan_verified:
  - claudecode/opus4_7_1m @ 2026-05-19 23:25
---

# Plan: t777_10 — Convert `aitask-fold` to template + stubs (4 agents)

## Context

`aitask-fold` is the next per-skill conversion in the t777 templated-dispatch
refactor (siblings t777_6 pilot, t777_8 explore, t777_9 review all complete).
The pilot established the pattern; siblings re-validated it. The shared
procedure closure was templated in t777_7. The conversion lets `aitask-fold`
use baked-in profile values for its single profile key (`explore_auto_continue`,
shared with aitask-explore) instead of re-reading the profile YAML at runtime
— eliminating the Step 0 (`--profile` parse) + Step 0a "Select Execution
Profile" round-trip.

**Verification findings vs. existing thin plan and prior siblings:**

- `.claude/skills/aitask-fold/SKILL.md` is the fat (non-template) original
  (145 lines, one `**Profile check:**` block at Step 4 line ~96 referencing
  `explore_auto_continue`).
- `.agents/skills/aitask-fold/SKILL.md`, `.gemini/commands/aitask-fold.toml`,
  `.opencode/commands/aitask-fold.md` exist as pre-templating wrappers and
  will be overwritten with canonical stubs.
- Resolver-key mapping already wired:
  `.aitask-scripts/aitask_skill_verify.sh:74` maps `aitask-fold → fold`.
- Profile YAML state: only `fast.yaml` defines `explore_auto_continue: false`;
  `default.yaml` and `remote.yaml` do not set it. Therefore the
  `{% if profile.explore_auto_continue is defined and profile.explore_auto_continue %}`
  guard's `{% else %}` arm fires for all three live profiles. The `{% if %}`
  arm is exercised structurally by `./ait skill verify`.
- Pattern is identical to t777_8 (aitask-explore): single profile key, same
  key name (`explore_auto_continue`). The branch wrapping at Step 4 follows
  the explore template's Step 4 wrap **verbatim**, substituting only the
  prose around the message.

## Decision: direct conversion, not staged

Per pilot lesson #2 (`feedback_stage_under_parallel_name`), parallel-name
staging applies when the conversion is driven by the skill being converted.
**`aitask-fold` is NOT driving this conversion** (`aitask-pick` is). Editing
in place is safe; no `aitask-foldn` stage.

## Critical Files

**Created / replaced (5 framework files):**
- `.claude/skills/aitask-fold/SKILL.md.j2` *(new)* — entry-point template
- `.claude/skills/aitask-fold/SKILL.md` *(replace with canonical stub per
  `aidocs/stub-skill-pattern.md` §3b, `<agent_literal>=claude`)*
- `.agents/skills/aitask-fold/SKILL.md` *(replace with canonical stub per
  §3b, `<agent_literal>=codex`)*
- `.gemini/commands/aitask-fold.toml` *(replace with canonical stub per §3c)*
- `.opencode/commands/aitask-fold.md` *(replace with canonical stub per §3d)*

**Test infrastructure (created):**
- `tests/test_skill_render_aitask_fold.sh` *(new)* — adapted from
  `tests/test_skill_render_aitask_review.sh`
- `tests/golden/skills/aitask-fold/SKILL-<profile>-<agent>.md` — 12 golden
  files (3 profiles × 4 agents), flat directory layout

**Read-only references:**
- `.claude/skills/aitask-fold/SKILL.md` *(existing — source for template)*
- `.claude/skills/aitask-explore/SKILL.md.j2` *(reference for Jinja conventions
  and the single-key wrap pattern — same key name)*
- `.claude/skills/aitask-explore/SKILL.md` *(reference for canonical Claude stub)*
- `.agents/skills/aitask-explore/SKILL.md` *(reference for Codex stub)*
- `.gemini/commands/aitask-explore.toml` *(reference for Gemini stub)*
- `.opencode/commands/aitask-explore.md` *(reference for OpenCode stub)*
- `aidocs/stub-skill-pattern.md` *(canonical bodies §3b-§3d, conventions §3f,
  template completeness §3j)*
- `aidocs/skill_authoring_conventions.md` *(Jinja inline-comment convention)*
- `tests/test_skill_render_aitask_review.sh` *(closest model for the new test
  script — 1-key wrap structure matches more closely than the 2-key explore
  test would; pick either as base, paths differ identically)*

## Template authoring (`.claude/skills/aitask-fold/SKILL.md.j2`)

Source: copy current `.claude/skills/aitask-fold/SKILL.md`, then apply these
five edits:

1. **Frontmatter** — `name: aitask-fold-{{ profile.name }}`.

2. **Delete Step 0 "(pre-parse): Extract `--profile` argument"** (current
   lines 8–18). The `--profile <name>` parsing is handled by the stub Step 1;
   the rendered body never re-resolves the profile (§3j).

3. **Delete Step 0a "Select Execution Profile"** (current lines 20–25).
   Profile is baked in at render time. Forbidden tokens per §3j MUST NOT
   appear after these two deletions: `aitask_scan_profiles.sh`,
   `Execute the Execution Profile Selection Procedure`,
   `Select Execution Profile`, `refresh execution profile`.

4. **Wrap Step 4 profile check on `explore_auto_continue`** (current
   lines 96–114). The pattern follows aitask-explore's Step 4 wrap exactly
   (same key, same guard). The `**Profile check:**` narrative wrapper and
   the "Default when …" note are dropped (replaced by the Jinja conditional).
   Wrap so the `{% if %}` arm covers the auto-continue display + handoff,
   and the `{% else %}` arm covers the existing AskUserQuestion sub-branches:

   ```jinja
   {# ---------- explore_auto_continue ---------- #}{% if profile.explore_auto_continue is defined and profile.explore_auto_continue %}
   - Display: "Profile '{{ profile.name }}': continuing to implementation"
   - Skip the AskUserQuestion below and proceed directly to the handoff
   {% else %}{# explore_auto_continue: when false / undefined #}
   Use `AskUserQuestion`:
   - Question: "Tasks folded successfully into t\<primary_id\>. How would you like to proceed?"
   - Header: "Proceed"
   - Options:
     - "Continue to implementation" (description: "Start implementing the merged task now via the standard workflow")
     - "Save for later" (description: "Task saved — pick it up later with /aitask-pick <N>")

   **If "Save for later":**
   - Inform user: "Task t\<primary_id\>_\<name\>.md is ready. Run `/aitask-pick <primary_id>` when you want to implement it."
   - End the workflow.

   **If "Continue to implementation":**
   - Proceed to the handoff below.
   {% endif %}{# ---------- end explore_auto_continue ---------- #}
   ```

   Follow the inline-comment convention from
   `aidocs/skill_authoring_conventions.md`: separator-on-same-line as
   `{% if %}`, inline labels on `{% else %}` / `{% endif %}`, render-neutral.

5. **Bake in profile values at Step 5 handoff** (current lines 126–127):
   - `active_profile`: `{ name: {{ profile.name }} }` (replace the
     "The execution profile loaded in Step 0a (or null if no profile)" prose).
   - `active_profile_filename`: `{{ profile.name }}.yaml` (replace the
     scanner-output prose).
   - Drop the parenthetical "(or null if no profile)" — profile is mandatory.
   - The handoff path stays `.claude/skills/task-workflow/SKILL.md` — the
     dep-walker rewrites it per-agent at render time (§3i).

6. **Scan body for stray `{{` / `{%`** outside Jinja directives. Wrap any
   hits in `{% raw %}…{% endraw %}`. Pre-conversion check:
   `grep -nE '\{\{|\{%' .claude/skills/aitask-fold/SKILL.md`.

## Stubs (4 files, byte-for-byte canonical from §3b–§3d)

Each stub uses `aitask-fold` for `<skill_short_name>` and `fold` for
`<resolver_key>`. Per-agent `<agent_literal>`:
`claude`/`codex`/`gemini`/`opencode`. Copy from the explore stubs and
substitute the slug + resolver key:

- `.claude/skills/aitask-fold/SKILL.md` ← copy from
  `.claude/skills/aitask-explore/SKILL.md`, replace
  `aitask-explore`→`aitask-fold` and ` explore`→` fold` (the resolver-key
  invocation), update the `description:` frontmatter to
  "Identify and merge related tasks into a single task, then optionally execute it."
- `.agents/skills/aitask-fold/SKILL.md` ← copy from
  `.agents/skills/aitask-explore/SKILL.md`, same substitutions + description.
- `.gemini/commands/aitask-fold.toml` ← copy from
  `.gemini/commands/aitask-explore.toml`, same substitutions + description.
- `.opencode/commands/aitask-fold.md` ← copy from
  `.opencode/commands/aitask-explore.md`, same substitutions + description.

## Test script (`tests/test_skill_render_aitask_fold.sh`)

Adapt `tests/test_skill_render_aitask_review.sh` line-for-line (review is
the closest neighbor — it has the same 5-test layout, just two profile keys
instead of one). For fold we collapse Test 2 to the single-key case
(mirrors aitask-explore's actual asserts but kept inline rather than
referencing the explore test):

- `TEMPLATE=".claude/skills/aitask-fold/SKILL.md.j2"`
- `GOLDEN_DIR="tests/golden/skills/aitask-fold"`
- Test 2 (profile-conditional sanity): the live profiles
  (`default`/`fast`/`remote`) leave `explore_auto_continue` undefined
  (default/remote) or `false` (fast), so all three render the `{% else %}`
  arm. Assertions for each profile:
  - else arm fires: contains
    `Tasks folded successfully into t\<primary_id\>. How would you like to proceed?`
    (the AskUserQuestion prompt unique to fold's Step 4 else arm).
  - if arm does NOT fire: forbidden substring
    `': continuing to implementation` (apostrophe-colon prefix avoids
    matching Notes-section prose; same discipline as t777_8/t777_9).
  - The `{% if %}` arm is exercised structurally by `./ait skill verify`
    (which renders without error against every profile).
- Test 3 (no Jinja markers leak): identical to review test.
- Test 3b (forbidden runtime profile-resolution tokens): identical token
  list to review test (`aitask_scan_profiles.sh`,
  `Execute the Execution Profile Selection Procedure`,
  `Select Execution Profile`, `refresh execution profile`).
- Test 4 (cross-agent ref rewrites): identical structure, substitute slug
  — assert `task-workflow-<profile>-/SKILL.md` is reachable under each of
  the 4 agent roots from the rendered entry-point.
- Test 5 (stub markers): each of the 4 stubs contains
  `aitask_skill_resolve_profile.sh fold`,
  `aitask_skill_render.sh aitask-fold`,
  the canonical Read-and-follow marker, and the correct `--agent` literal
  + per-agent rendered-variant path
  (`<agent_root>/skills/aitask-fold-<profile>-/SKILL.md`).

## Goldens (12 files, flat dir)

Generate via:

```bash
mkdir -p tests/golden/skills/aitask-fold
for p in default fast remote; do
  for a in claude codex gemini opencode; do
    "$PYTHON" .aitask-scripts/lib/skill_template.py \
      .claude/skills/aitask-fold/SKILL.md.j2 \
      aitasks/metadata/profiles/${p}.yaml ${a} \
      > tests/golden/skills/aitask-fold/SKILL-${p}-${a}.md
  done
done
```

(Reuse the `$PYTHON` resolution from the review test — the file
`.aitask-scripts/lib/python_resolve.sh` provides it.) All 12 are committed.

## Implementation Steps (in execution order)

1. **Author template** — copy `.claude/skills/aitask-fold/SKILL.md` →
   `SKILL.md.j2`, apply the six edits above. Verify with one manual render:
   ```bash
   $PYTHON .aitask-scripts/lib/skill_template.py \
     .claude/skills/aitask-fold/SKILL.md.j2 \
     aitasks/metadata/profiles/fast.yaml claude | head -40
   ```
2. **Write 4 stubs** by copying from explore equivalents (mapping above).
3. **Overwrite the old per-agent surfaces** (all 4 files already exist):
   - `.claude/skills/aitask-fold/SKILL.md`
   - `.agents/skills/aitask-fold/SKILL.md`
   - `.gemini/commands/aitask-fold.toml`
   - `.opencode/commands/aitask-fold.md`
4. **Generate goldens** — `mkdir -p tests/golden/skills/aitask-fold`; run
   the 3×4 render loop to produce all 12 files.
5. **Render the full closure** for each agent so live dispatch works:
   ```bash
   for a in claude codex gemini opencode; do
     ./.aitask-scripts/aitask_skill_render.sh aitask-fold \
       --profile fast --agent "$a" --force
   done
   ```
   (Also render `default` and `remote` so all three are on disk.)
6. **Write the test script** by copying from
   `tests/test_skill_render_aitask_review.sh` and substituting paths +
   collapsing Test 2 to the single-key case.
7. **Run tests**:
   ```bash
   bash tests/test_skill_render_aitask_fold.sh
   ./.aitask-scripts/aitask_skill_verify.sh
   ```
   Both MUST be green before committing.
8. **Grep for stragglers**:
   ```bash
   grep -rn 'aitask-fold' .claude/skills/aitask-fold/ \
     .agents/skills/aitask-fold/ \
     .gemini/commands/aitask-fold.toml \
     .opencode/commands/aitask-fold.md \
     tests/test_skill_render_aitask_fold.sh
   ```
   Confirm only intended occurrences.

## Verification

1. `bash tests/test_skill_render_aitask_fold.sh` — exits 0, all 12 golden
   diffs empty, profile-branch and stub-marker assertions pass.
2. `./.aitask-scripts/aitask_skill_verify.sh` — exits 0 (renders all 4
   agents for all 3 profiles, validates stub format, asserts 4 templates
   total — pick + explore + review + fold).
3. **Forbidden-token scan** on every rendered golden:
   ```bash
   for f in tests/golden/skills/aitask-fold/*.md; do
     for tok in 'aitask_scan_profiles.sh' \
                'Execute the Execution Profile Selection Procedure' \
                'Select Execution Profile' 'refresh execution profile'; do
       grep -F "$tok" "$f" && echo "FORBIDDEN: $tok in $f" && exit 1
     done
   done
   ```
4. **Stub-dispatch dry-run** (manual, post-merge): invoking `/aitask-fold`
   in Claude Code reads the stub, renders the appropriate profile variant,
   dispatches via Read-and-follow. The test script's Test 4 already exercises
   the render+rewrite layer on disk.

## Step 9 (Post-Implementation)

Per `task-workflow/SKILL.md` Step 9. Code commit message:
`refactor: Convert aitask-fold to template + stubs (t777_10)`. Plan commit
via `./ait git`. Archive with `./.aitask-scripts/aitask_archive.sh 777_10`.
Push with `./ait git push`. No linked issue.

## Notes for sibling tasks (t777_11..t777_15)

This conversion is structurally identical to t777_8 (single profile key —
same key name even). Future siblings with N profile keys can wrap each key
in its own Jinja block with the same `is defined and <key>` guard
(t777_9 demonstrated the two-key case).

## Out of scope (deferred)

None — `aitask-fold` references exactly one profile key
(`explore_auto_continue`); no other behavior to template.
