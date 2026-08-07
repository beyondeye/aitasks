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

# ── CLOSED-PIPE WRITE CONTRACT (t1444) ──────────────────────────────────────
# Stated once here; the emitters below reference it rather than repeating it.
#
# THE CONDITION. Every streaming emitter in this file writes into consumers that
# legitimately stop early: read_yaml_field returns mid-stream (line ~83) while
# join_yaml_flow_lists is still writing into its process substitution, and
# `| head -1` / `| grep -q` callers do the same for read_yaml_list and
# read_yaml_mappings. Under a DEFAULT SIGPIPE disposition the producer is killed
# silently — which is why this is invisible in an interactive shell. But agent
# harnesses built on Node/Python leave SIGPIPE as SIG_IGN, and child processes
# INHERIT that disposition, so the producer is not killed: every remaining write
# returns EPIPE and bash (or sed/tr/grep) reports it, once per remaining item,
# burying the structured output these helpers exist to emit. A script cannot
# repair this from the inside — a signal inherited as SIG_IGN can be neither
# trapped nor reset, so `trap - PIPE` does not help. Stopping on the first
# failed write is the only fix.
#
# THE BOUNDARY. Suppressing a write error is only safe where a failed write can
# ONLY mean "the reader is gone". Every in-tree call site of these emitters is a
# command substitution, a process substitution, or a pipeline — never a regular
# file. But this library is installer-synced into downstream projects and cannot
# bind future or external callers, so the premise is ENFORCED rather than
# assumed: _yaml_init_write_guard disables suppression when stdout is a regular
# file, where a failed write means a genuine error (ENOSPC, quota) that must
# stay loud and must never become silent truncation.
#
# Consequently a `2>/dev/null` below is never blanket error-swallowing. If you
# add an emitter here, route its writes through _yaml_emit.
#
# THE OTHER HALF: BEING KILLED. Guarding the write only helps if the write is
# reached. Under the DEFAULT SIGPIPE disposition the producer is not merely
# refused — it is KILLED, exiting 141 before any `||` can run. In a pipeline the
# emitter is a subshell, so under `set -o pipefail` that 141 becomes the whole
# pipeline's status even when the reader succeeded. A caller like
# `read_yaml_mappings "$f" artifacts | grep -q '^handle='` therefore reports "no
# artifacts" whenever the producer outlives grep -q — measured with the
# pre-t1444 reader: 60/60 correct detections for a task with 1 artifact record,
# 0/60 with 12. That silently skipped aitask_fold_mark.sh's attachment/artifact
# transfer for any non-trivial task.
#
# So each PUBLIC reader below is a thin wrapper that ignores SIGPIPE before
# delegating to its `_*_impl`, converting the kill into the EPIPE write error
# _yaml_emit already handles.
#
# It does that ONLY when `BASH_SUBSHELL > 0`. That is not a heuristic: an
# early-exiting reader can only exist when we are already in a subshell — a
# pipeline element, `$(...)` and `<(...)` all report BASH_SUBSHELL > 0 — and a
# subshell's trap change cannot reach its parent, so it is discarded on exit.
# At BASH_SUBSHELL == 0 the reader shares the caller's shell and we touch
# nothing, which makes leaking SIG_IGN into a caller structurally impossible
# rather than merely undone afterwards.
#
# Deliberately NOT save-and-restore via `_saved="$(trap -p PIPE)"`: that costs a
# fork per call on the hottest reader in the framework, and a command
# substitution is not guaranteed to report the caller's handler on older bash
# (this repo targets bash 3.2 — see the `bash-3.2 safe` note below). Not needing
# the value at all is the stronger property.
#
# KNOWN LIMIT: a bare top-level call whose stdout is a pipe from the PARENT
# PROCESS is not protected (BASH_SUBSHELL == 0), so a parent that stops reading
# can still kill it — the historical behaviour. No in-tree call site does this;
# every one is `$(...)`, `<(...)` or a pipeline.
#
# (A disposition INHERITED as SIG_IGN cannot be trapped or reset, so the `trap`
# is correctly a no-op in a harness that already ignores SIGPIPE.)

# _yaml_init_write_guard
# Decide ONCE per public-reader call whether the closed-pipe write guard
# applies, and assign the caller's dynamically-scoped `_yaml_guard_writes` local
# (the same dynamic-scope pattern as _read_yaml_mappings_set's f_*/p_* locals).
# Fail-safe direction: where /dev/fd/1 is unavailable the test is false and the
# guard stays ACTIVE, so the storm fix still works and only the regular-file
# diagnostic is lost.
_yaml_init_write_guard() {
    _yaml_guard_writes=1
    if [[ -f /dev/fd/1 ]]; then _yaml_guard_writes=""; fi
    return 0
}

# _yaml_emit <line>
# The single write seam for every streaming emitter in this file. Returns 1 ONLY
# when the write failed AND the guard is active — i.e. the reader is gone and
# the caller should stop emitting. Returns 0 in every other case, so callers
# stay set -e safe.
_yaml_emit() {
    if [[ -n "${_yaml_guard_writes:-}" ]]; then
        printf '%s\n' "$1" 2>/dev/null || return 1
        return 0
    fi
    # Unguarded (regular-file stdout): let the diagnostic through and keep the
    # historical continue-on-error behaviour, so a real failure is reported
    # rather than converted into silent truncation.
    printf '%s\n' "$1" || true
    return 0
}

# Join YAML flow-sequence values that wrap across multiple physical lines.
# Reads YAML text on stdin; emits it with any "key: [ ... ]" whose brackets
# span multiple physical lines collapsed onto a single line. Continuation
# lines are appended with a separating space (harmless — list parsers strip
# all whitespace). Bracket depth is tracked, so a wrap of any length folds
# back to one line.
#
# PyYAML's yaml.dump (used by the board via lib/task_yaml.py) wraps a flow list
# once it exceeds ~80 columns. The line-by-line frontmatter parsers below
# match each physical line against a key regex, so unjoined continuation
# lines are silently dropped — this filter must run before that matching.
join_yaml_flow_lists() {
    # See "THE OTHER HALF: BEING KILLED" in the header. SIGPIPE is ignored ONLY
    # inside a subshell, which is exactly where an early-exiting reader can
    # exist: a pipeline element, $(...) and <(...) all report BASH_SUBSHELL > 0,
    # and the change dies with the subshell. At BASH_SUBSHELL == 0 the reader
    # shares the caller's shell, so we touch nothing at all — leaking SIG_IGN
    # into a caller is then structurally impossible rather than merely undone
    # afterwards. This also needs no `$(trap -p PIPE)` capture, which costs a
    # fork and is not guaranteed to report the caller's handler from inside a
    # command substitution on older bash (this repo targets bash 3.2).
    if [[ ${BASH_SUBSHELL:-0} -gt 0 ]]; then trap '' PIPE; fi
    _join_yaml_flow_lists_impl   # reads stdin; no arguments
}

_join_yaml_flow_lists_impl() {
    local line buffer="" depth=0 opens closes
    local _yaml_guard_writes=""; _yaml_init_write_guard
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
            # Closed-pipe stop — see the write contract at the top of this file.
            _yaml_emit "$buffer" || return 0
            buffer=""
            depth=0
        fi
    done
    if [[ -n "$buffer" ]]; then
        _yaml_emit "$buffer" || return 0
    fi
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
    # See "THE OTHER HALF: BEING KILLED" in the header. SIGPIPE is ignored ONLY
    # inside a subshell, which is exactly where an early-exiting reader can
    # exist: a pipeline element, $(...) and <(...) all report BASH_SUBSHELL > 0,
    # and the change dies with the subshell. At BASH_SUBSHELL == 0 the reader
    # shares the caller's shell, so we touch nothing at all — leaking SIG_IGN
    # into a caller is then structurally impossible rather than merely undone
    # afterwards. This also needs no `$(trap -p PIPE)` capture, which costs a
    # fork and is not guaranteed to report the caller's handler from inside a
    # command substitution on older bash (this repo targets bash 3.2).
    if [[ ${BASH_SUBSHELL:-0} -gt 0 ]]; then trap '' PIPE; fi
    _read_yaml_field_impl "$@"
}

_read_yaml_field_impl() {
    local file_path="$1"
    local field_name="$2"
    local in_yaml=false has_frontmatter=false line first_line=""
    local _yaml_guard_writes=""; _yaml_init_write_guard

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
            # `|| true` + explicit `return 0`: the former bare `return`
            # propagated echo's status, so a closed pipe leaked out as a
            # non-zero read_yaml_field.
            _yaml_emit "$value" || true
            return 0
        fi
    # join_yaml_flow_lists rejoins multi-line flow lists (e.g. a wrapped
    # children_to_implement / verifies) so the field value is matched whole.
    done < <(join_yaml_flow_lists < "$file_path")

    _yaml_emit "" || true
    return 0
}

# read_yaml_list <file> <field>
# Extracts a YAML list field as newline-separated values.
# Handles both inline [a, b] and block list formats.
read_yaml_list() {
    # See "THE OTHER HALF: BEING KILLED" in the header. SIGPIPE is ignored ONLY
    # inside a subshell, which is exactly where an early-exiting reader can
    # exist: a pipeline element, $(...) and <(...) all report BASH_SUBSHELL > 0,
    # and the change dies with the subshell. At BASH_SUBSHELL == 0 the reader
    # shares the caller's shell, so we touch nothing at all — leaking SIG_IGN
    # into a caller is then structurally impossible rather than merely undone
    # afterwards. This also needs no `$(trap -p PIPE)` capture, which costs a
    # fork and is not guaranteed to report the caller's handler from inside a
    # command substitution on older bash (this repo targets bash 3.2).
    if [[ ${BASH_SUBSHELL:-0} -gt 0 ]]; then trap '' PIPE; fi
    _read_yaml_list_impl "$@"
}

_read_yaml_list_impl() {
    local file="$1"
    local field="$2"

    # Capture the field's value, joining a flow list wrapped across multiple
    # physical lines (PyYAML wraps past ~80 columns) onto a single line.
    local value="" capturing=false depth=0 fline opens closes
    local _yaml_guard_writes=""; _yaml_init_write_guard
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
        # Pure-bash equivalent of the former five-process pipeline
        #   echo | tr -d "[]'\"" | tr ',' '\n' | sed 's/^[[:space:]]*//' \
        #        | sed 's/[[:space:]]*$//' | grep -v '^$'
        # Each of those processes reported its own EPIPE independently, so there
        # was no single site to guard — the closed-pipe stop (see the write
        # contract at the top of this file) is only expressible without the
        # forks. Also saves five forks on the most common list-read path.
        local _clean="${value//[\[\]\'\"]/}" _item
        while [[ -n "$_clean" ]]; do
            _item="${_clean%%,*}"
            if [[ "$_item" == "$_clean" ]]; then _clean=""; else _clean="${_clean#*,}"; fi
            _item="${_item#"${_item%%[![:space:]]*}"}"   # was sed 's/^[[:space:]]*//'
            _item="${_item%"${_item##*[![:space:]]}"}"   # was sed 's/[[:space:]]*$//'
            [[ -n "$_item" ]] || continue                # was grep -v '^$'
            _yaml_emit "$_item" || return 0
        done
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
            if [[ "$fline" =~ ^[[:space:]]*-[[:space:]]+(.*)$ ]]; then
                # The capture is byte-identical to the former
                # `sed 's/^[[:space:]]*-[[:space:]]*//'` — POSIX ERE
                # leftmost-longest makes `[[:space:]]+` greedy — and `sed`'s own
                # "couldn't flush stdout" error could not be suppressed from
                # inside this loop. Closed-pipe stop: see the write contract at
                # the top of this file. Also saves a fork per list item.
                _yaml_emit "${BASH_REMATCH[1]}" || break
            else
                break
            fi
        fi
    done < "$file"
    return 0
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
    # Stop at the FIRST failed write. This guard is what makes that true: a
    # record makes nine sequential calls here, so merely recording the flag
    # would leave up to eight further failed writes per record — diagnostics
    # hidden, but emission not actually stopped.
    [[ -z "$_yaml_pipe_closed" ]] || return 0
    [[ "$1" == 1 ]] || return 0
    # This helper is contractually set -e safe (always returns 0), so a closed
    # pipe is signalled back through the caller's dynamically-scoped
    # _yaml_pipe_closed local rather than through an exit status.
    _yaml_emit "$2=$3" || _yaml_pipe_closed=1
    return 0
}

# _read_yaml_mappings_set <"key: value">
# Parse one mapping line and store it into read_yaml_mappings' per-item parser
# state. Operates on that function's dynamically-scoped locals (f_*/p_*) — it is
# a private helper, only ever called from within read_yaml_mappings. Only the
# known schema keys are recognized — the attachment schema (task_attachments
# design §3) plus the artifact schema (handle/kind — t1076_2, unified artifact
# design §4); any other key is ignored.
_read_yaml_mappings_set() {
    local kv="$1" key val
    if [[ "$kv" =~ ^[[:space:]]*([A-Za-z_][A-Za-z0-9_]*):[[:space:]]*(.*)$ ]]; then
        key="${BASH_REMATCH[1]}"
        val="$(_yaml_scalar_value "${BASH_REMATCH[2]}")"
        case "$key" in
            handle)   f_handle="$val";   p_handle=1 ;;
            kind)     f_kind="$val";     p_kind=1 ;;
            hash)     f_hash="$val";     p_hash=1 ;;
            name)     f_name="$val";     p_name=1 ;;
            mime)     f_mime="$val";     p_mime=1 ;;
            size)     f_size="$val";     p_size=1 ;;
            added_at) f_added_at="$val"; p_added_at=1 ;;
            backend)  f_backend="$val";  p_backend=1 ;;
            url)      f_url="$val";      p_url=1 ;;
            *) : ;;  # unknown key — reader knows only the schemas above
        esac
    fi
}

# _read_yaml_mappings_flush
# Emit the current item's present fields in schema order, preceded by a blank
# separator line for every record after the first. Operates on
# read_yaml_mappings' dynamically-scoped locals (private helper).
_read_yaml_mappings_flush() {
    [[ "$have_item" == true ]] || return 0
    if [[ -n "$_yaml_pipe_closed" ]]; then have_item=false; return 0; fi
    if [[ "$first_record" == true ]]; then
        first_record=false
    elif ! _yaml_emit ""; then
        _yaml_pipe_closed=1; have_item=false; return 0
    fi
    _read_yaml_mappings_emit_field "$p_handle"   handle   "$f_handle"
    _read_yaml_mappings_emit_field "$p_kind"     kind     "$f_kind"
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
# Read a block-style YAML list-of-mappings field and emit a stable, parseable,
# escaping-free record stream. Serves both the task-attachments `attachments:`
# field (schema: aidocs/task_attachments_design.md §3) and the artifact
# `artifacts:` field (handle/kind/name — t1076_2, unified artifact design §4).
# READ-ONLY (writing a mapping is frontmatter_patch.py's concern).
#
# ── OUTPUT CONTRACT (siblings t1030_2 / t1030_3 / t1076_2 depend on this) ─────
#   • One `key=value` line per present field, in SCHEMA ORDER:
#       handle, kind, hash, name, mime, size, added_at, backend, url
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
    # See "THE OTHER HALF: BEING KILLED" in the header. SIGPIPE is ignored ONLY
    # inside a subshell, which is exactly where an early-exiting reader can
    # exist: a pipeline element, $(...) and <(...) all report BASH_SUBSHELL > 0,
    # and the change dies with the subshell. At BASH_SUBSHELL == 0 the reader
    # shares the caller's shell, so we touch nothing at all — leaking SIG_IGN
    # into a caller is then structurally impossible rather than merely undone
    # afterwards. This also needs no `$(trap -p PIPE)` capture, which costs a
    # fork and is not guaranteed to report the caller's handler from inside a
    # command substitution on older bash (this repo targets bash 3.2).
    if [[ ${BASH_SUBSHELL:-0} -gt 0 ]]; then trap '' PIPE; fi
    _read_yaml_mappings_impl "$@"
}

_read_yaml_mappings_impl() {
    local file="$1" field="$2"
    [[ -f "$file" ]] || return 0

    local has_frontmatter=false first_line=""
    IFS= read -r first_line < "$file" 2>/dev/null || true
    [[ "$first_line" == "---" ]] && has_frontmatter=true

    local in_yaml=false in_list=false line
    local _yaml_guard_writes=""; _yaml_init_write_guard
    # Set by the two private helpers below when a write fails and the guard is
    # active; read by them and by the loop to stop emitting (see the write
    # contract at the top of this file).
    local _yaml_pipe_closed=""
    # Per-item parser state (bash-3.2 safe: named vars, not an associative array).
    local have_item=false first_record=true
    local f_handle="" f_kind=""
    local p_handle=0 p_kind=0
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
            if [[ -n "$_yaml_pipe_closed" ]]; then break; fi
            have_item=true
            f_handle=""; f_kind=""
            p_handle=0;  p_kind=0
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

    _read_yaml_mappings_flush              # flush the final item (no-ops on a closed pipe)
    return 0
}
