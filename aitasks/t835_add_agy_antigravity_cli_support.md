---
priority: medium
effort: high
depends: [834]
issue_type: feature
status: Implementing
labels: [codeagent]
children_to_implement: [t835_1, t835_2, t835_3, t835_4]
folded_tasks: [835_1, 835_2]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-05-26 12:13
updated_at: 2026-05-28 12:18
boardidx: 90
---

## Context

Sibling task of t812 (remove geminicli) and t834 (extend skill rendering
with agent-suffix). This task **adds Antigravity CLI (`agy`) as a
first-class supported code agent** in the aitasks framework.

`agy` is Google's replacement for `geminicli`. Per the migration guide
in `aidocs/geminicli_to_agy.md`:

- **Sandboxed execution:** agy uses a native Terminal Sandbox (nsjail
  on Linux) rather than approving host commands via TOML whitelists.
- **Global policies:** agy reads whitelists from `~/.gemini/policies/`
  globally. Framework does NOT install local policies.
- **Markdown skills, not TOML commands:** agy consumes Agent Skills
  at `.agents/skills/<name>/SKILL.md` (same physical path as Codex
  CLI — hence the t834 prerequisite).
- **Tool-name updates:** `run_shell_command` → `run_command`;
  `web_fetch` → `read_url_content`.

## Dependency

Depends on **t834** (agent-suffix skill rendering). Until t834 lands,
agy and codex would collide on the same `.agents/skills/<name>/SKILL.md`
output path.

## Primary historical context — t812 (remove geminicli)

**t812 removed every framework touchpoint that the geminicli agent
had. The agy addition reinstates the same touchpoints in inverse.**
When planning this task, **before exploring the codebase**, run:

```bash
./.aitask-scripts/aitask_explain_context.sh --max-plans 8 \
  <FILE_LIST_FROM_t812_PLANS>
```

where `<FILE_LIST_FROM_t812_PLANS>` is the union of "Key Files Modified"
across the t812 children's archived plans:

- `aiplans/archived/p812/p812_1_*.md` — agent infrastructure
- `aiplans/archived/p812/p812_2_*.md` — skill rendering
- `aiplans/archived/p812/p812_3_*.md` — setup/install/release
- `aiplans/archived/p812/p812_4_*.md` — documentation

Each of those archived plans contains a `### For t814 (add-agy):
inverse instructions` subsection in its Final Implementation Notes,
which spells out the exact inverse-direction recipe for each
removal. Read those first — they save a major exploration pass.

(Note: this task was originally referenced as "t814" in the t812
parent plan; it received its actual ID at creation time. The
inverse-instruction subsection inside each t812 child plan still
references "t814" by name — match by content, not ID.)

## Reference

- `aidocs/geminicli_to_agy.md` — the migration guide, retained
  specifically as input to this task. It can be removed (or
  archived to `aidocs/archive/`) as part of this task's cleanup.
- **Codex CLI** is the closest live analogue (same `.agents/skills/`
  path, same sandboxed-execution model). Most of this task's
  changes can mirror the codex pattern, then layer in agy-specific
  differences (tool names, model registry, command binary).

## Scope (high level — planner refines)

1. **Code-agent identity layer** (inverse of t812_1): register `agy`
   in `agent_string.sh`, `aitask_resolve_detected_agent.sh`,
   `aitask_codeagent.sh`, `agent_model_picker.py`, `stats_data.py`,
   `monitor/prompt_patterns.py`, `settings_app.py`,
   `aitask_review_detect_env.sh`, `aitask_add_model.sh`. Create
   `aitasks/metadata/models_agy.json`.

2. **Skill rendering** (inverse of t812_2, layered on t834):
   register agy in `skill_template.py`, `agent_skills_paths.sh`,
   `aitask_skill_render.sh`, `aitask_skill_rerender.sh`,
   `aitask_skill_verify.sh`, `aitask_audit_wrappers.sh`,
   `aitask_contribute.sh`. Per `aidocs/geminicli_to_agy.md`, update
   tool-name references in agy-rendered skills (`run_shell_command`
   → `run_command`, `web_fetch` → `read_url_content`).

3. **Setup/install/release** (inverse of t812_3): implement
   `setup_agy_cli()` modeled on `setup_codex_cli()` (no policy
   install). Mirror `install_codex_*` in `install.sh`. Add agy
   packaging to `.github/workflows/release.yml`. Add
   `seed/agy_instructions.seed.md` and `seed/models_agy.json`.
   Author `tests/test_agy_setup.sh`.

4. **Documentation** (inverse of t812_4): add `Antigravity CLI (agy)`
   to agent-list prose in README, CLAUDE.md, the 14 website docs,
   and skill source `.md` / `.md.j2` files. Regenerate goldens.
   Add a new CHANGELOG entry. Optional: blog post.

5. **Refresh agy model list**: after seeding `models_agy.json` with
   a stub, run `/aitask-refresh-code-models` to populate the actual
   model catalogue.

6. **Cleanup**: archive or delete `aidocs/geminicli_to_agy.md` once
   consumed.

## Complexity assessment hint

This task is at least as large as t812 (parent of 5 children). The
planner should expect to split it into child tasks of comparable
shape, ideally **mirroring the t812 child structure** (1:1 inverse
correspondence). This makes side-by-side reading of paired archived
plans (t812 removal vs t814 addition) much easier for future
maintenance.

## Inherited concerns — agy model-id detection

Two child tasks (t835_1, t835_2) were created externally before this
parent's own planning pass; both target the model-self-detection
surface of scope item 1 ("Code-agent identity layer"). They have been
folded back into this parent so planning can decide where their
substance belongs in the final child split.

**From t835_1** *(migrated from t345 — geminicli-era)*: agy's reliable
model-id identification surface must be identified and wired into
`aitask_resolve_detected_agent.sh` and the Model Self-Detection
Sub-Procedure. Candidates to test in practice: `agy --version`, a
`cli_help`/`cli_info` equivalent, or `~/.gemini/settings.json`
inspection. Detection must work headless (no interactive prompt). The
chosen surface must produce a valid `AGENT_STRING:agy/<name>` matching
an entry in `aitasks/metadata/models_agy.json`.

**From t835_2** *(migrated from t401_3 — geminicli-era)*: end-to-end
verification of the agy detection path: launch agy, trigger a workflow
that invokes model-self-detection (e.g. `/aitask-pick` on a test task),
confirm `./.aitask-scripts/aitask_parse_detected_agent.sh --agent agy
--cli-id <model_id>` returns the expected `AGENT_STRING:agy/<name>`,
and verify `implemented_with` is written correctly to the task
frontmatter. Presumes the t835_1 surface choice has landed first.

The planner is expected to either (a) carve a dedicated child for the
model-id detection surface plus its end-to-end verification, or
(b) absorb both concerns into the broader scope-item-1 child, depending
on the final child shape.

## Out of scope

- Anything to do with re-introducing geminicli.
- Changes to other agents (claude, codex, opencode) unless
  required for shared-path support inherited from t834.
