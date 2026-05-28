---
Task: t835_2_agy_skill_rendering.md
Parent Task: aitasks/t835_add_agy_antigravity_cli_support.md
Sibling Tasks: aitasks/t835/t835_1_*.md, aitasks/t835/t835_3_*.md, aitasks/t835/t835_4_*.md, aitasks/t835/t835_5_*.md, aitasks/t835/t835_6_*.md
Archived Sibling Plans: aiplans/archived/p835/p835_1_*.md (after t835_1 archives)
Inverse Blueprint: aiplans/archived/p812/p812_2_remove_geminicli_skill_rendering.md
Underlying Mechanism: aiplans/archived/p834_*.md (agent-suffix rendering)
Worktree: (none — fast profile, current branch)
Branch: main
Base branch: main
---

## Overview

Wire `agy` into the skill rendering pipeline. agy maps to
`.agents/skills` (same as codex); collisions resolved via t834's
agent-suffix mechanism (`<skill>-<profile>-agy-/SKILL.md`). Also apply
tool-name updates from `aidocs/geminicli_to_agy.md` to agy-rendered
skills.

The full file-by-file plan lives in the task description. The
**load-bearing reference** is the `### For t814 (add-agy): inverse
instructions` subsection in
`aiplans/archived/p812/p812_2_remove_geminicli_skill_rendering.md`.

## Order of operations

1. **Extend renderer dicts.** `skill_template.py::AGENT_ROOTS` add
   `"agy": ".agents/skills"`; `AGENT_SHARED_SKILLS_ROOT` add
   `"agy": True`. Verify `FULL_PATH_REF_RE` and
   `_skill_name_from_source` need no edit (they already accept
   `.agents/skills`).

2. **Extend bash equivalents.** `agent_skills_paths.sh::agent_skill_root()`
   add agy case; `agent_shared_skills_root()` add `agy) echo "true" ;;`.
   Drop the "+agy in t814" placeholder in the doc comment.

3. **Extend CLI helpers.** `aitask_skill_render.sh` (--agent usage),
   `aitask_skillrun.sh` (header comment + per-agent CMD case +
   --help), `aitask_skill_rerender.sh` (agent loop),
   `aitask_skill_verify.sh` (`_stub_path_for` case + `agents=(...)`).

4. **Tool-name divergence in shared skills.** Survey shared-root
   `.md.j2` sources for `run_shell_command` / `web_fetch`. For each
   site that emits executable instructions for the agent:
   - Introduce a `{% if agent == "agy" %}` Jinja gate emitting
     `run_command` / `read_url_content` for agy.
   - Add the new gate to `aidocs/agent_runtime_guards_audit.md`.

5. **Extend audit-wrappers.** `aitask_audit_wrappers.sh`: claim next
   free touchpoint IDs (start at 8+; **do NOT reuse** the vacant 2/5
   left by geminicli removal — per t812_2 hidden-coupling notes,
   stable IDs preserve unrelated lookups). Update `wrapper_path()`,
   `cmd_discover()` trees enum, helper-whitelist loop tuples. Verify
   whether `render_agents_skill()` intro should widen "Codex CLI
   skill wrapper" to "Codex CLI and Antigravity CLI skill wrapper".

6. **Extend contribute / codemap.** `aitask_contribute.sh::AREAS`
   add `agy|.agents/skills/|Antigravity CLI skills` and --area help.
   Verify `aitask_codemap.{py,sh}::FRAMEWORK_DIRS` requires no edit
   (agy has no agy-only dir per `aidocs/geminicli_to_agy.md`).

7. **Regenerate goldens.** Run
   `./.aitask-scripts/aitask_skill_rerender.sh <profile>` for each of
   default/fast/remote. Regenerate every affected golden under
   `tests/golden/skills/<skill>/` and `tests/golden/procs/<scope>/`
   in the SAME commit per CLAUDE.md.

8. **Verify co-existence.** Render the same skill for codex and agy;
   confirm both outputs land in `.agents/skills/` without
   overwriting (suffix disambiguates).

## Verification

- `./.aitask-scripts/aitask_skill_verify.sh` passes.
- `./.aitask-scripts/aitask_skill_render.sh aitask-pick --profile fast --agent agy` produces `.agents/skills/aitask-pick-fast-agy-/SKILL.md`.
- Same command with `--agent codex` produces `.agents/skills/aitask-pick-fast-codex-/SKILL.md` and leaves the agy variant intact.
- `grep -E "run_command|read_url_content" .agents/skills/aitask-pick-fast-agy-/SKILL.md` shows agy-correct tool names where applicable.
- Codex variant still uses codex-correct tool names (verify nothing was accidentally rewritten for codex).
- `bash tests/test_skill_template.sh` + render-suite tests pass.

## Step 9 reference

Standard task-workflow Step 9 archive after Step 8 approval.
