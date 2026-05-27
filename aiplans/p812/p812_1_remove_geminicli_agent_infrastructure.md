---
Task: t812_1_remove_geminicli_agent_infrastructure.md
Parent Task: aitasks/t812_remove_gemini_support.md
Sibling Tasks: aitasks/t812/t812_2_*.md, aitasks/t812/t812_3_*.md, aitasks/t812/t812_4_*.md, aitasks/t812/t812_5_*.md
Archived Sibling Plans: (none yet — first child)
Worktree: (current branch — fast profile)
Branch: main
Base branch: main
plan_verified:
  - claudecode/opus4_7_1m @ 2026-05-26 12:27
  - claudecode/opus4_7_1m @ 2026-05-27 13:36
---

# Plan: Remove geminicli from agent infrastructure (t812_1)

## Context

First child of t812. Strips `geminicli` from the **code-agent identity
layer** — registries, detection helpers, model lookups, stats, monitor
prompt patterns, and TUI display labels. Closest analogue agent for
inverse-direction reference (when t814 adds agy) is **Codex CLI**.

## Key files to modify

| File | Lines (from inventory; verify on read) | Change |
|------|----------------------------------------|--------|
| `.aitask-scripts/lib/agent_string.sh` | 28, 73, 85 | Remove `geminicli` enum entry + `--cli-id` flag mapping |
| `.aitask-scripts/aitask_resolve_detected_agent.sh` | 23 | Drop `geminicli` from `SUPPORTED_AGENTS` |
| `.aitask-scripts/aitask_codeagent.sh` | 3, 5, 147–276, 468–486, 589, 605 | Delete `format_gemini_model_label()`, both geminicli invocation cases, header comment refs, and help-text examples |
| `.aitask-scripts/aitask_verified_update.sh` | 12, 42 | Drop `geminicli` from `SUPPORTED_AGENTS` + help-text agent list |
| `.aitask-scripts/aitask_usage_update.sh` | 12, 43 | Drop `geminicli` from `SUPPORTED_AGENTS` + help-text agent list |
| `.aitask-scripts/lib/agent_model_picker.py` | 10, 40, 285 | Drop `models_geminicli.json` registration + picker UI branch + docstring agent list |
| `.aitask-scripts/stats/stats_data.py` | 59, 251, 276, 451, 644–647, 681–684 | Remove gemini model parsing regex + stats labels + display name |
| `.aitask-scripts/monitor/prompt_patterns.py` | 39 | Remove the empty `gemini` entry |
| `.aitask-scripts/settings/settings_app.py` | 133, 2532, 2564 | Remove TUI display labels + gemini path mapping |
| `.aitask-scripts/aitask_review_detect_env.sh` | 295, 298 | Drop `.gemini/skills/` and `.gemini/commands/` path-match branch |
| `.aitask-scripts/aitask_add_model.sh` | 24, 285 | Drop `geminicli` from `SUPPORTED_AGENTS` + help-text agent list |
| `aitasks/metadata/models_geminicli.json` | — | Delete file |

## Step-by-step

1. Read each target file at the listed lines (line numbers may drift —
   anchor by symbol/string, not line number).
2. For each file, remove the geminicli branch surgically. Preserve
   surrounding `if/elif/else` structure (no dangling branches).
3. Delete `aitasks/metadata/models_geminicli.json` (and the
   `.aitask-data/aitasks/metadata/models_geminicli.json` if data branch
   is active — check via `ls -la aitasks` to see if it's a symlink).
4. Run verification grep:
   ```bash
   grep -rn 'geminicli\|format_gemini\|models_geminicli' \
     .aitask-scripts/lib/agent_string.sh \
     .aitask-scripts/aitask_resolve_detected_agent.sh \
     .aitask-scripts/aitask_codeagent.sh \
     .aitask-scripts/lib/agent_model_picker.py \
     .aitask-scripts/stats/stats_data.py \
     .aitask-scripts/monitor/prompt_patterns.py \
     .aitask-scripts/settings/settings_app.py \
     .aitask-scripts/aitask_review_detect_env.sh \
     .aitask-scripts/aitask_add_model.sh
   # Expect: no output
   ```

## Verification

1. `shellcheck .aitask-scripts/aitask_*.sh .aitask-scripts/lib/*.sh` —
   no new warnings.
2. Run any `tests/test_stats*.sh`, `tests/test_codeagent*.sh`,
   `tests/test_agent_string*.sh` — pass.
3. `ait codeagent --list` (or `./.aitask-scripts/aitask_codeagent.sh
   --list`) — no geminicli entry.
4. `ait monitor` opens without crashing on missing gemini pattern entry.
5. `ait board` opens; stats per-agent breakdown does not crash.

## Step 9 (Post-Implementation)

Standard archival via task-workflow Step 9. Plan and task file get
archived to `aiplans/archived/p812/p812_1_*.md` and
`aitasks/archived/t812/t812_1_*.md`. Final Implementation Notes
**must** include the `### For t814 (add-agy): inverse instructions`
subsection per the parent plan's binding requirement.

## Final Implementation Notes (template — fill in during impl)

- **Actual work done:** …
- **Deviations from plan:** …
- **Issues encountered:** …
- **Key decisions:** …
- **Upstream defects identified:** None (or list)
- **Notes for sibling tasks:** Patterns of how agent enumerations are
  laid out — siblings t812_2/3/4/5 will recognize the same shapes.

### For t814 (add-agy): inverse instructions

- **Files re-touched by agy:** (fill with the exact file list + line
  ranges where geminicli was removed).
- **Pattern removed (anchor example):** (e.g., `geminicli) … ;;` case
  branch in `agent_string.sh`).
- **Inverse instruction:** to add agy, insert an `agy) … ;;` branch at
  the same location, modeled on the existing codex branch. Update
  `SUPPORTED_AGENTS` in `aitask_resolve_detected_agent.sh` to include
  `agy`. Create `aitasks/metadata/models_agy.json` (start with a stub
  entry; populate via `/aitask-refresh-code-models`).
- **Hidden coupling discovered during removal:** (note any
  cross-file dependencies surprises here — e.g.,
  `agent_string.sh::SUPPORTED_AGENTS` and
  `agent_model_picker.py::AGENT_REGISTRIES` must stay in lockstep).
