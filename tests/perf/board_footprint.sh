#!/usr/bin/env bash
# board_footprint.sh - RSS and import cold-start of a TUI module (t1794_1).
#
# Usage: tests/perf/board_footprint.sh [--runs N] <module> <interpreter>
#   <module>       bare module name, resolved as <module>.py under
#                  .aitask-scripts/board/ or tests/perf/
#                  (e.g. aitask_board, trails_app, footprint_ceiling)
#   <interpreter>  python executable (e.g. ~/.aitask/venv/bin/python,
#                  ~/.aitask/pypy_venv/bin/python)
#   --runs N       independent runs (default 5; the margin rule needs >= 5)
#
# Every run takes two samples, each independent of every other run:
#   coldstart_ms  median wall time of 5 fresh `<interpreter> -c 'import <module>'`
#                 processes (interpreter startup included), after one discarded
#                 warm-up import per invocation (bytecode cache)
#   rss_mib       VmRSS of a fresh launch of <module>.py in its own tmux session
#                 (200x50) on a PRIVATE socket, sampled once after 10 s idle
#
# stdout: one provenance line, one raw line per run, then one summary line —
#   provenance head=<full sha> tree=<sha>[+<fp>] changed=<path,path,…|none>
#   <sha>[+<fp>] <module> <impl>-<ver> run=<i>/<N> rss_mib=<n> coldstart_ms=<n> load1=<x> parent_tasks=<n>
#   summary <module> <impl>-<ver> n=<N> rss_mib=<median> [<min>–<max>] coldstart_ms=<median> [<min>–<max>]
# `+<fp>` is a 12-hex fingerprint of the uncommitted diff under .aitask-scripts/
# and tests/perf/ (untracked files included); `changed=` names those paths. In a
# shared worktree that set may include other sessions' edits — measure in an
# isolated `git worktree` when the numbers must describe one change set.
#
# Manual and Linux-only (/proc); never collected by a test runner. Run with
# nothing else heavy in flight and compare within one session — the margin rule
# is in aidocs/framework/python_tui_performance.md, "t1794 baseline".
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
# The sourced path is built from $PROJECT_DIR, so plain `shellcheck` cannot
# follow it (SC1091, info). `source=` lets `shellcheck -x` follow and check the
# gateway; `disable=SC1091` keeps the plain invocation clean — the same pairing
# as tests/test_minimonitor_single_instance_guard.sh.
# shellcheck source-path=SCRIPTDIR/../..
# shellcheck source=.aitask-scripts/lib/tmux_exec.sh disable=SC1091
source "$PROJECT_DIR/.aitask-scripts/lib/tmux_exec.sh"

IDLE_SECONDS=10
COLDSTART_REPS=5
runs=5

usage() {
    echo "Usage: $0 [--runs N] <module> <interpreter>" >&2
    exit 2
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --runs) [[ $# -ge 2 ]] || usage; runs="$2"; shift 2 ;;
        -h|--help) usage ;;
        --) shift; break ;;
        -*) usage ;;
        *) break ;;
    esac
done
[[ $# -eq 2 ]] || usage
module="$1"
interp="$2"

[[ "$runs" =~ ^[1-9][0-9]*$ ]] || die "--runs must be a positive integer (got '$runs')"
[[ "$module" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]] || die "module must be a bare module name (got '$module')"
[[ -x "$interp" ]] || die "interpreter is not executable: $interp"
[[ -r /proc/self/status ]] || die "needs /proc (Linux)"
command -v tmux >/dev/null 2>&1 || die "tmux not found"
if (( runs < 5 )); then
    warn "--runs $runs < 5: too small a sample for the margin rule" >&2
fi

module_file=""
for dir in "$PROJECT_DIR/.aitask-scripts/board" "$PROJECT_DIR/tests/perf"; do
    if [[ -f "$dir/$module.py" ]]; then
        module_file="$dir/$module.py"
        break
    fi
done
[[ -n "$module_file" ]] || die "no $module.py under .aitask-scripts/board or tests/perf"

cd "$PROJECT_DIR"
pypath="$(dirname "$module_file"):$PROJECT_DIR/.aitask-scripts/board:$PROJECT_DIR/.aitask-scripts/lib:$PROJECT_DIR/.aitask-scripts"
impl="$("$interp" -c 'import platform, sys; print(f"{sys.implementation.name}-{platform.python_version()}")')"
interp_real="$(readlink -f "$interp")"
# Provenance: HEAD plus an exact fingerprint of every uncommitted change that can
# reach the measured code (.aitask-scripts/ and tests/perf/, untracked files
# included), and the list of those paths. A generic "-dirty" cannot tell one
# session's edits from another's in a shared worktree — measure in an isolated
# worktree when the numbers must describe a specific change set.
head="$(git rev-parse HEAD)"
sha="${head:0:9}"
mapfile -t changed < <(git status --porcelain --untracked-files=all -- .aitask-scripts tests/perf | cut -c4-)
if (( ${#changed[@]} )); then
    fp="$( { git diff HEAD --binary -- .aitask-scripts tests/perf
             git ls-files --others --exclude-standard -z -- .aitask-scripts tests/perf \
                 | xargs -0 -r sha256sum; } | sha256sum | cut -c1-12)"
    sha="$sha+$fp"
fi
changed_list="$(IFS=,; echo "${changed[*]:-none}")"
shopt -s nullglob
parent_files=(aitasks/t*.md)
shopt -u nullglob
parent_tasks="${#parent_files[@]}"

# A private tmux server: never the live `ait` socket, and not whatever $TMUX
# points at (a bare tmux inside an agent pane follows $TMUX).
export AITASKS_TMUX_SOCKET="ait_footprint_$$"
unset TMUX TMUX_PANE
session=""

end_session() {
    if [[ -n "$session" ]]; then
        ait_tmux kill-session -t "$(ait_tmux_session_target "$session")" >/dev/null 2>&1 || true
        session=""
    fi
    return 0
}
trap end_session EXIT

# median / range over numeric arguments.
median() {
    printf '%s\n' "$@" | sort -g | awk '{ v[NR] = $1 }
        END { if (NR % 2) printf "%s", v[(NR + 1) / 2]
              else printf "%.1f", (v[NR / 2] + v[NR / 2 + 1]) / 2 }'
}
range() {
    printf '%s\n' "$@" | sort -g | awk 'NR == 1 { lo = $1 } { hi = $1 }
        END { printf "%s–%s", lo, hi }'
}

import_ms() {
    local t0 t1
    t0="$(date +%s%N)"
    env -u TASK_DIR PYTHONPATH="$pypath" "$interp" -c "import $module" >/dev/null 2>&1 \
        || die "import $module failed under $interp"
    t1="$(date +%s%N)"
    echo $(( (t1 - t0) / 1000000 ))
}

coldstart_sample() {
    local -a reps=()
    local r
    for (( r = 0; r < COLDSTART_REPS; r++ )); do
        reps+=("$(import_ms)")
    done
    median "${reps[@]}"
}

# Sets RSS_MIB and LOAD1 (globals, so the EXIT trap still sees `session`).
rss_sample() {
    local run="$1" cmd pid exe status pane
    session="footprint_$$_$run"
    # Pane-scoped verbs need the `=session:` window form: with a bare
    # `=session` target, display-message formats against no pane and prints an
    # empty string (measured on tmux 3.7c). Session verbs keep `=session`.
    pane="$(ait_tmux_window_target "$session" "")"
    cmd="exec env -u TASK_DIR PYTHONPATH=$(printf '%q' "$pypath") $(printf '%q' "$interp") $(printf '%q' "$module_file")"
    ait_tmux new-session -d -s "$session" -x 200 -y 50 -c "$PROJECT_DIR" "$cmd"
    ait_tmux set-option -w -t "$pane" remain-on-exit on >/dev/null 2>&1 || true
    pid="$(ait_tmux display-message -p -t "$pane" '#{pane_pid}')"
    [[ "$pid" =~ ^[0-9]+$ ]] || die "could not read the pane pid (got '$pid')"
    sleep "$IDLE_SECONDS"
    status="/proc/$pid/status"
    if [[ ! -r "$status" ]] || [[ "$(ait_tmux display-message -p -t "$pane" '#{pane_dead}')" == "1" ]]; then
        ait_tmux capture-pane -p -t "$pane" >&2 || true
        die "$module exited before the ${IDLE_SECONDS}s sample (pane output above)"
    fi
    exe="$(readlink -f "/proc/$pid/exe")"
    [[ "$exe" == "$interp_real" ]] \
        || die "pane process $pid is $exe, not $interp_real — refusing to report its RSS"
    RSS_MIB="$(awk '/^VmRSS:/ { printf "%.1f", $2 / 1024 }' "$status")"
    [[ -n "$RSS_MIB" ]] || die "no VmRSS for pid $pid"
    LOAD1="$(cut -d' ' -f1 /proc/loadavg)"
    end_session
}

echo "provenance head=$head tree=$sha changed=$changed_list"
import_ms >/dev/null  # discarded warm-up: bytecode cache

rss_values=()
cold_values=()
for (( i = 1; i <= runs; i++ )); do
    cold="$(coldstart_sample)"
    rss_sample "$i"
    rss_values+=("$RSS_MIB")
    cold_values+=("$cold")
    echo "$sha $module $impl run=$i/$runs rss_mib=$RSS_MIB coldstart_ms=$cold load1=$LOAD1 parent_tasks=$parent_tasks"
done
echo "summary $module $impl n=$runs rss_mib=$(median "${rss_values[@]}") [$(range "${rss_values[@]}")] coldstart_ms=$(median "${cold_values[@]}") [$(range "${cold_values[@]}")]"
