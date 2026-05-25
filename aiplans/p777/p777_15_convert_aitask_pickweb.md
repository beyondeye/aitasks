---
Task: t777_15_convert_aitask_pickweb.md
Parent Task: aitasks/t777_modular_pick_skill.md
Sibling Tasks: aitasks/t777/t777_17_per_run_profile_edit_in_agentcommandscreen.md, aitasks/t777/t777_18_docs_update_claudemd_and_website.md, aitasks/t777/t777_19_retrospective_evaluation.md, aitasks/t777/t777_20_profile_modification_invalidation.md, aitasks/t777/t777_27_recover_runtime_skills_and_parity_tests.md, aitasks/t777/t777_28_dedup_template_branches_common_proc_and_macros.md
Archived Sibling Plans: aiplans/archived/p777/p777_10_convert_aitask_fold.md, aiplans/archived/p777/p777_11_convert_aitask_qa.md, aiplans/archived/p777/p777_12_convert_aitask_pr_import.md, aiplans/archived/p777/p777_13_convert_aitask_revert.md, aiplans/archived/p777/p777_14_convert_aitask_pickrem.md, aiplans/archived/p777/p777_16_extract_profile_editor_widget.md, aiplans/archived/p777/p777_1_minijinja_dep_renderer_paths_resolver.md, aiplans/archived/p777/p777_21_map_pick_reference_closure_and_profile_keys.md, aiplans/archived/p777/p777_22_extend_renderer_for_uniform_recursive_rendering.md, aiplans/archived/p777/p777_23_swap_task_workflown_to_task_workflow.md, aiplans/archived/p777/p777_25_refactor_stubs_direct_helper_paths.md, aiplans/archived/p777/p777_26_template_completeness_and_resolver_key.md, aiplans/archived/p777/p777_2_aitask_skill_render_subcommand.md, aiplans/archived/p777/p777_3_stub_skill_design_and_gitignore.md, aiplans/archived/p777/p777_4_aitask_skill_verify_and_precommit.md, aiplans/archived/p777/p777_5_aitask_skillrun_wrapper_dispatcher.md, aiplans/archived/p777/p777_6_convert_aitask_pick_template_and_stubs.md, aiplans/archived/p777/p777_7_convert_task_workflow_shared_procs.md, aiplans/archived/p777/p777_8_convert_aitask_explore.md, aiplans/archived/p777/p777_9_convert_aitask_review.md
Base branch: main
plan_verified:
  - claudecode/opus4_7_1m @ 2026-05-25 09:51
---

# Plan: t777_15 — Convert `aitask-pickweb` to templated stub pattern across all 4 agents

## Context

The pickweb skill is the Claude-Code-Web-tailored variant of pickrem: zero
`AskUserQuestion` calls, no cross-branch operations, plan and completion
marker stored under `.aitask-data-updated/`. Today it lives as four full
monolithic SKILL.md files (one per agent root). Every other pick-family
skill has already been ported to the templated stub pattern (most
recently pickrem in t777_14). This task ports pickweb the same way so
profile decisions are baked at render time, pre-rendered remote variants
ship committed for all four agents (so the skill works on Claude Web where
minijinja is unavailable), and the dispatch + closure-rewrite plumbing is
uniform with pickrem.

While verifying the plan I uncovered a **pre-existing leftover from
templating** that affects pickweb's port directly:

- For *every* already-templated skill (pick, explore, review, fold, qa,
  pr-import, revert, pickrem), the file
  `.opencode/skills/<skill>/SKILL.md` still contains the
  pre-templating-era "Source of Truth" wrapper pointing at
  `.claude/skills/<skill>/SKILL.md`. That target is now the §3b Claude
  stub, not a workflow — so following the pointer routes OpenCode through
  Claude's rendered tree instead of OpenCode's. The §3d stub at
  `.opencode/commands/<skill>.md` is correct and is what `/<skill>` slash
  invocations actually fire; the legacy file is only reached via
  OpenCode's description-based skill auto-discovery
  (`.opencode/instructions.md` declares `.opencode/skills/` as the
  registry surface).
- The wrapper auditor (`aitask_audit_wrappers.sh::render_opencode_skill`,
  line 180) still emits the legacy pointer pattern, so re-running
  `/aitask-audit-wrappers` would recreate the leftover even after a fix.
- t777_14's commit (`bef1f819`) modified Codex `.agents/skills/aitask-pickrem/SKILL.md`,
  Gemini `.gemini/commands/aitask-pickrem.toml`, and OpenCode
  `.opencode/commands/aitask-pickrem.md` — but did NOT touch
  `.opencode/skills/aitask-pickrem/SKILL.md`. Same omission for the other
  6 already-templated skills.

Per user direction, this task fixes ONLY pickweb's own leftover (replace
its `.opencode/skills/aitask-pickweb/SKILL.md` body); the broader 7-skill
cleanup + audit-wrappers patch is deferred to a follow-up child task
**t777_29** authored at the end of this one.

## Verification of existing plan (verify-mode entry)

Existing plan at `aiplans/p777/p777_15_convert_aitask_pickweb.md` says
"mirror of t777_14, plus possibly web-specific keys". Re-checked:

- Pickweb's monolithic SKILL.md references only **2 profile keys**:
  `plan_preference` (3 values, used at Step 5.0) and `post_plan_action`
  (1 value used, Step 5 Checkpoint). All other profile fields from
  pickrem are explicitly ignored; web-mode behavior (no lock acquisition,
  no archive, abort-on-Done/orphaned, no `./ait git`) is hardcoded in
  pickweb. So no web-specific keys; the conversion is even smaller than
  pickrem.
- t777_14's stubs use a **"conditional-Read"** divergence from canonical
  §3b: Step 2 is `Render only if needed` — skip the render call if the
  pre-rendered file already exists. This pattern is required by the
  Claude Web context (no minijinja) and is asserted by the pickrem test.
  Pickweb must use the same pattern.
- The closure-rewrite walker already handles `task-workflow/` refs
  (proven by pickrem Test 4). Pickweb references
  `../task-workflow/agent-attribution.md`,
  `task-workflow/planning.md`, and
  `../task-workflow/code-agent-commit-attribution.md` — these will be
  rewritten automatically.
- Profile yaml: pickweb reuses the existing `remote.yaml`. No new yaml.
- Pickrem's vestigial `.opencode/skills/aitask-pickrem/SKILL.md` legacy
  pointer is present; pickweb must NOT inherit the same bug.

The plan's high-level scope is sound and current; minor additions below.

## Step Order

1. **Author `.claude/skills/aitask-pickweb/SKILL.md.j2`.** Copy the
   current `.claude/skills/aitask-pickweb/SKILL.md` and:
   - Change frontmatter `name:` to `aitask-pickweb-{{ profile.name }}`
     (mirrors pickrem template).
   - **Delete Step 0 (pre-parse `--profile` extraction)** — the stub
     handles profile resolution.
   - **Delete Step 1 "Load Execution Profile"** entirely (t777_26
     forbidden-token site — runtime profile resolution must not appear
     in the rendered body).
   - Wrap the `plan_preference` branch in Step 5.0 as a three-way Jinja
     `{% if profile.plan_preference == "verify" %} … {% elif
     profile.plan_preference == "create_new" %} … {% else %} … {% endif %}`
     using the same-line comment convention from
     `aidocs/skill_authoring_conventions.md`
     (`{# ---------- plan_preference ---------- #}`,
     `{# end plan_preference #}`).
   - Replace the Step 5 Checkpoint `post_plan_action` value-table with a
     single hardcoded "Profile: proceeding to implementation" line (web
     mode supports only the one value — no conditional needed).
   - Re-number sections to match pickrem's flow (Step 0a → 2 → 3 → 4 → 5
     → 6 → 7 → 8) for consistency, keeping pickweb's web-specific
     content intact (Steps 7–8 = Auto-Commit + Completion Marker).
   - Wrap any literal `{{` / `{%` in `{% raw %}{% endraw %}` (check the
     completion-marker JSON block in Step 8).

2. **Replace 4 agent stubs** per §3b / §3c / §3d, copying pickrem's
   stubs and substituting `pickrem` → `pickweb`,
   `aitask-pickrem` → `aitask-pickweb` throughout. All four use the
   resolver short name `pickweb` (not the full slug) and the
   conditional-Read "Render only if needed" pattern.

   | Agent | Path | Substitutions |
   |-------|------|---------------|
   | Claude | `.claude/skills/aitask-pickweb/SKILL.md` | `--agent claude` |
   | Codex | `.agents/skills/aitask-pickweb/SKILL.md` | `--agent codex` |
   | Gemini | `.gemini/commands/aitask-pickweb.toml` | `--agent gemini`, `{{args}}`, prereq `@`-includes |
   | OpenCode | `.opencode/commands/aitask-pickweb.md` | `--agent opencode`, `$ARGUMENTS`, prereq `@`-includes |

3. **Fix pickweb's OpenCode skill-registry leftover.** Replace
   `.opencode/skills/aitask-pickweb/SKILL.md` with the **same §3d-style
   stub body** as `.opencode/commands/aitask-pickweb.md` (frontmatter
   identical, same three steps, same dispatch target). Both surfaces
   now route through the proper render flow — the command file handles
   `/aitask-pickweb` slash invocations, and the skill file handles
   OpenCode's description-based auto-discovery (declared in
   `.opencode/instructions.md`). Rationale: the user picked "fix
   pickweb's own leftover only"; cleaner than the 7 already-templated
   skills which keep their broken pointers until the t777_29 follow-up.

4. **Pre-render remote variants for all 4 agents.** Run:
   ```bash
   for agent in claude codex gemini opencode; do
       ./.aitask-scripts/aitask_skill_render.sh aitask-pickweb \
           --profile remote --agent "$agent" --force
   done
   ```
   This produces `.<root>/aitask-pickweb-remote-/SKILL.md` for each
   agent and writes the per-agent task-workflow closure under the same
   per-profile sibling tree (closure-aware walker). These are committed
   to git so pickweb works without minijinja on Claude Web — same as
   pickrem-remote variants.

5. **Author golden + regression test.** Create
   `tests/test_skill_render_aitask_pickweb.sh` cloned from
   `tests/test_skill_render_aitask_pickrem.sh`:
   - Replace `aitask-pickrem` → `aitask-pickweb`, `pickrem` →
     `pickweb` everywhere (including the resolver-short-name
     assertion in Test 5).
   - Test 2 branch-firing assertions: replace pickrem-specific
     assertions (`force-unlocking stale lock`, `auto-archiving Done
     task`, `aitask_issue_update.sh --close`, `--status Ready`) with
     pickweb-specific ones — e.g., `plan_preference: use_current`
     branch fires (default), `.aitask-data-updated/` path in
     rendered body, absence of `aitask_pick_own.sh <task_num>
     --email` ownership claim, absence of `aitask_archive` invocations.
   - Test 5 conditional-Read marker: keep the `Render only if needed`
     assertion intact.
   - Create golden `tests/golden/skills/aitask-pickweb/SKILL-remote-claude.md`
     by capturing the freshly-rendered output (after the template lands
     and the renderer is run once).

6. **Final verification.**
   - `./.aitask-scripts/aitask_skill_verify.sh` → all templates pass
     (no forbidden tokens, all profiles render).
   - `bash tests/test_skill_render_aitask_pickweb.sh` → all assertions
     PASS.
   - `git ls-files | grep pickweb` shows the same 7-file layout pickrem
     has (1 template + 4 stubs + 4 remote variants + golden + test, with
     `.opencode/skills/aitask-pickweb/SKILL.md` re-added per Step 3).

7. **Author follow-up task t777_29** for the remaining cleanup:
   - Rewrite the 7 prior `.opencode/skills/<skill>/SKILL.md` legacy
     pointers (pick, pickrem, explore, review, fold, qa, pr-import,
     revert) to proper §3d-style stubs matching their command files.
   - Patch `aitask_audit_wrappers.sh::render_opencode_skill` (line 180)
     to detect templated skills (presence of `SKILL.md.j2` in
     `.claude/skills/<skill>/`) and emit a §3d-style stub for those
     skills instead of the legacy pointer. Optionally add a similar
     detection to `render_agents_skill` for symmetry, though Codex's
     `.agents/skills/<skill>/SKILL.md` IS the canonical §3b stub
     surface so the audit-wrappers default of "do not overwrite if
     present" already avoids regression there.
   - Add a regression assertion to a future test that no
     `.opencode/skills/aitask-<skill>/SKILL.md` for a templated skill
     contains the literal "Source of Truth" pointer phrase.

   Created via `aitask_create.sh --parent 777 --name fix_opencode_skill_legacy_pointers`
   with the full context inlined in the child task description per
   the parent-task documentation requirements.

## Critical Files

- New: `.claude/skills/aitask-pickweb/SKILL.md.j2`
- Replace: 5 stub files (4 canonical + 1 OpenCode-skill leftover):
  - `.claude/skills/aitask-pickweb/SKILL.md`
  - `.agents/skills/aitask-pickweb/SKILL.md`
  - `.gemini/commands/aitask-pickweb.toml`
  - `.opencode/commands/aitask-pickweb.md`
  - `.opencode/skills/aitask-pickweb/SKILL.md` (legacy-pointer fix)
- New (committed renders): `.<root>/aitask-pickweb-remote-/SKILL.md` for
  each of the 4 agents (plus their task-workflow-remote- closure
  re-renders, which already exist for pickrem and will not change for
  pickweb since the closure is shared)
- New: `tests/test_skill_render_aitask_pickweb.sh`
- New: `tests/golden/skills/aitask-pickweb/SKILL-remote-claude.md`
- New: `aitasks/t777/t777_29_fix_opencode_skill_legacy_pointers.md`
  (follow-up task description)

## Reference Files

- `.claude/skills/aitask-pickrem/SKILL.md.j2` — template pattern
- `.claude/skills/aitask-pickrem/SKILL.md` — Claude §3b stub
- `.agents/skills/aitask-pickrem/SKILL.md` — Codex §3b stub
- `.gemini/commands/aitask-pickrem.toml` — Gemini §3c stub
- `.opencode/commands/aitask-pickrem.md` — OpenCode §3d stub
- `tests/test_skill_render_aitask_pickrem.sh` — test scaffold
- `aidocs/stub-skill-pattern.md` — §3b/§3c/§3d/§3g spec
- `aidocs/skill_authoring_conventions.md` — Jinja comment conventions
- `.opencode/instructions.md` — declares `.opencode/skills/` as registry surface

## Verification

1. `bash tests/test_skill_render_aitask_pickweb.sh` → all PASS.
2. `./.aitask-scripts/aitask_skill_verify.sh` → no forbidden tokens.
3. Manual end-to-end dispatch check on each agent:
   - `cat .claude/skills/aitask-pickweb/SKILL.md` is the §3b stub, not
     full workflow.
   - `cat .opencode/commands/aitask-pickweb.md` and
     `cat .opencode/skills/aitask-pickweb/SKILL.md` are identical
     §3d-form stubs (verifying the leftover-fix).
   - Reading the rendered file at
     `.claude/skills/aitask-pickweb-remote-/SKILL.md` shows no `{% `
     or `{{` markers and no occurrences of `Use AskUserQuestion`.
4. `grep -L "Source of Truth" .opencode/skills/aitask-pickweb/SKILL.md`
   should print the filename (i.e., no legacy-pointer phrase present).
5. Confirm `aitasks/t777/t777_29_*.md` exists and is added to
   `children_to_implement` of `t777_modular_pick_skill.md`.

## Final Implementation Notes

- **Actual work done:** Authored `.claude/skills/aitask-pickweb/SKILL.md.j2`
  (357 lines) and the four canonical agent stubs plus the OpenCode
  skill-registry leftover fix (5 stubs total). Pre-rendered the `remote`
  profile for all 4 agents under `<root>/aitask-pickweb-remote-/`. Patched
  `.gitignore` to unblock the new pre-rendered dirs, registered `pickweb`
  in `aitask_skill_verify.sh::_resolver_key_for`, and authored a
  87-assertion regression test
  (`tests/test_skill_render_aitask_pickweb.sh`) cloned from the pickrem
  test with pickweb-specific Test 2 assertions (use_current branch,
  `.aitask-data-updated/` web layout, absence of ownership/archive/`./ait git`
  invocations) and a new Test 9 that asserts the OpenCode skill-registry
  leftover is gone (no legacy "Source of Truth" phrase). Committed golden
  file. All 87 tests pass; `./.aitask-scripts/aitask_skill_verify.sh`
  reports OK across 9 templates × 4 agents.

- **Deviations from plan:** None substantive. The only minor adjustment:
  Test 2 assertions for "no ownership / no archive / no ./ait git" had
  to be tightened to look for actual bash invocation patterns (e.g.
  `./.aitask-scripts/aitask_archive.sh`, `./ait git add`) rather than
  bare names, because pickweb's body legitimately documents those names
  in descriptive prose (e.g. "NO archival (`aitask_archive.sh`) —
  completion marker written instead"). The negative assertions now
  forbid the invocation pattern but allow the docstring mention.

- **Issues encountered:** Two related to leftover state:
  1. `aitask_skill_verify.sh::_resolver_key_for` switch-arm needed an
     explicit `aitask-pickweb)` entry; without it the global verifier
     fails with `STUB_FAIL: missing resolver call`. This is a known
     TODO(t777_29) hardcoded-mapping pattern — pickrem has the same
     workaround.
  2. `.gitignore`'s `*-/` ignore rule blocks committing
     `aitask-pickweb-remote-/SKILL.md` × 4. Added 4 exclamation-mark
     overrides next to the existing pickrem overrides (also flagged
     under the same TODO(t777_29) auto-generation comment).

- **Upstream defects identified:**
  - `.opencode/skills/<skill>/SKILL.md:1 — pre-templating-era "Source of Truth" pointer surface remains broken for 7 already-templated skills (pick, pickrem, explore, review, fold, qa, pr-import, revert). Pointer redirects to `.claude/skills/<skill>/SKILL.md` which is now the §3b Claude stub, so OpenCode auto-discovery routes through the wrong agent root. Captured as follow-up task t777_29.
  - `.aitask-scripts/aitask_audit_wrappers.sh:180 — `render_opencode_skill` still emits the legacy pointer; `/aitask-audit-wrappers --phase=skills` would re-create the broken pointer even after a manual fix. Captured as part of t777_29.

- **Key decisions:**
  - Replaced (rather than deleted) `.opencode/skills/aitask-pickweb/SKILL.md`
    with a §3d-style stub identical to `.opencode/commands/aitask-pickweb.md`
    so OpenCode's description-based skill auto-discovery (declared in
    `.opencode/instructions.md`) still works.
  - Deferred broader 7-skill cleanup to t777_29 per user scoping
    decision; this task fixes only its own surface.
  - Hardcoded `post_plan_action: start_implementation` (single line) in
    the rendered Step 5 Checkpoint instead of wrapping in a Jinja
    conditional, because pickweb's profile schema only recognizes one
    value for that key. Future profile values would need a conditional;
    none exist today.

- **Test results:** `bash tests/test_skill_render_aitask_pickweb.sh` →
  Tests: 87, Passed: 87, Failed: 0.
  `./.aitask-scripts/aitask_skill_verify.sh` → OK (9 templates × 4 agents).

- **Notes for sibling tasks:**
  - When porting any remaining "Pick"-family skill, expect the same
    `.opencode/skills/<slug>/SKILL.md` leftover pattern and the same
    `_resolver_key_for` and `.gitignore` patches. t777_29 will eliminate
    the per-skill `_resolver_key_for` hardcoding via a prerender marker
    — sibling tasks landing before t777_29 should still patch
    `_resolver_key_for` and `.gitignore` explicitly.
  - The `Render only if needed` (conditional-Read) stub pattern is now
    the established convention for headless skills that ship
    pre-rendered variants. Reuse pickrem/pickweb stub bodies verbatim
    with name substitutions.

