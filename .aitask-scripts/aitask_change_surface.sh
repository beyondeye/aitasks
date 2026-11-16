#!/usr/bin/env bash
# aitask_change_surface.sh - Per-task attribution of a repository's change surface
#
# Answers "which files did task t<id> change?" on a checkout that may hold
# several tasks' work at once. Replaces the raw `git diff --name-only HEAD` a
# consumer would otherwise run, which returns the ENTIRE dirty tree with no way
# to tell whose work it is (t1263).
#
# ---------------------------------------------------------------------------
# OWNERSHIP SIGNALS
#
#   P1  commit tag     proven positive   path is in a commit tagged (t<id>)
#   P2  plan scope     declared positive the task's own plan file names the path
#   N1  claim baseline proven negative   path was already dirty at claim time
#
# Nothing else attributes. A path with no positive signal is UNKNOWN and is the
# caller's to escalate -- never silently in scope.
#
# WHY N1 ALONE IS NOT ATTRIBUTION. A claim-time snapshot answers exactly one
# question: was this path already dirty before the task started? "Yes" is a
# proven negative. It cannot produce a positive:
#
#   t1 claims -> baseline = {}        # nothing dirty yet
#   t1 edits a.md
#   t2 claims -> baseline = {a.md}
#   t2 edits b.md                     # concurrent session, AFTER t1's claim
#   list 1    -> dirty = {a.md, b.md}, baseline(t1) = {} => BOTH look "new"
#
# b.md is indistinguishable from a.md by baseline alone, so the positive must
# come from P1 or P2 and everything else lands in UNKNOWN.
#
# RESIDUAL LIMITS (documented, not papered over):
#   - P2 is DECLARED, not proven. A concurrent edit to a file the plan happens
#     to name by exact path is classified TASK. Narrower than "any dirty file",
#     but real -- consumers should show the attributed set, not just UNKNOWN.
#   - Work the plan never named by exact path lands in UNKNOWN and needs
#     confirmation. Over-escalation is recoverable; false attribution is not.
#   - Worktree isolation is deliberately NOT a signal. That a tree is a linked
#     worktree on an aitask/* branch is an INFERENCE about how it was created,
#     not a proof: a reused or hand-made worktree can hold foreign dirt, and
#     trusting it would bypass the UNKNOWN escalation entirely. Proving it needs
#     framework-created-worktree metadata written at `git worktree add` time.
# ---------------------------------------------------------------------------
#
# All subcommands exit 0. Use output lines (not exit codes) for status.
#
# Usage:
#   ./.aitask-scripts/aitask_change_surface.sh capture <task-id>
#   ./.aitask-scripts/aitask_change_surface.sh list <task-id>
#   ./.aitask-scripts/aitask_change_surface.sh baseline <task-id>

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/terminal_compat.sh
source "$SCRIPT_DIR/lib/terminal_compat.sh"
# shellcheck source=lib/task_utils.sh
source "$SCRIPT_DIR/lib/task_utils.sh"
# shellcheck source=lib/atomic_write.sh
source "$SCRIPT_DIR/lib/atomic_write.sh"
# shellcheck source=lib/python_resolve.sh
source "$SCRIPT_DIR/lib/python_resolve.sh"
# lib/plan_paths_sh.sh is sourced LAZILY, by read_plan_scope: only `list` needs
# it, and `capture` -- run on every claim by aitask_pick_own.sh, including in
# scaffolded test repos that carry no plan-paths module -- must not grow a
# dependency it never uses.

# PATHS ARE BYTES (t2310). Every path this script handles is a raw filename as
# git reports it under -z, compared byte for byte: under a UTF-8 locale GNU
# `sort -u` may fold distinct names that collate equal, and grep may mis-handle
# a name that is not valid UTF-8. Set once, here, so no comparison below can
# forget it.
export LC_ALL=C

# Resolve the interpreter in THIS shell (not in a $(...) subshell) so the cache
# variable reaches both the plan-paths bridge and the v1 baseline decoder.
resolve_python >/dev/null 2>&1 || true

# Task/plan data paths are never part of a CODE change surface. Canonical site
# for this value set is `_DIGEST_EXCLUDES` in lib/gate_ledger.py (the code-state
# digest uses the same three); tests/test_change_surface.sh pins the two lists
# against each other so they cannot silently diverge.
EXCLUDES=(':(exclude)aitasks/**' ':(exclude)aiplans/**' ':(exclude).aitask-data/**')

BASELINE_ROOT="${AIT_CHANGE_SURFACE_DIR:-.aitask-gates}"

# Our own ephemeral state (baselines, gate sidecar logs). Separate from
# EXCLUDES above -- that array mirrors gate_ledger's canonical set and is
# drift-guarded against it; this one is this script's own bookkeeping. Normally
# redundant (`ait setup` gitignores .aitask-gates/, so --exclude-standard drops
# it), but a project that has not been through that step would otherwise see the
# baseline file reported as part of its own change surface.
SELF_EXCLUDES=(":(exclude)${BASELINE_ROOT}/**")

# --- Help ---
show_help() {
    cat <<'EOF'
Usage: aitask_change_surface.sh <subcommand> <task-id>

Classify a repository's change surface by which task each path belongs to.

Subcommands:
  capture <task-id>   Snapshot the working tree's dirty set as this task's
                      claim-time baseline (signal N1). Call once, at claim.
  list <task-id>      Print the task's classified change surface.
  baseline <task-id>  Print the raw claim-time baseline (signal N1 only).

`capture` output:
  CAPTURED:<n>              baseline written, <n> paths recorded
  CAPTURE_SKIPPED:<reason>  no baseline written (not_a_repo | no_commits)

`list` output -- two header lines, then one line per path:
  BASELINE:ok|missing|foreign     was signal N1 available?
  PLANSCOPE:ok|missing            was signal P2 available?
  COMMITTED:<path>   proven this task's (in a commit tagged (t<id>))
  TASK:<path>        declared this task's (named by the task's own plan)
  OTHER:<path>       proven other work (already dirty when this task claimed)
  UNKNOWN:<path>     no positive signal, or signals conflict -- ESCALATE

Both headers are always printed: a missing signal is its own state, not a
silent negative. Do NOT read PLANSCOPE:missing as "nothing is this task's".
PLANSCOPE:missing covers both "no plan file" and "the plan could not be
scanned" (the plan-reference search failed to run).

A rename is reported as two ordinary path lines -- its old path and its new
path -- each classified on its own (the same holds for `baseline`).

PATH ENCODING (both `list` and `baseline`):
  - Records are terminated by LF ALONE. Split on LF only -- never on a
    "universal newline" set: CR, VT and U+2028 are legal filename bytes.
  - A path is printed RAW (non-ASCII bytes as-is), split at the first `:`
    after the prefix.
  - A path that contains a control byte (LF, CR, TAB, ...) or begins with `"`
    is printed in git's C-quote form instead ("a\nb.md"). Such a path is never
    attributed TASK.
  - A path field that begins with `"` MUST be decoded with git's C-quote
    grammar BEFORE any filesystem lookup. Its wire spelling names no file -- a
    tracked file may literally be called `"a\nb.md"`.

`baseline` output -- one header line, then one line per recorded path:
  BASELINE:ok|missing|foreign
  DIRTY_AT_CLAIM:<path>     already dirty when the task was claimed

Unlike `list`, `baseline` combines N1 with nothing: a path the plan names is
still reported. The shadow's evidence helper needs the raw signal, because
`list` folds "plan names it AND it was dirty at claim" into UNKNOWN.
EOF
}

# --- Baseline path -----------------------------------------------------------
baseline_file() {
    printf '%s/%s/change_baseline\n' "$BASELINE_ROOT" "$1"
}

# --- git helpers -------------------------------------------------------------

# _z_to_lines: NUL-delimited paths on stdin -> one record per line on stdout.
#
# RAW, EXCEPT WHERE A RAW PATH WOULD BREAK THE LINE GRAMMAR (t2310). Every path
# is printed as git reported it under -z (non-ASCII bytes included), EXCEPT a
# path that contains a control byte (0x01-0x1f, 0x7f) or begins with `"`, which
# is printed in git's C-quote form: wrapped in `"..."`, `\` -> `\\`, `"` -> `\"`,
# `\a \b \t \n \v \f \r` by name, any other control byte as 3-digit octal.
#
#   - LF cannot be carried by a line at all.
#   - CR is unsafe raw too: a reader whose scanner drops one trailing CR (Go's
#     bufio.ScanLines, used by the testmap intake) would read
#     `COMMITTED:src/a.md<CR>` as `src/a.md` -- a different, possibly existing
#     file -- with no error. The same holds for any "universal newline" reader.
#   - Quoting a leading `"` too keeps the encoding INJECTIVE: every record whose
#     path field begins with `"` is an escaped form, and nothing else is.
#
# The escape is the subset of git's grammar that Python's codecs.escape_decode
# and the testmap intake's unquote both accept. An escaped record's wire
# spelling names no file: a consumer must decode it before any lookup.
_z_to_lines() {
    local p out c i code
    while IFS= read -r -d '' p; do
        [[ -n "$p" ]] || continue
        if [[ "$p" == *[[:cntrl:]]* || "$p" == \"* ]]; then
            out=""
            # shellcheck disable=SC1003  # '\\' is two literal backslashes, intended
            for (( i = 0; i < ${#p}; i++ )); do
                c="${p:i:1}"
                case "$c" in
                    \\) out+='\\' ;;
                    \") out+='\"' ;;
                    $'\a') out+='\a' ;;
                    $'\b') out+='\b' ;;
                    $'\t') out+='\t' ;;
                    $'\n') out+='\n' ;;
                    $'\v') out+='\v' ;;
                    $'\f') out+='\f' ;;
                    $'\r') out+='\r' ;;
                    [[:cntrl:]])
                        printf -v code '%d' "'$c"
                        printf -v c '\\%03o' "$code"
                        out+="$c" ;;
                    *) out+="$c" ;;
                esac
            done
            p="\"${out}\""
        fi
        printf '%s\n' "$p"
    done
}

# Dirty ∪ untracked, repo-relative, excluding task/plan data. Prints nothing
# when git is unavailable or the tree is clean.
#
# The trailing `|| true` is load-bearing: on a clean tree `grep -v '^$'` finds
# no lines and exits 1, and under `set -o pipefail` that failure propagates out
# of the command substitution and kills the caller with no message at all
# (shell_conventions.md, "silent set -e aborts via $(...) capture").
#
# RENAMES ARE TWO PATHS (t2304). `--no-renames` is load-bearing on this read AND
# on pass A's `git show` in cmd_list: git's default rename detection prints only
# a rename's NEW path, so the OLD one would never reach the surface. The testmap
# selector escalates a listed path that is absent from the tree to a full run (a
# deleted import drops every relationship derived from it); a missing old path
# under-selects instead, silently. Both reads carry the flag so `capture` /
# `baseline` and `list` see the same path set. It also overrides a user's
# `diff.renames` config (including `copies`). No new line prefix: each half is
# an ordinary path, classified by the ordinary rules.
#
# `-z` on both reads (t2310): without it git C-quotes any non-ASCII or special
# path under the default core.quotePath, and that quoted spelling can never
# equal a plan reference or the raw path another consumer compares against.
current_dirty_set() {
    {
        git diff --no-renames --name-only -z HEAD -- . "${EXCLUDES[@]}" "${SELF_EXCLUDES[@]}" 2>/dev/null || true
        git ls-files --others --exclude-standard -z -- . "${EXCLUDES[@]}" "${SELF_EXCLUDES[@]}" 2>/dev/null || true
    } | _z_to_lines | sed 's|^\./||' | grep -v '^$' | sort -u || true
}

# --- capture -----------------------------------------------------------------
cmd_capture() {
    local task_id="${1:-}"
    [[ -n "$task_id" ]] || die "Usage: aitask_change_surface.sh capture <task-id>"

    local toplevel head
    toplevel="$(git rev-parse --show-toplevel 2>/dev/null || true)"
    if [[ -z "$toplevel" ]]; then
        echo "CAPTURE_SKIPPED:not_a_repo"
        return 0
    fi
    head="$(git rev-parse HEAD 2>/dev/null || true)"
    if [[ -z "$head" ]]; then
        # An unborn HEAD has no diff base; the baseline would be meaningless.
        echo "CAPTURE_SKIPPED:no_commits"
        return 0
    fi

    local paths count content
    paths="$(current_dirty_set)"
    count=0
    [[ -n "$paths" ]] && count="$(printf '%s\n' "$paths" | wc -l | tr -d ' ')"

    local dest
    dest="$(baseline_file "$task_id")"
    mkdir -p "$(dirname "$dest")"

    # version=2: paths are recorded in _z_to_lines' encoding (raw, escaped only
    # where a raw path would break a line). A version=1 file recorded git's
    # default C-quoting instead; read_baseline converts it.
    content="version=2
task=${task_id}
toplevel=${toplevel}
head=${head}
captured_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)
paths:
${paths}"

    ait_atomic_write_text "$dest" "$content" || {
        warn "change-surface: could not write baseline $dest" >&2
        echo "CAPTURE_SKIPPED:write_failed"
        return 0
    }
    echo "CAPTURED:${count}"
}

# --- baseline read -----------------------------------------------------------
# Sets BASELINE_STATE (ok|missing|foreign) and BASELINE_PATHS (newline list).
read_baseline() {
    local task_id="$1" file recorded_top current_top
    BASELINE_STATE="missing"
    BASELINE_PATHS=""

    file="$(baseline_file "$task_id")"
    [[ -f "$file" ]] || return 0

    recorded_top="$(sed -n 's/^toplevel=//p' "$file" | head -n1)"
    current_top="$(git rev-parse --show-toplevel 2>/dev/null || true)"
    # A baseline taken in a different tree describes a different working set;
    # applying it here could exclude a path this task legitimately changed.
    if [[ -n "$recorded_top" && -n "$current_top" && "$recorded_top" != "$current_top" ]]; then
        BASELINE_STATE="foreign"
        return 0
    fi

    BASELINE_STATE="ok"
    BASELINE_PATHS="$(sed -n '/^paths:$/,$p' "$file" | tail -n +2 | grep -v '^$' || true)"

    # A version=1 baseline (written before t2310) recorded git's default
    # C-quoting: `"d\303\251.md"` for a path the current dirty set now reports
    # raw. Left as is, the two never match -- N1 is silently lost for that path,
    # and a plan-named, pre-claim-dirty path flips from UNKNOWN to a false TASK.
    # Decode each quoted record to its bytes and re-encode it through the same
    # _z_to_lines the dirty set uses. On a decode failure keep the records as
    # they are (the pre-t2310 behaviour) and say so.
    local version converted
    version="$(sed -n 's/^version=//p' "$file" | head -n1)"
    if [[ "$version" != "2" ]] && grep -q '^"' <<<"$BASELINE_PATHS"; then
        if converted="$(printf '%s\n' "$BASELINE_PATHS" | "${_AIT_RESOLVED_PYTHON:-python3}" -c '
import codecs, sys
out = sys.stdout.buffer
for line in sys.stdin.buffer.read().split(b"\n"):
    if not line:
        continue
    if len(line) >= 2 and line.startswith(b"\"") and line.endswith(b"\""):
        line = codecs.escape_decode(line[1:-1])[0]
    out.write(line + b"\0")
' 2>/dev/null | _z_to_lines)"; then
            BASELINE_PATHS="$converted"
        else
            warn "change-surface: could not decode the version-1 baseline $file; quoted records kept as recorded" >&2
        fi
    fi
}

# --- plan scope (P2) ---------------------------------------------------------
# Sets PLANSCOPE_STATE (ok|missing) and PLANSCOPE_PATHS (newline list).
#
# THE INVERTED SEARCH, NOT A GRAMMAR (t2310). P2 is only ever consulted as a
# membership test over the DIRTY set (cmd_list pass B), so the question is
# "which of these git-reported paths does the plan mention?" -- exactly what
# lib/plan_paths.py's find_references answers, through the lib/plan_paths_sh.sh
# bridge the remote drift check also uses. The candidates are the dirty paths
# themselves, byte for byte, so there is no filename grammar to get wrong: `|`,
# `@`, spaces, non-ASCII and an NFD name the plan writes in NFC all work. (The
# local `[A-Za-z0-9_./-]` tokenizer this replaces split `docs/a|b.md` and
# dropped every non-ASCII name.) Delimiter rules, NFC mapping and
# undecodable-byte handling: aidocs/framework/plan_path_reference_extraction_findings.md
# sections 3-5, and section 7 for this consumer's switch.
#
# EXACT FILE MATCHES ONLY. A reference must be the whole candidate path bounded
# by delimiters, so a directory the plan names in prose (.aitask-scripts/,
# tests/ ...) never attributes the files beneath it -- treating it as a
# recursive scope prefix would attribute nearly the whole repo, reopening the
# very failure this script exists to close.
#
# Only `full` hits attribute. `bare` (a single component with no `.`: `ait`,
# `Makefile`) is the same word as ordinary prose ("run `ait setup`"), and
# `suffix` (a module-relative trailing sub-path) is ambiguous across modules;
# both are evidence elsewhere, never a positive here. An escaped record (see
# _z_to_lines) is never a candidate: its spelling is not the path.
#
# Plan text is DATA: the search escapes every candidate and never evaluates the
# plan, which is agent/user-authored and may contain `.*` or `$(id)`.
#
# FAILS CLOSED. When the search cannot run (no interpreter, module missing, plan
# unreadable) the signal is unavailable: PLANSCOPE:missing, never an "ok" with
# nothing attributed -- the two would otherwise look identical.
read_plan_scope() {
    local task_id="$1" plan_file="" dirty="$2"
    PLANSCOPE_STATE="missing"
    PLANSCOPE_PATHS=""

    plan_file="$(resolve_plan_file "$task_id" 2>/dev/null || true)"
    if [[ -z "$plan_file" || ! -f "$plan_file" ]]; then
        return 0
    fi
    if [[ -z "$dirty" ]]; then
        # Nothing to attribute; the plan was found, so the signal is available.
        PLANSCOPE_STATE="ok"
        return 0
    fi

    local refs line keep=""
    # shellcheck source=lib/plan_paths_sh.sh
    if ! source "$SCRIPT_DIR/lib/plan_paths_sh.sh" 2>/dev/null \
        || ! refs="$( { grep -v '^"' <<<"$dirty" || true; } | tr '\n' '\0' \
            | plan_paths_references "$plan_file")"; then
        warn "change-surface: the plan-scope search could not run for $plan_file; reporting PLANSCOPE:missing" >&2
        return 0
    fi
    PLANSCOPE_STATE="ok"

    # `<kind>\t<path>`: the path is everything after the FIRST tab. (A path
    # holding a tab is a control-byte path, escaped and never a candidate.)
    while IFS= read -r line; do
        [[ "${line%%$'\t'*}" == "full" ]] && keep+="${line#*$'\t'}"$'\n'
    done <<< "$refs"

    PLANSCOPE_PATHS="$(printf '%s' "$keep" | grep -v '^$' | sort -u || true)"
}

# --- list --------------------------------------------------------------------
cmd_list() {
    local task_id="${1:-}"
    [[ -n "$task_id" ]] || die "Usage: aitask_change_surface.sh list <task-id>"

    local dirty committed
    dirty="$(current_dirty_set)"

    # Pass A input: every path in a commit tagged (t<id>). -F keeps the tag a
    # fixed string, so "(t126)" never matches "(t1263)".
    committed=""
    if git rev-parse HEAD >/dev/null 2>&1; then
        local shas sha
        shas="$(git log -F --grep="(t${task_id})" --format=%H 2>/dev/null || true)"
        if [[ -n "$shas" ]]; then
            while IFS= read -r sha; do
                [[ -n "$sha" ]] || continue
                # No `--` before the sha: that would make git read it as a
                # PATHSPEC rather than a revision, and Pass A would silently
                # return nothing for every task (t1263). `--no-renames`: a
                # renamed file contributes BOTH paths -- see current_dirty_set.
                # `-z` + _z_to_lines: raw paths, same encoding as the dirty set
                # (t2310). The pathspec applies the data-path exclusion BEFORE
                # encoding, so an escaped `aitasks/...` record cannot slip past
                # the line filter below.
                committed+="$(git show --no-renames --name-only -z --format= "$sha" \
                    -- . "${EXCLUDES[@]}" 2>/dev/null | _z_to_lines || true)"$'\n'
            done <<< "$shas"
        fi
    fi
    # The same data-path exclusion the dirty scan uses (belt to the pathspec).
    committed="$(printf '%s' "$committed" | sed 's|^\./||' | grep -v '^$' \
        | grep -Ev '^(aitasks/|aiplans/|\.aitask-data/)' | sort -u || true)"

    read_baseline "$task_id"
    read_plan_scope "$task_id" "$dirty"

    echo "BASELINE:${BASELINE_STATE}"
    echo "PLANSCOPE:${PLANSCOPE_STATE}"

    # --- Pass A: the tagged-commit set, emitted UNCONDITIONALLY ---------------
    # Independent of the dirty scan: a task that committed code earlier and left
    # the file clean still contributes it to the surface. Do not fold this into
    # the dirty loop.
    local p
    if [[ -n "$committed" ]]; then
        while IFS= read -r p; do
            [[ -n "$p" ]] && echo "COMMITTED:${p}"
        done <<< "$committed"
    fi

    # --- Pass B: the dirty set, classified; Pass A paths de-duplicated out ----
    [[ -n "$dirty" ]] || return 0
    local in_plan in_base
    while IFS= read -r p; do
        [[ -n "$p" ]] || continue
        # COMMITTED is the strongest signal: report such a path once, in Pass A.
        if [[ -n "$committed" ]] && printf '%s\n' "$committed" | grep -qxF -- "$p"; then
            continue
        fi
        in_plan=0; in_base=0
        [[ "$PLANSCOPE_STATE" == "ok" && -n "$PLANSCOPE_PATHS" ]] &&
            printf '%s\n' "$PLANSCOPE_PATHS" | grep -qxF -- "$p" && in_plan=1
        [[ "$BASELINE_STATE" == "ok" && -n "$BASELINE_PATHS" ]] &&
            printf '%s\n' "$BASELINE_PATHS" | grep -qxF -- "$p" && in_base=1

        if [[ "$in_plan" -eq 1 && "$in_base" -eq 1 ]]; then
            # Signals conflict (plan names it, but it was already dirty at
            # claim). Never guess a winner.
            echo "UNKNOWN:${p}"
        elif [[ "$in_plan" -eq 1 ]]; then
            echo "TASK:${p}"
        elif [[ "$in_base" -eq 1 ]]; then
            echo "OTHER:${p}"
        else
            # Appeared after the claim and unnamed by the plan -- the
            # concurrent-session case. Escalate; do not attribute.
            echo "UNKNOWN:${p}"
        fi
    done <<< "$dirty"
}

# --- baseline ----------------------------------------------------------------
# The raw N1 signal, uncombined. Consumers that weigh evidence themselves
# (aitask_shadow_scope.sh) must see a pre-claim-dirty path even when the plan
# names it -- `list` reports that combination as UNKNOWN, losing the N1 half.
cmd_baseline() {
    local task_id="${1:-}" p
    [[ -n "$task_id" ]] || die "Usage: aitask_change_surface.sh baseline <task-id>"
    read_baseline "$task_id"
    echo "BASELINE:${BASELINE_STATE}"
    [[ "$BASELINE_STATE" == "ok" && -n "$BASELINE_PATHS" ]] || return 0
    while IFS= read -r p; do
        [[ -n "$p" ]] && echo "DIRTY_AT_CLAIM:${p}"
    done <<< "$BASELINE_PATHS"
}

# --- Main ---
main() {
    local cmd="${1:-}"
    [[ $# -gt 0 ]] && shift
    case "$cmd" in
        capture) cmd_capture "$@" ;;
        list)    cmd_list "$@" ;;
        baseline) cmd_baseline "$@" ;;
        -h|--help|help|"") show_help ;;
        *) die "Unknown subcommand: $cmd (try --help)" ;;
    esac
}

main "$@"
