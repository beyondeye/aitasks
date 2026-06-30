#!/usr/bin/env bash
# Policy: which Codex CLI skills are launched through plan mode.
#
# Planning skills (pick, explore) are launched via the /plan PTY helper
# (aitask_codex_plan_invoke.py) so the load-bearing commit/merge approval
# prompts reliably surface and so plan mode benefits the planning itself.
# Read-only analysis skills (qa, explain) run in Codex's default mode, where
# request_user_input is available via the default_mode_request_user_input
# feature flag that `ait setup` enables.
#
# Single source of truth shared by aitask_codeagent.sh and aitask_skillrun.sh.

[[ -n "${_AIT_CODEX_PLAN_POLICY_LOADED:-}" ]] && return 0
_AIT_CODEX_PLAN_POLICY_LOADED=1

# codex_skill_forces_plan_mode <skill>
# Accepts either a bare operation name (pick/qa/explain/explore) or a full
# skill name (aitask-pick, ...). Returns 0 (force plan mode) for every skill
# except the relaxed skills; returns 1 for qa/explain/shadow/learn. `learn`
# (aitask-learn-skill) is interactive but not a task-planning skill — like
# shadow it should launch in Codex's default mode, not the /plan PTY wrapper.
codex_skill_forces_plan_mode() {
    case "${1#aitask-}" in
        qa|explain|shadow|learn) return 1 ;;
        *)                       return 0 ;;
    esac
}
