---
priority: medium
effort: high
depends: [t835_1]
issue_type: feature
status: Ready
labels: [codeagent]
created_at: 2026-05-28 12:18
updated_at: 2026-05-28 12:18
---

## Context

Inverse counterpart of t812_2. Wires `agy` into the skill rendering
pipeline. Layered on **t834** (agent-suffix mechanism, archived):
agy maps to `.agents/skills` (same as codex), and rendered output
disambiguates via `<skill>-<profile>-agy-/SKILL.md` suffix naming.

Also applies the **tool-name updates** from `aidocs/geminicli_to_agy.md`
to agy-rendered skills (`run_shell_command` → `run_command`,
`web_fetch` → `read_url_content`) so the output skills tell agy to
use the correct tool names.

Primary inverse reference: `aiplans/archived/p812/p812_2_remove_geminicli_skill_rendering.md`
→ `### For t814 (add-agy): inverse instructions`.

## Key Files to Modify

- `.aitask-scripts/lib/skill_template.py` — `AGENT_ROOTS` (L50-55) add
  `"agy": ".agents/skills"`, `AGENT_SHARED_SKILLS_ROOT` (L59-63) add
  `"agy": True`. Verify `FULL_PATH_REF_RE` (L37-41) and
  `_skill_name_from_source` (L134-148) need no edit.
- `.aitask-scripts/lib/agent_skills_paths.sh` — doc comment (L14-34)
  drop "+agy in t814" placeholder, `agent_skill_root()` (L38-45) add
  agy case, `agent_shared_skills_root()` (L50-57) add agy=true.
- `.aitask-scripts/aitask_skill_render.sh` (L37 --agent usage).
- `.aitask-scripts/aitask_skillrun.sh` — header comment (L17-19),
  per-agent CMD case (L227-238), --help examples (L62).
- `.aitask-scripts/aitask_skill_rerender.sh` (L39 agent loop).
- `.aitask-scripts/aitask_skill_verify.sh` — `_stub_path_for()` case
  and `agents=(...)` array.
- `.aitask-scripts/aitask_audit_wrappers.sh` — claim next free
  touchpoint IDs (start at 8+; do NOT reuse vacant 2/5), update
  `wrapper_path()`, `cmd_discover()` trees, helper-whitelist loop
  tuples, `render_agents_skill()` intro, usage text.
- `.aitask-scripts/aitask_contribute.sh` — `AREAS` (L49), `--area`
  help (L711).
- `.aitask-scripts/aitask_codemap.py` / `aitask_codemap.sh`
  (`FRAMEWORK_DIRS`) — verify no edit needed (agy reuses shared
  `.agents/skills/`).
- Per-skill `.md.j2` sources with tool-name divergence — introduce
  `{% if agent == "agy" %}` Jinja gates and update
  `aidocs/agent_runtime_guards_audit.md`.
- Goldens for all touched `.md.j2` — regenerate per CLAUDE.md.

## Reference Files for Patterns

- Codex branch at each touchpoint.
- t834's archived plans for the agent-suffix mechanism (the underlying
  rendering primitives).
- `aidocs/adding_a_new_codeagent.md` §§ 1, 9, 12-16 — render layer
  playbook.
- `aidocs/geminicli_to_agy.md` — tool-name list.
- `aidocs/agent_runtime_guards_audit.md` — for any new Jinja agent
  gates.
- `aidocs/stub-skill-pattern.md` — stub-per-(skill, agent) count.

## Implementation Plan

1. Add agy to `AGENT_ROOTS` and `AGENT_SHARED_SKILLS_ROOT` in
   `skill_template.py`. Add corresponding cases in
   `agent_skills_paths.sh`. Verify `agent_skill_dir()` already
   produces `<skill>-<profile>-agy-/` for the agy+shared-root combo
   (it does, via t834).
2. Update render/skillrun/rerender/verify CLI helpers' usage and
   agent-loop enumerations.
3. Survey `.md.j2` sources for `run_shell_command` / `web_fetch`
   tool-name references; introduce `{% if agent == "agy" %}` gates
   to emit `run_command` / `read_url_content` for agy. Add each new
   gate to `aidocs/agent_runtime_guards_audit.md`.
4. Update `aitask_audit_wrappers.sh`: claim new touchpoint IDs for
   the agy wrapper tree, register `wrapper_path()` case, add to
   `cmd_discover()` trees enum, helper-whitelist loop tuples; update
   `render_agents_skill()` intro to widen "Codex CLI skill wrapper"
   to "Codex CLI and Antigravity CLI skill wrapper" when the body
   is genuinely shared.
5. Update `aitask_contribute.sh` AREAS and help text.
6. Verify `aitask_codemap.{py,sh}` `FRAMEWORK_DIRS` requires no agy
   addition (no agy-only dir).
7. Regenerate goldens for every touched `.md.j2` source. Run
   `./.aitask-scripts/aitask_skill_rerender.sh <profile>` for each
   of default/fast/remote.
8. Verify codex and agy outputs co-exist in `.agents/skills/` without
   overwriting.

## Verification Steps

- `./.aitask-scripts/aitask_skill_verify.sh` passes.
- `./.aitask-scripts/aitask_skill_render.sh aitask-pick --profile fast --agent agy`
  produces `.agents/skills/aitask-pick-fast-agy-/SKILL.md`.
- `./.aitask-scripts/aitask_skill_render.sh aitask-pick --profile fast --agent codex`
  produces `.agents/skills/aitask-pick-fast-codex-/SKILL.md` (and
  does NOT overwrite the agy variant).
- `bash tests/test_skill_template.sh` and any other render-suite
  tests pass.
- Spot-check a rendered agy skill: `grep -E "run_command|read_url_content" .agents/skills/aitask-pick-fast-agy-/SKILL.md`
  shows agy-correct names; the same render for codex shows
  `run_shell_command` / `web_fetch` (or whatever codex actually uses).
