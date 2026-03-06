---
Task: t319_5_model_status_field_support.md
Parent Task: aitasks/t319_opencode_support.md
Sibling Tasks: aitasks/t319/t319_3_opencode_docs_update.md
Archived Sibling Plans: aiplans/archived/p319/p319_1_opencode_skill_wrappers.md, aiplans/archived/p319/p319_2_opencode_setup_install.md, aiplans/archived/p319/p319_4_opencode_model_discovery.md
Worktree: (none - working on current branch)
Branch: (current branch)
Base branch: main
---

# Plan: Model Status Field Support (t319_5)

## Context

The OpenCode model discovery script (t319_4) introduced a `status` field (`"active"` or `"unavailable"`) to `models_opencode.json` to track models that disappear from providers. Currently, nothing in the framework checks this field — unavailable models can still be selected and will fail at runtime. This task adds status-aware behavior to the CLI and TUI.

The board TUI and codebrowser both call `codeagent` via subprocess — they need to handle the "model unavailable" error gracefully instead of showing generic failures.

## Step 1: Update `get_cli_model_id()` in aitask_codeagent.sh

**File:** `aiscripts/aitask_codeagent.sh` (lines 85-103)

Add a status check after looking up the model. If status is `"unavailable"`, die with a clear error message.

The `// "active"` jq default ensures models without a status field (claude, codex, gemini files) work unchanged.

## Step 2: Update `cmd_list_models()` in aitask_codeagent.sh

**File:** `aiscripts/aitask_codeagent.sh` (lines 159-183)

Add `[UNAVAILABLE]` tag and `--active-only` flag support.

## Step 3: Update model picker in settings_app.py

**File:** `aiscripts/settings/settings_app.py` (lines 747-768)

Skip unavailable models in the model picker so they can't be selected.

## Step 4: Update models tab display in settings_app.py

**File:** `aiscripts/settings/settings_app.py` (lines 1688-1704)

Add status indicator and dim styling for unavailable models.

## Step 5: Update codebrowser error handling

**File:** `aiscripts/codebrowser/codebrowser_app.py` (lines 553-575)

In `_resolve_agent_binary()`, check stderr for "unavailable" to show a specific error notification.

## Step 6: Update board error handling

**File:** `aiscripts/board/aitask_board.py` (lines 2986-3001)

In suspend-mode `run_aitask_pick()`, check return code and show error notification on failure.

## Step 7: Commit

## Verification

- `ait codeagent list-models opencode` shows STATUS field, unavailable models tagged
- `ait codeagent list-models opencode --active-only` filters out unavailable
- `ait codeagent resolve <operation>` with an unavailable model fails with clear error
- Settings TUI models tab shows `[UNAVAIL]` indicator for unavailable models
- Settings TUI model picker skips unavailable models
- Models without status field (claudecode, codex, gemini) work unchanged
- Board TUI: suspend-mode invoke shows error notification on failure
- Codebrowser: resolve shows specific "unavailable" error instead of generic message
- Shellcheck passes on aitask_codeagent.sh

## Final Implementation Notes

- **Actual work done:** Added status field checks in `get_cli_model_id()`, `cmd_list_models()` with `--active-only` flag, settings TUI model picker (skip unavailable) and models tab (dim + `[UNAVAIL]` tag), codebrowser specific error propagation, board error notification on invoke failure.
- **Deviations from plan:** None significant. Board TUI `aitask_board.py` was confirmed to have no model selection widgets (only invoke launch), so the change there is limited to error handling on subprocess return code.
- **Issues encountered:** All models in `models_opencode.json` are currently `"active"` — no unavailable models to test against. The `// "active"` jq default was verified to work correctly for model files without the status field (claudecode, codex, gemini).
- **Key decisions:**
  - Used `// "active"` jq default to ensure backward compatibility with model files that lack the status field
  - Codebrowser stores resolve error in `self._resolve_error` attribute rather than changing the return type signature
  - Board only adds error notification for suspend mode (Popen mode shows errors in the terminal directly)
- **Notes for sibling tasks:**
  - t319_3 (docs): Should document the `--active-only` flag in list-models help and any user-facing documentation about model management
  - The STATUS column is now part of `list-models` output — any scripts parsing this output need to account for the new field
