#!/usr/bin/env bash
# aitask_premise_stale.sh - Decide whether a task's premise may have gone stale:
# did the code its premise depends on change since the premise was last known
# valid? ADVISORY: it never blocks anything. `check` rewrites nothing; `advance`
# is the mechanism's ONLY write path (an explicitly confirmed baseline advance,
# delegated to aitask_update.sh -- see cmd_advance below).
#
# Design record (source of truth):
#   aidocs/framework/task_premise_staleness.md
#
# Usage:
#   aitask_premise_stale.sh check <task_file>
#   aitask_premise_stale.sh advance <task_file> --checked <sha> --fingerprint <fp>
#                                   --owner <email> [--remove-ref <path>]...
#   aitask_premise_stale.sh owner <task_file> --owner <email>
#
# CWD CONTRACT: run from inside the CODE repository (the framework's `ait`
# convention). The repo root is `git rev-parse --show-toplevel` from the cwd --
# deliberately never derived from `dirname <task_file>`, which under the
# data-branch layout resolves into the `.aitask-data` worktree, whose HEAD
# carries no code paths.
#
# THE SPLIT. This script does git; the pure core `lib/task_premise.py` decides
# and emits. The shell hands the core interchange rows on stdin (vocabulary in
# the core's docstring) and prints the core's protocol after VALIDATING it.
# The only lines formatted here are the `python_unavailable` and `engine_error`
# SKIPs -- there the core is unreachable or untrusted.
#
# Output (exit 0 for every content state):
#   BASELINE:<sha>|<enc ts>   or  BASELINE:NONE
#   CHECKED:<sha>             or  CHECKED:NONE    (no revision was pinned)
#   FINGERPRINT:<16 hex>      or  FINGERPRINT:NONE   (NONE on every SKIP)
#   FILES:<n>
#   CHANGED:<path>|<n_commits>|<task_ids>        0+ lines
#   DELETED:<path>|<culprit_task>|<subject>      0+ lines
#   UNKNOWN:<path or origin id>|<reason>         0+ lines
#   DISPLAY:<one-line human summary>
#   DECISION:<FRESH|ASK_STALE|SKIP>
# CLI misuse (missing verb, missing/nonexistent task file) dies: a typo'd path
# must never read as SKIP.
#
# THE GOVERNING INVARIANT. FRESH is a positive claim, never the absence of a
# failure: every scope path present at both ends AND a successful,
# count-attested history query that returned zero commits. Every probe failure
# maps to evidence (ASK_STALE) or SKIP, never to "unchanged". In particular a
# FAILED `git log` is `history_unavailable`, never an empty history -- the
# template's `log_out=$(git log ...) || log_out=""` reads exit 128 as "no
# commits", and `log.date=invalid-date-mode` makes exactly that happen while both
# `cat-file -e` probes still succeed.
#
# ORDERED EVALUATION -- normative:
#   1. CLI misuse                                    -> die
#   2. no python                                     -> SKIP python_unavailable
#   3. not a git repo / no HEAD                      -> SKIP not_a_git_repo
#   4. read premise_baseline: + file_references: through the framework's YAML
#      reader (task_yaml), count-attested            -> else SKIP scope_error
#      frontmatter is not valid YAML                 -> SKIP invalid_frontmatter
#      no premise_baseline:                          -> SKIP no_stored_baseline (FILES:0)
#      premise_baseline: not a full 40/64-hex id     -> SKIP invalid_baseline
#   5. pin the checked revision once (CHECKED:)
#   6. baseline not an ancestor of it (exit 1/128)   -> SKIP history_rewritten
#   7. scope: Tier A file_references:, else Tier B exact origin surface
#      (followup_origin.py + `--batch-map --encode-paths`); a failed Tier-B
#      subprocess, or a map that fails the emitter's own count attestation
#      (TASKFILES_COUNT per id, END record count, exactly one STATUS per
#      requested origin and no other id)           -> SKIP scope_error
#   8. classify every path against COMMITTED trees (a dirty worktree is
#      invisible by construction). A path absent at the baseline is
#      absent_at_baseline when present at the checked revision or touched
#      inside the window; absent at BOTH ends with no commit in the window it
#      is `retired` when history reachable from the baseline shows it once
#      existed (deleted at/before the baseline: not evidence, not checked) and
#      `never_existed` otherwise (evidence). Every query has an explicit
#      status; a failure is history_unavailable.
#   9. core decides; output validated structurally   -> else SKIP engine_error
# Baseline comes before scope so the common v1 case (no stored baseline) costs
# zero git-history work.
#
# IMMUTABLE BASELINE. Step 4 accepts only a full SHA-1/SHA-256 object id
# (normalized to lowercase). `HEAD` is an ancestor of every checked revision, so
# `HEAD..<rev>` is empty: a symbol handed to merge-base/log would read FRESH over
# a real change. Task files are hand-editable, so the writer's validation alone
# cannot protect this reader; the core re-checks the same grammar.
#
# ENCODING (every variable path field, interchange and output alike):
#   '%' -> '%25' first, then '|' -> '%7C', LF -> '%0A', CR -> '%0D'; decode in
#   reverse, '%25' last. A filename may hold '|' and even a newline; both stay one
#   field on one line. Candidate paths are carried ENCODED (the dedupe key, which
#   can never contain a newline) and decoded only at the git probes. DISPLAY:
#   carries raw paths except LF/CR. The DELETED subject is sanitized ('|' -> ' ').
#   `--batch-map` is called with `--encode-paths`: its default output writes
#   paths raw into newline-framed records, so one newline-bearing filename
#   anywhere in history could split a record or forge a TASKFILES: line.
#
# SCOPE IS READ AS YAML, AND ITS COMPLETENESS IS ATTESTED. file_references: is
# parsed by task_yaml, never comma-split: a comma-splitting reader turns the
# valid entry "a,b.py" into `a` and `b.py`, and when those exist unchanged a
# change to a,b.py reads FRESH. Every scope source states its own size -- FIELD_END for the
# fields reader, TASKFILES_COUNT/END for the batch map -- and the TIER counts the
# core checks are derived only after those attestations hold.
#
# PATHSPECS: every history query passes `:(literal)<path>` (git would otherwise
# fnmatch-glob `*`, `?`, `[...]`) and `-C "$repo_root"` (log pathspecs are
# cwd-relative, `<rev>:<path>` is root-relative).
#
# Used by: task-workflow Step 3 (t1663_4), t1981_6 (one evidence row).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/terminal_compat.sh
source "$SCRIPT_DIR/lib/terminal_compat.sh"
# shellcheck source=lib/task_utils.sh
source "$SCRIPT_DIR/lib/task_utils.sh"
# shellcheck source=lib/python_resolve.sh
source "$SCRIPT_DIR/lib/python_resolve.sh"

# The published line vocabulary as the validator below knows it. ONE line, so
# tests/test_premise_stale.sh can pin it against task_premise.LINE_PREFIXES.
_PREMISE_LINE_PREFIXES=(BASELINE CHECKED FINGERPRINT FILES CHANGED DELETED UNKNOWN DISPLAY DECISION)

_OID_RE='^([0-9a-f]{40}|[0-9a-f]{64})$'
_OID_ANYCASE_RE='^([0-9a-fA-F]{40}|[0-9a-fA-F]{64})$'

ERR_FILE=""
MAP_FILE=""

usage() {
    cat <<'EOF'
Usage:
  aitask_premise_stale.sh check <task_file>
  aitask_premise_stale.sh advance <task_file> --checked <sha> --fingerprint <fp>
                                  --owner <email> [--remove-ref <path>]...
  aitask_premise_stale.sh owner <task_file> --owner <email>
EOF
}

_premise_cleanup() {
    rm -f "${ERR_FILE:-}" "${MAP_FILE:-}"
}

# --- encoding --------------------------------------------------------------

# _enc <value> -> encoded on stdout (never contains a newline, so $( ) is safe).
_enc() {
    local s="$1"
    s="${s//"%"/%25}"
    s="${s//"|"/%7C}"
    s="${s//$'\n'/%0A}"
    s="${s//$'\r'/%0D}"
    printf '%s' "$s"
}

# _dec <encoded> -> sets _DEC. Not $( ): a decoded path may END in a newline,
# which command substitution would silently strip.
_DEC=""
_dec() {
    local s="$1"
    s="${s//"%0D"/$'\r'}"
    s="${s//"%0A"/$'\n'}"
    s="${s//"%7C"/|}"
    s="${s//"%25"/%}"
    _DEC="$s"
}

# Strip a file_references range suffix ("path:N", "path:N-M", "path:N-M^N-M").
# Same grammar as aitask_verification_stale.sh / validate_file_ref(). An entry
# that is nothing but a suffix strips to "" -- the caller makes that
# `invalid_reference`, a REQUIRED guard: `git cat-file -e "<sha>:"` resolves the
# root tree and exits 0.
_strip_ranges() {
    local ref="$1"
    if [[ "$ref" =~ ^(.*)(:[0-9]+(-[0-9]+)?(\^[0-9]+(-[0-9]+)?)*)$ ]]; then
        printf '%s' "${BASH_REMATCH[1]}"
    else
        printf '%s' "$ref"
    fi
}

# "(t16)" -> "16", "(t16_2)" -> "16_2" (the parenthesised tag convention).
_task_id_from_subject() {
    if [[ "$1" =~ \(t([0-9]+(_[0-9]+)?)\) ]]; then
        printf '%s' "${BASH_REMATCH[1]}"
    fi
}

# First captured stderr line, made safe for a DISPLAY: segment.
_first_err_line() {
    local first=""
    [[ -s "${ERR_FILE:-}" ]] && IFS= read -r first < "$ERR_FILE" || true
    first="${first//"|"/ }"
    first="${first//$'\r'/ }"
    printf '%s' "${first:0:120}"
}

# --- shell-formatted SKIPs (core unreachable or untrusted) -----------------

_emit_shell_skip() {
    local reason="$1" text="$2"
    printf 'BASELINE:NONE\nCHECKED:NONE\nFINGERPRINT:NONE\nFILES:0\n'
    printf 'DISPLAY:Premise check skipped (%s): %s.\n' "$reason" "$text"
    printf 'DECISION:SKIP\n'
}

# --- the core call -----------------------------------------------------------

# The glue is the PROGRAM, so it must not travel on stdin -- stdin is the data
# channel (`"$py" - <<'PY'` would hand the core an empty stdin and every check
# would read a silent SKIP). Single-quoted: nothing is interpolated into it.
# The lib dir arrives as argv[1] and is APPENDED: a `-c` program gets
# sys.path[0] == '' (cwd), which is dropped, and a PYTHONPATH shadow still wins
# (the documented fault-injection seam).
_PREMISE_GLUE='
import sys
sys.path = [p for p in sys.path if p not in ("", ".")]
sys.path.append(sys.argv[1])
import task_premise
sys.stdout.write("\n".join(task_premise.check(sys.stdin).lines) + "\n")
'

# The task-fields reader: premise_baseline: and file_references: as the
# framework's YAML reader parses them (task_yaml.parse_frontmatter), NEVER by
# splitting the flow list on commas, which turns the valid entry "a,b.py" into
# the two paths `a` and `b.py`. The string-only rule is
# task_yaml.file_reference_entries, shared with the shell reader
# get_file_references() (lib/task_utils.sh). argv[1] = lib dir,
# argv[2] = task file. A file whose frontmatter does not parse prints
# FIELD_INVALID (-> SKIP invalid_frontmatter); any other failure exits non-zero.
_FIELDS_GLUE='
import sys
sys.path = [p for p in sys.path if p not in ("", ".")]
sys.path.append(sys.argv[1])
import task_premise, task_yaml
with open(sys.argv[2], encoding="utf-8") as fh:
    text = fh.read()
try:
    parsed = task_yaml.parse_frontmatter(text)
except Exception:
    parsed = None
meta = parsed[0] if parsed else None
sys.stdout.write("\n".join(task_premise.task_fields(meta)) + "\n")
'

_is_line_prefix() {
    local want="$1" p
    for p in "${_PREMISE_LINE_PREFIXES[@]}"; do
        [[ "$p" == "$want" ]] && return 0
    done
    return 1
}

# _validate_core_output <text> -> 0 when structurally trustworthy.
# Structural, not a DECISION: sniff: a broken core that prints garbage plus
# DECISION:FRESH must not become an all-clear. (Evidence the core already
# discarded is invisible here -- the core's own row-integrity rules close that.)
_validate_core_output() {
    local text="$1" line
    local -a lines=()
    while IFS= read -r line; do lines+=("$line"); done <<< "$text"
    local n=${#lines[@]}
    (( n >= 6 )) || return 1

    local i
    for (( i = 0; i < n; i++ )); do
        line="${lines[$i]}"
        [[ "$line" == *:* ]] || return 1
        _is_line_prefix "${line%%:*}" || return 1
    done

    local base_re='^BASELINE:(NONE|([0-9a-f]{40}|[0-9a-f]{64})\|.*)$'
    local checked_re='^CHECKED:(NONE|[0-9a-f]{40}|[0-9a-f]{64})$'
    local fp_re='^FINGERPRINT:(NONE|[0-9a-f]{16})$'
    local files_re='^FILES:[0-9]+$'
    local decision_re='^DECISION:(FRESH|ASK_STALE|SKIP)$'
    [[ "${lines[0]}" =~ $base_re ]] || return 1
    [[ "${lines[1]}" =~ $checked_re ]] || return 1
    [[ "${lines[2]}" =~ $fp_re ]] || return 1
    [[ "${lines[3]}" =~ $files_re ]] || return 1
    [[ "${lines[n-2]}" == DISPLAY:* ]] || return 1
    [[ "${lines[n-1]}" =~ $decision_re ]] || return 1

    local evidence=0
    for (( i = 4; i < n - 2; i++ )); do
        case "${lines[$i]}" in
            CHANGED:*|DELETED:*|UNKNOWN:*) evidence=$((evidence + 1)) ;;
            *) return 1 ;;
        esac
    done

    case "${lines[n-1]#DECISION:}" in
        SKIP)
            [[ $evidence -eq 0 && "${lines[2]}" == "FINGERPRINT:NONE" ]] || return 1 ;;
        FRESH|ASK_STALE)
            [[ "${lines[0]}" != "BASELINE:NONE" ]] || return 1
            [[ "${lines[1]}" != "CHECKED:NONE" ]] || return 1
            [[ "${lines[2]}" != "FINGERPRINT:NONE" ]] || return 1
            if [[ "${lines[n-1]}" == "DECISION:FRESH" ]]; then
                [[ $evidence -eq 0 ]] || return 1
            else
                [[ $evidence -gt 0 ]] || return 1
            fi
            ;;
    esac
    return 0
}

# _run_core <py> <display-detail-or-empty>; reads the global ROWS array.
_run_core() {
    local py="$1" detail="$2" rows_text out rc=0
    rows_text=$(printf '%s\n' "${ROWS[@]}")
    : > "$ERR_FILE"
    out=$("$py" -c "$_PREMISE_GLUE" "$SCRIPT_DIR/lib" <<< "$rows_text" 2>>"$ERR_FILE") || rc=$?
    if [[ $rc -ne 0 || -z "$out" ]] || ! _validate_core_output "$out"; then
        local why="the premise engine failed"
        local first; first=$(_first_err_line)
        [[ -n "$first" ]] && why="$why: $first"
        _emit_shell_skip engine_error "$why"
        return 0
    fi
    if [[ -n "$detail" ]]; then
        # Fold the captured diagnostic into DISPLAY: (free text; the validator
        # has already accepted the line structure).
        local -a lines=()
        local line
        while IFS= read -r line; do lines+=("$line"); done <<< "$out"
        local n=${#lines[@]}
        lines[n-2]="${lines[n-2]} Detail: $detail"
        printf '%s\n' "${lines[@]}"
        return 0
    fi
    printf '%s\n' "$out"
}

# --- check <task_file> -----------------------------------------------------

ROWS=()

cmd_check() {
    local task_file="${1:-}"
    [[ -z "$task_file" ]] && die "check requires <task_file>"
    [[ -f "$task_file" ]] || die "task file not found: $task_file"

    # --- 2. python ----------------------------------------------------------
    local py
    py="$(resolve_python)"
    if [[ -z "$py" ]]; then
        _emit_shell_skip python_unavailable "no Python interpreter found (ait setup installs one)"
        return 0
    fi

    ERR_FILE=$(mktemp "${TMPDIR:-/tmp}/aitask_premise_err_XXXXXX")
    trap '_premise_cleanup' EXIT
    ait_archive_rearm_exit_trap

    # --- 3. git repo + HEAD -------------------------------------------------
    local repo_root="" rev=""
    repo_root=$(git rev-parse --show-toplevel 2>/dev/null) || repo_root=""
    if [[ -n "$repo_root" ]]; then
        rev=$(git -C "$repo_root" rev-parse --verify --quiet HEAD 2>/dev/null) || rev=""
    fi
    if [[ -z "$repo_root" || ! "$rev" =~ $_OID_RE ]]; then
        ROWS=("BASE:||not_a_git_repo" "TIER:NONE|0|0")
        _run_core "$py" ""
        return 0
    fi

    # --- 4. task fields (read through YAML) + immutable commit-id grammar ----
    # One YAML read of the frontmatter supplies both fields, count-attested by
    # FIELD_END so a truncated read can never shrink the scope.
    local fields_out="" f_rc=0
    fields_out=$("$py" -c "$_FIELDS_GLUE" "$SCRIPT_DIR/lib" "$task_file" 2>>"$ERR_FILE") || f_rc=$?
    if [[ $f_rc -eq 0 && "$fields_out" == "FIELD_INVALID:frontmatter" ]]; then
        ROWS=("BASE:||invalid_frontmatter" "TIER:NONE|0|0")
        _run_core "$py" ""
        return 0
    fi
    local -a ref_keys=() ref_bad=()
    local enc_baseline="" fields_ok=0 fline idx=0 end_n=-1
    if [[ $f_rc -eq 0 ]]; then
        fields_ok=1
        while IFS= read -r fline; do
            if [[ $end_n -ge 0 ]]; then fields_ok=0; break; fi   # nothing after FIELD_END
            if [[ $idx -eq 0 ]]; then
                [[ "$fline" == FIELD_BASELINE:* ]] || { fields_ok=0; break; }
                enc_baseline="${fline#FIELD_BASELINE:}"
            else
                case "$fline" in
                    FIELD_REF:*)    ref_keys+=("${fline#FIELD_REF:}"); ref_bad+=(0) ;;
                    FIELD_BADREF:*) ref_keys+=("${fline#FIELD_BADREF:}"); ref_bad+=(1) ;;
                    FIELD_END:*)    end_n="${fline#FIELD_END:}"
                                    [[ "$end_n" =~ ^[0-9]+$ ]] || { fields_ok=0; break; } ;;
                    *)              fields_ok=0; break ;;
                esac
            fi
            idx=$((idx + 1))
        done <<< "$fields_out"
        [[ "$end_n" =~ ^[0-9]+$ && "$end_n" -eq ${#ref_keys[@]} ]] || fields_ok=0
    fi
    if [[ $fields_ok -ne 1 ]]; then
        local d; d=$(_first_err_line)
        ROWS=("BASE:||scope_error" "TIER:NONE|0|0")
        _run_core "$py" "the task's fields could not be read${d:+: $d}"
        return 0
    fi

    local raw_baseline sha ts
    _dec "$enc_baseline"; raw_baseline="$_DEC"
    if [[ -z "$raw_baseline" ]]; then
        ROWS=("BASE:||no_stored_baseline" "TIER:NONE|0|0")
        _run_core "$py" ""
        return 0
    fi
    if [[ "$raw_baseline" == *" @ "* ]]; then
        sha="${raw_baseline%% @ *}"
        ts="${raw_baseline#* @ }"
    else
        sha="$raw_baseline"
        ts=""
    fi
    if [[ ! "$sha" =~ $_OID_ANYCASE_RE ]]; then
        # HEAD, HEAD~1, @{u}, a branch/tag, an abbreviation, `<sha>^`, whitespace:
        # never handed to merge-base or log.
        ROWS=("BASE:$(_enc "$sha")|$(_enc "$ts")|invalid_baseline" "TIER:NONE|0|0")
        _run_core "$py" ""
        return 0
    fi
    sha=$(printf '%s' "$sha" | tr 'A-F' 'a-f')
    local base_fields
    base_fields="$sha|$(_enc "$ts")"

    # --- 6. ancestry (exit 1 = not an ancestor, 128 = unresolvable) ---------
    if ! git -C "$repo_root" merge-base --is-ancestor "$sha" "$rev" >/dev/null 2>&1; then
        ROWS=("REV:$rev" "BASE:$base_fields|history_rewritten" "TIER:NONE|0|0")
        _run_core "$py" ""
        return 0
    fi

    # --- 7. scope -----------------------------------------------------------
    # Candidates are ENCODED keys; dedupe on a newline-delimited seen-set (an
    # encoded key can never contain a newline; a raw path could). Each seen key
    # is TAGGED 0: (a path to check) or 1: (an invalid entry), so an invalid
    # entry can never be deduped away behind a valid one with the same text --
    # if both survive with one key, the core rejects the duplicate PATH row
    # (SKIP), which is still not FRESH. Range suffixes are stripped from the
    # encoded form -- the suffix alphabet (`:`, digits, `-`, `^`) never overlaps
    # an escape, so this equals stripping the raw path.
    local -a cand=() cand_invalid=() origin_rows=()
    local seen=$'\n' tier="NONE" key stripped inv i

    for (( i = 0; i < ${#ref_keys[@]}; i++ )); do
        stripped=$(_strip_ranges "${ref_keys[$i]}")
        if [[ "${ref_bad[$i]}" == "1" || -z "$stripped" ]]; then
            key="${ref_keys[$i]}"; inv=1
        else
            key="$stripped"; inv=0
        fi
        case "$seen" in
            *$'\n'"$inv:$key"$'\n'*) continue ;;
        esac
        seen="${seen}${inv}:${key}"$'\n'
        cand+=("$key")
        cand_invalid+=("$inv")
    done
    [[ ${#cand[@]} -gt 0 ]] && tier="A"

    if [[ "$tier" == "NONE" ]]; then
        # Tier B: an EXACT origin only (topic/unknown refuse to claim causation).
        local origin_out="" o_rc=0 quality="" origins_csv=""
        origin_out=$("$py" "$SCRIPT_DIR/lib/followup_origin.py" "$task_file" 2>>"$ERR_FILE") || o_rc=$?
        if [[ $o_rc -ne 0 ]]; then
            local d; d=$(_first_err_line)
            ROWS=("REV:$rev" "BASE:$base_fields|scope_error" "TIER:NONE|0|0")
            _run_core "$py" "followup_origin.py failed${d:+: $d}"
            return 0
        fi
        IFS=$'\t' read -r _ quality origins_csv _ <<< "$origin_out" || true
        if [[ "$quality" == "exact" && -n "$origins_csv" && "$origins_csv" != "-" ]]; then
            tier="B"
            local -a raw_ids=() origin_ids=()
            local oid j dup
            IFS=',' read -r -a raw_ids <<< "$origins_csv"
            for oid in "${raw_ids[@]}"; do
                dup=0
                for (( j = 0; j < ${#origin_ids[@]}; j++ )); do
                    [[ "${origin_ids[$j]}" == "$oid" ]] && dup=1
                done
                [[ $dup -eq 0 ]] && origin_ids+=("$oid")
            done
            MAP_FILE=$(mktemp "${TMPDIR:-/tmp}/aitask_premise_map_XXXXXX")
            local map_rc=0
            printf '%s\n' "${origin_ids[@]}" \
                | ( cd "$repo_root" && "$SCRIPT_DIR/aitask_revert_analyze.sh" \
                        --batch-map --encode-paths --ids-from - ) \
                > "$MAP_FILE" 2>>"$ERR_FILE" || map_rc=$?
            if [[ $map_rc -ne 0 ]]; then
                local d; d=$(_first_err_line)
                ROWS=("REV:$rev" "BASE:$base_fields|scope_error" "TIER:NONE|0|0")
                _run_core "$py" "the origin file surface could not be resolved${d:+: $d}"
                return 0
            fi
            # Completeness is checked against what the EMITTER attested -- per-id
            # TASKFILES_COUNT and the final END record count -- never against
            # what survived this parse. A dropped STATUS: row would otherwise
            # erase an UNKNOWN_HISTORY origin, and a dropped TASKFILES: row a
            # changed file; both read FRESH.
            local -a o_seen=() o_count=() o_status=()
            for (( j = 0; j < ${#origin_ids[@]}; j++ )); do
                o_seen[j]=0; o_count[j]=-1; o_status[j]=""
            done
            local line rest id val dec records=0 map_end=-1 broken=0 oi
            while IFS= read -r line || [[ -n "$line" ]]; do
                [[ -z "$line" ]] && continue
                if [[ $map_end -ge 0 ]]; then broken=1; break; fi   # nothing after END
                case "$line" in
                    END:*)
                        map_end="${line#END:}"
                        [[ "$map_end" =~ ^[0-9]+$ ]] || { broken=1; break; }
                        continue ;;
                    TASKFILES_COUNT:*|TASKFILES:*|STATUS:*)
                        rest="${line#*:}"
                        if [[ "$rest" != *"|"* ]]; then broken=1; break; fi
                        id="${rest%%|*}"; val="${rest#*|}"
                        oi=-1
                        for (( j = 0; j < ${#origin_ids[@]}; j++ )); do
                            [[ "${origin_ids[$j]}" == "$id" ]] && oi=$j
                        done
                        if [[ $oi -lt 0 ]]; then broken=1; break; fi  # an id nobody asked for
                        case "$line" in
                            TASKFILES_COUNT:*)
                                [[ "$val" =~ ^[0-9]+$ && "${o_count[$oi]}" -eq -1 ]] \
                                    || { broken=1; break; }
                                o_count[oi]="$val" ;;
                            STATUS:*)
                                [[ -z "${o_status[$oi]}" ]] || { broken=1; break; }
                                case "$val" in
                                    FILES|NO_FILES|UNKNOWN_HISTORY) o_status[oi]="$val" ;;
                                    *) broken=1; break ;;
                                esac ;;
                            TASKFILES:*)
                                o_seen[oi]=$(( ${o_seen[$oi]} + 1 ))
                                key="$val"                     # already encoded
                                _dec "$key"; dec="$_DEC"
                                case "$dec" in
                                    "${TASK_DIR}/"*|"${PLAN_DIR}/"*|.aitask-gates/*) ;;
                                    *)
                                        case "$seen" in
                                            *$'\n'"0:$key"$'\n'*) ;;
                                            *)
                                                seen="${seen}0:${key}"$'\n'
                                                cand+=("$key")
                                                cand_invalid+=(0) ;;
                                        esac ;;
                                esac ;;
                        esac ;;
                    COMMIT:*|TRACKED:*) ;;
                    *)  broken=1; break ;;     # with --encode-paths no path splits a record
                esac
                records=$((records + 1))
            done < "$MAP_FILE"
            [[ $broken -eq 0 && $map_end -ge 0 && $map_end -eq $records ]] || broken=1
            for (( j = 0; j < ${#origin_ids[@]} && broken == 0; j++ )); do
                # Every requested id: exactly one STATUS, one attested count that
                # equals the rows seen, and a status consistent with that count.
                if [[ -z "${o_status[$j]}" || "${o_count[$j]}" -ne "${o_seen[$j]}" ]]; then
                    broken=1
                elif [[ "${o_status[$j]}" == "FILES" && "${o_seen[$j]}" -eq 0 ]] \
                     || [[ "${o_status[$j]}" != "FILES" && "${o_seen[$j]}" -ne 0 ]]; then
                    broken=1
                else
                    origin_rows+=("ORIGIN:${origin_ids[$j]}|${o_status[$j]}")
                fi
            done
            if [[ $broken -ne 0 ]]; then
                ROWS=("REV:$rev" "BASE:$base_fields|scope_error" "TIER:NONE|0|0")
                _run_core "$py" "the origin file map failed its completeness check"
                return 0
            fi
        fi
    fi

    # --- 8. classify against committed trees --------------------------------
    local -a path_rows=()
    local i p log_out n csha subject culprit tid
    for (( i = 0; i < ${#cand[@]}; i++ )); do
        key="${cand[$i]}"
        if [[ "${cand_invalid[$i]}" == "1" ]]; then
            path_rows+=("PATH:$key|invalid_reference")
            continue
        fi
        _dec "$key"; p="$_DEC"

        if ! git -C "$repo_root" cat-file -e "$sha:$p" >/dev/null 2>&1; then
            # Absent at the baseline. Present now -> added in the window
            # (evidence, resolved by an advance). Absent at BOTH ends -> decide
            # between "retired" (deleted at/before the baseline: not evidence)
            # and "never_existed" from two history queries, each with an
            # EXPLICIT status: a failed query is history_unavailable, never an
            # empty history (the governing invariant above).
            if git -C "$repo_root" cat-file -e "$rev:$p" >/dev/null 2>&1; then
                path_rows+=("PATH:$key|absent_at_baseline")
                continue
            fi
            local win_out prior_out
            if ! win_out=$(git -C "$repo_root" log --no-show-signature --format='%H' \
                    "$sha..$rev" -- ":(literal)$p" 2>>"$ERR_FILE"); then
                path_rows+=("PATH:$key|history_unavailable")
                continue
            fi
            if [[ -n "$win_out" ]]; then
                # Created and removed again inside the window: still evidence.
                path_rows+=("PATH:$key|absent_at_baseline")
                continue
            fi
            if ! prior_out=$(git -C "$repo_root" log --no-show-signature -n1 --format='%H' \
                    "$sha" -- ":(literal)$p" 2>>"$ERR_FILE"); then
                path_rows+=("PATH:$key|history_unavailable")
                continue
            fi
            if [[ -n "$prior_out" ]]; then
                path_rows+=("PATH:$key|retired")
            else
                path_rows+=("PATH:$key|never_existed")
            fi
            continue
        fi
        if ! git -C "$repo_root" cat-file -e "$rev:$p" >/dev/null 2>&1; then
            subject=$(git -C "$repo_root" log --no-show-signature --diff-filter=D -M -n1 \
                --format='%s' "$sha..$rev" -- ":(literal)$p" 2>>"$ERR_FILE") || subject=""
            culprit=$(_task_id_from_subject "$subject")
            [[ -n "$culprit" ]] || culprit="unknown"
            path_rows+=("PATH:$key|deleted" "GONE:$key|$culprit|${subject//"|"/ }")
            continue
        fi

        # Present at both ends: an EXPLICIT status, never `|| log_out=""`.
        if log_out=$(git -C "$repo_root" log --no-show-signature --format='%H|%s' \
                "$sha..$rev" -- ":(literal)$p" 2>>"$ERR_FILE"); then
            local -a logs=()
            n=0
            while IFS= read -r line; do
                [[ -z "$line" ]] && continue
                csha="${line%%|*}"
                tid=$(_task_id_from_subject "${line#*|}")
                logs+=("LOG:$key|$csha|$tid")
                n=$((n + 1))
            done <<< "$log_out"
            path_rows+=("PATH:$key|ok|$n")
            [[ $n -gt 0 ]] && path_rows+=("${logs[@]}")
        else
            path_rows+=("PATH:$key|history_unavailable")
        fi
    done

    ROWS=("REV:$rev" "BASE:$base_fields|" "TIER:$tier|${#cand[@]}|${#origin_rows[@]}")
    [[ ${#origin_rows[@]} -gt 0 ]] && ROWS+=("${origin_rows[@]}")
    [[ ${#path_rows[@]} -gt 0 ]] && ROWS+=("${path_rows[@]}")
    _run_core "$py" ""
}

# --- shared by advance / owner ---------------------------------------------

# _resolve_active_task <task_file> <verb> -> sets _ACTIVE_ID, _ACTIVE_PATH; dies
# when <task_file> is not the active task the writer resolves by id.
#
# IDENTITY. Every write here goes through aitask_update.sh, which resolves the
# task BY ID -- so a copy (or any other file named like t<id>_*.md) would be
# checked while the real task moved, marking changes nobody saw as reviewed.
# Resolve the active file by the writer's own rule (exactly one match in the
# active tree) and require it to BE <task_file>: `-ef` compares device and
# inode, so the data-branch symlink alias (aitasks/ -> .aitask-data/aitasks/)
# still passes.
_ACTIVE_ID=""
_ACTIVE_PATH=""
_resolve_active_task() {
    local task_file="$1" verb="$2" base matches=""
    base=$(basename "$task_file")
    [[ "$base" =~ ^t([0-9]+(_[0-9]+)?)_.*\.md$ ]] \
        || die "$verb: cannot derive a task id from '$base'"
    _ACTIVE_ID="${BASH_REMATCH[1]}"
    if [[ "$_ACTIVE_ID" =~ ^([0-9]+)_([0-9]+)$ ]]; then
        matches=$(ls "$TASK_DIR/t${BASH_REMATCH[1]}/t${_ACTIVE_ID}_"*.md 2>/dev/null || true)
    else
        matches=$(ls "$TASK_DIR/t${_ACTIVE_ID}_"*.md 2>/dev/null || true)
    fi
    _ACTIVE_PATH=""
    if [[ -n "$matches" && "$(printf '%s\n' "$matches" | wc -l)" -eq 1 ]]; then
        _ACTIVE_PATH="$matches"
    fi
    [[ -n "$_ACTIVE_PATH" ]] \
        || die "$verb: no single active task file for t${_ACTIVE_ID} under ${TASK_DIR}/ (found: ${matches:-none})"
    [[ "$task_file" -ef "$_ACTIVE_PATH" ]] \
        || die "$verb: '$task_file' is not the active task file for t${_ACTIVE_ID} ('$_ACTIVE_PATH') -- refusing to check one file and write another"
}

# _owner_proof <task_id> <owner> -> prints exactly one of
#   OK
#   not_owner|<detail>            the lock is held by someone else, or by nobody
#   owner_unverifiable|<detail>   the holding session cannot be proven
#
# OWNERSHIP, proven rather than assumed. The answer being applied was given
# before the claim, and a session that lost or never got the task (a lock error
# it continued past, another session's force-claim, a stop path that runs before
# the Step 7 guard) must not write. The lock record must name <owner> on THIS
# host AND this session: email and host are shared by every session of the same
# user on a machine, so the lock's recorded session anchor (pid + start-time
# token + token kind) must pass lock_anchor_is_self -- the test the lock's own
# acquire gate uses. Either side unresolvable is "unverifiable", never a pass.
_owner_proof() {
    local task_id="$1" owner="$2"
    local lock_out lock_rc=0 locked_by locked_host this_host
    lock_out=$("$SCRIPT_DIR/aitask_lock.sh" --check "$task_id" 2>/dev/null) || lock_rc=$?
    if [[ $lock_rc -ne 0 ]]; then
        echo "not_owner|no lock held on t${task_id}"
        return 0
    fi
    locked_by=$(printf '%s\n' "$lock_out" | sed -n 's/^locked_by: *//p' | head -n1)
    locked_host=$(printf '%s\n' "$lock_out" | sed -n 's/^hostname: *//p' | head -n1)
    this_host=$(hostname 2>/dev/null || echo unknown)
    if [[ "$locked_by" != "$owner" || "$locked_host" != "$this_host" ]]; then
        echo "not_owner|locked by ${locked_by:-unknown}@${locked_host:-unknown}"
        return 0
    fi
    local lpid lstart lkind self_pid
    lpid=$(printf '%s\n' "$lock_out" | sed -n 's/^pid: *//p' | head -n1)
    lstart=$(printf '%s\n' "$lock_out" | sed -n 's/^pid_starttime: *//p' | head -n1)
    lkind=$(printf '%s\n' "$lock_out" | sed -n 's/^pid_starttime_kind: *//p' | head -n1)
    # shellcheck source=lib/pid_anchor.sh
    source "$SCRIPT_DIR/lib/pid_anchor.sh"
    self_pid=$(get_session_anchor_pid 2>/dev/null || true)
    if [[ ! "$self_pid" =~ ^[0-9]+$ ]]; then
        echo "owner_unverifiable|this session has no resolvable anchor (run inside the agent's tmux pane, or set AIT_AGENT_PID)"
        return 0
    fi
    if [[ ! "$lpid" =~ ^[0-9]+$ ]]; then
        echo "owner_unverifiable|the lock on t${task_id} records no session anchor"
        return 0
    fi
    if ! lock_anchor_is_self "$lpid" "${lstart:--}" "${lkind:-proc}"; then
        echo "not_owner|held by another session of ${locked_by} on ${locked_host} (pid ${lpid})"
        return 0
    fi
    echo "OK"
}

# --- owner <task_file> --owner <email> ---------------------------------------
#
# The ownership proof on its own, for the procedure's other post-lock writes
# (a postpone, a revert to Ready) -- which change the task just as an advance
# does. Prints OWNER_OK, NOT_OWNER:<detail> or OWNER_UNVERIFIABLE:<detail>;
# exit 0 for every content state, dies on CLI misuse.
cmd_owner() {
    local task_file="" owner=""
    [[ $# -gt 0 ]] || die "owner requires <task_file>"
    task_file="$1"; shift
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --owner) [[ $# -ge 2 ]] || die "--owner requires an email"; owner="$2"; shift 2 ;;
            *)       die "owner: unknown argument: $1" ;;
        esac
    done
    [[ -f "$task_file" ]] || die "task file not found: $task_file"
    [[ -n "$owner" ]] || die "--owner <email> is required"
    _resolve_active_task "$task_file" owner
    local proof
    proof=$(_owner_proof "$_ACTIVE_ID" "$owner")
    case "$proof" in
        OK)                    echo "OWNER_OK" ;;
        not_owner\|*)          echo "NOT_OWNER:${proof#not_owner|}" ;;
        owner_unverifiable\|*) echo "OWNER_UNVERIFIABLE:${proof#owner_unverifiable|}" ;;
        *)                     echo "OWNER_UNVERIFIABLE:unexpected proof result" ;;
    esac
}

# --- advance <task_file> --checked <sha> --fingerprint <fp> --owner <email> [--remove-ref <path>]... ---
#
# The ONE write path of the premise mechanism (t1663_4). The caller (the
# task-workflow Premise Staleness Procedure) runs it with ownership held, after
# the user explicitly confirmed the premise against the evidence a `check`
# printed. Transaction, in this order:
#
#   0. <task_file> must BE the active task the writer resolves by id;
#   1. re-run `check`; its FINGERPRINT must equal the prompted one, else the
#      confirmation is VOID (MISMATCH:) -- the metadata the user judged changed;
#   2. evidence that could not be checked (history_unavailable / malformed_row /
#      a Tier-B origin's unknown_history) refuses (ADVANCE_REFUSED:unverifiable) -- advancing would mark commits
#      nobody saw as reviewed;
#   3. every --remove-ref must be a `never_existed` path of the FRESH check
#      (ADVANCE_REFUSED:not_removable otherwise -- a live reference is never
#      removed), and the stored list must be all strings (else
#      ADVANCE_REFUSED:list_unwritable -- the writer refuses such a list by
#      design, and a partial write is exactly what this verb must not do);
#   3b. the task's lock must be held by --owner on this host AND by this
#      session (its recorded pid anchor is ours, per lock_anchor_is_self),
#      checked last before the write (ADVANCE_REFUSED:not_owner, or
#      ADVANCE_REFUSED:owner_unverifiable when either anchor cannot be named);
#   4. ONE aitask_update.sh invocation carries every removal AND the baseline.
#      That writer validates --premise-baseline (grammar + commit existence)
#      and reads the reference list before its single write, so a rejected
#      value leaves the task byte-identical. Never split it into two calls.
#      The baseline written is --checked -- the revision the user saw -- never
#      current HEAD: commits after it stay uncovered and surface next time;
#   5. commit the task file path-scoped (aitask_task_commit.sh).
#
# Output (exit 0 for every content state; CLI misuse dies):
#   MISMATCH:<prompted>|<fresh>            + the fresh protocol lines
#   ADVANCE_REFUSED:not_owner|<detail>     the lock is not held by --owner, here, by this session
#   ADVANCE_REFUSED:owner_unverifiable|<detail>  the holding session cannot be proven
#   ADVANCE_REFUSED:unverifiable|<n>       + the fresh protocol lines
#   ADVANCE_REFUSED:not_removable|<enc path>
#   ADVANCE_REFUSED:list_unwritable|<n invalid entries>
#   ADVANCE_FAILED:<reason>                (task file untouched)
#   REMOVED:<enc entry>                    0+ lines, then
#   ADVANCED:<checked sha>                 then the commit helper's output lines
#
# KNOWN LIMIT. The re-check -> write window is not atomic against writers that
# bypass the workflow (a sync merge, a hand edit). The task lock narrows it;
# the merge driver resolves divergent advances to PARTIAL (t1663_2).

cmd_advance() {
    local task_file="" checked="" fp="" owner=""
    local -a remove=()
    [[ $# -gt 0 ]] || die "advance requires <task_file>"
    task_file="$1"; shift
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --checked)     [[ $# -ge 2 ]] || die "--checked requires a value"; checked="$2"; shift 2 ;;
            --fingerprint) [[ $# -ge 2 ]] || die "--fingerprint requires a value"; fp="$2"; shift 2 ;;
            --owner)       [[ $# -ge 2 ]] || die "--owner requires an email"; owner="$2"; shift 2 ;;
            --remove-ref)  [[ $# -ge 2 && -n "$2" ]] || die "--remove-ref requires a path"
                           remove+=("$2"); shift 2 ;;
            *)             die "advance: unknown argument: $1" ;;
        esac
    done
    [[ -f "$task_file" ]] || die "task file not found: $task_file"
    [[ "$checked" =~ $_OID_RE ]] \
        || die "--checked must be a full lowercase 40/64-hex commit id (got '${checked}')"
    [[ "$fp" =~ ^[0-9a-f]{16}$ ]] \
        || die "--fingerprint must be 16 lowercase hex (got '${fp}'); a SKIP has nothing to confirm"
    [[ -n "$owner" ]] || die "--owner <email> is required: an advance is applied only by the session holding the task's lock"
    local task_id canonical
    _resolve_active_task "$task_file" advance
    task_id="$_ACTIVE_ID"; canonical="$_ACTIVE_PATH"

    # 1. fingerprint re-check (a subshell: cmd_check owns its own traps).
    local fresh fresh_fp line
    fresh=$(cmd_check "$task_file")
    fresh_fp=$(printf '%s\n' "$fresh" | sed -n 's/^FINGERPRINT://p' | head -n1)
    if [[ "$fresh_fp" != "$fp" ]]; then
        echo "MISMATCH:${fp}|${fresh_fp:-NONE}"
        printf '%s\n' "$fresh"
        return 0
    fi

    # 2. unverifiable evidence; collect never_existed paths for step 3.
    local n_unverifiable=0 enc reason
    local -a never=()
    while IFS= read -r line; do
        [[ "$line" == UNKNOWN:* ]] || continue
        enc="${line#UNKNOWN:}"; reason="${enc##*|}"; enc="${enc%|*}"
        case "$reason" in
            history_unavailable|malformed_row|unknown_history) n_unverifiable=$((n_unverifiable + 1)) ;;
            never_existed) _dec "$enc"; never+=("$_DEC") ;;
        esac
    done <<< "$fresh"
    if [[ $n_unverifiable -gt 0 ]]; then
        echo "ADVANCE_REFUSED:unverifiable|$n_unverifiable"
        printf '%s\n' "$fresh"
        return 0
    fi

    # 3. removals: each a never_existed path; resolve to the STORED entries
    #    (range suffixes are stripped by the check, so "a.sh:1-5" and "a.sh:9"
    #    both watch "a.sh" and both go).
    local -a entries=()
    if [[ ${#remove[@]} -gt 0 ]]; then
        local r n ok
        for r in "${remove[@]}"; do
            ok=0
            for n in "${never[@]+"${never[@]}"}"; do
                [[ "$n" == "$r" ]] && { ok=1; break; }
            done
            if [[ $ok -ne 1 ]]; then
                echo "ADVANCE_REFUSED:not_removable|$(_enc "$r")"
                return 0
            fi
        done
        local py fields_out f_rc=0 n_bad=0 raw
        py="$(resolve_python)"
        [[ -n "$py" ]] || { echo "ADVANCE_FAILED:python_unavailable"; return 0; }
        fields_out=$("$py" -c "$_FIELDS_GLUE" "$SCRIPT_DIR/lib" "$task_file" 2>/dev/null) || f_rc=$?
        if [[ $f_rc -ne 0 ]]; then
            echo "ADVANCE_FAILED:fields_unreadable"
            return 0
        fi
        while IFS= read -r line; do
            case "$line" in
                FIELD_BADREF:*) n_bad=$((n_bad + 1)) ;;
                FIELD_REF:*)
                    _dec "${line#FIELD_REF:}"; raw="$_DEC"
                    for r in "${remove[@]}"; do
                        if [[ "$(_strip_ranges "$raw")" == "$r" ]]; then
                            entries+=("$raw"); break
                        fi
                    done ;;
            esac
        done <<< "$fields_out"
        if [[ $n_bad -gt 0 ]]; then
            echo "ADVANCE_REFUSED:list_unwritable|$n_bad"
            return 0
        fi
    fi

    # 3b. ownership -- checked LAST before the write, so the window between
    #     this proof and the write is as short as it can be (_owner_proof).
    local proof
    proof=$(_owner_proof "$task_id" "$owner")
    if [[ "$proof" != "OK" ]]; then
        echo "ADVANCE_REFUSED:$proof"
        return 0
    fi

    # 4. one validated write.
    local -a upd=(--batch "$task_id")
    local e
    for e in "${entries[@]+"${entries[@]}"}"; do upd+=(--remove-file-ref "$e"); done
    upd+=(--premise-baseline "$checked" --silent)
    local upd_out upd_rc=0
    upd_out=$("$SCRIPT_DIR/aitask_update.sh" "${upd[@]}" 2>&1) || upd_rc=$?
    if [[ $upd_rc -ne 0 ]]; then
        local first
        first=$(printf '%s\n' "$upd_out" | grep -v '^[[:space:]]*$' | tail -n1)
        echo "ADVANCE_FAILED:writer_refused: ${first//$'\r'/}"
        return 0
    fi
    for e in "${entries[@]+"${entries[@]}"}"; do echo "REMOVED:$(_enc "$e")"; done
    echo "ADVANCED:$checked"

    # 5. path-scoped commit; its outcome lines are passed through verbatim.
    #    The CANONICAL path (identity proven in step 0): an alias outside the
    #    repository is out of the commit helper's scope.
    "$SCRIPT_DIR/aitask_task_commit.sh" -m "ait: Advance premise baseline for t${task_id}" \
        "$canonical" 2>&1 || true
}

# --- Dispatcher ---

cmd="${1:-}"
shift || true
case "$cmd" in
    check)          cmd_check "$@" ;;
    advance)        cmd_advance "$@" ;;
    owner)          cmd_owner "$@" ;;
    help|-h|--help) usage ;;
    "")             usage >&2; die "missing subcommand" ;;
    *)              die "Unknown subcommand: $cmd" ;;
esac
