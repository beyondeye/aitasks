#!/usr/bin/env bash
# aitask_trail_depth.sh — deterministic mode/depth resolver for /aitask-trail
# (t1505_4).
#
# WHY THIS EXISTS. The trail skill's Step 0 grammar has two orthogonal axes
# (mode and depth), position-independent depth flags, mutually exclusive mode
# selectors, and a conflict rule. Left as prose, the *model* applies that
# grammar and then types the resolved depth into both `rendering_hints.depth`
# and `trail_schema.py --expect-depth`. A self-consistent mistake — deciding
# "deep" on a flag-free invocation, writing the marker "deep", and asserting
# "deep" — validates cleanly, because every side of the claim came from the
# same place.
#
# This script moves the grammar out of the model: it parses the invocation's
# arguments and DECIDES. The skill forwards its arguments verbatim and copies
# the resolved DEPTH: line. That does not make the boundary fully trusted —
# the skill is prose executed by a model, so nothing here can stop a run that
# declines to call this script or mistypes what it forwards — but it removes
# the interpretation step, which is where a wrong-but-consistent depth comes
# from, and it makes the grammar executable and testable rather than a set of
# phrase pins. The residual limit is documented in the plan and in
# aidocs/implementation_trail_design.md §3.
#
# Usage:  aitask_trail_depth.sh resolve -- [args...]
#
# stdout (line protocol, split on the FIRST colon):
#   MODE:create|refresh|show|ambiguous_handle
#   DEPTH:lite|deep|n/a|unresolved  (the default is lite; n/a for show, which
#                                    authors nothing — the show flow reports the
#                                    artifact's STORED depth; unresolved for
#                                    ambiguous_handle, where the mode is not
#                                    decided yet — re-resolve after the choice)
#   HANDLE:<handle>                 (refresh / show / ambiguous_handle)
#   TOPICS:<csv>                    (--topics)
#   TARGET:<id>                     (bare task id)
#   NOTE:depth_ignored_for_show     (a depth flag was given with --show)
#   ERROR:<kind>[:<detail>]         (grammar violation; emitted alone)
#
# Exit: 0 resolved, 1 grammar violation (one ERROR: line), 2 usage.

set -euo pipefail

usage() {
    printf 'usage: %s resolve -- [args...]\n' "${0##*/}" >&2
    exit 2
}

[[ "${1:-}" == "resolve" ]] || usage
shift
[[ "${1:-}" == "--" ]] || usage
shift

mode=""          # create | refresh | show | ambiguous_handle
mode_flag=""     # the selector that set it, for the conflict message
handle=""
topics=""
target=""
depth=""         # empty until an explicit flag sets it
depth_flag_seen=0

fail() { printf 'ERROR:%s\n' "$1"; exit 1; }

set_mode() {
    if [[ -n "$mode" && "$mode" != "$1" ]]; then
        fail "conflicting_modes:$mode_flag,$2"
    fi
    if [[ -n "$mode" && "$mode" == "$1" ]]; then
        fail "repeated_mode:$2"
    fi
    mode="$1"
    mode_flag="$2"
}

# Sets OPERAND rather than echoing it. A `$(...)` capture would swallow the
# ERROR: line from fail() into the caller's variable and leave `set -e` to kill
# the script with no output at all — the exact silent-abort shape
# aidocs/framework/shell_conventions.md warns about, and what the first version
# of this script did (exit 1, empty stdout).
OPERAND=""
take_operand() {
    # $1 = flag name, $2 = the candidate operand.
    #
    # ANY dash-leading token is refused, not just a depth flag: `--refresh --`
    # and `--refresh --bogus` would otherwise resolve "successfully" to
    # HANDLE:art:-- / HANDLE:art:--bogus and send a malformed request
    # downstream. This script is the grammar authority and promises that a
    # grammar violation arrives as an ERROR line, so an option-looking operand
    # has to stop here rather than be normalized into a handle. A handle or
    # task id never begins with '-'.
    if [[ -z "${2:-}" || "${2}" == -* ]]; then
        fail "missing_operand:$1"
    fi
    OPERAND="$2"
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --deep|--lite)
            want="${1#--}"
            if [[ $depth_flag_seen -eq 1 && "$depth" != "$want" ]]; then
                # Never prefer one, never take the last occurrence: the flag
                # exists so the cost decision is explicit, and guessing it
                # defeats the purpose.
                fail "conflicting_depth_flags"
            fi
            depth="$want"
            depth_flag_seen=1
            shift
            ;;
        --refresh)
            set_mode refresh --refresh
            take_operand --refresh "${2:-}"; handle="$OPERAND"
            shift 2
            ;;
        --show)
            set_mode show --show
            take_operand --show "${2:-}"; handle="$OPERAND"
            shift 2
            ;;
        --topics)
            set_mode create --topics
            take_operand --topics "${2:-}"; topics="$OPERAND"
            shift 2
            ;;
        --)
            shift
            ;;
        -*)
            fail "unknown_flag:$1"
            ;;
        *)
            # Bare token: a handle (auto-detect) or a task id.
            if [[ "$1" == art:trail-* || "$1" == trail-* ]]; then
                set_mode ambiguous_handle "$1"
                handle="$1"
            else
                if [[ -n "$target" ]]; then
                    fail "unexpected_argument:$1"
                fi
                set_mode create "$1"
                target="$1"
            fi
            shift
            ;;
    esac
done

# Absence means lite — for create and refresh alike, including the board's R.
[[ -n "$depth" ]] || depth="lite"
[[ -n "$mode" ]] || mode="create"

# Normalize the handle to art:<trail-id>.
if [[ -n "$handle" && "$handle" != art:* ]]; then
    handle="art:$handle"
fi

printf 'MODE:%s\n' "$mode"
# DEPTH: is the AUTHORING depth for this run.
#
# show      -> n/a. Show authors nothing, so there is no run depth. Reporting
#              the caller's flag would be actively misleading: the show flow
#              states the artifact's STORED depth, and a run told "deep" could
#              print "deep" for a lite or entirely unmarked artifact.
# ambiguous -> unresolved. The mode is not decided yet (a bare trail-* token),
#              and depth is meaningful only once it is: emitting a usable
#              "deep" here is how a supplied flag leaks into a show that the
#              user only chooses afterwards. Withholding it makes the
#              re-resolve below structurally necessary rather than merely
#              instructed.
case "$mode" in
    show)             printf 'DEPTH:n/a\n' ;;
    ambiguous_handle) printf 'DEPTH:unresolved\n' ;;
    *)                printf 'DEPTH:%s\n' "$depth" ;;
esac
[[ -n "$handle" ]] && printf 'HANDLE:%s\n' "$handle"
[[ -n "$topics" ]] && printf 'TOPICS:%s\n' "$topics"
[[ -n "$target" ]] && printf 'TARGET:%s\n' "$target"
# Say the flag was dropped rather than silently dropping it, which would teach
# the user that `--show --deep` "worked".
[[ "$mode" == "show" && $depth_flag_seen -eq 1 ]] && printf 'NOTE:depth_ignored_for_show\n'

exit 0
