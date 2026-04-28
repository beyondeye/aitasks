#!/usr/bin/env bash
# aitask_audit_wrappers.sh — Audit and port aitask skill wrappers across code-agent trees.
#
# Source of truth: .claude/skills/aitask-*/SKILL.md
# Wrapper trees:
#   - .gemini/commands/<name>.toml
#   - .agents/skills/<name>/SKILL.md
#   - .opencode/skills/<name>/SKILL.md
#   - .opencode/commands/<name>.md
# Plus per-skill activate_skill entries in:
#   - .gemini/policies/aitasks-whitelist.toml          (runtime)
#   - seed/geminicli_policies/aitasks-whitelist.toml   (seed)
#
# Phase 2 (helper-script whitelist auditing) is added in t691_2.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/terminal_compat.sh
source "${SCRIPT_DIR}/lib/terminal_compat.sh"
# shellcheck source=lib/task_utils.sh
source "${SCRIPT_DIR}/lib/task_utils.sh"

REPO_ROOT="$(git rev-parse --show-toplevel)"
cd "$REPO_ROOT"

# -----------------------------------------------------------------------------
# Constants
# -----------------------------------------------------------------------------

readonly SOURCE_SKILLS_DIR=".claude/skills"
readonly TREE_GEMINI_COMMANDS=".gemini/commands"
readonly TREE_AGENTS_SKILLS=".agents/skills"
readonly TREE_OPENCODE_SKILLS=".opencode/skills"
readonly TREE_OPENCODE_COMMANDS=".opencode/commands"
readonly POLICY_RUNTIME=".gemini/policies/aitasks-whitelist.toml"
readonly POLICY_SEED="seed/geminicli_policies/aitasks-whitelist.toml"

# -----------------------------------------------------------------------------
# Skill discovery
# -----------------------------------------------------------------------------

# Emit the names of every user-invokable aitask-* skill in the source of truth.
list_source_skills() {
    local entry name
    for entry in "$SOURCE_SKILLS_DIR"/aitask-*; do
        [[ -d "$entry" ]] || continue
        [[ -f "$entry/SKILL.md" ]] || continue
        name="${entry##*/}"
        printf '%s\n' "$name"
    done | sort
}

# Read the description field from a skill's source-of-truth SKILL.md frontmatter.
read_skill_description() {
    local skill_name="$1"
    local skill_md="${SOURCE_SKILLS_DIR}/${skill_name}/SKILL.md"
    [[ -f "$skill_md" ]] || { echo ""; return; }
    read_yaml_field "$skill_md" "description"
}

# Extract a short "Arguments" summary from a skill's source-of-truth SKILL.md.
# Looks for the first non-empty paragraph under "## Usage" or "## Arguments".
# If neither exists, prints a generic fallback.
read_skill_arguments() {
    local skill_name="$1"
    local skill_md="${SOURCE_SKILLS_DIR}/${skill_name}/SKILL.md"
    [[ -f "$skill_md" ]] || { echo "See source skill documentation."; return; }

    local body
    body=$(awk '
        /^## (Usage|Arguments)/ || /^\*\*(Usage|Arguments):\*\*/ {
            in_section = 1; capture = 1; next
        }
        /^## / && in_section { exit }
        capture && NF > 0 && !/^```/ {
            print
            captured = 1
            next
        }
        capture && captured && (NF == 0 || /^```/) { exit }
    ' "$skill_md")

    if [[ -n "$body" ]]; then
        printf '%s\n' "$body" | head -3
    else
        echo "See source skill documentation."
    fi
}

# -----------------------------------------------------------------------------
# Wrapper discovery
# -----------------------------------------------------------------------------

# wrapper_path <tree> <skill_name> -> echoes the canonical path for that wrapper.
wrapper_path() {
    local tree="$1" skill="$2"
    case "$tree" in
        gemini)            printf '%s\n' "${TREE_GEMINI_COMMANDS}/${skill}.toml" ;;
        agents)            printf '%s\n' "${TREE_AGENTS_SKILLS}/${skill}/SKILL.md" ;;
        opencode-skill)    printf '%s\n' "${TREE_OPENCODE_SKILLS}/${skill}/SKILL.md" ;;
        opencode-command)  printf '%s\n' "${TREE_OPENCODE_COMMANDS}/${skill}.md" ;;
        *) die "Unknown tree: $tree" ;;
    esac
}

# discover -> emit GAP:<tree>:<skill> for every missing wrapper.
cmd_discover() {
    local skill tree path
    while IFS= read -r skill; do
        for tree in gemini agents opencode-skill opencode-command; do
            path=$(wrapper_path "$tree" "$skill")
            if [[ ! -f "$path" ]]; then
                printf 'GAP:%s:%s\n' "$tree" "$skill"
            fi
        done
    done < <(list_source_skills)
}

# discover-policy -> emit POLICY_GAP:<runtime|seed>:<skill> for missing activate_skill rules.
cmd_discover_policy() {
    local skill
    while IFS= read -r skill; do
        if ! grep -qF "argsPattern = \"${skill}\"" "$POLICY_RUNTIME" 2>/dev/null; then
            printf 'POLICY_GAP:runtime:%s\n' "$skill"
        fi
        if ! grep -qF "argsPattern = \"${skill}\"" "$POLICY_SEED" 2>/dev/null; then
            printf 'POLICY_GAP:seed:%s\n' "$skill"
        fi
    done < <(list_source_skills)
}

# -----------------------------------------------------------------------------
# Wrapper templates
# -----------------------------------------------------------------------------

render_gemini_command() {
    local skill="$1" description="$2"
    cat <<EOF
description = "${description}"
prompt = """

@.gemini/skills/geminicli_tool_mapping.md

Execute the following Claude Code skill. Follow each step precisely, translating tool references per the mapping above.

Arguments: {{args}}

@.claude/skills/${skill}/SKILL.md
"""
EOF
}

render_agents_skill() {
    local skill="$1" description="$2" arguments="$3"
    cat <<EOF
---
name: ${skill}
description: ${description}
---

## Source of Truth

This is a unified skill wrapper for Codex CLI and Gemini CLI. The authoritative skill definition is:

**\`.claude/skills/${skill}/SKILL.md\`**

Read that file and follow its complete workflow.

**If you are Codex CLI:** For tool mapping and adaptations, read **\`.agents/skills/codex_tool_mapping.md\`**.

**If you are Gemini CLI:** For tool mapping and adaptations, read **\`.agents/skills/geminicli_tool_mapping.md\`**.

## Arguments

${arguments}
EOF
}

render_opencode_skill() {
    local skill="$1" description="$2" arguments="$3"
    cat <<EOF
---
name: ${skill}
description: ${description}
---

## Source of Truth

This is an OpenCode wrapper. The authoritative skill definition is:

**\`.claude/skills/${skill}/SKILL.md\`**

Read that file and follow its complete workflow. For tool mapping and
OpenCode adaptations, read **\`.opencode/skills/opencode_tool_mapping.md\`**.

## Arguments

${arguments}
EOF
}

render_opencode_command() {
    local skill="$1" description="$2"
    cat <<EOF
---
description: ${description}
---

@.opencode/skills/opencode_tool_mapping.md

Execute the following Claude Code skill. Follow each step precisely, translating tool references per the mapping above.

Arguments: \$ARGUMENTS

@.claude/skills/${skill}/SKILL.md
EOF
}

# render-wrapper <tree> <skill_name> -> emit the rendered wrapper to stdout.
cmd_render_wrapper() {
    local tree="${1:-}" skill="${2:-}"
    [[ -n "$tree" && -n "$skill" ]] || die "Usage: render-wrapper <tree> <skill_name>"

    local description arguments
    description=$(read_skill_description "$skill")
    [[ -n "$description" ]] || die "Cannot read description for $skill (source SKILL.md missing or no frontmatter)"

    case "$tree" in
        gemini)            render_gemini_command "$skill" "$description" ;;
        agents)
            arguments=$(read_skill_arguments "$skill")
            render_agents_skill "$skill" "$description" "$arguments"
            ;;
        opencode-skill)
            arguments=$(read_skill_arguments "$skill")
            render_opencode_skill "$skill" "$description" "$arguments"
            ;;
        opencode-command)  render_opencode_command "$skill" "$description" ;;
        *) die "Unknown tree: $tree" ;;
    esac
}

# apply-wrapper <tree> <skill_name> [--force] -> write the wrapper to its canonical path.
cmd_apply_wrapper() {
    local tree="${1:-}" skill="${2:-}" force="${3:-}"
    [[ -n "$tree" && -n "$skill" ]] || die "Usage: apply-wrapper <tree> <skill_name> [--force]"

    local target
    target=$(wrapper_path "$tree" "$skill")

    if [[ -e "$target" && "$force" != "--force" ]]; then
        warn "Refusing to overwrite existing $target (pass --force to override)"
        return 1
    fi

    mkdir -p "$(dirname "$target")"
    cmd_render_wrapper "$tree" "$skill" > "$target"
    printf 'WROTE:%s\n' "$target"
}

# -----------------------------------------------------------------------------
# Policy file manipulation
# -----------------------------------------------------------------------------

# Insert an activate_skill rule into a gemini policy file at the alphabetical
# position. Idempotent — does nothing if the skill already has a rule.
insert_activate_skill_rule() {
    local file="$1" skill="$2"

    if [[ ! -f "$file" ]]; then
        warn "Policy file not found: $file"
        return 1
    fi

    if grep -qF "argsPattern = \"${skill}\"" "$file"; then
        return 0
    fi

    # Find the line number of the first activate_skill block whose argsPattern
    # is alphabetically AFTER the new skill.
    local target_line
    target_line=$(awk -v skill="$skill" '
        /^\[\[rule\]\]$/ {
            rule_line = NR
            in_block = 1
            block_kind = ""
            next
        }
        in_block && /^toolName = "activate_skill"$/ {
            block_kind = "activate_skill"
            next
        }
        in_block && block_kind == "activate_skill" && /^argsPattern = / {
            match($0, /"[^"]+"/)
            pat = substr($0, RSTART+1, RLENGTH-2)
            if (pat > skill) {
                print rule_line
                exit
            }
            in_block = 0
            next
        }
    ' "$file")

    local tmp
    tmp=$(mktemp "${TMPDIR:-/tmp}/audit_wrappers_policy_XXXXXX")

    if [[ -z "$target_line" ]]; then
        # No alphabetically-later activate_skill block — append at end of file.
        {
            cat "$file"
            printf '\n[[rule]]\ntoolName = "activate_skill"\nargsPattern = "%s"\ndecision = "allow"\npriority = 100\n' "$skill"
        } > "$tmp"
    else
        local before_lines=$((target_line - 1))
        {
            head -n "$before_lines" "$file"
            printf '[[rule]]\ntoolName = "activate_skill"\nargsPattern = "%s"\ndecision = "allow"\npriority = 100\n\n' "$skill"
            tail -n "+${target_line}" "$file"
        } > "$tmp"
    fi

    mv "$tmp" "$file"
    printf 'WROTE:%s:%s\n' "$file" "$skill"
}

# apply-policy <runtime|seed> <skill_name>
cmd_apply_policy() {
    local target="${1:-}" skill="${2:-}"
    [[ -n "$target" && -n "$skill" ]] || die "Usage: apply-policy <runtime|seed> <skill_name>"

    local file
    case "$target" in
        runtime) file="$POLICY_RUNTIME" ;;
        seed)    file="$POLICY_SEED" ;;
        *) die "Unknown target: $target (expected runtime|seed)" ;;
    esac

    insert_activate_skill_rule "$file" "$skill"
}

# -----------------------------------------------------------------------------
# Phase 2: helper-script whitelist audit
# -----------------------------------------------------------------------------

# Map a touchpoint number (1-5) to its file path.
touchpoint_file() {
    case "$1" in
        1) printf '%s\n' ".claude/settings.local.json" ;;
        2) printf '%s\n' ".gemini/policies/aitasks-whitelist.toml" ;;
        3) printf '%s\n' "seed/claude_settings.local.json" ;;
        4) printf '%s\n' "seed/geminicli_policies/aitasks-whitelist.toml" ;;
        5) printf '%s\n' "seed/opencode_config.seed.json" ;;
        *) return 1 ;;
    esac
}

# Check if a helper is whitelisted in a given touchpoint. Returns 0 if present.
helper_present_in_touchpoint() {
    local touchpoint="$1" helper="$2"
    local file
    file=$(touchpoint_file "$touchpoint") || return 1
    [[ -f "$file" ]] || return 1

    case "$touchpoint" in
        1|3) grep -qF "Bash(./.aitask-scripts/${helper}:*)" "$file" ;;
        2|4) grep -qF "commandPrefix = \"./.aitask-scripts/${helper}\"" "$file" ;;
        5)   grep -qF "\"./.aitask-scripts/${helper} *\": \"allow\"" "$file" ;;
        *)   return 1 ;;
    esac
}

# discover-helpers -> emit HELPER:<basename> for each .aitask-scripts/aitask_*.sh
# referenced by any aitask-* skill or framework-internal procedure tree.
cmd_discover_helpers() {
    grep -hroE '\.aitask-scripts/aitask_[a-z_]+\.sh' \
        .claude/skills/aitask-*/ \
        .claude/skills/task-workflow/ \
        .claude/skills/user-file-select/ \
        .claude/skills/ait-git/ 2>/dev/null \
      | sed 's|.*/||' \
      | sort -u \
      | while IFS= read -r helper; do
            [[ -f ".aitask-scripts/${helper}" ]] && printf 'HELPER:%s\n' "$helper"
        done
}

# audit-helper-whitelist <helper> -> emit MISSING:<touchpoint>:<helper> lines.
cmd_audit_helper_whitelist() {
    local helper="${1:-}"
    [[ -n "$helper" ]] || die "Usage: audit-helper-whitelist <helper>"

    local touchpoint
    for touchpoint in 1 2 3 4 5; do
        if ! helper_present_in_touchpoint "$touchpoint" "$helper"; then
            printf 'MISSING:%d:%s\n' "$touchpoint" "$helper"
        fi
    done
}

# Splice a single new line into a file just before the line number $target_line.
# Picks indent from the target line so the new entry visually aligns.
splice_line_before() {
    local file="$1" target_line="$2" line_body="$3"

    local indent
    indent=$(awk -v lineno="$target_line" 'NR == lineno { match($0, /^[ \t]*/); print substr($0, 1, RLENGTH); exit }' "$file")

    local tmp
    tmp=$(mktemp "${TMPDIR:-/tmp}/audit_wrappers_splice_XXXXXX")
    local before=$((target_line - 1))
    {
        head -n "$before" "$file"
        printf '%s%s\n' "$indent" "$line_body"
        tail -n "+${target_line}" "$file"
    } > "$tmp"
    mv "$tmp" "$file"
}

# Insert a Claude-settings Bash permission entry at the alphabetical position.
# Used for touchpoints 1 and 3.
insert_claude_settings_helper_line() {
    local file="$1" helper="$2"

    local target_line
    target_line=$(awk -v helper="$helper" '
        /"Bash\(\.\/\.aitask-scripts\/aitask_[a-z_]+\.sh:\*\)"/ {
            line = $0
            sub(/^.*aitask-scripts\//, "", line)
            sub(/:.*$/, "", line)
            if (line > helper) {
                print NR
                exit
            }
        }
    ' "$file")

    if [[ -z "$target_line" ]]; then
        warn "No alphabetically-later aitask helper line found in $file — manual insert required"
        return 1
    fi

    splice_line_before "$file" "$target_line" "\"Bash(./.aitask-scripts/${helper}:*)\","
}

# Insert an OpenCode bash permission entry at the alphabetical position.
# Used for touchpoint 5.
insert_opencode_helper_line() {
    local file="$1" helper="$2"

    local target_line
    target_line=$(awk -v helper="$helper" '
        /"\.\/\.aitask-scripts\/aitask_[a-z_]+\.sh \*": "allow"/ {
            line = $0
            sub(/^.*aitask-scripts\//, "", line)
            sub(/ \*.*$/, "", line)
            if (line > helper) {
                print NR
                exit
            }
        }
    ' "$file")

    if [[ -z "$target_line" ]]; then
        warn "No alphabetically-later aitask helper line found in $file — manual insert required"
        return 1
    fi

    splice_line_before "$file" "$target_line" "\"./.aitask-scripts/${helper} *\": \"allow\","
}

# Insert a TOML run_shell_command rule with a commandPrefix at the alphabetical position.
# Used for touchpoints 2, 4.
insert_toml_command_prefix_rule() {
    local file="$1" helper="$2"

    if grep -qF "commandPrefix = \"./.aitask-scripts/${helper}\"" "$file"; then
        return 0
    fi

    local target_line
    target_line=$(awk -v helper="$helper" '
        /^\[\[rule\]\]$/ {
            rule_line = NR
            in_block = 1
            block_kind = ""
            next
        }
        in_block && /^toolName = "run_shell_command"$/ {
            block_kind = "run_shell_command"
            next
        }
        in_block && block_kind == "run_shell_command" && /^commandPrefix = "\.\/\.aitask-scripts\/aitask_/ {
            line = $0
            sub(/^.*aitask-scripts\//, "", line)
            sub(/".*$/, "", line)
            if (line > helper) {
                print rule_line
                exit
            }
            in_block = 0
            next
        }
    ' "$file")

    if [[ -z "$target_line" ]]; then
        warn "No alphabetically-later commandPrefix rule found in $file — manual insert required"
        return 1
    fi

    local tmp
    tmp=$(mktemp "${TMPDIR:-/tmp}/audit_wrappers_toml_helper_XXXXXX")
    local before=$((target_line - 1))
    {
        head -n "$before" "$file"
        printf '[[rule]]\ntoolName = "run_shell_command"\ncommandPrefix = "./.aitask-scripts/%s"\ndecision = "allow"\npriority = 100\n\n' "$helper"
        tail -n "+${target_line}" "$file"
    } > "$tmp"
    mv "$tmp" "$file"
}

# apply-helper-whitelist <helper> [--touchpoint N]
# Inserts the helper into all 5 missing touchpoints, or just one if --touchpoint is given.
cmd_apply_helper_whitelist() {
    local helper="${1:-}"
    [[ -n "$helper" ]] || die "Usage: apply-helper-whitelist <helper> [--touchpoint N]"

    local single_touchpoint=""
    if [[ "${2:-}" == "--touchpoint" && -n "${3:-}" ]]; then
        single_touchpoint="$3"
    fi

    local touchpoint file
    for touchpoint in 1 2 3 4 5; do
        if [[ -n "$single_touchpoint" && "$touchpoint" != "$single_touchpoint" ]]; then
            continue
        fi
        if helper_present_in_touchpoint "$touchpoint" "$helper"; then
            continue
        fi
        file=$(touchpoint_file "$touchpoint")
        case "$touchpoint" in
            1|3)
                insert_claude_settings_helper_line "$file" "$helper" \
                    && printf 'WROTE:%d:%s:%s\n' "$touchpoint" "$helper" "$file"
                ;;
            2|4)
                insert_toml_command_prefix_rule "$file" "$helper" \
                    && printf 'WROTE:%d:%s:%s\n' "$touchpoint" "$helper" "$file"
                ;;
            5)
                insert_opencode_helper_line "$file" "$helper" \
                    && printf 'WROTE:%d:%s:%s\n' "$touchpoint" "$helper" "$file"
                ;;
        esac
    done
}

# -----------------------------------------------------------------------------
# Dispatcher
# -----------------------------------------------------------------------------

usage() {
    cat <<'EOF'
Usage: aitask_audit_wrappers.sh <subcommand> [args]

Phase 1 subcommands (skill wrapper audit + port):
  discover                              List GAP:<tree>:<skill> lines for every missing wrapper.
  discover-policy                       List POLICY_GAP:<runtime|seed>:<skill> lines for missing activate_skill rules.
  render-wrapper <tree> <skill_name>    Print a wrapper template to stdout.
  apply-wrapper <tree> <skill_name> [--force]
                                        Write the wrapper to its canonical path. Refuses to overwrite without --force.
  apply-policy <runtime|seed> <skill_name>
                                        Insert an activate_skill rule at the alphabetical position in the gemini policy file.

Phase 2 subcommands (helper-script whitelist audit):
  discover-helpers                      List HELPER:<basename> for each helper referenced by aitask-* skills or shared procedures.
  audit-helper-whitelist <helper>       Emit MISSING:<touchpoint>:<helper> for each of the 5 touchpoints not covered.
  apply-helper-whitelist <helper> [--touchpoint N]
                                        Insert the helper into missing touchpoints (or just touchpoint N if specified).

Touchpoints (per CLAUDE.md "Adding a New Helper Script"):
  1 = .claude/settings.local.json                            (Bash permission)
  2 = .gemini/policies/aitasks-whitelist.toml                (run_shell_command commandPrefix rule)
  3 = seed/claude_settings.local.json                        (mirror of #1)
  4 = seed/geminicli_policies/aitasks-whitelist.toml         (mirror of #2)
  5 = seed/opencode_config.seed.json                         (bash permission entry)

Trees (for --wrapper subcommands):
  gemini             .gemini/commands/<skill>.toml
  agents             .agents/skills/<skill>/SKILL.md       (unified Codex/Gemini)
  opencode-skill     .opencode/skills/<skill>/SKILL.md
  opencode-command   .opencode/commands/<skill>.md

All subcommands exit 0 on success and emit structured KEY:value lines on stdout.
EOF
}

main() {
    local cmd="${1:-}"
    shift || true

    case "$cmd" in
        discover)                cmd_discover "$@" ;;
        discover-policy)         cmd_discover_policy "$@" ;;
        render-wrapper)          cmd_render_wrapper "$@" ;;
        apply-wrapper)           cmd_apply_wrapper "$@" ;;
        apply-policy)            cmd_apply_policy "$@" ;;
        discover-helpers)        cmd_discover_helpers "$@" ;;
        audit-helper-whitelist)  cmd_audit_helper_whitelist "$@" ;;
        apply-helper-whitelist)  cmd_apply_helper_whitelist "$@" ;;
        ""|-h|--help|help)       usage ;;
        *) die "Unknown subcommand: $cmd (run --help for usage)" ;;
    esac
}

main "$@"
