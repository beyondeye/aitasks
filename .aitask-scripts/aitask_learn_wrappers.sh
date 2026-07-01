#!/usr/bin/env bash
# aitask_learn_wrappers.sh — Emit GENERIC, self-contained cross-agent wrappers
# for a skill produced by aitask-learn-skill.
#
# Unlike aitask_audit_wrappers.sh (which renders the *framework's* wrapper stubs
# for aitask-* skills — framework voice, references to codex_tool_mapping.md /
# opencode_tool_mapping.md), this helper emits minimal wrappers that point ONLY
# at the canonical Claude skill and carry NO framework internals. A user's own
# learned skill must stay free of aitasks-framework conventions.
#
# Source of truth: .claude/skills/<name>/SKILL.md
# Wrapper trees (same vocabulary as aitask_audit_wrappers.sh):
#   agents           -> .agents/skills/<name>/SKILL.md     (gated on .agents/skills)
#   opencode-skill   -> .opencode/skills/<name>/SKILL.md   (gated on .opencode)
#   opencode-command -> .opencode/commands/<name>.md       (gated on .opencode)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/terminal_compat.sh
source "${SCRIPT_DIR}/lib/terminal_compat.sh"
# shellcheck source=lib/task_utils.sh
source "${SCRIPT_DIR}/lib/task_utils.sh"

REPO_ROOT="$(git rev-parse --show-toplevel)"
cd "$REPO_ROOT"

readonly SOURCE_SKILLS_DIR=".claude/skills"

# -----------------------------------------------------------------------------
# Source validation
# -----------------------------------------------------------------------------

# source_skill_md <name> -> path to the canonical Claude skill file.
source_skill_md() {
    printf '%s\n' "${SOURCE_SKILLS_DIR}/${1}/SKILL.md"
}

# read_source_description <name> -> echo the skill's description, or empty.
read_source_description() {
    local md
    md="$(source_skill_md "$1")"
    [[ -f "$md" ]] || { printf '\n'; return; }
    read_yaml_field "$md" "description"
}

# validate_source <name> -> echo the description on success (exit 0), or print
# ERROR:source-unreadable:<name> to stderr and exit 1. Called before any write.
validate_source() {
    local name="$1" md desc
    md="$(source_skill_md "$name")"
    if [[ ! -f "$md" ]]; then
        printf 'ERROR:source-unreadable:%s\n' "$name" >&2
        exit 1
    fi
    desc="$(read_source_description "$name")"
    if [[ -z "$desc" ]]; then
        printf 'ERROR:source-unreadable:%s\n' "$name" >&2
        exit 1
    fi
    printf '%s\n' "$desc"
}

# -----------------------------------------------------------------------------
# Tree paths + presence gating
# -----------------------------------------------------------------------------

wrapper_path() {
    local tree="$1" name="$2"
    case "$tree" in
        agents)            printf '%s\n' ".agents/skills/${name}/SKILL.md" ;;
        opencode-skill)    printf '%s\n' ".opencode/skills/${name}/SKILL.md" ;;
        opencode-command)  printf '%s\n' ".opencode/commands/${name}.md" ;;
        *) die "Unknown tree: $tree" ;;
    esac
}

# _tree_root_present <tree> -> 0 if the project uses that agent tree.
_tree_root_present() {
    case "$1" in
        agents)                          [[ -d ".agents/skills" ]] ;;
        opencode-skill|opencode-command) [[ -d ".opencode" ]] ;;
        *) return 1 ;;
    esac
}

# -----------------------------------------------------------------------------
# Generic stub renderers (NO framework references)
# -----------------------------------------------------------------------------

render_pointer_skill() {
    local name="$1" description="$2"
    cat <<EOF
---
name: ${name}
description: ${description}
---

Read and follow \`.claude/skills/${name}/SKILL.md\` and execute its workflow.
EOF
}

render_opencode_command() {
    local name="$1" description="$2"
    # \$ARGUMENTS stays literal; @-include is a standard OpenCode command feature.
    cat <<EOF
---
description: ${description}
---

Arguments: \$ARGUMENTS

@.claude/skills/${name}/SKILL.md
EOF
}

# render_stub <tree> <name> <description> -> emit the stub for that tree.
render_stub() {
    local tree="$1" name="$2" description="$3"
    case "$tree" in
        agents|opencode-skill) render_pointer_skill "$name" "$description" ;;
        opencode-command)      render_opencode_command "$name" "$description" ;;
        *) die "Unknown tree: $tree" ;;
    esac
}

# -----------------------------------------------------------------------------
# Subcommands
# -----------------------------------------------------------------------------

# render <tree> <name> -> print the stub to stdout (pure, no writes).
cmd_render() {
    local tree="${1:-}" name="${2:-}"
    [[ -n "$tree" && -n "$name" ]] || die "Usage: render <tree> <name>"
    local description
    description="$(validate_source "$name")"
    render_stub "$tree" "$name" "$description"
}

# emit <name> [--force] -> write generic wrappers to every present agent tree.
# Fails fast (nonzero) if the source skill is unreadable; otherwise best-effort
# per-tree with SKIP:/EXISTS:/WROTE: lines and exit 0.
cmd_emit() {
    local name="${1:-}" force="${2:-}"
    [[ -n "$name" ]] || die "Usage: emit <name> [--force]"

    local description
    description="$(validate_source "$name")"   # exits nonzero on bad source

    local tree target
    for tree in agents opencode-skill opencode-command; do
        target="$(wrapper_path "$tree" "$name")"
        if ! _tree_root_present "$tree"; then
            printf 'SKIP:%s:tree-absent\n' "$tree"
            continue
        fi
        if [[ -e "$target" && "$force" != "--force" ]]; then
            printf 'EXISTS:%s\n' "$target"
            continue
        fi
        mkdir -p "$(dirname "$target")"
        render_stub "$tree" "$name" "$description" > "$target"
        printf 'WROTE:%s\n' "$target"
    done
}

# -----------------------------------------------------------------------------
# Dispatcher
# -----------------------------------------------------------------------------

usage() {
    cat <<'EOF'
Usage: aitask_learn_wrappers.sh <subcommand> [args]

Emit generic, self-contained cross-agent wrappers for a learned Claude skill.
Wrappers point only at .claude/skills/<name>/SKILL.md — no framework internals.

Subcommands:
  render <tree> <name>       Print the generic stub for one tree to stdout (no writes).
  emit <name> [--force]      Write wrappers to every agent tree the project has.
                             Fails nonzero (ERROR:source-unreadable:<name>) if the
                             source skill is missing or lacks a description. Per tree:
                               SKIP:<tree>:tree-absent  (project doesn't use that agent)
                               EXISTS:<target>          (already present; not overwritten)
                               WROTE:<target>           (created)

Trees:
  agents             .agents/skills/<name>/SKILL.md     (gated on .agents/skills)
  opencode-skill     .opencode/skills/<name>/SKILL.md   (gated on .opencode)
  opencode-command   .opencode/commands/<name>.md       (gated on .opencode)
EOF
}

main() {
    local cmd="${1:-}"
    shift || true
    case "$cmd" in
        render)            cmd_render "$@" ;;
        emit)              cmd_emit "$@" ;;
        ""|-h|--help|help) usage ;;
        *) die "Unknown subcommand: $cmd (run --help for usage)" ;;
    esac
}

main "$@"
