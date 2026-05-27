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

## Final Implementation Notes

- **Actual work done:** Removed `geminicli` from 11 code files
  (agent identity registry, model picker, stats, codeagent invoke and
  coauthor, monitor prompt patterns, settings TUI, review-env detection,
  add-model whitelist), deleted `aitasks/metadata/models_geminicli.json`,
  updated 4 test files to drop gemini-specific assertions or substitute
  another agent in non-gemini-specific tests. Also extended
  `aidocs/adding_a_new_codeagent.md` with 10 new sections (+419 lines)
  cataloguing every touchpoint encountered during removal, so the doc
  is now a usable add-a-new-agent checklist (mirrors what t814 must
  reverse for agy).
- **Deviations from plan:** None for the code touchpoints. **Plan
  scope expanded mid-task** at user request to also extend
  `aidocs/adding_a_new_codeagent.md`. Plan inventory line ranges were
  accurate; one extra touchpoint (auto-rerender message string
  "× 4 agents" → "× 3 agents" in `settings_app.py`) was caught during
  implementation and updated alongside the loop tuple. The
  `aitask_codeagent.sh::format_gemini_model_label` deletion also
  removed the now-unused helper entirely (rather than leaving a stub)
  per the framework's no-backwards-compat preference.
- **Issues encountered:** None. Tests that broke after removal were
  exactly the ones expected (geminicli enum assertions, fixture copy,
  coauthor tests for `geminicli/*`). All resolved in-loop.
- **Key decisions:**
  - For Test 6/7 in `test_codeagent.sh` (which used
    `geminicli/gemini2_5pro` and `geminicli/gemini3pro` as override
    examples), substituted with `codex/gpt5_4` to preserve test
    coverage of the override mechanism rather than deleting the tests.
  - For Test 26/26b/26c (geminicli coauthor metadata), deleted
    entirely — the coauthor mechanism is still covered by claudecode,
    codex, and opencode tests.
  - For `test_add_model.sh` Test 4 (which used `--agent geminicli` as a
    "non-claudecode" rejection example), substituted `--agent codex` —
    the test's intent is to verify `promote-default-agent-string`
    rejects any non-claudecode agent.
- **Upstream defects identified:** None.
- **Notes for sibling tasks:**
  - The agent enumeration shape (case branch with `claudecode | codex |
    opencode` ordering) is consistent across `agent_string.sh`,
    `aitask_codeagent.sh`, `stats_data.py`, and
    `aitask_resolve_detected_agent.sh`. t812_2/3/4/5 should preserve
    the same canonical ordering when removing further references.
  - The `SUPPORTED_AGENTS` array is **re-declared** in five separate
    files (see §2b of `aidocs/adding_a_new_codeagent.md`). No
    cross-file validator exists today — the test suite is the safety
    net. Future tasks that add/remove agents must touch all of them.
  - The `aitask_codeagent.sh` header comment and `--help` text both
    list agents; remember to update both narrative spots when changing
    the agent set.
  - The pickrem auto-rerender loop in `settings_app.py` uses the
    **short agent name** (`claude`, `codex`, `gemini`, `opencode`)
    matching `aitask_skill_render.sh --agent`, NOT the canonical
    agent_string.sh name (`claudecode`, etc.).

### For t814 (add-agy): inverse instructions

- **Files re-touched by agy** (exact list + ranges where geminicli was
  removed):
  - `.aitask-scripts/lib/agent_string.sh` — `SUPPORTED_AGENTS` (line
    28), `get_cli_binary` case branch (line ~73), `get_model_flag`
    case branch (line ~85).
  - `.aitask-scripts/aitask_resolve_detected_agent.sh` —
    `SUPPORTED_AGENTS` (line 23).
  - `.aitask-scripts/aitask_codeagent.sh` — header comment (lines 3+5),
    `format_gemini_model_label()` helper (was lines 147–172, now
    deleted), `get_agent_coauthor_name` case branch (was lines
    246–253), `get_agent_coauthor_email` case branch (was line 276),
    `build_invoke_command` case branch (was lines 468–486), `--help`
    "Agent string format" line (was 589), `Examples:` line (was 605).
  - `.aitask-scripts/aitask_verified_update.sh` — `SUPPORTED_AGENTS`
    (line 12), help-text agent list (line 42).
  - `.aitask-scripts/aitask_usage_update.sh` — `SUPPORTED_AGENTS`
    (line 12), help-text agent list (line 43).
  - `.aitask-scripts/lib/agent_model_picker.py` — module docstring
    mode-count line (line 10), `MODEL_FILES` dict (line 40),
    `AgentModelPickerScreen._MODES` tuple (line 285) + docstring
    "seven modes" → "six modes".
  - `.aitask-scripts/stats/stats_data.py` — `AGENT_DISPLAY_NAMES`
    (line 59), `load_model_cli_ids` agent tuple (line 251),
    `load_verified_rankings` agent tuple (line 276),
    `load_usage_rankings` agent tuple (line 451), `canonical_model_id`
    gemini regex branch (lines 644–650), `model_display_from_cli_id`
    gemini regex branch (lines 681–687).
  - `.aitask-scripts/monitor/prompt_patterns.py` — empty `"gemini": []`
    entry in `PROMPT_PATTERNS_BY_AGENT` (line 39).
  - `.aitask-scripts/settings/settings_app.py` —
    `CONFIG_FILE_DESCRIPTIONS` entry (line 133),
    pickrem-auto-rerender loop tuple (line 2532), message string
    "× 4 agents", `_pickrem_rendered_paths::root_map` (line 2564).
  - `.aitask-scripts/aitask_review_detect_env.sh` — `.gemini/skills/`
    + `.gemini/commands/` path-match branch and comment (lines
    295–298).
  - `.aitask-scripts/aitask_add_model.sh` — `SUPPORTED_AGENTS` (line
    24), help-text "Supported agents:" line (line 285).
  - `aitasks/metadata/models_geminicli.json` — file existed, deleted
    via `./ait git rm`.

- **Pattern removed (anchor examples):**
  - In `agent_string.sh`:
    ```bash
    geminicli)  echo "gemini" ;;   # get_cli_binary
    geminicli)  echo "-m" ;;       # get_model_flag
    ```
  - In `aitask_codeagent.sh::get_agent_coauthor_name`:
    ```bash
    geminicli)
        cli_id="$(lookup_cli_model_id_if_known "$agent" "$model_name")"
        if [[ -n "$cli_id" && "$cli_id" != "null" ]]; then
            echo "Gemini CLI/$(format_gemini_model_label "$cli_id")"
        else
            echo "Gemini CLI/$model_name"
        fi
        ;;
    ```
  - In `agent_model_picker.py::_MODES`:
    ```python
    ("geminicli",  "All Gemini models"),
    ```
  - In `stats_data.py::AGENT_DISPLAY_NAMES`:
    ```python
    "geminicli": "Gemini CLI",
    ```

- **Inverse instruction:** to add agy, insert an `agy) … ;;` branch at
  the same location as each removed `geminicli) … ;;` branch, modeled
  on the existing **codex** branch (closest analogue — sandboxed
  execution, `.agents/skills/` shared root). Specifically:
  - Add `agy` to every `SUPPORTED_AGENTS` array enumerated above (5
    files).
  - Add `agy) echo "agy" ;;` to `get_cli_binary` and `agy) echo
    "<flag>" ;;` to `get_model_flag` (likely `-m` mirroring codex).
  - Add the `agy)` branch to `get_agent_coauthor_name` /
    `get_agent_coauthor_email` and to `build_invoke_command`. If agy's
    cli_id format needs a custom label, add a
    `format_agy_model_label()` helper above `get_agent_coauthor_name`.
  - Add `"agy": METADATA_DIR / "models_agy.json"` to `MODEL_FILES` and
    `("agy", "All Agy models")` to `_MODES`; bump the mode-count from
    "six" back to "seven" in the picker docstring.
  - Add `"agy": "Agy"` (or chosen display name) to
    `AGENT_DISPLAY_NAMES` and `"agy"` to every agent tuple in
    `stats_data.py`.
  - Add `"agy": []` to `PROMPT_PATTERNS_BY_AGENT` (empty list is fine
    until prompt wording is observed).
  - Add `"models_agy.json": "Agy model list and verification scores"`
    to `CONFIG_FILE_DESCRIPTIONS`. If agy stays inside
    `.agents/skills/` (shared with codex), the
    pickrem-auto-rerender loop does NOT need an `agy` entry — the
    codex render path already covers the shared root. Update
    `_pickrem_rendered_paths::root_map` only if agy targets a
    different directory.
  - Update `aitask_review_detect_env.sh` only if agy lives outside
    `.agents/skills/`. (It does not — keep the existing
    `.agents/skills/*` branch.)
  - Create `aitasks/metadata/models_agy.json` with a stub entry
    (populate via `/aitask-refresh-code-models` after the runtime
    settles).
  - Add `agy` to `aitask_add_model.sh`'s `SUPPORTED_AGENTS` and
    help-text "Supported agents:" list.
  - Regenerate / extend the test fixtures listed in §11 of
    `aidocs/adding_a_new_codeagent.md`.

- **Hidden coupling discovered during removal:**
  - **`SUPPORTED_AGENTS` is duplicated in 5 files** (see §2b of
    `aidocs/adding_a_new_codeagent.md`): `agent_string.sh` (canonical),
    `aitask_resolve_detected_agent.sh`, `aitask_verified_update.sh`,
    `aitask_usage_update.sh`, `aitask_add_model.sh`. No verifier
    enforces consistency — tests are the safety net. `stats_data.py`
    additionally hard-codes the agent tuple in three places (line
    251, 276, 451).
  - **`settings_app.py::_pickrem_rendered_paths::root_map` and the
    auto-rerender loop tuple use the renderer short name**
    (`claude`, `codex`, `opencode`), NOT the canonical agent_string
    name. When adding an agent, decide which name applies per
    touchpoint — the renderer uses short names, everything else uses
    the canonical name.
  - **The `× N agents` message string in `settings_app.py`** is a
    hard-coded human number; it must be updated alongside the loop
    length whenever the agent list changes.
  - **`aitask_codeagent.sh` header comment + `--help` text both list
    agents narratively** — update both, not just the case branches.
  - **`agent_model_picker.py` has both a `_MODES` tuple and a
    docstring mode-count** ("seven modes" / "six modes") — these
    must stay in sync.
  - **Test substitutions for non-agent-specific tests** (e.g. tests
    that use any non-claudecode agent as a rejection example): rather
    than delete the test, substitute another supported agent
    (codex/opencode). Delete the test only when it covers
    agent-specific functionality (e.g. the gemini coauthor metadata
    tests).
  - No goldens regeneration was triggered by this task — none of the
    edited files are part of the skill-rendering pipeline.
