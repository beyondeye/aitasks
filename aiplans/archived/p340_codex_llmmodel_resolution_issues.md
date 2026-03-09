---
Task: t340_codex_llmmodel_resolution_issues.md
Worktree: (none - working on current branch)
Branch: main
Base branch: main
---

# Plan: Fix Codex CLI LLM Model Resolution (t340)

## Context

The Agent Attribution Procedure records which code agent and model implements each task via `implemented_with` (e.g., `codex/gpt5_4`). For Claude Code this works because the system message explicitly states the model ID. Codex CLI doesn't have such an explicit statement — leading models to report generic IDs like "GPT-5" instead of the specific `gpt-5.4`.

**Key insight:** The model is a *dynamic* property in Codex — it can change via `/model`, and plan mode may use a different model than normal mode. Reading `~/.codex/config.toml` only gives the startup default, not the current runtime model.

**Approach:** Test-driven. Created and ran a batch test script testing 4 prompt formulations across 6 Codex models. Then updated instructions based on findings.

## Test Results (24 runs, 6 models x 4 prompts)

| MODEL              | P1:direct         | P2:format-hint    | P3:context-directed | P4:assertive-context |
|--------------------|-------------------|-------------------|---------------------|----------------------|
| gpt-5.4            | MATCH             | PARTIAL(gpt-5)    | PARTIAL(gpt-5)      | ERROR(verbose)       |
| gpt-5.3-codex      | MISS(gpt-5-codex) | PARTIAL(gpt-5)    | PARTIAL(gpt-5)      | MATCH                |
| gpt-5.3-codex-spark| ERROR(all)        | ERROR(all)        | ERROR(all)          | ERROR(all)           |
| gpt-5.2-codex      | MISS(unknown)     | MISS(unknown)     | MISS(unknown)       | MISS(gpt-5.4)        |
| gpt-5.1-codex-max  | MISS(o4-mini)     | MISS(gpt-5.0)    | MISS(no access)     | MISS(not available)  |
| gpt-5.1-codex-mini | ERROR             | MISS(gpt-5.0)    | MISS(gpt-5.4)       | MISS(gpt-5.4)        |

**Conclusion:** No single prompt reliably works across all models. Self-identification is fundamentally unreliable because Codex CLI does not expose the model ID explicitly in the system prompt.

## Solution

**Practical approach:**
1. **Primary:** `AITASK_AGENT_STRING` env var (set by `ait codeagent invoke` — reliable)
2. **Fallback:** Read `~/.codex/config.toml` for the `model` field, match against `models_codex.json`
3. **Document limitation:** `/model` switches within a session cannot be accurately captured
4. **Recommend:** Use `ait codeagent invoke` for accurate model tracking

## Implementation

### Step 1: Created batch test script
- **File:** `tests/test_codex_model_detect.sh`
- Tests 4 prompt formulations across 6 models
- Captures JSON output, extracts ground truth and reported model, normalizes and compares

### Step 2: Updated Agent Attribution Procedure
- **File:** `.claude/skills/task-workflow/procedures.md`
- Added agent-specific model identification methods
- Codex: explicit `grep` command to read `~/.codex/config.toml`
- Gemini: `jq` command to read `~/.gemini/settings.json`
- Documents limitation of config-file approach for dynamic model switches

### Step 3: Updated all agent instruction files (10 files)
- `seed/codex_instructions.seed.md` — seed template
- `seed/geminicli_instructions.seed.md` — seed template
- `seed/opencode_instructions.seed.md` — seed template
- `.codex/instructions.md` — live Codex instructions
- `.agents/skills/codex_tool_mapping.md` — Codex tool mapping
- `.gemini/skills/geminicli_tool_mapping.md` — Gemini tool mapping
- `.opencode/instructions.md` — live OpenCode instructions
- `.opencode/skills/opencode_tool_mapping.md` — OpenCode tool mapping

All updated to:
1. Check `AITASK_AGENT_STRING` env var first
2. Use agent-specific config file fallback (Codex: config.toml, Gemini: settings.json)
3. Match against `models_<agent>.json` for name resolution
4. Explicitly warn against guessing model IDs (for Codex)

## Final Implementation Notes

- **Actual work done:** Created batch test script testing 4 prompt formulations across 6 Codex models (24 test runs). Updated Agent Attribution Procedure with agent-specific model detection. Updated all 8 agent instruction files (3 seeds + 5 live) with explicit model identification steps.
- **Deviations from plan:** Original plan proposed a `self-detect` shell subcommand, removed from scope per user feedback about dynamic model switching. Config-file reading was adopted as the fallback instead of self-detection scripts.
- **Issues encountered:** (1) No prompt reliably makes Codex models self-identify — gpt-5.4 and gpt-5.3-codex work inconsistently, older models fail completely. (2) `codex exec --ephemeral` doesn't persist session files, so session-file lookup approach fails. (3) gpt-5.3-codex-spark timed out on all prompts (possibly unavailable).
- **Key decisions:** Adopted pragmatic 2-tier approach: env var for managed invocations, config-file for direct invocations, with documented limitation for `/model` switches.
