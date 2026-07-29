#!/usr/bin/env bash
# aitask_audit_wrappers.sh — Audit and port aitask skill wrappers across code-agent trees.
#
# Source of truth: .claude/skills/aitask-*/SKILL.md
# Wrapper trees:
#   - .agents/skills/<name>/SKILL.md
#   - .opencode/skills/<name>/SKILL.md
#   - .opencode/commands/<name>.md
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
readonly TREE_AGENTS_SKILLS=".agents/skills"
readonly TREE_OPENCODE_SKILLS=".opencode/skills"
readonly TREE_OPENCODE_COMMANDS=".opencode/commands"

# -----------------------------------------------------------------------------
# Skill discovery
# -----------------------------------------------------------------------------

# True for a rendered per-profile variant dir name (`aitask-pick-fast-`,
# `aitask-pickrem-remote-`, …). Rendered dirs end with a trailing hyphen — the
# "generated" marker the `*-/` gitignore globs rely on (see
# aidocs/framework/stub-skill-pattern.md and lib/agent_skills_paths.sh). Authoring
# dirs never end with one, so this cleanly separates source from artifact.
_is_rendered_variant() {
    [[ "$1" == *- ]]
}

# Emit the names of every aitask-* skill in the source of truth.
list_source_skills() {
    local entry name
    for entry in "$SOURCE_SKILLS_DIR"/aitask-*; do
        [[ -d "$entry" ]] || continue
        [[ -f "$entry/SKILL.md" ]] || continue
        name="${entry##*/}"
        _is_rendered_variant "$name" && continue
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
        agents)            printf '%s\n' "${TREE_AGENTS_SKILLS}/${skill}/SKILL.md" ;;
        opencode-skill)    printf '%s\n' "${TREE_OPENCODE_SKILLS}/${skill}/SKILL.md" ;;
        opencode-command)  printf '%s\n' "${TREE_OPENCODE_COMMANDS}/${skill}.md" ;;
        *) die "Unknown tree: $tree" ;;
    esac
}

# tree_root <root> <tree> -> echoes the directory that holds that tree's wrappers.
tree_root() {
    local root="$1" tree="$2"
    case "$tree" in
        agents)            printf '%s\n' "${root}/${TREE_AGENTS_SKILLS}" ;;
        opencode-skill)    printf '%s\n' "${root}/${TREE_OPENCODE_SKILLS}" ;;
        opencode-command)  printf '%s\n' "${root}/${TREE_OPENCODE_COMMANDS}" ;;
        *) die "Unknown tree: $tree" ;;
    esac
}

# list_wrapper_skills <root> <tree> -> names of the aitask-* wrappers in that tree.
# Rendered per-profile variants are excluded (see _is_rendered_variant): they are
# generated artifacts, not stubs. Counting them is exactly what makes a naive
# `git ls-files '.opencode/skills/aitask-*/SKILL.md'` report 30 where there are 28
# wrappers.
list_wrapper_skills() {
    local root="$1" tree="$2" dir entry name
    dir="$(tree_root "$root" "$tree")"
    [[ -d "$dir" ]] || return 0
    for entry in "$dir"/aitask-*; do
        [[ -e "$entry" ]] || continue
        name="${entry##*/}"
        case "$tree" in
            agents|opencode-skill)
                [[ -d "$entry" && -f "$entry/SKILL.md" ]] || continue
                ;;
            opencode-command)
                [[ -f "$entry" && "$name" == *.md ]] || continue
                name="${name%.md}"
                ;;
        esac
        _is_rendered_variant "$name" && continue
        printf '%s\n' "$name"
    done | sort
}

# parity [--strict] [<root>] -> cross-tree wrapper-set check.
#
# The three ported wrapper trees are authored independently, so requiring
# identical membership is a ground truth that does NOT come from any one of them.
# This is the check that catches the realistic omission: a skill added to some but
# not all trees (t1210_3 gave aitask-trail a Codex stub and an OpenCode command
# wrapper but no OpenCode skill-dir stub; see t1317 / t1325).
#
# Emits, per case:
#   PARITY_GAP:<tree>:<skill>  a skill present in >=1 PRESENT tree, missing from
#                              this PRESENT tree.
#   ORPHAN:<skill>             a wrapper with no source-of-truth
#                              .claude/skills/<skill>/SKILL.md.
#
# Tree-presence rule: a tree whose root directory does not exist means that agent
# is simply not installed in this project (a Claude-only consumer install), so it
# is dropped from the comparison instead of reporting every skill as missing.
# With fewer than two trees present nothing can disagree, so no PARITY_GAP can be
# emitted — the ORPHAN check still runs while at least one tree is present.
#
# Residual limit (deliberate): a skill removed from ALL trees at once is invisible
# here. That is a deliberate removal, not the omission this guard targets.
#
# Exit status: 0 by default even when findings were emitted, matching the
# `discover` / `audit-helper-whitelist` reporters and this script's documented
# "all subcommands exit 0" contract. With --strict, exit 2 when any line was
# emitted — deliberately not 1, which die() already uses for usage/infrastructure
# errors, so a caller can distinguish "findings" from "could not run".
cmd_parity() {
    local strict=false root="" arg
    for arg in "$@"; do
        case "$arg" in
            --strict) strict=true ;;
            -*)       die "parity: unknown option: $arg" ;;
            *)        root="$arg" ;;
        esac
    done
    root="${root:-$REPO_ROOT}"
    root="${root%/}"

    local tree present_trees=() findings=0
    for tree in agents opencode-skill opencode-command; do
        [[ -d "$(tree_root "$root" "$tree")" ]] && present_trees+=("$tree")
    done

    # Union of every wrapper name seen across the present trees.
    local union
    union="$(
        for tree in ${present_trees[@]+"${present_trees[@]}"}; do
            list_wrapper_skills "$root" "$tree"
        done | sort -u
    )"
    [[ -n "$union" ]] || return 0

    local skill path
    while IFS= read -r skill; do
        [[ -n "$skill" ]] || continue
        # PARITY_GAP needs at least two present trees to be meaningful.
        if (( ${#present_trees[@]} >= 2 )); then
            for tree in "${present_trees[@]}"; do
                path="${root}/$(wrapper_path "$tree" "$skill")"
                if [[ ! -f "$path" ]]; then
                    printf 'PARITY_GAP:%s:%s\n' "$tree" "$skill"
                    findings=$((findings + 1))
                fi
            done
        fi
        if [[ ! -f "${root}/${SOURCE_SKILLS_DIR}/${skill}/SKILL.md" ]]; then
            printf 'ORPHAN:%s\n' "$skill"
            findings=$((findings + 1))
        fi
    done <<< "$union"

    if [[ "$strict" == true ]] && (( findings > 0 )); then
        return 2
    fi
    return 0
}

# discover -> emit GAP:<tree>:<skill> for every missing wrapper.
cmd_discover() {
    local skill tree path
    while IFS= read -r skill; do
        for tree in agents opencode-skill opencode-command; do
            path=$(wrapper_path "$tree" "$skill")
            if [[ ! -f "$path" ]]; then
                printf 'GAP:%s:%s\n' "$tree" "$skill"
            fi
        done
    done < <(list_source_skills)
}

# -----------------------------------------------------------------------------
# Wrapper templates
# -----------------------------------------------------------------------------

# True if this skill is templated (has a SKILL.md.j2 entry-point template).
# Templated skills dispatch through the profile-aware renderer; their wrappers
# must be §3b/§3d-style stubs, not the legacy "Source of Truth" pointer.
_skill_is_templated() {
    local skill="$1"
    [[ -f "${SOURCE_SKILLS_DIR}/${skill}/SKILL.md.j2" ]]
}

render_agents_skill() {
    local skill="$1" description="$2" arguments="$3"

    if _skill_is_templated "$skill"; then
        local resolver_key="${skill#aitask-}"
        cat <<EOF
---
name: ${skill}
description: ${description}
---

This is a profile-aware skill stub. Execute these steps in order, then stop:

1. **Resolve active profile.** Parse ARGUMENTS for \`--profile <name>\`. If
   found, use that as \`<profile>\` and remove the \`--profile <name>\` pair
   from ARGUMENTS. Otherwise run:
   \`./.aitask-scripts/aitask_skill_resolve_profile.sh ${resolver_key}\`
   and use the single-line stdout as \`<profile>\`.

2. **Render per-profile variant.** Run:
   \`./.aitask-scripts/aitask_skill_render.sh ${skill} --profile <profile> --agent codex\`
   No-op if the per-profile SKILL.md is already up to date.

3. **Dispatch via Read-and-follow.** Read the file at
   \`.agents/skills/${skill}-<profile>-codex-/SKILL.md\` and execute its
   instructions as if they were this skill, forwarding the (possibly
   stripped) ARGUMENTS unchanged.
EOF
        return
    fi

    cat <<EOF
---
name: ${skill}
description: ${description}
---

## Source of Truth

This is a Codex CLI skill wrapper. The authoritative skill definition is:

**\`.claude/skills/${skill}/SKILL.md\`**

Read that file and follow its complete workflow.

**If you are Codex CLI:** For tool mapping and adaptations, read **\`.agents/skills/codex_tool_mapping.md\`**.

## Arguments

${arguments}
EOF
}

render_opencode_skill() {
    local skill="$1" description="$2" arguments="$3"

    if _skill_is_templated "$skill"; then
        local resolver_key="${skill#aitask-}"
        cat <<EOF
---
name: ${skill}
description: ${description}
---

@.opencode/skills/opencode_planmode_prereqs.md
@.opencode/skills/opencode_tool_mapping.md

This is a profile-aware skill stub. Execute these steps in order, then stop:

1. **Resolve active profile.** Parse \$ARGUMENTS for \`--profile <name>\`.
   If found, use that as \`<profile>\` and remove the \`--profile <name>\`
   pair. Otherwise run:
   \`./.aitask-scripts/aitask_skill_resolve_profile.sh ${resolver_key}\`
   and use the single-line stdout as \`<profile>\`.

2. **Render per-profile variant.** Run:
   \`./.aitask-scripts/aitask_skill_render.sh ${skill} --profile <profile> --agent opencode\`

3. **Dispatch via Read-and-follow.** Read the file at
   \`.opencode/skills/${skill}-<profile>-/SKILL.md\` and execute its
   instructions as if they were this command, forwarding the (possibly
   stripped) \$ARGUMENTS unchanged.
EOF
        return
    fi

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
# Phase 2: helper-script whitelist audit
# -----------------------------------------------------------------------------

# Map a touchpoint number (1-7) to its file path. IDs 2 and 5 are retired
# (formerly the gemini runtime/seed policies); the numeric IDs are kept
# stable so other touchpoints don't silently shift.
touchpoint_file() {
    case "$1" in
        1) printf '%s\n' ".claude/settings.local.json" ;;
        3) printf '%s\n' ".codex/rules/default.rules" ;;
        4) printf '%s\n' "seed/claude_settings.local.json" ;;
        6) printf '%s\n' "seed/codex_rules.default.rules" ;;
        7) printf '%s\n' "seed/opencode_config.seed.json" ;;
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
        1|4) grep -qF "Bash(./.aitask-scripts/${helper}:*)" "$file" ;;
        3|6) grep -qF "pattern = [\"./.aitask-scripts/${helper}\"]" "$file" ;;
        7)   grep -qF "\"./.aitask-scripts/${helper} *\": \"allow\"" "$file" ;;
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
    for touchpoint in 1 3 4 6 7; do
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
# Used for touchpoint 7.
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

# Insert a Codex prefix_rule at the alphabetical position.
# Used for touchpoints 3, 6.
insert_codex_prefix_rule() {
    local file="$1" helper="$2"

    mkdir -p "$(dirname "$file")"
    touch "$file"

    if grep -qF "pattern = [\"./.aitask-scripts/${helper}\"]" "$file"; then
        return 0
    fi

    local target_line
    target_line=$(awk -v helper="$helper" '
        /^prefix_rule\(pattern = \["\.\/\.aitask-scripts\/aitask_[a-z_]+\.sh"\]/ {
            line = $0
            sub(/^.*aitask-scripts\//, "", line)
            sub(/".*$/, "", line)
            if (line > helper) {
                print NR
                exit
            }
        }
    ' "$file")

    local tmp
    tmp=$(mktemp "${TMPDIR:-/tmp}/audit_wrappers_codex_rule_XXXXXX")
    if [[ -n "$target_line" ]]; then
        local before=$((target_line - 1))
        {
            head -n "$before" "$file"
            printf 'prefix_rule(pattern = ["./.aitask-scripts/%s"], decision = "allow", justification = "Aitasks helper script")\n' "$helper"
            tail -n "+${target_line}" "$file"
        } > "$tmp"
    else
        {
            cat "$file"
            if [[ -s "$file" ]]; then
                printf '\n'
            fi
            printf 'prefix_rule(pattern = ["./.aitask-scripts/%s"], decision = "allow", justification = "Aitasks helper script")\n' "$helper"
        } > "$tmp"
    fi
    mv "$tmp" "$file"
}

# apply-helper-whitelist <helper> [--touchpoint N]
# Inserts the helper into all missing touchpoints, or just one if --touchpoint is given.
cmd_apply_helper_whitelist() {
    local helper="${1:-}"
    [[ -n "$helper" ]] || die "Usage: apply-helper-whitelist <helper> [--touchpoint N]"

    local single_touchpoint=""
    if [[ "${2:-}" == "--touchpoint" && -n "${3:-}" ]]; then
        single_touchpoint="$3"
    fi

    local touchpoint file
    for touchpoint in 1 3 4 6 7; do
        if [[ -n "$single_touchpoint" && "$touchpoint" != "$single_touchpoint" ]]; then
            continue
        fi
        if helper_present_in_touchpoint "$touchpoint" "$helper"; then
            continue
        fi
        file=$(touchpoint_file "$touchpoint")
        case "$touchpoint" in
            1|4)
                insert_claude_settings_helper_line "$file" "$helper" \
                    && printf 'WROTE:%d:%s:%s\n' "$touchpoint" "$helper" "$file"
                ;;
            3|6)
                insert_codex_prefix_rule "$file" "$helper" \
                    && printf 'WROTE:%d:%s:%s\n' "$touchpoint" "$helper" "$file"
                ;;
            7)
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
  parity [--strict] [<root>]            Cross-tree wrapper-set check. Emits PARITY_GAP:<tree>:<skill>
                                        for a skill present in some but not all installed wrapper
                                        trees, and ORPHAN:<skill> for a wrapper with no source-of-truth
                                        .claude/skills/<skill>/SKILL.md. Trees whose root dir is absent
                                        are treated as "agent not installed" and skipped. <root>
                                        defaults to the repo root; pass one to check a fixture tree.
  render-wrapper <tree> <skill_name>    Print a wrapper template to stdout.
  apply-wrapper <tree> <skill_name> [--force]
                                        Write the wrapper to its canonical path. Refuses to overwrite without --force.

Phase 2 subcommands (helper-script whitelist audit):
  discover-helpers                      List HELPER:<basename> for each helper referenced by aitask-* skills or shared procedures.
  audit-helper-whitelist <helper>       Emit MISSING:<touchpoint>:<helper> for each helper touchpoint not covered.
  apply-helper-whitelist <helper> [--touchpoint N]
                                        Insert the helper into missing touchpoints (or just touchpoint N if specified).

Touchpoints (per CLAUDE.md "Adding a New Helper Script"; IDs 2 and 5 retired):
  1 = .claude/settings.local.json                            (Bash permission)
  3 = .codex/rules/default.rules                             (prefix_rule allow)
  4 = seed/claude_settings.local.json                        (mirror of #1)
  6 = seed/codex_rules.default.rules                         (mirror of #3)
  7 = seed/opencode_config.seed.json                         (bash permission entry)

Trees (for --wrapper subcommands):
  agents             .agents/skills/<skill>/SKILL.md       (Codex)
  opencode-skill     .opencode/skills/<skill>/SKILL.md
  opencode-command   .opencode/commands/<skill>.md

All subcommands exit 0 on success and emit structured KEY:value lines on stdout.
Findings are reported as lines, not as an exit status. The single exception is
`parity --strict`, which exits 2 when it emitted any finding (2, not 1, so it
stays distinguishable from a usage/infrastructure error).
EOF
}

main() {
    local cmd="${1:-}"
    shift || true

    case "$cmd" in
        discover)                cmd_discover "$@" ;;
        parity)                  cmd_parity "$@" ;;
        render-wrapper)          cmd_render_wrapper "$@" ;;
        apply-wrapper)           cmd_apply_wrapper "$@" ;;
        discover-helpers)        cmd_discover_helpers "$@" ;;
        audit-helper-whitelist)  cmd_audit_helper_whitelist "$@" ;;
        apply-helper-whitelist)  cmd_apply_helper_whitelist "$@" ;;
        ""|-h|--help|help)       usage ;;
        *) die "Unknown subcommand: $cmd (run --help for usage)" ;;
    esac
}

main "$@"
