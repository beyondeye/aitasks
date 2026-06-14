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
#   ./.aitask-scripts/aitask_shadow_capture.sh -      # clean raw capture from stdin
#
#   <pane_id>   tmux pane id (e.g. %5) or any target the gateway can address.
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
# visible cells. All tmux access routes through lib/tmux_exec.sh per
# tests/test_no_raw_tmux.sh.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/terminal_compat.sh
source "$SCRIPT_DIR/lib/terminal_compat.sh"
# shellcheck source=lib/tmux_exec.sh
source "$SCRIPT_DIR/lib/tmux_exec.sh"

# Scrollback lines to capture (mirrors monitor_core.py capture_lines default).
SHADOW_CAPTURE_LINES="${SHADOW_CAPTURE_LINES:-200}"

show_help() {
    cat <<'EOF'
Usage: aitask_shadow_capture.sh <pane_id>
       aitask_shadow_capture.sh -      (clean a raw capture read from stdin)

Capture a followed agent's tmux pane as clean, escape-free text on stdout.

Arguments:
  <pane_id>   tmux pane id (e.g. %5) of the agent being shadowed
  -           read raw capture from stdin instead of tmux

Read-only: never sends input to the pane.
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
shadow_capture_pane() {
    local pane="$1"
    ait_tmux capture-pane -p -t "$pane" -S "-${SHADOW_CAPTURE_LINES}"
}

main() {
    local pane=""
    while [[ $# -gt 0 ]]; do
        case "$1" in
            -h|--help) show_help; exit 0 ;;
            -)         pane="-"; shift ;;
            -*)        die "Unknown option: $1" ;;
            *)
                [[ -z "$pane" ]] || die "Unexpected extra argument: $1"
                pane="$1"; shift ;;
        esac
    done

    [[ -n "$pane" ]] || { show_help >&2; die "pane id required"; }

    if [[ "$pane" == "-" ]]; then
        shadow_clean
    else
        shadow_capture_pane "$pane" | shadow_clean
    fi
}

# Run main only when executed directly (sourcing exposes the functions for
# tests / reuse without triggering a capture).
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
