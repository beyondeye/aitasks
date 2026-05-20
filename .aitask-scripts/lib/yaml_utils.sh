#!/usr/bin/env bash
# yaml_utils.sh - Canonical YAML readers shared by task_utils.sh and
# agentcrew_utils.sh. Pure bash (plus sed/grep/tr); no dependencies.
# Source this file; do not execute directly.
#
# read_yaml_field once lived independently in BOTH task_utils.sh and
# agentcrew_utils.sh. aitask_archive.sh sources both, so whichever was sourced
# last silently won — a latent footgun (t815). Keeping the YAML readers here,
# behind a double-source guard, makes each definition canonical.

# --- Guard against double-sourcing ---
[[ -n "${_AIT_YAML_UTILS_LOADED:-}" ]] && return 0
_AIT_YAML_UTILS_LOADED=1

# Join YAML flow-sequence values that wrap across multiple physical lines.
# Reads YAML text on stdin; emits it with any "key: [ ... ]" whose brackets
# span multiple physical lines collapsed onto a single line. Continuation
# lines are appended with a separating space (harmless — list parsers strip
# all whitespace). Bracket depth is tracked, so a wrap of any length folds
# back to one line.
#
# PyYAML's yaml.dump (used by the board via task_yaml.py) wraps a flow list
# once it exceeds ~80 columns. The line-by-line frontmatter parsers below
# match each physical line against a key regex, so unjoined continuation
# lines are silently dropped — this filter must run before that matching.
join_yaml_flow_lists() {
    local line buffer="" depth=0 opens closes
    while IFS= read -r line || [[ -n "$line" ]]; do
        if [[ $depth -gt 0 ]]; then
            buffer+=" $line"
        else
            buffer="$line"
        fi
        # Count unbalanced brackets across the accumulated buffer.
        opens="${buffer//[^\[]/}"
        closes="${buffer//[^\]]/}"
        depth=$(( ${#opens} - ${#closes} ))
        if [[ $depth -le 0 ]]; then
            printf '%s\n' "$buffer"
            buffer=""
            depth=0
        fi
    done
    [[ -n "$buffer" ]] && printf '%s\n' "$buffer"
    return 0
}

# read_yaml_field <file> <field>
# Extracts a scalar YAML field's value, returned as a single line.
#   - Markdown task/plan files open with a `---` frontmatter delimiter; only
#     the frontmatter block is searched.
#   - Plain YAML files (e.g. crew *_status.yaml) have no frontmatter; the
#     whole file is searched.
# A flow list wrapped across multiple physical lines (PyYAML wraps past ~80
# columns) is rejoined via join_yaml_flow_lists, so list-valued fields such as
# folded_tasks / verifies are returned whole rather than truncated.
# Prints an empty line and returns 0 if the field is not found.
read_yaml_field() {
    local file_path="$1"
    local field_name="$2"
    local in_yaml=false has_frontmatter=false line first_line=""

    # A markdown task/plan file opens with a `---` frontmatter delimiter;
    # a plain YAML file (crew *_status.yaml) does not.
    IFS= read -r first_line < "$file_path" 2>/dev/null || true
    [[ "$first_line" == "---" ]] && has_frontmatter=true

    while IFS= read -r line; do
        if [[ "$has_frontmatter" == true && "$line" == "---" ]]; then
            if [[ "$in_yaml" == true ]]; then
                break
            else
                in_yaml=true
                continue
            fi
        fi
        if [[ ( "$has_frontmatter" == false || "$in_yaml" == true ) \
              && "$line" =~ ^${field_name}:[[:space:]]*(.*) ]]; then
            local value="${BASH_REMATCH[1]}"
            # Trim whitespace
            value=$(echo "$value" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')
            echo "$value"
            return
        fi
    # join_yaml_flow_lists rejoins multi-line flow lists (e.g. a wrapped
    # children_to_implement / verifies) so the field value is matched whole.
    done < <(join_yaml_flow_lists < "$file_path")

    echo ""
}

# read_yaml_list <file> <field>
# Extracts a YAML list field as newline-separated values.
# Handles both inline [a, b] and block list formats.
read_yaml_list() {
    local file="$1"
    local field="$2"

    # Capture the field's value, joining a flow list wrapped across multiple
    # physical lines (PyYAML wraps past ~80 columns) onto a single line.
    local value="" capturing=false depth=0 fline opens closes
    while IFS= read -r fline; do
        if [[ "$capturing" == false ]]; then
            [[ "$fline" == "${field}:"* ]] || continue
            capturing=true
            value="${fline#"${field}":}"
        else
            value="$value $fline"
        fi
        opens="${value//[^\[]/}"
        closes="${value//[^\]]/}"
        depth=$(( ${#opens} - ${#closes} ))
        [[ $depth -le 0 ]] && break
    done < "$file"
    [[ "$capturing" == false ]] && return 0

    # Strip leading whitespace left by the "${field}:" prefix removal.
    value="${value#"${value%%[![:space:]]*}"}"

    # Inline format: [a, b, c]
    if [[ "$value" =~ ^\[.*\]$ ]]; then
        echo "$value" | tr -d "[]'\"" | tr ',' '\n' | sed 's/^[[:space:]]*//' | sed 's/[[:space:]]*$//' | grep -v '^$'
        return 0
    fi

    # Block format: lines starting with "- "
    local in_list=false
    while IFS= read -r fline; do
        if [[ "$fline" == "${field}:"* ]]; then
            in_list=true
            continue
        fi
        if $in_list; then
            if [[ "$fline" =~ ^[[:space:]]*-[[:space:]] ]]; then
                echo "$fline" | sed 's/^[[:space:]]*-[[:space:]]*//'
            else
                break
            fi
        fi
    done < "$file"
}
