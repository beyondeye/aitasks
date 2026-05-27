---
Task: t777_18_docs_update_claudemd_and_website.md
Parent Task: aitasks/t777_modular_pick_skill.md
Archived Sibling Plans: aiplans/archived/p777/p777_10_convert_aitask_fold.md, aiplans/archived/p777/p777_11_convert_aitask_qa.md, aiplans/archived/p777/p777_12_convert_aitask_pr_import.md, aiplans/archived/p777/p777_13_convert_aitask_revert.md, aiplans/archived/p777/p777_14_convert_aitask_pickrem.md, aiplans/archived/p777/p777_15_convert_aitask_pickweb.md, aiplans/archived/p777/p777_16_extract_profile_editor_widget.md, aiplans/archived/p777/p777_17_per_run_profile_edit_in_agentcommandscreen.md, aiplans/archived/p777/p777_1_minijinja_dep_renderer_paths_resolver.md, aiplans/archived/p777/p777_20_profile_modification_invalidation.md, aiplans/archived/p777/p777_21_map_pick_reference_closure_and_profile_keys.md, aiplans/archived/p777/p777_22_extend_renderer_for_uniform_recursive_rendering.md, aiplans/archived/p777/p777_23_swap_task_workflown_to_task_workflow.md, aiplans/archived/p777/p777_25_refactor_stubs_direct_helper_paths.md, aiplans/archived/p777/p777_26_template_completeness_and_resolver_key.md, aiplans/archived/p777/p777_27_recover_runtime_skills_and_parity_tests.md, aiplans/archived/p777/p777_28_dedup_template_branches_common_proc_and_macros.md, aiplans/archived/p777/p777_29_fix_opencode_skill_legacy_pointers.md, aiplans/archived/p777/p777_2_aitask_skill_render_subcommand.md, aiplans/archived/p777/p777_3_stub_skill_design_and_gitignore.md, aiplans/archived/p777/p777_4_aitask_skill_verify_and_precommit.md, aiplans/archived/p777/p777_5_aitask_skillrun_wrapper_dispatcher.md, aiplans/archived/p777/p777_6_convert_aitask_pick_template_and_stubs.md, aiplans/archived/p777/p777_7_convert_task_workflow_shared_procs.md, aiplans/archived/p777/p777_8_convert_aitask_explore.md, aiplans/archived/p777/p777_9_convert_aitask_review.md
Base branch: main
plan_verified:
  - claudecode/opus4_7_1m @ 2026-05-27 10:41
---

# Plan: t777_18 — Documentation update (verified, refined after sibling/cross-task scan)

## Context

Add user-facing and authoring documentation for the templated-skill mechanism shipped by t777_1..15 and refined by t803, t834, t777_16/17/22/23/25/27/28/29.

The task description (written before later siblings landed) flagged itself as outdated. Verification against the current state of the framework, plus a scan of completed siblings t777_1..t777_29 and the two cross-cutting siblings t803 (agent-gate Jinja) and t834 (shared-root agent suffix), produced these refinements:

1. **Location.** Original plan said `website/content/docs/workflows/skill-templating.md`. The website has since grown a `concepts/` section that hosts the companion page `concepts/execution-profiles.md`. Skill templating is a conceptual mechanism (not a step-by-step workflow), so the natural home is **`website/content/docs/concepts/skill-templating.md`**. We will also cross-link from `concepts/execution-profiles.md` and `skills/aitask-pick/execution-profiles.md`.

2. **CLAUDE.md anchor.** The original plan referenced an "Adding a New Helper Script" section that has since been promoted to `aidocs/aitasks_extension_points.md` (pointer style). The new subsection lives at the end of "Working on Skills / Custom Commands", following CLAUDE.md's current thin-pointer style.

3. **Shared-root agent suffix (t834).** Per-agent stub-surface table must reflect that **codex** rendered variants live at `.agents/skills/<skill>-<profile>-codex-/SKILL.md`, not `<skill>-<profile>-/SKILL.md`. The trailing hyphen is preserved so the `*-/` gitignore glob still works. Claude / Gemini / OpenCode are unchanged. Future agent `agy` (t814) will append a parallel `-agy-` segment in the same shared root. The shared-root predicate is declared in `agent_skills_paths.sh::agent_shared_skills_root` (Python mirror: `AGENT_SHARED_SKILLS_ROOT`).

4. **Agent-gate Jinja pattern (t803).** Document the `{% if agent == "claude" %}` gate (introduced by t803 in `aitask-wrap`) alongside the existing `{% if profile.X %}` pattern. Reference the audit doc `aidocs/agent_runtime_guards_audit.md` for the inventory of remaining runtime guards that may move to Jinja gates later.

5. **Per-run profile editor (t777_17).** The `AgentCommandScreen` launch dialog gained a Profile row with `(E)dit`, opening a reusable `ProfileEditScreen`. Two save modes:
   - **Save persistently** → `aitasks/metadata/profiles/local/<name>.yaml` (user-layer override, gitignored, shadows the same-name project profile).
   - **Save as one-shot** → `aitasks/metadata/profiles/local/_skillrun_<unique>.yaml`; the launch command is rewritten to `--profile _skillrun_<unique>`. Mirrors what `ait skillrun --profile-override` does from the shell.

6. **Reference-rewriting model (t777_22).** Briefly mention the three reference shapes (full path / sibling / skill-relative) and how the dep-walker rewrites them into the per-(profile, agent) rendered tree. Skill authors care.

7. **README.md.** No formal CLI command listing exists — there is no clean place for an `ait skillrun` mention. Skip.

## Critical files

- `CLAUDE.md` (modify) — extend the "Working on Skills / Custom Commands" section with a "Skill templating and per-profile dispatch" subsection (≤40 lines).
- `website/content/docs/concepts/skill-templating.md` (new) — user-facing intro + mechanism walk-through.
- `website/content/docs/concepts/_index.md` (touch if it lists concepts manually) — add a link to the new page.
- `website/content/docs/concepts/execution-profiles.md` (touch) — add a one-line cross-link to the new page in "See also".

## Step 1 — CLAUDE.md

Insert a new subsection at the **end of "Working on Skills / Custom Commands"** (after the two read-on-demand `aidocs/` pointers, before `## TUI Development`). Concise (≤40 lines) — pointer-style consistent with the rest of CLAUDE.md.

Cover:

- Profile-aware skills are authored as `.claude/skills/<skill>/SKILL.md.j2` (Claude is the single source of truth). Each agent has a thin profile-agnostic stub at its discovery surface (per-agent surface table below). The stub resolves the active profile (default OR `--profile <name>` override on ARGUMENTS), calls `./.aitask-scripts/aitask_skill_render.sh`, then Read-and-follows the rendered variant.
- Rendered variants land in trailing-hyphen directories. **Non-shared roots** (claude, gemini, opencode): `<root>/<skill>-<profile>-/`. **Shared roots** (currently `.agents/skills/` for codex; +agy in t814): `<root>/<skill>-<profile>-<agent>-/`. The trailing hyphen is load-bearing for the single `*-/` gitignore glob per agent root. Authoring dir names MUST NOT end with `-`.
- Compact per-agent surface table (4 rows, mirrors `aidocs/stub-skill-pattern.md` §3g). Codex row's "Rendered variant location" cell explicitly shows the `-codex-` segment.
- Two invocation paths user-side:
  - From inside an agent session: `/aitask-pick --profile fast 42`.
  - From the shell: `ait skillrun pick --profile fast 42` (the framework launches the agent with the slash command pre-loaded; honors `--profile-override <file|->` for ad-hoc YAML merges).
- Two Jinja conditional patterns:
  - `{% if profile.<key> %}` — branch on profile keys (e.g. `default_email`, `create_worktree`, `post_plan_action`).
  - `{% if agent == "<name>" %}` — gate per-agent content (t803 pattern, currently only `aitask-wrap` Step 1b).
- Use `{% raw %} ... {% endraw %}` for literal `{{` / `{%` that should not be evaluated.
- Render-correctness contract: `./.aitask-scripts/aitask_skill_verify.sh` is already mentioned earlier in the section. **Same-commit rule**: regenerate goldens under `tests/golden/skills/<skill>/` and `tests/golden/procs/<scope>/` in the same commit as any `.md.j2` or closure-`.md` edit.
- Cross-references:
  - `aidocs/stub-skill-pattern.md` — canonical stub bodies (§3b/§3c/§3d), per-agent surfaces (§3g), argument-forwarding contract (§3h), reference resolution (§3i), template-completeness rules (§3j).
  - `aidocs/skill_authoring_conventions.md` — Jinja conventions (comments, macros, `{% from %}`, whitespace control, minijinja caveats), golden regeneration, NON-SKIPPABLE banner rule.
  - `aidocs/agent_runtime_guards_audit.md` — inventory of remaining "If running in Claude Code" guards eligible to move to `{% if agent %}` gates.

The two existing reads-on-demand pointers (`aidocs/skill_authoring_conventions.md`, `aidocs/stub-skill-pattern.md`) already cover the trigger conditions ("when editing anything under `.claude/skills/...`"). The new subsection states the mechanism positively so a CLAUDE.md reader alone understands the architecture and can decide which aidoc to pull next.

## Step 2 — website/content/docs/concepts/skill-templating.md (new)

User-facing, current-state-only (no "previously" wording). Frontmatter follows the concept page convention:

```yaml
---
title: "Skill templating and per-profile dispatch"
linkTitle: "Skill templating"
weight: 70
description: "How profile-aware skills materialize per-(skill, profile, agent) variants on demand via templated dispatch."
depth: [intermediate]
---
```

Sections:

1. **Overview** — Why skill bodies vary per profile cannot live in a single `SKILL.md`: SKILL.md is re-read by the agent mid-session and mutating it produces torn reads. The solution: a thin stub resolves the active profile, renders a per-(skill, profile, agent) variant on demand, and Reads-and-follows the rendered file.

2. **Invocation paths**
   - **From inside an agent session:** `/aitask-pick --profile fast 42` — the stub strips `--profile fast` from `ARGUMENTS` (Claude / Codex) / `{{args}}` (Gemini) / `$ARGUMENTS` (OpenCode) before dispatch.
   - **From the shell:** `ait skillrun pick --profile fast 42`. Launches the resolved code agent (default from `$AIT_AGENT_STRING` / `$DEFAULT_AGENT_STRING`, override with `--agent-string <agent>/<model>`) with the slash command pre-loaded. Supports `--profile-override <yaml|->` to merge an ad-hoc YAML on top of the resolved profile (one-shot, gitignored under `aitasks/metadata/profiles/local/_skillrun_<unique>.yaml`, auto-deleted on exit). `--dry-run` previews the launch command.
   - **From the launch dialog (TUI):** In `ait board` or `ait codeagent`, the `AgentCommandScreen` has a **Profile** row with `(E)dit`. The editor offers two saves:
     - **Save persistently** → `aitasks/metadata/profiles/local/<name>.yaml` (user override, gitignored, shadows the project YAML).
     - **Save as one-shot** → `aitasks/metadata/profiles/local/_skillrun_<unique>.yaml` and rewrites the launch command to `--profile _skillrun_<unique>`. Same mechanism as `ait skillrun --profile-override`.

3. **Resolution order** — `--profile` argument > `userconfig.yaml` `default_profiles.<key>` > `project_config.yaml` `default_profiles.<key>` > interactive selection. Cross-link to the [`/aitask-pick` execution-profiles page]({{< relref "/docs/skills/aitask-pick/execution-profiles" >}}) for the full table and key reference.

4. **How dispatch works** — Plain-language walk-through:
   - User types `/aitask-pick`.
   - Claude reads `.claude/skills/aitask-pick/SKILL.md` (the stub — committed, profile-agnostic).
   - Stub runs `./.aitask-scripts/aitask_skill_resolve_profile.sh pick` (or honors `--profile <name>`).
   - Stub runs `./.aitask-scripts/aitask_skill_render.sh aitask-pick --profile <p> --agent claude` — no-op if the rendered variant is fresh.
   - Stub Reads `.claude/skills/aitask-pick-<p>-/SKILL.md` and follows it.

5. **Per-agent surfaces** — Compact table mirroring `aidocs/stub-skill-pattern.md` §3g. Codex row shows the `-codex-` segment; explanation that this is gated by `agent_shared_skills_root codex == true` and applies whenever an agent shares a physical root with another (today: codex; soon: agy under `.agents/skills/`).

   | Agent | Stub location | Rendered variant location |
   |-------|---------------|---------------------------|
   | Claude | `.claude/skills/<skill>/SKILL.md` | `.claude/skills/<skill>-<profile>-/SKILL.md` |
   | Codex | `.agents/skills/<skill>/SKILL.md` | `.agents/skills/<skill>-<profile>-codex-/SKILL.md` |
   | Gemini | `.gemini/commands/<skill>.toml` (`prompt` field) | `.gemini/skills/<skill>-<profile>-/SKILL.md` |
   | OpenCode | `.opencode/commands/<skill>.md` | `.opencode/skills/<skill>-<profile>-/SKILL.md` |

6. **Rendered dirs and `.gitignore`** — Explain the trailing-hyphen marker is encoded in the dir name so each agent root has a single `*-/` gitignore glob. Authoring dirs MUST NOT end with `-`. Rendered files are autogenerated; never edit them by hand.

7. **Authoring (short pointer)** — One paragraph: skill authors write `.claude/skills/<skill>/SKILL.md.j2` (Claude is source of truth) plus profile-agnostic stubs at each agent surface (canonical bodies in `aidocs/stub-skill-pattern.md`). Two conditional patterns: `{% if profile.X %}` for profile branches, `{% if agent == "Y" %}` for agent gates. Run `./.aitask-scripts/aitask_skill_verify.sh` before committing. Goldens regenerated in the same commit. Link to the two `aidocs/` references (use absolute github links so users without a checkout can read them).

8. **See also**
   - [Execution Profiles]({{< relref "/docs/concepts/execution-profiles" >}})
   - [`/aitask-pick` Execution Profiles reference]({{< relref "/docs/skills/aitask-pick/execution-profiles" >}})
   - [`/aitask-pick` skill]({{< relref "/docs/skills/aitask-pick" >}})
   - Authoring references in-repo: `aidocs/stub-skill-pattern.md`, `aidocs/skill_authoring_conventions.md`, `aidocs/agent_runtime_guards_audit.md` (linked to github source).

## Step 3 — concepts/execution-profiles.md cross-link

Add a single bullet at the end of the existing "See also" section linking to the new `skill-templating` page (kept terse — the new page links back).

## Step 4 — concepts/_index.md

If the file lists pages manually, add a row for the new skill-templating page. (Read the file first to confirm structure.)

## Step 5 — README.md

Skip per the verification finding above (no CLI listing where `ait skillrun` would land cleanly).

## Verification

1. `./.aitask-scripts/aitask_skill_verify.sh` exits clean (sanity — no `.j2` or stub edits in this task).
2. `cd website && hugo build --gc --minify` builds without errors; every `{{< relref ... >}}` in the new page resolves (Hugo reports broken refs as build errors).
3. `markdownlint` (if configured) clean on CLAUDE.md and the new doc.
4. Grep for "previously"/"used to be"/"this corrects" in the new doc and CLAUDE.md additions — zero hits.
5. Fresh-context reader test: open CLAUDE.md alone and answer:
   - What is a `.md.j2` template?
   - Where do rendered variants live (claude vs codex)?
   - What does the stub do at invocation time?
   - When do you use `{% if profile %}` vs `{% if agent %}`?
6. Same exercise on the new website page: invocation paths, dispatch flow, per-agent surface, TUI per-run override.

## Step 9 reference

After implementation: review (Step 8), commit code and plan separately (per CLAUDE.md "Git Operations on Task/Plan Files"), and proceed through Step 8/8b/8c/9 of task-workflow as normal. Docs-only — no Codex/Gemini/OpenCode skill porting needed (per the "Working on Skills / Custom Commands" rule, doc changes do not have parallel skill files to update).
