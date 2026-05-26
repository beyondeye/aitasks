---
Task: t812_remove_gemini_support.md
Base branch: main
plan_verified: []
---

# Plan: Remove geminicli support — t812 (with sibling tasks t813, t814)

## Context

Google is sunsetting the Gemini CLI (`geminicli`) and replacing it with the
Antigravity CLI (`agy`), a different product integrated with Antigravity 2.0.
Per `aidocs/geminicli_to_agy.md`:
- agy disables local `.gemini/settings.json` policy overrides (whitelists live
  in `~/.gemini/policies/` globally).
- agy uses a native Terminal Sandbox (nsjail on Linux) rather than approving
  host-side commands via TOML rules.
- agy replaces `.gemini/commands/*.toml` slash commands with **Agent Skills**
  in `.agents/skills/<name>/SKILL.md` — the **same physical path used by
  Codex CLI**.

That shared-path collision matters: the aitasks framework currently renders
**per-agent Jinja skill variants** to per-agent directories. Two agents
targeting the same physical path cannot each receive a fully agent-specific
rendering at that path without filename disambiguation.

### Decisions reached in planning conversation

1. **No runtime-check revert.** The current Jinja-rendered per-agent variant
   model stays. For agents that share a physical skills directory, the
   existing execution-profile filename-suffix mechanism will be extended to
   carry an agent suffix as well.
2. **agy support is in scope overall — but split off into a separate sibling
   task** (not a child of t812).
3. **Three sibling top-level tasks** total: t812 (this), t813, t814.
4. **Historical docs:** keep prior CHANGELOG entries and the v0.9.0 blog
   intact (dated record). Each new task adds its own CHANGELOG entry.
5. **Pending gemini-related aitasks** (t343, t344, t345, t401_3): handled by
   a dedicated child of t812.

### Sibling task overview

| Conceptual ID | Actual ID | Scope |
|---------------|-----------|-------|
| **t812** *(this plan)* | t812 | Remove all geminicli support from the framework. |
| **t813** *(new sibling)* | **t834** | Extend execution-profile skill rendering to support an **agent-type suffix** in rendered filenames when multiple agents share a physical skills directory (e.g., `.agents/skills/aitask-pick-fast-codex-/SKILL.md` vs `aitask-pick-fast-agy-/SKILL.md`). Prerequisite for adding agy. |
| **t814** *(new sibling)* | **t835** | Add `agy` (Antigravity CLI) as a first-class supported code agent (depends on t834 for the rendering enhancement). |

Throughout this plan and the child plans, the conceptual names "t813" and
"t814" are used. The actual IDs assigned at creation time are **t834** and
**t835** — match by content, not by literal ID.

t834 and t835 have been created with `aitask_create.sh --batch` (no
`--parent`) alongside this plan's commit.

---

## t812 scope: remove all geminicli support

t812 itself is too large to implement in one pass (touches ~30+ files across
multiple verticals). Split into **5 child tasks**:

### t812_1 — Remove code-agent infrastructure (registry, detection, models, stats)

Strip `geminicli` from the agent-identity layer:

- `.aitask-scripts/lib/agent_string.sh` — remove the `geminicli` enum entry
  and `--cli-id` flag mapping (lines 28, 73, 85).
- `.aitask-scripts/aitask_resolve_detected_agent.sh` — drop `geminicli` from
  `SUPPORTED_AGENTS` (line 23).
- `.aitask-scripts/aitask_codeagent.sh` — delete `format_gemini_model_label()`
  and the geminicli invocation block (lines 147–276).
- `.aitask-scripts/lib/agent_model_picker.py` — drop the
  `models_geminicli.json` registration (lines 40, 285) and the gemini branch
  in the picker UI.
- `.aitask-scripts/stats/stats_data.py` — remove gemini model parsing and
  stats labels (lines 59, 251, 276, 451, 644, 681).
- `.aitask-scripts/monitor/prompt_patterns.py` — remove the empty `gemini`
  entry (line 39).
- `.aitask-scripts/settings/settings_app.py` — remove TUI display labels
  (lines 133, 2532, 2564).
- `.aitask-scripts/aitask_review_detect_env.sh` — drop gemini detection
  branch.
- `.aitask-scripts/aitask_add_model.sh` — drop gemini-registry manipulation
  cases.
- Delete `aitasks/metadata/models_geminicli.json` (active project's data).

### t812_2 — Remove skill rendering, templating, and shared helpers

- `.aitask-scripts/lib/skill_template.py` — remove `.gemini` path
  registration (lines 38, 53, 121).
- `.aitask-scripts/lib/agent_skills_paths.sh` — drop the `gemini` →
  `.gemini/skills` path mapping (lines 14, 36).
- `.aitask-scripts/aitask_skill_render.sh` — drop the `geminicli` agent
  branch (line 37).
- `.aitask-scripts/aitask_skillrun.sh` — remove geminicli execution paths
  (lines 18, 62, 231).
- `.aitask-scripts/aitask_skill_rerender.sh` — drop gemini branches.
- `.aitask-scripts/aitask_skill_verify.sh` — drop gemini branches.
- `.aitask-scripts/aitask_audit_wrappers.sh` — remove extensive gemini
  command-rendering and policy logic (lines 6–11, 32, 36, 99, 111,
  137–209, 298, 334, 419, 422, 696, 709, 714).
- `.aitask-scripts/aitask_contribute.sh` — drop gemini from the
  contribution-area enum (lines 49, 712).
- `.aitask-scripts/aitask_codemap.sh` — keep `.gemini` in exclude list only
  if the directory itself stays (it will not — see below); remove the entry
  along with the directory.
- Delete the entire **`.gemini/` directory tree** in the active project:
  `commands/`, `policies/`, `settings.json`, `skills/`.
- Delete `.agents/skills/geminicli_planmode_prereqs.md` and
  `.agents/skills/geminicli_tool_mapping.md`.
- Delete `aidocs/geminicli_tools.md` and
  `aidocs/extract_geminicli_tools.sh`.
- **Retain** `aidocs/geminicli_to_agy.md` (the migration guide — used by
  t814) until t814 has consumed it; t814 can decide whether to archive
  or delete.
- Regenerate skill goldens whose template input changes (per
  `aidocs/skill_authoring_conventions.md` golden-regen rule).
- Run `./.aitask-scripts/aitask_skill_verify.sh` and confirm the remaining
  agents (claude, codex, opencode) still render cleanly.

### t812_3 — Remove setup/install/release pipeline + tests

- `.aitask-scripts/aitask_setup.sh` — delete `setup_gemini_cli()`,
  `merge_gemini_policies()`, `merge_gemini_settings()`,
  `install_gemini_global_policy()`, the `is_agent_installed()` gemini
  branch, and the `.gemini/` gitignore-skip entry (lines 103, 976,
  1525–1866, 2070, 2266, 2656).
- `install.sh` — delete `install_gemini_staging()`,
  `install_seed_gemini_config()`, and the `.gemini/` gitignore-skip entry
  (lines 481, 563–623, 776, 1051, 1054).
- `.github/workflows/release.yml` — remove all gemini build/packaging
  steps (commands, skills, policies, settings packaging).
- `seed/` — delete `seed/geminicli_policies/`,
  `seed/geminicli_settings.seed.json`,
  `seed/geminicli_instructions.seed.md`, `seed/models_geminicli.json`.
- `tests/test_gemini_setup.sh` — delete entirely.

### t812_4 — Documentation cleanup

User-facing docs describe current state only (per CLAUDE.md docs-writing
rules). Removed agents stop being mentioned in current-state prose. Dated
records (CHANGELOG, blog) stay intact.

- `README.md` line 20 — remove "Gemini CLI" from the supported-agent list.
- `CLAUDE.md` lines 202, 222–223 — remove the `.gemini/` agent-directory
  entry from the "Working on Skills" section.
- Update 14 website docs — remove geminicli mentions (current-state prose
  only; do not add "previously…" notes):
  - `installation/_index.md`, `installation/known-issues.md`,
    `installation/updating-model-lists.md`,
    `installation/windows-wsl.md`
  - `commands/codeagent.md`
  - `concepts/agent-attribution.md`, `concepts/verified-scores.md`
  - `skills/aitask-pick/commit-attribution.md`,
    `skills/aitask-add-model.md`,
    `skills/aitask-refresh-code-models.md`
  - `development/skills/aitask-audit-wrappers.md`
  - `tuis/settings/_index.md`, `tuis/settings/how-to.md`,
    `tuis/settings/reference.md`
- `CHANGELOG.md` — add a new entry: "Removed geminicli support
  (geminicli is being sunset by Google in favor of agy)".
- `website/content/blog/` — optionally add a brief blog post explaining
  the removal and pointing to t813/t814 for the agy migration path
  (judgement call during impl).
- `.claude/skills/task-workflow*/model-self-detection.md`,
  `satisfaction-feedback.md`, `aitask-add-model/SKILL.md`,
  `aitask-refresh-code-models/SKILL.md`, and any other SKILL.md files
  that mention `geminicli` in agent-name enumerations — remove the
  geminicli mentions. Regenerate the per-profile rendered variants.

### t812_5 — Cleanup pending gemini-related aitasks

Survey each pending gemini-targeted aitask and choose a disposition.
Suggested per-task default; final call made during this child's
implementation:

- `aitasks/t343_geminicli_support_bug_planning_step_is_skipped.md` —
  obsolete (the bug refers to a geminicli-specific workflow). Close as
  not-applicable.
- `aitasks/t344_seed_execution_permission_for_geminicli.md` — obsolete
  (agy uses sandboxed execution, no seed-exec-permission step).
  Close as not-applicable.
- `aitasks/t345_identifying_model_id_in_gemini.md` — concern may
  reapply to agy; either close-as-obsolete OR migrate to a new
  agy-targeted task referenced from t814.
- `aitasks/t401/t401_3_verify_detection_geminicli.md` — child task;
  close as obsolete and note in parent t401.

Apply disposition via `aitask_update.sh --batch --status …` plus
`aitask_archive.sh` for the not-applicable closes. If any task
genuinely migrates to agy, recreate it as a child of t814 (don't try
to rename in place).

---

## Dependencies

- Children of t812 auto-depend on siblings in numeric order.
- t812 does **not** depend on t813 or t814 — geminicli removal is
  self-contained and can land first.
- t813 has no dependencies; can be picked any time after t812 lands
  (or in parallel by another contributor).
- t814 depends on t813 (rendering enhancement) and informally on t812
  (cleaner if geminicli is already gone before agy is added).

## Verification (parent-level)

After all t812 children complete:

1. `shellcheck .aitask-scripts/aitask_*.sh` — no new warnings.
2. Each `tests/test_*.sh` passes individually; no test crashes from
   missing `models_geminicli.json` or `.gemini/` paths.
3. `./.aitask-scripts/aitask_skill_verify.sh` — confirm remaining
   agents (claude, codex, opencode) render cleanly.
4. `cd website && hugo build --gc --minify` — no broken
   cross-references after doc updates.
5. Spot-check `ait setup` on a fresh project — no `.gemini/`
   directory created, no gemini steps run.
6. Spot-check `ait monitor`, `ait board`, `ait codeagent` TUIs — no
   geminicli appears in agent lists.
7. `grep -rni 'geminicli\|gemini-cli' --include='*.md' --include='*.sh'
   --include='*.py' --include='*.json' --include='*.yaml' .` returns
   ONLY: archived plans/tasks, CHANGELOG historical entries, the
   v0.9.0 blog post, and `aidocs/geminicli_to_agy.md` (retained for
   t814).

## Cross-task context preservation (t812 → t814)

Adding a code agent (t814) touches **the same files** as removing one (this
task) but in the inverse direction. When t814 is planned, its planner MUST
have t812's archived plans surfaced as primary context — the patterns
established here (which files hold what kind of agent registration, which
helpers to extend, how the rendering pipeline branches) are exactly the
patterns t814 will re-instantiate for agy.

**Concrete mechanisms wired in by this plan:**

1. **Each t812 child's plan adds a "For t814 (add-agy)" subsection** in
   its Final Implementation Notes. This subsection lists:
   - The exact files modified in this child, with line ranges.
   - The pattern that was stripped (e.g., "geminicli enum entry in
     `SUPPORTED_AGENTS` array").
   - The **inverse instruction** for adding agy (e.g., "to add agy: insert
     `agy` into `SUPPORTED_AGENTS` at the same array; CLI-id mapping at
     line 73 follows the codex format").
   - Any gotchas discovered during removal that apply to addition
     (e.g., golden-regeneration triggers, profile-rendering re-runs).

2. **t814's auto-created description** (in the post-children step below)
   explicitly references the t812 archived plans by path and points the
   t814 planner at `aitask_explain_context.sh` over the same file list
   that t812 modified. This causes `aitask_explain_context.sh` to surface
   t812's archived plans as historical context when t814 is picked.

3. **`aidocs/geminicli_to_agy.md` is retained** (deferred from t812_2) so
   it remains available as the migration spec for t814.

## Post-children steps

After all children are committed:

1. **Aggregate the file-touchpoint list across t812 children.** From the
   archived plan files in `aiplans/archived/p812/`, extract the
   "Key Files Modified" entries and build a flat list — this is the file
   list t814's planner will pass to `aitask_explain_context.sh`.

2. **Create the two sibling tasks** via `aitask_create.sh --batch` (no
   `--parent`):

   ```bash
   # t813 — rendering enhancement (no t812 dependency)
   ./.aitask-scripts/aitask_create.sh --batch \
     --name "extend_profile_rendering_with_agent_suffix" \
     --issue-type enhancement --priority medium --effort medium \
     --labels skills,agy \
     --desc "Extend execution-profile skill rendering to include an
   agent-type suffix in the rendered SKILL.md filename when multiple
   coding agents share a physical skills directory (currently codex
   and agy on .agents/skills/). Today rendered variants land at
   .agents/skills/<name>-<profile>-/SKILL.md; the enhancement adds an
   agent dimension so each agent gets its own variant at
   .agents/skills/<name>-<profile>-<agent>-/SKILL.md (or equivalent
   naming). Prerequisite for adding agy support (t814)."

   # t814 — add agy support (depends on t813; references t812 plans)
   ./.aitask-scripts/aitask_create.sh --batch \
     --name "add_agy_antigravity_cli_support" \
     --issue-type feature --priority medium --effort high \
     --labels agy --depends <t813-id> \
     --desc "Add Antigravity CLI (agy) as a first-class supported code
   agent in the aitasks framework. Mirror the support pattern of Codex
   CLI (shared .agents/skills/ path). Depends on the agent-suffix
   rendering enhancement (t813). See aidocs/geminicli_to_agy.md for
   the migration guide and architectural differences (sandboxed
   execution, global policies, markdown SKILL.md instead of TOML
   commands, tool-name updates: run_shell_command → run_command,
   web_fetch → read_url_content).

   ### Primary historical context — t812 (remove geminicli)
   t812 removed every framework touchpoint that the geminicli agent
   had. The agy addition reinstates the same touchpoints in inverse.
   When planning this task, before exploring the codebase, run:

       ./.aitask-scripts/aitask_explain_context.sh --max-plans 8 \\
         <FILE_LIST_FROM_t812_PLANS>

   where <FILE_LIST_FROM_t812_PLANS> is the union of 'Key Files
   Modified' across:
     aiplans/archived/p812/p812_1_*.md  (agent infrastructure)
     aiplans/archived/p812/p812_2_*.md  (skill rendering)
     aiplans/archived/p812/p812_3_*.md  (setup/install/release)
     aiplans/archived/p812/p812_4_*.md  (docs)

   Each of those archived plans contains a 'For t814 (add-agy)'
   subsection in its Final Implementation Notes that gives the
   inverse-direction instructions you need."
   ```

3. **Offer the aggregate manual-verification sibling** child (covers
   `ait setup` / `ait monitor` / `ait board` / `ait codeagent` TUI checks
   after geminicli removal). Recommended **yes** — these touch live
   agent enumerations.

4. Proceed to the **child-task checkpoint** (Stop here vs. Start first
   child). Recommended **Stop here** given the breadth — children
   benefit from fresh contexts.

## Child-task documentation requirement (binding on every t812 child)

Each child task's `aiplans/p812/p812_<N>_*.md` plan file MUST include —
in its Final Implementation Notes section, alongside the standard
subsections — a top-level subsection titled exactly:

```
### For t814 (add-agy): inverse instructions
```

Contents of that subsection:

- **Files re-touched by agy:** list every file this child modified,
  with absolute line ranges where applicable. (This is the same list
  surfaced under "Key Files Modified" — repeat it here for the
  cross-task scanner.)
- **Pattern removed (with one anchor example):** the shape of the
  geminicli code that was deleted (function name, enum entry,
  template branch, etc.). Just enough that the agy planner can grep
  for the same shape in codex's analogue.
- **Inverse instruction:** the corresponding "to add agy, do …"
  recipe, derived from the codex pattern observed during removal
  (since codex is the closest analogue — both use sandboxed
  execution and `.agents/skills/`).
- **Hidden coupling discovered during removal:** anything that
  surprised the implementer (e.g., "removing the entry in
  `agent_skills_paths.sh` required regenerating goldens X, Y, Z;
  adding agy will need the same regen for `agy` outputs").

