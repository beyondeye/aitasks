#!/usr/bin/env bash
# aitask_verification_stale.sh - Decide whether a manual-verification task's
# checklist may have gone stale since the commit it was written against.
#
# A manual-verification checklist is authored once and then sits Ready for weeks.
# If the code it describes changed meanwhile, the Pass/Fail/Skip/Defer loop walks
# the user through verifying items that may no longer describe reality. This
# helper is the deterministic seam that detects it. It is ADVISORY: it never
# blocks archival and rewrites nothing.
#
# Design record (source of truth):
#   aidocs/framework/manual_verification_staleness.md
#
# Usage:
#   aitask_verification_stale.sh check <task_file>
#
# Output (exit 0). Fixed first/last lines, evidence lines in between:
#   BASELINE:<sha>|<YYYY-MM-DD HH:MM>      or  BASELINE:NONE
#   FILES:<n>
#   CHANGED:<path>|<n_commits>|<task_ids>        0+ lines
#   DELETED:<path>|<culprit_task>|<subject>      0+ lines
#   UNKNOWN:<path>|<reason>                      0+ lines
#   DISPLAY:<one-line human summary>
#   DECISION:<FRESH|ASK_STALE|SKIP>
#
# EXIT STATUS: every *content* state exits 0 -- that is the "always exits 0"
# contract the caller relies on. CLI misuse still dies: a missing verb or a
# <task_file> that does not exist is a caller bug, and silently emitting SKIP for
# a typo'd path is exactly the "a silent-skip precondition can mask a broken
# implementation" hazard the design doc names. (Same split as
# aitask_plan_verified.sh, whose `decide` dies on bad args but tolerates every
# content state.)
#
# ORDERED EVALUATION -- the order is normative:
#   1. not a git repo, or no HEAD                 -> SKIP
#   2. file_references: empty/absent              -> SKIP   (precondition)
#   3. verification_baseline: absent              -> SKIP   (precondition)
#   4. baseline not an ancestor of HEAD           -> SKIP   (history rewritten)
#   5. classify each curated path
#   6. any CHANGED / DELETED / UNKNOWN            -> ASK_STALE
#   7. otherwise                                  -> FRESH
#
# SKIP is fail-open and silent: "cannot tell" is never rendered as "stale"
# (mirrors code_digest in lib/gate_ledger.py, where unverifiable is its own
# answer). Steps 2 and 3 are the common case for every task that has not been
# seeded -- that is intended, not a bug.
#
# UNKNOWN DRIVES THE VERDICT -- it is NOT advisory. A curated path that cannot be
# checked means the check covers LESS scope than it claims, so reporting FRESH
# would be a false all-clear. An UNKNOWN: line raises ASK_STALE exactly like a
# change does. DISPLAY: distinguishes the causes because the remedies differ: a
# changed file suggests amending the checklist, an uncheckable path suggests
# repairing file_references:.
#
# CURATED PATHS ARE PATHSPECS, AND GIT GLOBS THEM. `git log -- <path>` matches a
# pathspec, and a pathspec containing `*`, `?` or `[...]` is fnmatch-globbed --
# all of which are legal POSIX filename characters. A task curated for the
# literal file `docs/a[bc].md` would otherwise pick up every commit touching
# `docs/ab.md`, reporting a stale checklist for a file nothing touched and
# attributing the wrong task ids. Both history queries therefore pass
# `:(literal)$p`, which also neutralises a curated path that itself begins with
# `:` (which git would otherwise read as pathspec magic). Root-relativity is a
# separate property, supplied by `-C "$repo_root"` on every call. The
# `git cat-file -e "<rev>:<path>"` probes need no such guard: that form is an
# exact tree-path lookup, not a pathspec.
#
# EXISTENCE IS PROBED, NOT INFERRED. `git log -- <path>` reports history but says
# nothing about current existence, so a history-only implementation handles
# modification and SILENTLY MISSES DELETION. Each curated path is classified by
# two cheap probes against the COMMITTED trees (never the dirty worktree):
#   git cat-file -e "<baseline>:<path>"   present at baseline?
#   git cat-file -e "HEAD:<path>"         present now?
#
# PARSE CONTRACT (what the consuming procedure gets):
#   * Records split left-to-right on '|'. Every variable-content field except the
#     DELETED subject is delimiter-encoded, and no reason token contains '|', so
#     a naive split is unambiguous.
#   * ENCODING: '%' -> '%25' first, then '|' -> '%7C'. Decode in reverse
#     ('%7C' -> '|', then '%25' -> '%'). Encoding '%' first is what makes it
#     lossless: a real filename containing the literal text "%7C" round-trips as
#     "%257C" and is never confused with an encoded delimiter. This matters
#     because validate_file_ref's grammar is ^[^:]+(:...)?$ -- which ACCEPTS '|'
#     -- and '|' is legal in a POSIX filename.
#   * Emitted paths are the STRIPPED path (range suffixes removed), then encoded.
#     The one exception is `invalid_reference`, whose stripped form is empty by
#     definition; that line carries the raw entry, encoded by the same rule.
#   * The DELETED subject is SANITIZED ('|' -> ' '), not encoded: it is human
#     display text, not an identity key anything reads back. A commit subject may
#     legitimately contain '|'. `%s` is single-line, so newlines cannot occur.
#   * DISPLAY: carries RAW (unencoded) paths -- it is free-form human text with no
#     internal delimiters, and showing "a%7Cb.md" to a person would be worse.
#   * Reason vocabulary is closed: absent_at_baseline | invalid_reference
#
# SCOPING IS THE CALLER'S RESPONSIBILITY. `file_references:` means "verification
# scope" only on a manual_verification task; on other issue types it means
# "context files relevant to this task". The normative order above has no
# issue_type check by design -- the consuming procedure step runs only on
# manual_verification tasks.
#
# Used by:
#   .claude/skills/task-workflow/manual-verification.md (staleness pre-check)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/terminal_compat.sh
source "$SCRIPT_DIR/lib/terminal_compat.sh"
# shellcheck source=lib/task_utils.sh
source "$SCRIPT_DIR/lib/task_utils.sh"

usage() {
    cat <<'EOF'
Usage:
  aitask_verification_stale.sh check <task_file>
EOF
}

# --- Protocol helpers ---

# Encode a value for a delimited protocol field. '%' MUST be encoded before '|'
# (see the PARSE CONTRACT above) or the mapping is not injective.
_enc() {
    local s="$1"
    s="${s//%/%25}"
    s="${s//|/%7C}"
    printf '%s' "$s"
}

# Strip a file_references range suffix: "path:N", "path:N-M",
# "path:N-M^N-M^...". v1 compares whole files, so ranges are ignored. The
# grammar mirrors validate_file_ref() in lib/task_utils.sh. An entry that is
# nothing but a suffix strips to the empty string -- the caller turns that into
# UNKNOWN:<raw>|invalid_reference, which is a REQUIRED guard rather than polish:
# `git cat-file -e "<sha>:"` resolves to the root tree and exits 0, so an empty
# path would otherwise read as "present".
_strip_ranges() {
    local ref="$1"
    if [[ "$ref" =~ ^(.*)(:[0-9]+(-[0-9]+)?(\^[0-9]+(-[0-9]+)?)*)$ ]]; then
        printf '%s' "${BASH_REMATCH[1]}"
    else
        printf '%s' "$ref"
    fi
}

# Extract a task id from a commit subject via the parenthesised tag convention:
# "(t16)" -> "16", "(t16_2)" -> "16_2". Same convention as extract_task_id() in
# aitask_revert_analyze.sh (kept local here rather than promoted to a shared lib,
# which is a change this slice deliberately does not make).
_task_id_from_subject() {
    local msg="$1"
    if [[ "$msg" =~ \(t([0-9]+(_[0-9]+)?)\) ]]; then
        printf '%s' "${BASH_REMATCH[1]}"
    fi
}

# Join the remaining arguments with ", " for a DISPLAY segment.
_join_display() {
    local out="" item
    for item in "$@"; do
        if [[ -z "$out" ]]; then out="$item"; else out="$out, $item"; fi
    done
    printf '%s' "$out"
}

# _emit_skip <baseline_line> <files_n> <reason>
_emit_skip() {
    printf '%s\n' "$1"
    printf 'FILES:%s\n' "$2"
    printf 'DISPLAY:Staleness check skipped: %s.\n' "$3"
    printf 'DECISION:SKIP\n'
}

# --- check <task_file> ---
cmd_check() {
    local task_file="${1:-}"
    [[ -z "$task_file" ]] && die "check requires <task_file>"
    [[ -f "$task_file" ]] || die "task file not found: $task_file"

    # --- 1. git repo + HEAD -------------------------------------------------
    # Bind the repo root once and pass -C to EVERY git call below. `git log --
    # <path>` pathspecs are cwd-relative while `<rev>:<path>` is root-relative;
    # curated paths are root-relative, so mixing the two silently mis-resolves
    # from any subdirectory. Both probes are guarded so a failure produces the
    # fixed SKIP protocol instead of aborting the script under `set -e`.
    local repo_root=""
    repo_root=$(git rev-parse --show-toplevel 2>/dev/null) || repo_root=""
    if [[ -z "$repo_root" ]] \
       || ! git -C "$repo_root" rev-parse --verify --quiet HEAD >/dev/null 2>&1; then
        _emit_skip "BASELINE:NONE" 0 "not a git repository"
        return 0
    fi

    # --- 2. curated scope ---------------------------------------------------
    # Range suffixes are stripped, then entries are DEDUPED: two ranges of one
    # file are one path to check, so FILES:<n> always equals the number of
    # entries actually accounted for. The `seen` membership test is delimited by
    # NEWLINE, not '|': a path may legally contain '|', and a '|'-delimited test
    # would then false-positive ("a|b" recorded makes a bare "a" look seen). A
    # path can never contain a newline -- it came from one YAML flow-list line.
    local -a units=() unit_invalid=()
    local seen=$'\n'
    local raw stripped key inv
    while IFS= read -r raw; do
        [[ -z "$raw" ]] && continue
        stripped=$(_strip_ranges "$raw")
        if [[ -z "$stripped" ]]; then
            key="$raw"; inv=1
        else
            key="$stripped"; inv=0
        fi
        case "$seen" in
            *$'\n'"$key"$'\n'*) continue ;;
        esac
        seen="${seen}${key}"$'\n'
        units+=("$key")
        unit_invalid+=("$inv")
    done < <(get_file_references "$task_file")

    local files_n=${#units[@]}
    if [[ $files_n -eq 0 ]]; then
        _emit_skip "BASELINE:NONE" 0 "no file_references: on this task"
        return 0
    fi

    # --- 3. baseline --------------------------------------------------------
    local raw_baseline sha ts
    raw_baseline=$(read_yaml_field "$task_file" "verification_baseline")
    if [[ -z "$raw_baseline" ]]; then
        _emit_skip "BASELINE:NONE" "$files_n" "no verification_baseline: on this task"
        return 0
    fi
    # Stored form is "<sha> @ <YYYY-MM-DD HH:MM>". No shape validation: a
    # malformed sha fails the ancestry probe below and falls out as SKIP, which
    # is the correct fail-open answer.
    if [[ "$raw_baseline" == *" @ "* ]]; then
        sha="${raw_baseline%% @ *}"
        ts="${raw_baseline#* @ }"
    else
        sha="$raw_baseline"
        ts=""
    fi
    local baseline_line
    baseline_line="BASELINE:$(_enc "$sha")|$ts"

    # --- 4. ancestry --------------------------------------------------------
    # --is-ancestor returns 1 (not an ancestor) and 128 (unresolvable rev);
    # both mean "cannot tell" -> SKIP.
    if ! git -C "$repo_root" merge-base --is-ancestor "$sha" HEAD >/dev/null 2>&1; then
        _emit_skip "$baseline_line" "$files_n" \
            "baseline $sha is not an ancestor of HEAD (history rewritten)"
        return 0
    fi

    # --- 5. classify --------------------------------------------------------
    local -a evidence=() changed=() deleted=() unknown=()
    local i p at_base at_head subject culprit log_out n_commits ids line sub tid
    for (( i = 0; i < files_n; i++ )); do
        p="${units[$i]}"
        if [[ "${unit_invalid[$i]}" == "1" ]]; then
            evidence+=("UNKNOWN:$(_enc "$p")|invalid_reference")
            unknown+=("$p")
            continue
        fi

        at_base=0
        at_head=0
        if git -C "$repo_root" cat-file -e "$sha:$p" >/dev/null 2>&1; then at_base=1; fi
        if git -C "$repo_root" cat-file -e "HEAD:$p" >/dev/null 2>&1; then at_head=1; fi

        if [[ $at_base -eq 0 ]]; then
            evidence+=("UNKNOWN:$(_enc "$p")|absent_at_baseline")
            unknown+=("$p")
            continue
        fi

        if [[ $at_head -eq 0 ]]; then
            subject=$(git -C "$repo_root" log --diff-filter=D -M -n1 --format='%s' \
                "$sha..HEAD" -- ":(literal)$p" 2>/dev/null) || subject=""
            culprit=$(_task_id_from_subject "$subject")
            [[ -n "$culprit" ]] || culprit="unknown"
            subject="${subject//|/ }"
            evidence+=("DELETED:$(_enc "$p")|$culprit|$subject")
            deleted+=("$p")
            continue
        fi

        # Present at both ends: ask history whether it moved.
        log_out=$(git -C "$repo_root" log --format='%h|%ad|%s' \
            "$sha..HEAD" -- ":(literal)$p" 2>/dev/null) || log_out=""
        [[ -z "$log_out" ]] && continue

        n_commits=$(printf '%s\n' "$log_out" | wc -l | tr -d '[:space:]')
        ids=""
        while IFS= read -r line; do
            [[ -z "$line" ]] && continue
            sub="${line#*|}"      # drop %h
            sub="${sub#*|}"       # drop %ad -> the subject remains
            tid=$(_task_id_from_subject "$sub")
            [[ -z "$tid" ]] && continue
            case ",$ids," in
                *",$tid,"*) continue ;;
            esac
            if [[ -z "$ids" ]]; then ids="$tid"; else ids="$ids,$tid"; fi
        done <<< "$log_out"
        evidence+=("CHANGED:$(_enc "$p")|$n_commits|$ids")
        changed+=("$p")
    done

    # --- 6/7. verdict -------------------------------------------------------
    printf '%s\n' "$baseline_line"
    printf 'FILES:%s\n' "$files_n"

    if [[ ${#evidence[@]} -eq 0 ]]; then
        printf 'DISPLAY:All %s curated file(s) unchanged since baseline %s (%s) — checklist looks current.\n' \
            "$files_n" "$sha" "$ts"
        printf 'DECISION:FRESH\n'
        return 0
    fi

    printf '%s\n' "${evidence[@]}"

    # DISPLAY names the causes separately: the remedy for a changed file (amend
    # the checklist) differs from the remedy for an uncheckable one (repair
    # file_references:).
    local segs=""
    if [[ ${#changed[@]} -gt 0 ]]; then
        segs="changed since baseline: $(_join_display "${changed[@]}")"
    fi
    if [[ ${#deleted[@]} -gt 0 ]]; then
        [[ -n "$segs" ]] && segs="$segs; "
        segs="${segs}deleted since baseline: $(_join_display "${deleted[@]}")"
    fi
    if [[ ${#unknown[@]} -gt 0 ]]; then
        [[ -n "$segs" ]] && segs="$segs; "
        segs="${segs}not present at baseline (fix file_references:): $(_join_display "${unknown[@]}")"
    fi

    printf 'DISPLAY:Checklist may be stale — baseline %s (%s), %s curated file(s): %s — amend the checklist for changed/deleted files; repair file_references: for uncheckable paths.\n' \
        "$sha" "$ts" "$files_n" "$segs"
    printf 'DECISION:ASK_STALE\n'
}

# --- Dispatcher ---

cmd="${1:-}"
shift || true
case "$cmd" in
    check)             cmd_check "$@" ;;
    ""|help|-h|--help) usage ;;
    *)                 die "Unknown subcommand: $cmd" ;;
esac
