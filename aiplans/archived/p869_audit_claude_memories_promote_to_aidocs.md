---
Task: t869_audit_claude_memories_promote_to_aidocs.md
Worktree: (none — profile 'fast', current branch)
Branch: main
Base branch: main
---

# Plan: Audit Claude Code memories → promote conventions to aidocs, delete redundant

## Context

The Claude Code memory store for this project
(`~/.claude/projects/-home-ddt-Work-aitasks/memory/`) has accumulated 26 content
memories. Many encode durable engineering conventions that are better hosted in
`aidocs/` — the on-demand authoring-reference docs CLAUDE.md points to during the
relevant flow — where they are discoverable by *any* future session/agent, not
just one whose memory recall happens to surface them. An audit (two verification
sub-agents) found **no obsolete memories** (every fact still maps to live code),
so this is **promotion + redundancy cleanup**, not obsolescence deletion.

Decisions locked with the user:
- **Disposition:** once a memory's substance lives in an aidoc, **delete** the
  memory file and remove its `MEMORY.md` index line (aidocs become the sole
  source of truth). Stay-as-memory items (below) are left untouched.
- **Wiring:** add a CLAUDE.md pointer for the new `documentation_conventions.md`;
  fix residual "sister"→"cross-repo" in `cross_repo_references.md`; augment the 3
  mostly-covered aidoc sections with each memory's extra nuance.

**Core method (applies to every memory below): verify-before-act.** The
verification sub-agent sometimes marked a memory "covered" because the *codebase
follows* the pattern, not because an *aidoc documents* it. So for each memory,
**first read the target aidoc section** and confirm the *rule* is actually
written there. If documented → just delete the memory. If the aidoc lacks the
rule → add a short section/sentence (in that doc's voice and density), verify any
file/function references still exist, then delete the memory.

## Files touched

Aidocs (extend or create), all in `aidocs/`:
`skill_authoring_conventions.md`, `tui_conventions.md`,
`aitasks_extension_points.md`, `testing_conventions.md`,
`planning_conventions.md`, `model_reference_locations.md`,
`monitor_idle_and_prompt_detection.md`, `cross_repo_references.md`,
**new** `documentation_conventions.md`.
Plus `CLAUDE.md` (one pointer), `MEMORY.md` (index trims), and deletion of the
processed memory `.md` files.

## Part A — Genuine gaps confirmed (add aidoc content, then delete memory)

For each: add the named section/sentence, then `rm` the memory file + drop its
MEMORY.md line.

1. **feedback_golden_file_tests_for_template_engines** → `testing_conventions.md`,
   NEW section "Golden-file regression tests for template-engine output". Capture:
   for any code path that renders via an external template engine (minijinja,
   jinja2, …), commit golden outputs per (input × params) and diff every run —
   "renders without error" / `ait skill verify` only catches hard failures, not
   silent whitespace/filter/escape drift across engine versions. (Confirmed gap:
   the doc currently has only the threading/asyncio section.)

2. **feedback_generic_agent_enumerations_in_docs** → **new**
   `aidocs/documentation_conventions.md`. Capture: in user-facing docs prefer
   "Claude Code and all other supported coding agents" over fixed
   `(Claude Code, Codex, Gemini, OpenCode)` enumerations; keep literal lists only
   where normative (model-self-detection, CLI mapping tables, per-agent install
   sections). Rationale: every fixed enumeration is a future-churn site.

3. **feedback_autonomous_not_auto_execution_in_docs** → same new
   `documentation_conventions.md` (a second doc-language convention). Capture: in
   manual-verification auto-mode prose, avoid "auto-execution"; say "autonomous"
   and frame as a human checklist optionally run fully/partially by an AI agent.
   Keep literal `auto` / `autonomous_with_plan` tokens verbatim.

4. **feedback_drop_legacy_no_profile_fallback** → `skill_authoring_conventions.md`,
   augment §"Profile-aware skills require a stub + `.md.j2` pair" with an explicit
   rule: the renderer always binds a non-empty profile
   (`skill_template.py::render_skill` — verify signature still requires `profile`),
   so delete legacy no-profile branches outright; do NOT wrap them in
   `{% if not profile %}…{% endif %}`.

5. **feedback_port_skill_wording_check_stub_vs_full** →
   `skill_authoring_conventions.md`, NEW short subsection "Before porting skill
   wording: stub vs. full copy". Capture: plain non-templated skills keep one
   canonical body in `.claude/skills/<skill>/SKILL.md`; the Codex/OpenCode
   surfaces are thin delegating stubs, so "port wording to other agents" spawns
   are no-ops there — verify stub-vs-full before editing.

## Part B — Verify-then-act (likely gaps; heading scan shows no matching section)

Read the target aidoc section; promote if the rule isn't documented, then delete
the memory (delete-without-promote only if already documented).

6. **feedback_tui_switcher_registration** → `tui_conventions.md`. Likely gap.
   Verify against `.aitask-scripts/lib/tui_registry.py` (`TUI_REGISTRY`) and
   `tui_switcher.py` (`_TUI_SHORTCUTS`, `BINDINGS`, `action_shortcut_*`) using
   `applink` as the worked example. Document the registration *quadruple*:
   registry position + single-letter shortcut + `Binding` row + `action_*` method.
7. **feedback_modal_self_contained_css** → `tui_conventions.md`. Likely gap.
   Verify a `lib/` modal carries class-level `DEFAULT_CSS`
   (e.g. `profile_editor.py`). Document: multi-App-pushed ModalScreens must carry
   their own DEFAULT_CSS; they don't inherit the pushing App's CSS.
8. **feedback_ait_subcommands_user_facing_only** → `aitasks_extension_points.md`.
   Likely gap. Document: the `ait` dispatcher is user-facing only; plumbing helpers
   stay invoked via `./.aitask-scripts/<name>.sh` and get no `ait <foo>` case.
9. **feedback_no_task_creation_in_plan_mode** → `planning_conventions.md`. Likely
   gap (embodied in task-workflow/SKILL.md comments, not the aidoc). Document:
   planning-phase procedures are read-only; split design (record decomposition +
   return a flag) from post-approval creation (Step 7).
10. **feedback_claude_code_1m_model_id** → `model_reference_locations.md`. Verify
    `aitasks/metadata/models_claudecode.json` still has both `claude-opus-4-7` and
    `claude-opus-4-7[1m]` entries; document: pass the `[1m]`-suffixed cli_id
    verbatim to the resolver (stripping it mis-resolves).
11. **feedback_authoring_docs_in_aidocs**, **feedback_whitelist_only_for_skill_invoked_helpers**,
    **feedback_framework_constants_in_source_not_yaml** → `aitasks_extension_points.md`.
    Verify each rule is actually written there; if any is only implicit, add a
    one/two-sentence note; then delete.
12. **feedback_monitor_idle_vs_prompt_states** → `monitor_idle_and_prompt_detection.md`.
    Verify the idle-vs-awaiting-input distinction (positive prompt-pattern layer)
    is documented; promote-if-gap, then delete.

## Part C — Augment the 3 mostly-covered sections (then delete memory)

13. **feedback_stage_under_parallel_name** → add to `skill_authoring_conventions.md`
    §"SKILL.md files are re-read during execution …": for *manual* refactors of an
    in-use skill/script, stage the new impl under a parallel name (convention:
    append `n`, e.g. `aitask-pickn`), verify fully, then atomic-rename in one
    final commit.
14. **feedback_modal_keys_vs_app_priority_bindings** → add to `tui_conventions.md`
    §"Priority bindings + `App.query_one` gotcha": App `priority=True` bindings fire
    before a modal's `priority=True` bindings; when the App handler must detect
    "am I over a modal", duck-type across class boundaries (`hasattr` for
    `cycle_prev`/`cycle_next`) rather than `isinstance`.
15. **feedback_profile_variants_autogenerated** → add to
    `skill_authoring_conventions.md` §"Use recognizable name-suffix conventions …":
    note the **install/distribution** glob narrows to `aitask-*/` (variant `*-/`
    dirs are excluded from install distribution even when git-tracked) — distinct
    from the gitignore `*-/` glob already documented. Verify against
    `tests/test_opencode_setup.sh` (`aitask-*/`).

## Part D — Cross-repo terminology fix (then delete memory)

16. **feedback_cross_repo_terminology** → normalize residual "sister" →
    "cross-repo" in `cross_repo_references.md` (e.g. the "sister project's task ID"
    phrasing). The convention itself is already used; this is a cleanup pass.

## Part E — Redundant, delete-only (verify covered first)

17. **feedback_expand_jinja_in_skills** — confirmed FULLY-COVERED by
    `skill_authoring_conventions.md` §"Jinja templating in skills" (Macros +
    "When to use what" table + dep-walker note). Delete memory + MEMORY.md line.
18. **project_t832_cross_repo_planning_architecture** (reclassified by user) —
    an implementation summary of completed t832_5, already embodied in the code
    and the procedure files it describes (`planning-cross-repo.md`,
    `cross-repo-child-assignment.md`) and partly in `planning_conventions.md`.
    Delete-as-redundant: no aidoc edit, just `rm` + MEMORY.md line.

## Part G — Reclassified from stay → promote (user-approved)

For each: add the named content (verify-then-act), then delete the memory + line.

19. **feedback_plan_explicit_docs_and_mirror_exportimport** →
    `planning_conventions.md`, NEW section. Capture: a plan for a user-facing
    feature must include a dedicated docs child task (under
    `website/content/docs/…`), and any export/import surface must reuse
    `export_all_configs` / `import_all_configs` rather than a parallel flow.
20. **feedback_filter_keeps_selected_visible** → `tui_conventions.md`, short
    section/one-liner: a search/fuzzy filter over a multi-select list must keep
    already-checked items visible even when they don't match the query (don't let
    filtering hide selected state).
21. **feedback_shared_skill_path_extend_suffix** → `skill_authoring_conventions.md`
    (verify-then-act — partially overlaps §"Use recognizable name-suffix
    conventions" and CLAUDE.md's shared-roots note). Capture the stable principle:
    when two code agents target the same physical skills root (shared root, e.g.
    `.agents/skills/` for codex +future `agy`), disambiguate by extending the
    rendered-variant filename with an `-<agent>-` segment — do NOT collapse to
    runtime `{% if agent %}` checks inside a shared skill body. Cross-ref the
    `agent_skill_root` / `agent_shared_skills_root` predicates in
    `.aitask-scripts/lib/agent_skills_paths.sh`.

## Part F — Wiring

- Add a CLAUDE.md pointer for the new doc under the **Documentation Writing**
  section, matching the existing `> **Read aidocs/… .md** when …` style, e.g.:
  "> Read `aidocs/documentation_conventions.md` when writing user-facing doc prose
  that enumerates supported agents or describes manual-verification auto mode."
- `testing_conventions.md`, `planning_conventions.md`, `code_conventions.md`,
  `aitasks_extension_points.md`, etc. are already pointed to from CLAUDE.md — no
  new pointer needed for extensions to existing docs.

## Part H — Enforce-in-source, then delete (user-directed)

22. **feedback_system_injected_directives_scope** — the user does NOT want correct
    checkpoint behavior propped up by an implicit memory; the **skill source** must
    enforce it. Approach (audit-and-fix, bounded):
    1. Audit NON-SKIPPABLE coverage in the source of truth
       `.claude/skills/task-workflow/SKILL.md.j2` for the checkpoints the memory
       enumerates: **Step 8** (review-before-commit) and **Step 9** (merge approval)
       — these already carry "⚠️ NON-SKIPPABLE" blocks in the rendered variants;
       confirm the same in the `.md.j2`. **Steps 8b / 8c / 9b** (upstream-defect
       follow-up, manual-verification follow-up, satisfaction feedback).
    2. Distinguish *load-bearing gates* (8, 9 — they gate irreversible actions:
       commit, merge) from *soft procedure-steps* (8b/8c offers, 9b feedback). The
       two gates are the ones that genuinely must not be skipped, and are already
       protected. For 8b/8c/9b, confirm they remain explicit sequential steps the
       agent executes by reading SKILL.md.
    3. **If a load-bearing gate is found under-protected**, strengthen its
       NON-SKIPPABLE wording in `SKILL.md.j2`, then regenerate the affected
       per-profile goldens under `tests/golden/skills/task-workflow/` (and procs)
       and run `./.aitask-scripts/aitask_skill_verify.sh` per CLAUDE.md. If the
       needed change is structural (larger than wording), surface it as a separate
       follow-up task rather than expanding this one.
    4. Delete the memory + MEMORY.md line.
    5. **Save a new `feedback` memory** capturing the user's principle: prefer
       explicit skill-source enforcement (NON-SKIPPABLE markers / numbered steps)
       over implicit memories for correct workflow behavior — when tempted to keep a
       behavior-enforcing memory, fix the skill instead. (Net memory count still
       drops; this records *how to work*, not *what the skill does*.)

## Stay-as-memory (DO NOT touch)

feedback_geminicli_to_agy_migrate_dont_close (transient t812→t835 lifecycle
guidance), project_agy_cli_no_model_flag (external-tool fact / t835 reference),
project_concurrent_aitask_data_branch (operational caveat),
user_machine_omarchy_g16, project_g16_line_out_override (personal/hardware).

## Out of scope (note in plan's Final Implementation Notes; suggest follow-ups)

- AGENTS.md test coverage gap: `tests/test_agent_instructions.sh` (16 tests) has
  no AGENTS.md create-if-missing / marker-idempotency case. (Side-finding from the
  original exploration; `ait setup` itself is correct — `update_agentsmd` runs
  unconditionally and `insert_aitasks_instructions` creates the file when absent.)
  → suggested separate `test`-type task.

## Verification

- `MEMORY.md` index has exactly one line per *remaining* memory file; no orphaned
  lines for deleted memories, no remaining lines for promoted ones. Cross-check:
  `ls memory/*.md` (minus MEMORY.md) vs the bullet list in MEMORY.md.
- Each new/edited aidoc section reads in the host doc's voice; every file/function
  reference cited (render_skill, TUI_REGISTRY/_TUI_SHORTCUTS, models_claudecode.json,
  profile_editor DEFAULT_CSS, test_opencode_setup.sh glob) verified present.
- New `aidocs/documentation_conventions.md` exists and is referenced from CLAUDE.md.
- `grep -ri "sister" aidocs/cross_repo_references.md` → no stray "sister <entity>".
- No code/runtime behavior changes; docs + memory-store maintenance only. (No
  build/test command applies; this task edits markdown only.)
- Step 9 (Post-Implementation): commit on current branch (profile 'fast'), then
  archive t869 via `aitask_archive.sh 869`. Memory files live outside the repo —
  their deletion is not part of any git commit.

## Final Implementation Notes

- **Actual work done:** Added/extended aidoc conventions across 7 existing files
  + 1 new file, plus 2 CLAUDE.md edits, then deleted 24 now-redundant memories,
  kept 5, added 1 new feedback memory, and rewrote `MEMORY.md`.
  - `skill_authoring_conventions.md`: manual-refactor parallel-name staging;
    install-distribution `aitask-*/` glob; drop-no-profile-fallback; stub-vs-full
    before porting wording; authoring-docs-live-in-aidocs.
  - `tui_conventions.md`: switcher-registration quadruple; modal self-contained
    DEFAULT_CSS; multi-select filter visibility; modal-vs-App priority-binding
    augmentation (check_action + duck-typing).
  - `aitasks_extension_points.md`: dispatcher-user-facing-only; constants-in-
    source-not-yaml; whitelist-only-for-skill-invoked-helpers clarification.
  - `planning_conventions.md`: planning-is-read-only/split-design-from-creation;
    user-facing-feature docs-child + reuse export/import.
  - `testing_conventions.md`: golden-file template-engine tests (intro de-scoped).
  - `model_reference_locations.md` + CLAUDE.md Model Attribution: 1M `[1m]`
    verbatim cli_id rule.
  - `cross_repo_references.md`: "sister" → "cross-repo".
  - new `documentation_conventions.md`: autonomous-not-auto-execution + a
    cross-ref to the genericization rule; CLAUDE.md Documentation-Writing pointer.
- **Deviations from plan (all driven by verify-before-act discovering existing
  coverage):**
  1. `feedback_shared_skill_path_extend_suffix` was planned as a promotion to
     `skill_authoring_conventions.md`, but `aidocs/adding_a_new_codeagent.md`
     §1a/1b/1d already documents the `<skill>-<profile>-<agent>-/` naming AND a
     callout that cites the memory by name ("Don't substitute runtime checks for
     prerendering"). → delete-only, no edit.
  2. `feedback_generic_agent_enumerations_in_docs` was planned as primary content
     for the new doc, but `adding_a_new_codeagent.md` §23b already documents the
     full genericization rule (preferred phrasing + literal-exception list). →
     `documentation_conventions.md` now cross-references §23b instead of
     duplicating it, and carries the autonomous-terminology rule as its primary
     new content.
  3. `feedback_authoring_docs_in_aidocs` landed in `skill_authoring_conventions.md`
     (closure/dep-walker hygiene) rather than `aitasks_extension_points.md` — a
     better home for that rationale.
  4. `feedback_claude_code_1m_model_id` was additionally placed in CLAUDE.md's
     Model Attribution section (always-loaded → load-bearing at detection time
     without a skill-closure goldens regen), not only `model_reference_locations.md`.
- **Part H (system_injected_directives_scope):** audited the task-workflow source
  (`.claude/skills/task-workflow/SKILL.md`). Steps 8 (commit review) and 9 (merge
  approval) — the load-bearing gates over irreversible actions — already carry
  `⚠️ NON-SKIPPABLE` banners (`:296`, `:429`), so deleting the memory does not
  remove the safety net. Steps 8b/8c/9b lack banners; the follow-up the memory
  cited (t782) no longer exists anywhere. Re-filed as a focused follow-up task
  (kept out of this docs task because it is a profile-aware closure edit + full
  task-workflow goldens regen). Saved a new `feedback` memory recording the
  user's principle: prefer explicit skill-source enforcement over implicit
  behavior-memories.
- **Issues encountered:** A concurrent session's uncommitted customizable-shortcuts
  work (`settings_app.py` +340, `config_utils.py`, `keybinding_registry.py`,
  `shortcut_scopes.py`, three `tests/*.py`) was present in the working tree
  (t848_5 `Implementing`). Staged only my own 9 docs files explicitly; left all
  concurrent changes and pre-existing untracked files untouched.
- **Upstream defects identified:** None.
