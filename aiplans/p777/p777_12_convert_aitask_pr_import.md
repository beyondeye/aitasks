---
Task: t777_12_convert_aitask_pr_import.md
Parent Task: aitasks/t777_modular_pick_skill.md
Sibling Tasks: aitasks/t777/t777_13_convert_aitask_revert.md, aitasks/t777/t777_14_convert_aitask_pickrem.md, aitasks/t777/t777_15_convert_aitask_pickweb.md, aitasks/t777/t777_16_extract_profile_editor_widget.md, aitasks/t777/t777_17_per_run_profile_edit_in_agentcommandscreen.md, aitasks/t777/t777_18_docs_update_claudemd_and_website.md, aitasks/t777/t777_19_retrospective_evaluation.md, aitasks/t777/t777_20_profile_modification_invalidation.md
Archived Sibling Plans: aiplans/archived/p777/p777_10_convert_aitask_fold.md, aiplans/archived/p777/p777_11_convert_aitask_qa.md, aiplans/archived/p777/p777_1_minijinja_dep_renderer_paths_resolver.md, aiplans/archived/p777/p777_21_map_pick_reference_closure_and_profile_keys.md, aiplans/archived/p777/p777_22_extend_renderer_for_uniform_recursive_rendering.md, aiplans/archived/p777/p777_23_swap_task_workflown_to_task_workflow.md, aiplans/archived/p777/p777_25_refactor_stubs_direct_helper_paths.md, aiplans/archived/p777/p777_26_template_completeness_and_resolver_key.md, aiplans/archived/p777/p777_2_aitask_skill_render_subcommand.md, aiplans/archived/p777/p777_3_stub_skill_design_and_gitignore.md, aiplans/archived/p777/p777_4_aitask_skill_verify_and_precommit.md, aiplans/archived/p777/p777_5_aitask_skillrun_wrapper_dispatcher.md, aiplans/archived/p777/p777_6_convert_aitask_pick_template_and_stubs.md, aiplans/archived/p777/p777_7_convert_task_workflow_shared_procs.md, aiplans/archived/p777/p777_8_convert_aitask_explore.md, aiplans/archived/p777/p777_9_convert_aitask_review.md
Base branch: main
plan_verified:
  - claudecode/opus4_7_1m @ 2026-05-20 13:03
---

# Plan: t777_12 — Convert `aitask-pr-import` to template + stubs (4 agents)

## Context

`aitask-pr-import` is the next per-skill conversion in the t777 templated-dispatch
refactor. Siblings t777_6 (pilot `pick`), t777_8 (`explore`), t777_9 (`review`),
t777_10 (`fold`), t777_11 (`qa`) are all complete; the dep-walker (t777_22),
shared-proc templating (t777_7) and template-completeness rules (t777_26) all
landed. The conversion lets `aitask-pr-import` bake profile values in at render
time instead of re-reading the profile YAML at runtime — eliminating the
Step 0a "Select Execution Profile" round-trip.

**Verify-path finding — the conversion is simpler than `aitask-qa`.**
Unlike `aitask-qa` (t777_11, the first conversion with its own procedure-file
closure), `aitask-pr-import` has **no own procedure files** — only a single
`.claude/skills/aitask-pr-import/SKILL.md`. All cross-skill references point at
`task-workflow/` procedures. A `grep` for profile usage found exactly **one**
`**Profile check:**` wrap site:

| Profile key | File | Site |
|---|---|---|
| `explore_auto_continue` (bool) | `SKILL.md` | Step 6 "Decision Point" |

This makes `aitask-pr-import` a near-exact structural twin of `aitask-explore`
(t777_8): both delete Step 0a, both wrap the single `explore_auto_continue`
key, both hand off to `task-workflow`, both have no own procedure files.
`aitask-explore/SKILL.md.j2` is the direct model for this conversion.

**Profile-YAML state (verified):** `explore_auto_continue` is `false` in
`fast.yaml`, unset in `default.yaml` and `remote.yaml`. All three committed
profiles therefore render the `{% else %}` (interactive) arm; the `{% if %}`
(auto-continue) arm is exercised structurally by `ait skill verify` and
guarded by the Test 1b invariance assertion — identical to `aitask-explore`.

**Pre-checks passed:**
- No bare `SKILL.md` token in prose — both `SKILL.md` mentions are
  `task-workflow/SKILL.md` full-path refs, so the t777_11 dep-walker
  target-path collision cannot occur here.
- No stray `{{` / `{%` in the source — no `{% raw %}` wrapping needed.
- Resolver key `aitask-pr-import → pr-import` already wired in
  `aitask_skill_verify.sh:76` — no script change needed.
- `aitask_skill_verify.sh` auto-discovers `SKILL.md.j2` via `find` — adding
  the new template needs no registration.

## Decision: direct conversion, not staged

Per pilot lesson #2 (`feedback_stage_under_parallel_name`), parallel-name
staging applies only when the conversion is driven by the skill being
converted. `aitask-pr-import` is **not** driving this conversion
(`aitask-pick` is). Editing in place is safe — same call as
t777_8/t777_9/t777_10/t777_11.

## Critical Files

**Created / replaced (5 framework files):**
- `.claude/skills/aitask-pr-import/SKILL.md.j2` *(new)* — entry-point template
- `.claude/skills/aitask-pr-import/SKILL.md` *(replace — canonical Claude stub, `aidocs/stub-skill-pattern.md` §3b, `<agent_literal>=claude`)*
- `.agents/skills/aitask-pr-import/SKILL.md` *(replace — Codex stub §3b, `codex`)*
- `.gemini/commands/aitask-pr-import.toml` *(replace — Gemini stub §3c)*
- `.opencode/commands/aitask-pr-import.md` *(replace — OpenCode stub §3d)*

**Test infrastructure (created):**
- `tests/test_skill_render_aitask_pr_import.sh` *(new)* — adapted from `tests/test_skill_render_aitask_explore.sh`
- `tests/golden/skills/aitask-pr-import/SKILL-<profile>-claude.md` — 3 entry-point goldens (3 profiles, claude canonical, per the t809 golden-dimensionality refinement)

**Left untouched (out of scope — see below):**
- `.opencode/skills/aitask-pr-import/SKILL.md` — orphaned legacy OpenCode
  wrapper. `aitask-explore` and `aitask-qa` both left their equivalents
  (`.opencode/skills/aitask-explore/SKILL.md`,
  `.opencode/skills/aitask-qa/SKILL.md`) in place; following that precedent.

**Read-only references:** `.claude/skills/aitask-explore/SKILL.md.j2`
(direct model — same `explore_auto_continue` key, same handoff shape),
`aiplans/archived/p777/p777_8_convert_aitask_explore.md`,
`aiplans/archived/p777/p777_11_convert_aitask_qa.md`,
`aidocs/stub-skill-pattern.md` §3b–§3d/§3f/§3g/§3i/§3j,
`aidocs/skill_authoring_conventions.md` (Jinja-comment convention + golden
regen rule), `tests/test_skill_render_aitask_explore.sh` (test model).

## Template authoring — `.claude/skills/aitask-pr-import/SKILL.md.j2`

Source: copy current `.claude/skills/aitask-pr-import/SKILL.md`, then apply:

1. **Frontmatter** — `name: aitask-pr-import-{{ profile.name }}`; keep the
   `description:` line; **drop `user-invocable: true`** (the rendered variant
   is reached via Read-and-follow, not auto-discovery — matches
   `aitask-explore`/`aitask-qa` j2 frontmatter).

2. **Delete the `## Arguments (Optional)` section** (lines 7–13) — it only
   documents runtime `--profile` parsing into `profile_override`, which the
   stub now owns (§3h argument-forwarding contract). First surviving heading
   becomes `## Workflow`.

3. **Delete Step 0a "Select Execution Profile"** (lines 17–21). Profile is
   baked in at render time; this is a forbidden runtime profile-resolution
   site (§3j). Its `execution-profile-selection.md` cross-ref disappears with
   it. **Keep Step 0c "Sync with Remote"** unchanged — it is not a profile
   check. First surviving Workflow heading: `### Step 0c`.

4. **Wrap Step 6 "Decision Point" `explore_auto_continue` check** — bool key,
   two-armed, modelled exactly on `aitask-explore/SKILL.md.j2` Step 4:
   ```jinja
   {# ---------- explore_auto_continue ---------- #}{% if profile.explore_auto_continue is defined and profile.explore_auto_continue %}
   - Display: "Profile '{{ profile.name }}': continuing to implementation"
   - Skip the AskUserQuestion below and proceed directly to the handoff
   {% else %}{# explore_auto_continue: when false / undefined #}
   Use `AskUserQuestion`:
   - Question: "Task created successfully. How would you like to proceed?"
   ... (existing options + the **Note:** about "Save for later" default + the
       two **If "..."** action blocks, verbatim)
   {% endif %}{# ---------- end explore_auto_continue ---------- #}
   ```
   The `**Default when explore_auto_continue is not defined:** false` prose
   line is dropped — the `is defined and` guard makes it implicit (same as
   the `aitask-explore` conversion). **Behavior preserved exactly:** the
   `{% else %}` arm keeps `aitask-pr-import`'s current "Save for later" /
   "Continue to implementation" ordering and its **Note** explaining the
   PR-task-specific default — this is NOT changed to match `aitask-explore`.

5. **Step 7 handoff context variables** — replace the two runtime-resolved
   lines with baked-in values (mirrors `aitask-explore` Step 5):
   ```
   - **active_profile**: `{ name: {{ profile.name }} }` (baked in at render time)
   - **active_profile_filename**: `{{ profile.name }}.yaml`
   ```

6. **Keep** the three `task-workflow/` full-path refs intact
   (`task-creation-batch.md` in Step 5, `SKILL.md` in Step 7 and Notes) — the
   dep-walker rewrites them per-agent to `<root>/task-workflow-<profile>-/`.

7. **Pre-check before save:** `grep -nE '\{\{|\{%' SKILL.md.j2` — only the
   intended Jinja directives from steps 1/4/5 should appear.

## Stubs (4 files, canonical bodies §3b–§3d)

Copy from the `aitask-explore` stubs, substituting `aitask-explore` →
`aitask-pr-import`, resolver key `explore` → `pr-import`, and the description
to `Create an aitask from a pull request by analyzing PR data and generating a structured task with implementation plan.`:
- `.claude/skills/aitask-pr-import/SKILL.md` ← Claude stub (`--agent claude`)
- `.agents/skills/aitask-pr-import/SKILL.md` ← Codex stub (`--agent codex`)
- `.gemini/commands/aitask-pr-import.toml` ← Gemini stub (`--agent gemini`)
- `.opencode/commands/aitask-pr-import.md` ← OpenCode stub (`--agent opencode`)

Each stub: §3b/§3c/§3d canonical body, profile-agnostic, resolver call
`aitask_skill_resolve_profile.sh pr-import`, render call
`aitask_skill_render.sh aitask-pr-import --profile <profile> --agent <literal>`,
Read target `<root>/aitask-pr-import-<profile>-/SKILL.md`.

## Test script — `tests/test_skill_render_aitask_pr_import.sh`

Adapt `tests/test_skill_render_aitask_explore.sh` (no procedure-golden loop
needed — `aitask-pr-import` has no own procedure files):

- **Test 1** — 3 entry-point golden diffs (`default`/`fast`/`remote`, claude render).
- **Test 1b** — agent-dimension invariance: `codex`/`gemini`/`opencode` stdout
  renders byte-identical to `claude` (no `{% if agent %}` gate).
- **Test 2** — profile-conditional sanity: all 3 profiles render the
  `{% else %}` arm — assert `Task created successfully. How would you like to proceed?`
  present, assert `': continuing to implementation` absent.
- **Test 3** — no Jinja markers (`{%`, `{{`) leak into any rendered entry-point.
- **Test 3b** — §3j forbidden tokens absent (`aitask_scan_profiles.sh`,
  `Execute the Execution Profile Selection Procedure`, `Select Execution Profile`,
  `refresh execution profile`) across all profile × agent renders.
- **Test 4** — cross-agent ref rewrite via `aitask_skill_render.sh ... --force`:
  assert `<agent_root>/task-workflow-fast-/SKILL.md` appears in each agent's
  rendered `aitask-pr-import-fast-/SKILL.md`.
- **Test 5** — 4 stubs contain canonical markers:
  `aitask_skill_resolve_profile.sh pr-import` (and NOT `... aitask-pr-import`),
  `aitask_skill_render.sh aitask-pr-import`, `Dispatch via Read-and-follow`,
  the correct `--agent` literal, and the per-agent rendered-variant path.

## Goldens (3 files)

Generate with the framework Python (`python_resolve.sh::require_ait_python`):
```bash
mkdir -p tests/golden/skills/aitask-pr-import
for p in default fast remote; do
  "$PYTHON" .aitask-scripts/lib/skill_template.py \
    .claude/skills/aitask-pr-import/SKILL.md.j2 \
    aitasks/metadata/profiles/$p.yaml claude \
    > tests/golden/skills/aitask-pr-import/SKILL-$p-claude.md
done
```
All 3 committed (claude-only, per the t809 golden-dimensionality refinement —
the basic stdout render does no per-agent rewriting, so codex/gemini/opencode
are byte-identical and covered by Test 1b).

## Implementation Steps (execution order)

1. Author `.claude/skills/aitask-pr-import/SKILL.md.j2` (edits 1–7 above).
   Smoke-render: `$PYTHON .aitask-scripts/lib/skill_template.py .claude/skills/aitask-pr-import/SKILL.md.j2 aitasks/metadata/profiles/fast.yaml claude | head -40`.
2. Write the 4 stubs (overwrite existing per-agent surfaces).
3. Generate the 3 goldens (loop above).
4. Render the full closure for all 4 agents × 3 profiles so live dispatch works:
   `for a in claude codex gemini opencode; do for p in default fast remote; do ./.aitask-scripts/aitask_skill_render.sh aitask-pr-import --profile $p --agent "$a" --force; done; done`.
5. Write `tests/test_skill_render_aitask_pr_import.sh`.
6. Run `bash tests/test_skill_render_aitask_pr_import.sh` and
   `./.aitask-scripts/aitask_skill_verify.sh` — both MUST be green.
7. Grep stragglers: `grep -rn 'aitask-pr-import' .claude/skills/aitask-pr-import/ .agents/skills/aitask-pr-import/ .gemini/commands/aitask-pr-import.toml .opencode/commands/aitask-pr-import.md tests/test_skill_render_aitask_pr_import.sh`.

## Verification

1. `bash tests/test_skill_render_aitask_pr_import.sh` — exits 0, all 3 golden
   diffs empty, invariance / profile-branch / forbidden-token / ref-rewrite /
   stub assertions pass.
2. `./.aitask-scripts/aitask_skill_verify.sh` — exits 0 (renders all 4 agents
   × default profile, walk-checks the pr-import closure incl. the
   `task-workflow` subtree, validates the 4 stubs).
3. Forbidden-token scan on every rendered golden — clean.
4. Stub-dispatch dry-run (manual, post-merge): `/aitask-pr-import` reads the
   stub → renders → Read-and-follows the rendered variant.

## Out of scope (deferred)

- `.opencode/skills/aitask-pr-import/SKILL.md` orphan cleanup — left in place
  per the `aitask-explore` / `aitask-qa` precedent. A framework-wide sweep of
  these orphaned `.opencode/skills/<skill>/SKILL.md` (and any stale
  `.agents/skills/`) files is a candidate follow-up across all converted
  skills, not a per-skill task.
- `aitask-pr-import`'s current "Save for later" branch ends the workflow
  without calling the Satisfaction Feedback Procedure, whereas
  `aitask-explore`'s equivalent branch does. This pre-existing inconsistency
  is preserved (mechanical conversion only) — reconciling it is a separate
  behavior decision.

## Step 9 (Post-Implementation)

Standard child-task archival. Code commit:
`refactor: Convert aitask-pr-import to template + stubs (t777_12)`. Plan commit
via `./ait git`. Archive: `./.aitask-scripts/aitask_archive.sh 777_12`. Push
via `./ait git push`. No linked issue. Profile `fast` → no worktree (work on
current branch); the Step 9 merge-approval gate is a no-op.

The 4 stubs cover all 4 agents in this same task — no separate
Codex/Gemini/OpenCode follow-up tasks are needed.

## Notes for sibling tasks

`aitask-pr-import` is a structural twin of `aitask-explore` — no own procedure
files, single `explore_auto_continue` wrap, handoff to `task-workflow`.
`aitask-revert` (t777_13) / `aitask-pickrem` (t777_14) / `aitask-pickweb`
(t777_15) should each first check whether they own procedure files: if yes,
follow the `aitask-qa` (t777_11) procedure-closure pattern; if no, follow this
`aitask-explore`/`aitask-pr-import` single-template pattern.
