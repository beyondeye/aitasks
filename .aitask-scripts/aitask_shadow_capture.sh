#!/usr/bin/env bash
# aitask_shadow_capture.sh - Capture a followed agent's tmux pane as clean text.
#
# The shadow agent's runtime data source (t986_4). Given the tmux pane id of the
# agent being shadowed, capture its recent screen content through the tmux
# gateway and emit clean, escape-free text on stdout. The shadow skill calls
# this on demand, so it always reads the followed agent's *current* output
# rather than a frozen launch-time snapshot.
#
# Usage:
#   ./.aitask-scripts/aitask_shadow_capture.sh <pane_id>
#   ./.aitask-scripts/aitask_shadow_capture.sh --deep <pane_id>  # plan-review depth
#   ./.aitask-scripts/aitask_shadow_capture.sh -      # clean raw capture from stdin
#
#   <pane_id>   tmux pane id (e.g. %5) or any target the gateway can address.
#   --deep      Capture SHADOW_PLAN_CAPTURE_LINES (default 400) scrollback lines
#               instead of the default SHADOW_CAPTURE_LINES (200). For the shadow's
#               plan-review sub-procedures, whose long plans the 200-line window
#               can truncate. No effect with - (stdin has no scrollback).
#   -           Read a raw capture from stdin instead of tmux, clean it, emit it.
#               (Useful for piping a pre-captured buffer; also the test seam.)
#
# Output: the captured screen as plain text on stdout (CSI escape sequences
# stripped, trailing blank lines trimmed). Capture is read-only: this helper
# never sends input to the pane.
#
# Capture flags mirror monitor_core.py (`-p`, `-S -<N>`) but deliberately OMIT
# `-e`, so tmux emits escape-free cell text directly; shadow_strip_ansi is a
# belt-and-suspenders pass for stray control bytes a program wrote into the
# visible cells. `-J` joins soft-wrapped rows back into their logical lines so a
# long line is not split mid-word at the pane edge: required by the concern
# parser's capture-join contract (aidocs/framework/shadow_concern_format.md,
# t1037_4) and harmless for the shadow skill's prose reading. All tmux access
# routes through lib/tmux_exec.sh per tests/test_no_raw_tmux.sh.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/terminal_compat.sh
source "$SCRIPT_DIR/lib/terminal_compat.sh"
# shellcheck source=lib/tmux_exec.sh
source "$SCRIPT_DIR/lib/tmux_exec.sh"

# Scrollback lines to capture (mirrors monitor_core.py capture_lines default).
SHADOW_CAPTURE_LINES="${SHADOW_CAPTURE_LINES:-200}"

# Deeper scrollback for plan-review flows. The shadow's plan-* sub-procedures
# (plan-explain / plan-challenge / plan-socratic / plan-assumptions) analyze a
# whole plan; when the plan is only on screen (e.g. awaiting approval, not yet
# externalized) the 200-line default can truncate earlier constraints,
# decisions, or risk notes. Those procedures opt in with --deep, which selects
# this depth. Ordinary shadow reads (explain-output, help-answer-prompt,
# diagnose-errors) stay at SHADOW_CAPTURE_LINES to stay cheap. Env-overridable,
# mirroring SHADOW_CAPTURE_LINES.
SHADOW_PLAN_CAPTURE_LINES="${SHADOW_PLAN_CAPTURE_LINES:-400}"

show_help() {
    cat <<'EOF'
Usage: aitask_shadow_capture.sh <pane_id>
       aitask_shadow_capture.sh --deep <pane_id>   (deeper plan-review capture)
       aitask_shadow_capture.sh -                  (clean a raw capture from stdin)

Capture a followed agent's tmux pane as clean, escape-free text on stdout.

Arguments:
  <pane_id>   tmux pane id (e.g. %5) of the agent being shadowed
  --deep      capture SHADOW_PLAN_CAPTURE_LINES (default 400) scrollback lines
              instead of the default SHADOW_CAPTURE_LINES (200); for the shadow's
              plan-review sub-procedures, whose long plans the 200-line default
              can truncate. Has no effect with - (stdin has no scrollback).
  -           read raw capture from stdin instead of tmux

When run inside a shadow pane capturing its bound followed agent, this also
stamps the current epoch onto the shadow's own pane (@aitask_shadow_analyzed_at)
so minimonitor can detect stale feedback — i.e. the followed agent having changed
since the shadow last read it (t1104).

Read-only with respect to the followed pane: never sends input to it.
EOF
}

# shadow_strip_ansi - remove CSI escape sequences from stdin -> stdout.
# Portable: builds a literal ESC byte (GNU and BSD sed both match a literal
# byte; the \x1b shorthand is GNU-only). Pattern mirrors monitor_core.py
# _ANSI_CSI_RE = \x1b\[[0-?]*[ -/]*[@-~].
shadow_strip_ansi() {
    local esc
    esc=$(printf '\033')
    sed "s|${esc}\[[0-?]*[ -/]*[@-~]||g"
}

# shadow_clean - normalize captured text from stdin -> stdout: strip ANSI,
# strip trailing whitespace per line, and drop trailing blank lines (awk keeps
# everything up to the last non-blank line; a whitespace-only line is NF==0).
shadow_clean() {
    shadow_strip_ansi \
        | sed 's/[[:space:]]*$//' \
        | awk '{ a[NR] = $0 } NF { last = NR } END { for (i = 1; i <= last; i++) print a[i] }'
}

# shadow_capture_pane - capture a pane through the gateway -> stdout (raw).
# Optional $2 overrides the scrollback depth (defaults to the normal global, so
# existing call sites are unaffected); --deep passes SHADOW_PLAN_CAPTURE_LINES.
shadow_capture_pane() {
    local pane="$1"
    local lines="${2:-$SHADOW_CAPTURE_LINES}"
    ait_tmux capture-pane -p -J -t "$pane" -S "-${lines}"
}

# Pane-scoped tmux user-options (t1104). The shadow marker option is set by the
# spawn glue (monitor_core SHADOW_TARGET_OPTION); the analyzed-at option records
# *when* the shadow last read its followed agent, so minimonitor can tell whether
# the followed agent has produced new output since — i.e. whether the shadow's
# feedback is still current. A wall-clock epoch is used (not a content signature):
# an exact snapshot hash of a live terminal is too brittle — a render settling by
# a single character reads as "stale" even when the agent is idle. Comparing
# *times* (did the followed pane change after the shadow read it?) is robust to
# that jitter.
SHADOW_TARGET_OPTION="@aitask_shadow_target"
SHADOW_ANALYZED_AT_OPTION="@aitask_shadow_analyzed_at"

# shadow_stamp_analyzed_at - when this process is running *inside a shadow pane*
# and is capturing its bound followed agent, stamp the current wall-clock epoch
# onto the shadow's own pane. Best-effort: any failure is swallowed so the
# capture (the primary job) never breaks. Self-guarding: minimonitor's own
# captures run from the minimonitor pane (no @aitask_shadow_target) and the stdin
# path never reaches here, so they cannot mis-stamp.
#   $1 = captured pane id
shadow_stamp_analyzed_at() {
    local pane="$1"
    local own_pane="${TMUX_PANE:-}"
    # Guard TMUX_PANE under `set -u`: outside a live pane (tests, non-tmux
    # helper flows) there is nothing to stamp.
    [[ -n "$own_pane" ]] || return 0
    local self_target
    self_target="$(ait_tmux show-options -pqv -t "$own_pane" \
        "$SHADOW_TARGET_OPTION" 2>/dev/null || true)"
    # Only a shadow pane reading its own bound followed agent stamps.
    [[ -n "$self_target" && "$self_target" == "$pane" ]] || return 0
    ait_tmux set-option -p -t "$own_pane" \
        "$SHADOW_ANALYZED_AT_OPTION" "$(date +%s)" 2>/dev/null || true
}

main() {
    local pane="" deep=0
    while [[ $# -gt 0 ]]; do
        case "$1" in
            -h|--help) show_help; exit 0 ;;
            --deep)    deep=1; shift ;;
            -)         pane="-"; shift ;;
            -*)        die "Unknown option: $1" ;;
            *)
                [[ -z "$pane" ]] || die "Unexpected extra argument: $1"
                pane="$1"; shift ;;
        esac
    done

    [[ -n "$pane" ]] || { show_help >&2; die "pane id required"; }

    # --deep selects the deeper plan-review scrollback; default stays cheap.
    # (No effect on the stdin path — there is no scrollback to deepen.)
    local capture_lines="$SHADOW_CAPTURE_LINES"
    [[ "$deep" -eq 1 ]] && capture_lines="$SHADOW_PLAN_CAPTURE_LINES"

    if [[ "$pane" == "-" ]]; then
        shadow_clean
        return 0
    fi

    shadow_capture_pane "$pane" "$capture_lines" | shadow_clean
    # Record when this analysis read the followed pane (freshness anchor, t1104).
    shadow_stamp_analyzed_at "$pane"
}

# Run main only when executed directly (sourcing exposes the functions for
# tests / reuse without triggering a capture).
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
