---
Task: t268_5_tui_integration.md
Parent Task: aitasks/t268_wrapper_for_claude_code.md
Sibling Tasks: aitasks/t268/t268_6_settings_tui.md, aitasks/t268/t268_7_implemented_with_metadata.md, aitasks/t268/t268_8_documentation.md
Archived Sibling Plans: aiplans/archived/p268/p268_1_core_wrapper_script.md, p268_2_config_infrastructure.md, p268_3_common_config_library.md, p268_4_board_config_split.md, p268_9_refresh_code_models_skill.md
Worktree: (none - working on current branch)
Branch: main
Base branch: main
---

## Context

The board TUI and codebrowser TUI currently hardcode `"claude"` as the CLI binary for agent invocations. Task t268_1 created `aitask_codeagent.sh` — a unified wrapper that resolves agent/model via a 4-level chain (flag → local config → project config → default) and builds agent-specific CLI commands. This task replaces the hardcoded calls with wrapper invocations, making both TUIs agent-agnostic.

## Files to Modify

| File | Change |
|------|--------|
| `aiscripts/board/aitask_board.py` | Add `CODEAGENT_SCRIPT` constant; rewrite `run_aitask_pick` method |
| `aiscripts/codebrowser/codebrowser_app.py` | Rename `action_launch_claude` → `action_launch_agent`; add `_resolve_agent_binary` helper; update binding; rewrite subprocess calls |

No new files created. No config file changes needed — both TUIs delegate agent resolution entirely to the wrapper's existing config chain (`codeagent_config.json` / `codeagent_config.local.json`).

## Implementation Steps

### Step 1: Board TUI — Replace hardcoded claude calls [DONE]

**File:** `aiscripts/board/aitask_board.py`

**1a.** Added `CODEAGENT_SCRIPT` constant at line 42.

**1b.** Rewrote `run_aitask_pick` to use `wrapper invoke task-pick num` instead of `"claude" f"/aitask-pick {num}"`.

### Step 2: Codebrowser TUI — Replace hardcoded claude calls [DONE]

**File:** `aiscripts/codebrowser/codebrowser_app.py`

**2a.** Updated binding from `launch_claude` / "Explain in Claude" to `launch_agent` / "Explain".

**2b.** Added `_resolve_agent_binary` helper that calls `aitask_codeagent.sh resolve <operation>` and parses structured output to get agent name and binary.

**2c.** Renamed `action_launch_claude` → `action_launch_agent` with dynamic agent resolution, agent-aware error messages, and `cwd` parameter on subprocess calls.

## Design Decisions

1. **No TUI-level agent config:** TUIs don't maintain their own agent settings. Agent resolution is fully delegated to `aitask_codeagent.sh`'s existing config chain. This avoids split-brain config and keeps agent management centralized.

2. **No codebrowser_config.json:** Not needed for this change. The task spec suggested creating one, but since we're not adding TUI-level agent config, there's nothing to put in it. Can be added later if codebrowser gets other settings.

3. **`resolve` for binary check:** Codebrowser uses `aitask_codeagent.sh resolve explain` to discover the actual binary name (e.g., `gemini`), then `shutil.which()` on that. This gives accurate error messages. Board skips this check (matches existing behavior — it just calls the wrapper and lets it fail).

4. **`exec` transparency:** The wrapper's `exec` is transparent to subprocess.call/Popen. No special handling needed.

## Final Implementation Notes

- **Actual work done:** Replaced all hardcoded `"claude"` CLI references in both board TUI (2 subprocess calls in `run_aitask_pick`) and codebrowser TUI (3 references: `shutil.which` check, 2 subprocess calls in `action_launch_claude`). Added `_resolve_agent_binary` helper to codebrowser for dynamic agent discovery. Renamed `action_launch_claude` to `action_launch_agent` with updated binding.
- **Deviations from plan:** Skipped creating `seed/codebrowser_config.json` — not needed since TUIs delegate agent resolution entirely to the codeagent wrapper's existing config chain. The task spec suggested it, but adding an empty config file with just `{"default_agent": null}` would be premature.
- **Issues encountered:** Minor indentation bug in `_resolve_agent_binary` during initial edit — the `binary`/`agent` variable assignments were accidentally placed inside the `for` loop. Fixed immediately.
- **Key decisions:**
  - Board uses `CODEAGENT_SCRIPT` module constant (Path object), matching the existing `METADATA_FILE`, `TASKS_DIR` pattern
  - Codebrowser builds wrapper path from `self._project_root` dynamically, since codebrowser may be launched from different working directories
  - Added `cwd=str(self._project_root)` to codebrowser subprocess calls so the wrapper can find `aitasks/metadata/` configs
  - Board does NOT do a pre-flight binary check (matches existing behavior — lets the wrapper fail naturally)
  - Codebrowser does a pre-flight resolve+check for better UX (shows "gemini CLI (gemini) not found" instead of a cryptic wrapper error)
- **Notes for sibling tasks:**
  - t268_7 (implemented_with metadata) can now use the `AITASK_AGENT_STRING` env var set by the wrapper — both TUIs invoke via the wrapper which sets this var before exec-ing the agent
  - t268_6 (settings TUI) should reference the centralized codeagent config pattern — TUIs don't need their own agent settings, they delegate to `codeagent_config.json`
  - t268_8 (documentation) should document that TUIs are agent-agnostic and rely on the codeagent wrapper for agent/model resolution
  - The `_resolve_agent_binary` pattern in codebrowser could be extracted to a shared utility if other TUIs need it in the future
