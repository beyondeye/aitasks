---
Task: t308_refactoring_of_claude_code_setup.md
Worktree: (none - working on current branch)
Branch: main
Base branch: main
---

# Plan: Refactor `ait setup` to extract agent-specific setup into dedicated methods

## Context

Currently `ait setup` has Claude Code-specific setup logic (`install_claude_settings()` + `merge_claude_settings()`) called unconditionally from `main()`. The task is to:
1. Extract all Claude Code-specific setup into a dedicated `setup_claude_code()` method — **always called** (Claude Code settings/skills are core framework infrastructure)
2. Create stub methods for Gemini CLI, Codex CLI, and OpenCode — each conditionally called only if the agent CLI is installed

## Key Files

- `aiscripts/aitask_setup.sh` — Main setup script (lines 1136-1228 for Claude functions, line 1590 in main)

## Implementation Steps

### 1. Create agent detection helper function

Add a helper `_is_agent_installed()` near the top of the file (after the existing helper functions around line ~85):

```bash
# Uses `command -v` which is a shell builtin that only checks if a command
# exists on $PATH — it does NOT execute the agent or load anything.
_is_agent_installed() {
    case "$1" in
        claude)    command -v claude &>/dev/null ;;
        gemini)    command -v gemini &>/dev/null ;;
        codex)     command -v codex &>/dev/null ;;
        opencode)  command -v opencode &>/dev/null ;;
        *)         return 1 ;;
    esac
}
```

### 2. Rename `install_claude_settings()` → `setup_claude_code()`

Rename the existing function to `setup_claude_code()`. Keep `merge_claude_settings()` as an internal helper (it's already well-named). No logic changes needed — just rename.

### 3. Create stub methods for other agents

Add three new stub functions after `setup_claude_code()`:

```bash
setup_gemini_cli() {
    info "Gemini CLI setup (placeholder)"
    info "  Future: install .gemini/ skills and commands"
}

setup_codex_cli() {
    info "Codex CLI setup (placeholder)"
    info "  Future: install .codex/ prompts and .agents/ skills"
}

setup_opencode() {
    info "OpenCode setup (placeholder)"
    info "  Future: install .opencode/ skills and commands"
}
```

### 4. Create orchestrating `setup_code_agents()` function

Add a wrapper function that always runs Claude setup and conditionally runs others:

```bash
setup_code_agents() {
    # Claude Code settings are always installed (core framework infrastructure)
    setup_claude_code

    # Other agents: only set up if their CLI is installed
    if _is_agent_installed gemini; then
        echo ""
        setup_gemini_cli
    fi

    if _is_agent_installed codex; then
        echo ""
        setup_codex_cli
    fi

    if _is_agent_installed opencode; then
        echo ""
        setup_opencode
    fi
}
```

### 5. Update `main()` function

Replace the direct `install_claude_settings` call (line 1590) with `setup_code_agents`:

```bash
# Before:
    install_claude_settings
    echo ""

# After:
    setup_code_agents
    echo ""
```

## Verification

1. Run `shellcheck aiscripts/aitask_setup.sh` — no new warnings
2. Run existing tests: `bash tests/test_setup_git.sh` — passes
3. Manual check: `bash -n aiscripts/aitask_setup.sh` — valid syntax
4. Grep for `install_claude_settings` to ensure no stale references remain

## Final Implementation Notes
- **Actual work done:** Extracted Claude Code setup into `setup_claude_code()`, added `_is_agent_installed()` helper using safe `command -v`, created stub functions for gemini/codex/opencode, added `setup_code_agents()` orchestrator. Claude Code setup always runs; other agents are conditional on CLI presence.
- **Deviations from plan:** None — implemented exactly as planned.
- **Issues encountered:** None.
- **Key decisions:** Used `command -v` (shell builtin, no execution) for agent detection per user feedback. Claude Code settings always installed since they're core framework infrastructure.
