---
Task: t835_1_agy_agent_infrastructure.md
Parent Task: aitasks/t835_add_agy_antigravity_cli_support.md
Sibling Tasks: aitasks/t835/t835_2_*.md, aitasks/t835/t835_3_*.md, aitasks/t835/t835_4_*.md, aitasks/t835/t835_5_*.md, aitasks/t835/t835_6_*.md
Inverse Blueprint: aiplans/archived/p812/p812_1_remove_geminicli_agent_infrastructure.md
Worktree: (none — fast profile, current branch)
Branch: main
Base branch: main
---

## Overview

Add `agy` to every "agent identity" surface in the framework:
registries, dispatch helpers, model picker, stats, monitor, settings
TUI, add-model whitelist. Mirror the existing **codex** branch at each
touchpoint. Absorbs the migrated t345-style concern: pick & wire a
reliable model-id detection surface for agy.

The full file-by-file plan lives in the task description
(`aitasks/t835/t835_1_agy_agent_infrastructure.md`). The
**load-bearing reference** is the `### For t814 (add-agy): inverse
instructions` subsection in
`aiplans/archived/p812/p812_1_remove_geminicli_agent_infrastructure.md`
— it lists exact files and ranges and identifies hidden coupling.

## Order of operations

1. **Pick agy model-id detection surface.** Practical test in a real
   agy session (cannot be done from a Claude session). Candidates in
   priority order:
   - `agy --version` (preferred if it includes the model id).
   - An equivalent of `cli_help` / `cli_info`.
   - `~/.gemini/settings.json` inspection.
   Document the choice + rationale in Final Implementation Notes.

2. **Extend `SUPPORTED_AGENTS`** in all 5 files (canonical: agent_string.sh;
   replicas: aitask_resolve_detected_agent.sh,
   aitask_verified_update.sh, aitask_usage_update.sh,
   aitask_add_model.sh). Alphabetical order: `(agy claudecode codex opencode)`.

3. **Extend dispatch functions** in `agent_string.sh`
   (`get_cli_binary`, `get_model_flag`) and `aitask_codeagent.sh`
   (`get_agent_coauthor_name`, `get_agent_coauthor_email`,
   `build_invoke_command`). Mirror codex at every site. Update header
   comment and --help text.

4. **Wire detection branch** in
   `aitask_resolve_detected_agent.sh` using the surface from step 1.
   Add matching branch to
   `.claude/skills/task-workflow/model-self-detection.md`.

5. **Extend model picker** (`agent_model_picker.py`): MODEL_FILES,
   _MODES (mode-count six → seven). Extend
   `settings_app.py::MODEL_FILES` and `CONFIG_FILE_DESCRIPTIONS`.

6. **Extend stats** (`stats_data.py`): `AGENT_DISPLAY_NAMES` and the
   three agent tuples (load_model_cli_ids, load_verified_rankings,
   load_usage_rankings).

7. **Extend monitor**: `PROMPT_PATTERNS_BY_AGENT["agy"] = []` (empty;
   populated when prompt wording is observed in real use).

8. **Settings pickrem-auto-rerender:** decide per-touchpoint whether
   agy needs an entry. Loop uses canonical names (agy is distinct from
   codex — likely needs an entry); root_map uses renderer short names
   (codex already covers `.agents/skills/`). Update `× N agents`
   message string accordingly.

9. **Create `aitasks/metadata/models_agy.json`** with a stub entry
   (placeholder model). Real catalog comes in t835_5.

## Verification

- `bash tests/test_agent_string.sh tests/test_codeagent*.sh tests/test_resolve_detected_agent.sh` (or equivalent suite) all pass.
- `./.aitask-scripts/aitask_codeagent.sh list-agents` output includes `agy`.
- `./.aitask-scripts/aitask_resolve_detected_agent.sh --agent agy --cli-id <stub-id>` returns `AGENT_STRING:agy/<stub-name>`.
- Settings TUI launches; the agy mode tab is reachable and lists the stub model without error.
- `grep -rn "geminicli" .aitask-scripts/` returns nothing new (no accidental reversal of t812).

## Step 9 reference

After this child completes (Step 8 user-review approval), proceed
through the standard task-workflow Step 9 (archive script, push). The
parent t835 archive happens automatically when the last child
(t835_6) lands.
