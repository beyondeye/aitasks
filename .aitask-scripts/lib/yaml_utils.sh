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

# _yaml_scalar_value <raw-rhs>
# Clean a single YAML scalar value (everything to the right of "key:") for the
# block-mapping reader below. Strips surrounding matching quotes; for unquoted
# values, strips a YAML inline comment — the first whitespace-preceded '#' to
# end of line — then trailing whitespace. A '#' that is NOT preceded by
# whitespace (e.g. a filename `bug#3.png`) or one inside quotes is preserved.
# Does not handle escaped quotes inside double-quoted strings (out of scope).
_yaml_scalar_value() {
    local raw="$1" v
    # Strip leading whitespace.
    v="${raw#"${raw%%[![:space:]]*}"}"
    case "$v" in
        '"'*)  v="${v#\"}"; v="${v%%\"*}" ;;       # double-quoted: take up to next "
        "'"*)  v="${v#\'}"; v="${v%%\'*}" ;;       # single-quoted: take up to next '
        *)
            # Unquoted: drop an inline comment. sed's leftmost match anchors at
            # the FIRST `<whitespace>#`, so `bug#3.png` (no space before #) is
            # left intact while `local   # note` becomes `local`.
            v="$(printf '%s' "$v" | sed 's/[[:space:]]#.*$//')"
            # Strip trailing whitespace.
            v="${v%"${v##*[![:space:]]}"}"
            ;;
    esac
    printf '%s' "$v"
}

# _read_yaml_mappings_emit_field <present-flag> <key> <value>
# Print "key=value" only when the field was present on the item. Kept set-e safe
# (always returns 0). Helper for the flush below.
_read_yaml_mappings_emit_field() {
    [[ "$1" == 1 ]] || return 0
    printf '%s=%s\n' "$2" "$3"
}

# _read_yaml_mappings_set <"key: value">
# Parse one mapping line and store it into read_yaml_mappings' per-item parser
# state. Operates on that function's dynamically-scoped locals (f_*/p_*) — it is
# a private helper, only ever called from within read_yaml_mappings. Only the
# design §3 schema keys are recognized; any other key is ignored.
_read_yaml_mappings_set() {
    local kv="$1" key val
    if [[ "$kv" =~ ^[[:space:]]*([A-Za-z_][A-Za-z0-9_]*):[[:space:]]*(.*)$ ]]; then
        key="${BASH_REMATCH[1]}"
        val="$(_yaml_scalar_value "${BASH_REMATCH[2]}")"
        case "$key" in
            hash)     f_hash="$val";     p_hash=1 ;;
            name)     f_name="$val";     p_name=1 ;;
            mime)     f_mime="$val";     p_mime=1 ;;
            size)     f_size="$val";     p_size=1 ;;
            added_at) f_added_at="$val"; p_added_at=1 ;;
            backend)  f_backend="$val";  p_backend=1 ;;
            url)      f_url="$val";      p_url=1 ;;
            *) : ;;  # unknown key — reader knows only the design §3 schema
        esac
    fi
}

# _read_yaml_mappings_flush
# Emit the current item's present fields in schema order, preceded by a blank
# separator line for every record after the first. Operates on
# read_yaml_mappings' dynamically-scoped locals (private helper).
_read_yaml_mappings_flush() {
    [[ "$have_item" == true ]] || return 0
    if [[ "$first_record" == true ]]; then
        first_record=false
    else
        printf '\n'
    fi
    _read_yaml_mappings_emit_field "$p_hash"     hash     "$f_hash"
    _read_yaml_mappings_emit_field "$p_name"     name     "$f_name"
    _read_yaml_mappings_emit_field "$p_mime"     mime     "$f_mime"
    _read_yaml_mappings_emit_field "$p_size"     size     "$f_size"
    _read_yaml_mappings_emit_field "$p_added_at" added_at "$f_added_at"
    _read_yaml_mappings_emit_field "$p_backend"  backend  "$f_backend"
    _read_yaml_mappings_emit_field "$p_url"      url      "$f_url"
    have_item=false
    return 0
}

# read_yaml_mappings <file> <field>
# Read a block-style YAML list-of-mappings field (the task-attachments
# `attachments:` field, schema in aidocs/task_attachments_design.md §3) and emit
# a stable, parseable, escaping-free record stream. READ-ONLY (writing a mapping
# is t1030_2's concern).
#
# ── OUTPUT CONTRACT (siblings t1030_2 / t1030_3 depend on this) ───────────────
#   • One `key=value` line per present field, in SCHEMA ORDER:
#       hash, name, mime, size, added_at, backend, url
#     Only keys actually present on an item are emitted (no synthesized empties).
#   • Records (attachments) are separated by a single BLANK LINE. A consumer
#     accumulates `key=value` lines into a record until a blank line.
#   • Consumers MUST split each line on the FIRST '=' only: the key never
#     contains '=', so the value may freely contain '=', ';', spaces, or any
#     shell-significant text with NO escaping. (This is why the format is
#     newline-delimited rather than a single `k=v;k=v` line.)
#   • A missing field (or an empty/inline `[]` list) emits nothing, exit 0.
#   • `url: null` is preserved verbatim as `url=null`.
#
# Parsing notes: only the frontmatter block is scanned for markdown files (those
# opening with `---`). Full-line comments and blank lines inside the block are
# skipped; inline `<ws>#…` comments and surrounding quotes are handled by
# _yaml_scalar_value. Inline flow-style lists are not parsed (block style only).
read_yaml_mappings() {
    local file="$1" field="$2"
    [[ -f "$file" ]] || return 0

    local has_frontmatter=false first_line=""
    IFS= read -r first_line < "$file" 2>/dev/null || true
    [[ "$first_line" == "---" ]] && has_frontmatter=true

    local in_yaml=false in_list=false line
    # Per-item parser state (bash-3.2 safe: named vars, not an associative array).
    local have_item=false first_record=true
    local f_hash="" f_name="" f_mime="" f_size="" f_added_at="" f_backend="" f_url=""
    local p_hash=0 p_name=0 p_mime=0 p_size=0 p_added_at=0 p_backend=0 p_url=0

    while IFS= read -r line || [[ -n "$line" ]]; do
        # Frontmatter delimiters.
        if [[ "$has_frontmatter" == true && "$line" == "---" ]]; then
            if [[ "$in_yaml" == true ]]; then
                break                      # end of frontmatter → end of list
            else
                in_yaml=true
                continue
            fi
        fi
        # Outside the frontmatter block (markdown body): ignore.
        if [[ "$has_frontmatter" == true && "$in_yaml" == false ]]; then
            continue
        fi

        if [[ "$in_list" == false ]]; then
            # Find the field's list header (a top-level `<field>:`).
            [[ "$line" =~ ^${field}:[[:space:]]*(.*)$ ]] && in_list=true
            continue
        fi

        # Inside the list block.
        if [[ -z "${line//[[:space:]]/}" ]]; then
            continue                       # blank line — skip
        fi
        if [[ "$line" =~ ^[[:space:]]*# ]]; then
            continue                       # full-line comment — skip
        fi
        if [[ "$line" =~ ^[[:space:]]*-[[:space:]]+(.*)$ ]]; then
            # New list item: flush the previous, reset, parse the inline first key.
            _read_yaml_mappings_flush
            have_item=true
            f_hash=""; f_name=""; f_mime=""; f_size=""; f_added_at=""; f_backend=""; f_url=""
            p_hash=0;  p_name=0;  p_mime=0;  p_size=0;  p_added_at=0;  p_backend=0;  p_url=0
            _read_yaml_mappings_set "${BASH_REMATCH[1]}"
            continue
        fi
        if [[ "$line" =~ ^[[:space:]]+[A-Za-z_] ]]; then
            _read_yaml_mappings_set "$line"  # continuation field of current item
            continue
        fi
        # Dedent to a top-level key (or anything else) → the list ended.
        break
    done < "$file"

    _read_yaml_mappings_flush              # flush the final item
}
