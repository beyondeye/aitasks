---
priority: medium
effort: high
depends: []
issue_type: feature
status: Ready
labels: [codeagent]
created_at: 2026-05-28 12:17
updated_at: 2026-05-28 12:17
---

## Context

Inverse counterpart of t812_1. Adds `agy` (Antigravity CLI) to every
"agent identity" surface in the framework — the registries, dispatch
helpers, model picker, stats, monitor, settings TUI, and add-model
whitelist. Mirrors the existing **codex** branch at each touchpoint.

Absorbs the t835_1 fold concern (migrated from t345): picking and
wiring a reliable model-id detection surface for agy. Candidates:
`agy --version`, an equivalent of `cli_help`/`cli_info`, or
`~/.gemini/settings.json` inspection. Decide via practical test in a
real agy session before committing. The chosen surface must work
headless and produce `AGENT_STRING:agy/<name>` matching an entry in
`aitasks/metadata/models_agy.json`.

Primary inverse reference: `aiplans/archived/p812/p812_1_remove_geminicli_agent_infrastructure.md`
→ `### For t814 (add-agy): inverse instructions`.

## Key Files to Modify

- `.aitask-scripts/lib/agent_string.sh` — `SUPPORTED_AGENTS` (L28),
  `get_cli_binary()` (L69-77), `get_model_flag()` (L80-88).
- `.aitask-scripts/aitask_resolve_detected_agent.sh` —
  `SUPPORTED_AGENTS` (L23) + new agy detection branch.
- `.aitask-scripts/aitask_codeagent.sh` — header comment,
  `get_agent_coauthor_name` (L197-231), `get_agent_coauthor_email`
  (L233-244), `build_invoke_command` (L390-479), --help examples
  (L542-551).
- `.aitask-scripts/aitask_verified_update.sh` (L12, L42),
  `aitask_usage_update.sh` (L12, L43).
- `.aitask-scripts/lib/agent_model_picker.py` — `MODEL_FILES` (L37-41),
  `_MODES` (L277-284), docstring mode-count (L10).
- `.aitask-scripts/stats/stats_data.py` — `AGENT_DISPLAY_NAMES`
  (L56-61), agent tuples at L250, L275, L450.
- `.aitask-scripts/monitor/prompt_patterns.py` — `PROMPT_PATTERNS_BY_AGENT`
  add `"agy": []` (L25-40).
- `.aitask-scripts/settings/settings_app.py` — `MODEL_FILES` (L37-41),
  `CONFIG_FILE_DESCRIPTIONS` (L126-134), pickrem auto-rerender loop
  (decide per-touchpoint), `× N agents` message string.
- `.aitask-scripts/aitask_add_model.sh` — `SUPPORTED_AGENTS` (L24),
  --help text (L285).
- `aitasks/metadata/models_agy.json` — NEW stub (placeholder entry;
  populated by t835_5).
- `.claude/skills/task-workflow/model-self-detection.md` — add agy
  detection branch.

## Reference Files for Patterns

- Codex branch at each touchpoint — closest analogue (sandboxed
  execution, shared `.agents/skills/` root).
- `aidocs/adding_a_new_codeagent.md` §§ 2, 3, 4, 5, 6, 7, 8, 10 —
  canonical playbook for the identity layer.
- `aidocs/geminicli_to_agy.md` — agy-specific tool-name updates (note:
  this child does NOT touch tool names in skills — that's t835_2; here
  only the agent registration matters).

## Implementation Plan

1. Research and pick the agy model-id detection surface (practical
   test in agy session). Document the choice in the plan's Final
   Implementation Notes.
2. Add `agy` to all `SUPPORTED_AGENTS` arrays (5 files) — keep
   alphabetical order: `(agy claudecode codex opencode)`.
3. Add agy branches to `get_cli_binary`, `get_model_flag`,
   `get_agent_coauthor_name`, `get_agent_coauthor_email`,
   `build_invoke_command`. Mirror codex; if agy needs a custom label
   helper (e.g. `format_agy_model_label`), add it above
   `get_agent_coauthor_name`.
4. Update `aitask_codeagent.sh` --help text and header comment.
5. Add agy to `MODEL_FILES`, `_MODES` (with mode-count bump
   six→seven), `AGENT_DISPLAY_NAMES`, and the three stats agent
   tuples.
6. Add empty `"agy": []` to `PROMPT_PATTERNS_BY_AGENT` (populate
   later when real prompt wording is observed).
7. Add `"models_agy.json"` to `CONFIG_FILE_DESCRIPTIONS`; decide per
   pickrem-loop touchpoint whether agy needs an entry. Update the
   `× N agents` message string accordingly.
8. Add agy to `aitask_add_model.sh` (whitelist + help).
9. Create `aitasks/metadata/models_agy.json` with a stub entry
   (single placeholder model — real list comes in t835_5).
10. Add agy branch to `.claude/skills/task-workflow/model-self-detection.md`
    using the chosen surface from step 1.

## Verification Steps

- `bash tests/test_agent_string.sh tests/test_codeagent*.sh`.
- `./.aitask-scripts/aitask_codeagent.sh list-agents` shows agy.
- `./.aitask-scripts/aitask_resolve_detected_agent.sh --agent agy --cli-id <known>`
  returns `AGENT_STRING:agy/<name>`.
- Launch the settings TUI; the agy mode tab is present with the stub
  model list.
