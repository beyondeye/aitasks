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
#   ./.aitask-scripts/aitask_shadow_capture.sh            # resolve from the binding
#   ./.aitask-scripts/aitask_shadow_capture.sh <pane_id>
#   ./.aitask-scripts/aitask_shadow_capture.sh --deep <pane_id>  # plan-review depth
#   ./.aitask-scripts/aitask_shadow_capture.sh -      # clean raw capture from stdin
#
#   (no args)   resolve the followed pane from THIS pane's @aitask_shadow_target
#               binding (t1319). This is the primary form for a spawned shadow:
#               the pane id never crosses the model's token stream, so it cannot
#               be mangled in transcription. Fails closed (exit 1) when there is
#               no verifiable binding — it never falls back to a guess.
#   <pane_id>   tmux pane id (e.g. %237) or any target the gateway can address.
#   --deep      Capture SHADOW_PLAN_CAPTURE_LINES (default 400) scrollback lines
#               instead of the default SHADOW_CAPTURE_LINES (200). The plan-review
#               depth: used by the shadow's plan-review sub-procedures, whose long
#               plans the 200-line window can truncate, and by minimonitor's
#               capture of the shadow pane for the concern picker, whose block is
#               itself plan-review-sized. No effect with - (stdin has no scrollback).
#   --any-pane  Capture the given <pane_id> even when this pane's own binding
#               says otherwise (see "Wrong-pane refusal" below). The single
#               sanctioned opt-out; every other caller should leave it off.
#   -           Read a raw capture from stdin instead of tmux, clean it, emit it.
#               (Useful for piping a pre-captured buffer; also the test seam.)
#
# Output: the captured screen as plain text on stdout (CSI escape sequences
# stripped, trailing blank lines trimmed). Capture is read-only: this helper
# never sends input to the pane. Resolution notices go to stderr so stdout stays
# pure capture text.
#
# Wrong-pane refusal (t1319). A pane id transcribed by a model can be truncated
# (%237 -> %7) into an id that names a DIFFERENT live pane: the capture then
# succeeds, raises no error, and the shadow advises on the wrong agent's work.
# So when an explicit <pane_id> is given, this helper consults its own pane:
#
#   own pane state                       decision
#   -----------------------------------  --------------------------------------
#   TMUX_PANE unset (no tmux context)    allow — nothing can contradict the arg
#   same server, no binding              allow — a true unbound caller
#   same server, binding == <pane_id>    allow
#   same server, binding != <pane_id>    REFUSE, exit 2 (conflicting binding)
#   different/unverifiable server        REFUSE, exit 2 (cross-server)
#
# --any-pane overrides both refusals. "Cross-server" refuses rather than falling
# through to "unbound" on purpose: pane ids collide across tmux servers, so a
# caller whose own binding we cannot read is exactly the case where a truncated
# id may name a live pane on the server we ARE addressing.
#
# Capture flags mirror monitor_core.py (`-p`, `-S -<N>`) but deliberately OMIT
# `-e`, so tmux emits escape-free cell text directly; shadow_strip_ansi is a
# belt-and-suspenders pass for stray control bytes a program wrote into the
# visible cells. `-J` joins soft-wrapped rows back into their logical lines so a
# long line is not split mid-word at the pane edge: required by the concern
# parser's capture-join contract (.claude/skills/aitask-shadow/concern-format.md,
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
# this depth. Minimonitor's capture of the SHADOW pane for the concern picker
# opts in too: the shadow's concern block is plan-review-sized output, and at
# the narrow width a shadow pane runs at, the 200-line window can start inside
# the block and clip its opening fence (t1187). Ordinary shadow reads
# (explain-output, help-answer-prompt, diagnose-errors) stay at
# SHADOW_CAPTURE_LINES to stay cheap. Env-overridable, mirroring
# SHADOW_CAPTURE_LINES.
SHADOW_PLAN_CAPTURE_LINES="${SHADOW_PLAN_CAPTURE_LINES:-400}"

# How long the no-argument path waits for its @aitask_shadow_target binding
# (t1319). `spawn_shadow` (monitor/monitor_core.py) stamps the option only AFTER
# `launch_in_tmux` returns, so a shadow that captures in its first moments can
# outrun its own stamp. Poll briefly, then fail closed — never guess. Set to 0
# to disable the wait entirely (used by the ordering test's negative control).
SHADOW_BIND_WAIT_MS="${SHADOW_BIND_WAIT_MS:-2000}"
SHADOW_BIND_POLL_MS=100

show_help() {
    cat <<'EOF'
Usage: aitask_shadow_capture.sh                    (resolve from this pane's binding)
       aitask_shadow_capture.sh <pane_id>
       aitask_shadow_capture.sh --deep <pane_id>   (deeper plan-review capture)
       aitask_shadow_capture.sh --phase [<task_id>] (advisory workflow phase; one line, always exit 0)
       aitask_shadow_capture.sh -                  (clean a raw capture from stdin)

Capture a followed agent's tmux pane as clean, escape-free text on stdout.

Arguments:
  (no args)   resolve the followed pane from THIS pane's @aitask_shadow_target
              binding — the preferred form for a spawned shadow, because the
              pane id never has to be transcribed and so cannot be mangled.
              Exits 1 if there is no verifiable binding; never guesses.
  <pane_id>   tmux pane id (e.g. %237) of the agent being shadowed; pass it
              exactly as given — never abbreviate or re-derive it
  --deep      capture SHADOW_PLAN_CAPTURE_LINES (default 400) scrollback lines
              instead of the default SHADOW_CAPTURE_LINES (200); the plan-review
              depth, used by the shadow's plan-review sub-procedures (whose long
              plans the 200-line default can truncate) and by minimonitor's
              shadow-pane capture for the concern picker. Has no effect with -
              (stdin has no scrollback).
  --any-pane  capture <pane_id> even when this pane's own binding disagrees
              (or cannot be verified because this pane is on another tmux
              server). Without it, either case exits 2 rather than risk a
              silent wrong-pane capture.
  -           read raw capture from stdin instead of tmux

Environment:
  SHADOW_BIND_WAIT_MS   ms to wait for the binding on the no-argument path
                        (default 2000; 0 disables the wait)

Exit codes: 1 = usage / no resolvable pane id; 2 = refused (conflicting binding
or unverifiable cross-server caller) — re-run with no argument, or --any-pane.

When run inside a shadow pane capturing its bound followed agent, this also
stamps the current epoch onto the shadow's own pane (@aitask_shadow_analyzed_at)
so minimonitor can detect stale feedback — i.e. the followed agent having changed
since the shadow last read it (t1104).

Read-only with respect to the followed pane: never sends input to it.
EOF
}

# shadow_strip_ansi - remove OSC and CSI escape sequences from stdin -> stdout.
# Portable: builds literal ESC / BEL bytes (GNU and BSD sed both match a literal
# byte; the \x1b shorthand is GNU-only). Mirrors monitor/ansi_utils.py —
# ANSI_OSC_RE = \x1b\][^\x07\x1b]*(?:\x07|\x1b\\) then
# ANSI_CSI_RE = \x1b\[[0-?]*[ -/]*[@-~] — and tests/test_shadow_strip_ansi.sh
# asserts the two implementations agree, so this is a checked mirror rather than
# a hand-maintained one.
#
# The OSC pass earns its keep on the `-` stdin form, whose input is whatever the
# user pasted: a `capture-pane -e` transcript carries OSC 8 hyperlinks verbatim
# (ESC]8;;<url>ESC\ text ESC]8;;ESC\). The tmux path here omits `-e` and so sees
# none — the pass is harmless there.
#
# Two expressions rather than one alternation: `\|` in a BRE is a GNU extension
# that BSD sed rejects (aidocs/framework/sed_macos_issues.md). Bracketing the
# body as [^BEL ESC]* keeps each substitution inside a single sequence, so an
# unterminated OSC is left intact instead of swallowing the visible text after
# it — same fail-safe direction the Python side documents.
shadow_strip_ansi() {
    local esc bel
    esc=$(printf '\033')
    bel=$(printf '\007')
    sed -e "s|${esc}\][^${bel}${esc}]*${bel}||g" \
        -e "s|${esc}\][^${bel}${esc}]*${esc}\\\\||g" \
        -e "s|${esc}\[[0-?]*[ -/]*[@-~]||g"
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
# Advisory workflow-phase signal stamped on THIS pane by the monitor TUIs
# (monitor_core.SHADOW_PHASE_OPTION, t1420). Read-only here.
SHADOW_PHASE_OPTION="@aitask_shadow_phase"
# Emitted by --phase when nothing can be resolved. Mirrors
# lib/workflow_phase.format_signal so the skill parses one shape either way.
SHADOW_PHASE_UNKNOWN_LINE="PHASE:UNKNOWN|WAITING:UNKNOWN|SOURCE:none|CONSULTED:-|RECORDING:unknown|DETAIL:no phase stamp and no task id"

# shadow_self_target - classify THIS pane's shadow binding (t1319). Echoes one
# of four states on stdout:
#
#   ""              TMUX_PANE is unset — no tmux context at all, nothing to say
#   "unbound"       this pane is on the gateway server and carries no binding
#   "bound:<id>"    this pane is a shadow bound to followed pane <id>
#   "cross-server"  this pane belongs to a DIFFERENT tmux server than the one
#                   the gateway addresses, or its identity could not be read
#
# The four-way return is load-bearing: "verified unbound" and "could not verify"
# must not collapse into one value. `ait_tmux` addresses the dedicated `ait`
# socket by default while $TMUX_PANE names a pane on whatever server the CALLER
# is attached to, and pane ids collide across servers — so reading a foreign
# server's @aitask_shadow_target and acting on it would be exactly the
# wrong-pane hazard this file exists to prevent.
#
# `#{socket_path}` is the queried server's socket path and $TMUX is
# "<socket-path>,<server-pid>,<session-index>"; asking for both the socket and
# the option in ONE display-message keeps this at a single round-trip.
shadow_self_target() {
    local own_pane="${TMUX_PANE:-}"
    # Guard TMUX_PANE under `set -u`: outside a live pane (tests, non-tmux
    # helper flows) there is nothing to classify.
    [[ -n "$own_pane" ]] || return 0
    local own_sock="${TMUX:-}"
    own_sock="${own_sock%%,*}"
    local fmt out sock="" target=""
    fmt="#{socket_path}"$'\t'"#{${SHADOW_TARGET_OPTION}}"
    out="$(ait_tmux display-message -p -t "$own_pane" "$fmt" 2>/dev/null || true)"
    if [[ "$out" == *$'\t'* ]]; then
        sock="${out%%$'\t'*}"
        target="${out#*$'\t'}"
    fi
    # No $TMUX (an inherited/stale TMUX_PANE), an unreadable pane, or a socket
    # that is not ours ⇒ we cannot vouch for this pane's binding.
    if [[ -z "$own_sock" || -z "$sock" || "$own_sock" != "$sock" ]]; then
        printf '%s' "cross-server"
        return 0
    fi
    if [[ -n "$target" ]]; then
        printf '%s' "bound:$target"
    else
        printf '%s' "unbound"
    fi
}

# shadow_wait_self_target - shadow_self_target, but bounded-polling for a
# binding that has not landed yet (t1319). Used ONLY by the no-argument path:
# the explicit-argument path and its refusal guard must never be delayed, and
# `capture_shadow_text`'s per-tick capture runs on that path.
#
# Echoes whatever state it ends on — "bound:<id>" as soon as one appears, else
# the last observed state once the budget is spent. The caller fails closed on
# anything that is not "bound:"; waiting never turns into guessing.
#
# Only "unbound" is worth waiting on: it is the one state the pending stamp can
# change. "" (not in a pane) and "cross-server" are properties of where this
# process runs, so they are terminal and returned immediately rather than
# burning the whole budget on a verdict that cannot move.
shadow_wait_self_target() {
    local waited=0 state
    while :; do
        state="$(shadow_self_target)"
        if [[ "$state" == bound:* ]]; then
            printf '%s' "$state"
            return 0
        fi
        if [[ "$state" != "unbound" ]]; then
            break
        fi
        if (( waited >= SHADOW_BIND_WAIT_MS )); then
            break
        fi
        # ms -> fractional seconds without spawning awk/bc.
        sleep "$(printf '%d.%03d' \
            "$(( SHADOW_BIND_POLL_MS / 1000 ))" "$(( SHADOW_BIND_POLL_MS % 1000 ))")"
        waited=$(( waited + SHADOW_BIND_POLL_MS ))
    done
    printf '%s' "$state"
}

# shadow_stamp_analyzed_at - when this process is running *inside a shadow pane*
# and is capturing its bound followed agent, stamp the current wall-clock epoch
# onto the shadow's own pane. Best-effort: any failure is swallowed so the
# capture (the primary job) never breaks. Self-guarding: minimonitor's own
# captures run from the minimonitor pane (no @aitask_shadow_target) and the stdin
# path never reaches here, so they cannot mis-stamp. Since t1319 the binding is
# additionally verified to live on the gateway server, so a same-numbered pane
# on another tmux server can no longer be mistaken for our own.
#   $1 = captured pane id
#   $2 = optional pre-resolved shadow_self_target state (main resolves it once)
# Read the advisory phase stamped on our own pane. Prints the raw line or
# nothing. Same single display-message round-trip idiom as shadow_self_target,
# and the same socket check: a stamp we cannot vouch for is not used.
shadow_self_phase() {
    local own_pane="${TMUX_PANE:-}"
    [[ -n "$own_pane" ]] || return 0
    local own_sock="" out sock="" value=""
    own_sock="$(ait_tmux display-message -p "#{socket_path}" 2>/dev/null || true)"
    [[ -n "$own_sock" ]] || return 0
    out="$(ait_tmux display-message -p -t "$own_pane" \
        "#{socket_path}"$'\t'"#{${SHADOW_PHASE_OPTION}}" 2>/dev/null || true)"
    if [[ "$out" == *$'\t'* ]]; then
        sock="${out%%$'\t'*}"
        value="${out#*$'\t'}"
    fi
    [[ "$own_sock" == "$sock" ]] || return 0
    printf '%s' "$value"
}

# --phase: print ONE advisory status line on stdout and nothing else; always
# exit 0. Deliberately unlike the capture path, which refuses (die_code 2) on an
# unverifiable binding: the phase is a hint, so "cannot tell" is a legitimate
# answer that must never cost the user a capture or a keystroke.
#
# Terminating ladder: the monitor's stamp (current, includes the live tiers) →
# the ledger-only CLI when a task id is known → all-UNKNOWN.
shadow_report_phase() {
    local task_id="${1:-}"
    local stamped
    stamped="$(shadow_self_phase || true)"
    if [[ -n "$stamped" && "$stamped" == PHASE:* ]]; then
        printf '%s|VIA:pane-option\n' "$stamped"
        return 0
    fi
    if [[ -n "$task_id" ]]; then
        local line
        if line="$("$SCRIPT_DIR/aitask_gate.sh" workflow-phase "$task_id" 2>/dev/null)" \
                && [[ -n "$line" ]]; then
            printf '%s|VIA:ledger-cli\n' "$line"
            return 0
        fi
    fi
    printf '%s|VIA:none\n' "$SHADOW_PHASE_UNKNOWN_LINE"
    return 0
}

shadow_stamp_analyzed_at() {
    local pane="$1"
    local state="${2-}"
    [[ -n "$state" ]] || state="$(shadow_self_target)"
    local self_target=""
    [[ "$state" == bound:* ]] && self_target="${state#bound:}"
    local own_pane="${TMUX_PANE:-}"
    # Only a shadow pane reading its own bound followed agent stamps.
    [[ -n "$self_target" && "$self_target" == "$pane" ]] || return 0
    ait_tmux set-option -p -t "$own_pane" \
        "$SHADOW_ANALYZED_AT_OPTION" "$(date +%s)" 2>/dev/null || true
}

main() {
    local pane="" deep=0 any_pane=0 phase_mode=0
    while [[ $# -gt 0 ]]; do
        case "$1" in
            -h|--help)  show_help; exit 0 ;;
            --phase)    phase_mode=1; shift ;;
            --deep)     deep=1; shift ;;
            --any-pane) any_pane=1; shift ;;
            -)          pane="-"; shift ;;
            -*)         die "Unknown option: $1" ;;
            *)
                [[ -z "$pane" ]] || die "Unexpected extra argument: $1"
                pane="$1"; shift ;;
        esac
    done

    # --phase short-circuits: it addresses no pane content and captures nothing,
    # so it runs before the binding checks the capture path needs.
    if [[ "$phase_mode" -eq 1 ]]; then
        shadow_report_phase "${pane:-}"
        return 0
    fi

    # --deep selects the deeper plan-review scrollback; default stays cheap.
    # (No effect on the stdin path — there is no scrollback to deepen.)
    local capture_lines="$SHADOW_CAPTURE_LINES"
    [[ "$deep" -eq 1 ]] && capture_lines="$SHADOW_PLAN_CAPTURE_LINES"

    # The stdin seam short-circuits everything below: no tmux is addressed, so
    # there is no pane to resolve, no binding to check and nothing to stamp.
    if [[ "$pane" == "-" ]]; then
        shadow_clean
        return 0
    fi

    local self_state=""
    if [[ -z "$pane" ]]; then
        # No argument: the binding IS the pane id (t1319). Bounded wait, then
        # fail closed — a shadow that cannot prove its target captures nothing.
        self_state="$(shadow_wait_self_target)"
        if [[ "$self_state" != bound:* ]]; then
            die "pane id required: no <pane_id> argument and no verifiable ${SHADOW_TARGET_OPTION} binding on this pane (${self_state:-no tmux pane}). Pass the followed pane id explicitly, exactly as you received it."
        fi
        pane="${self_state#bound:}"
        printf 'resolved followed pane %s from %s\n' \
            "$pane" "$SHADOW_TARGET_OPTION" >&2
    else
        self_state="$(shadow_self_target)"
        if [[ "$any_pane" -eq 0 ]]; then
            case "$self_state" in
                bound:*)
                    local bound="${self_state#bound:}"
                    [[ "$bound" == "$pane" ]] || die_code 2 \
"refusing to capture ${pane}: this pane is bound to ${bound} via ${SHADOW_TARGET_OPTION}. If ${pane} is a mistyped or truncated id, re-run with NO argument to capture the bound pane; pass --any-pane to capture ${pane} deliberately."
                    ;;
                cross-server)
                    die_code 2 \
"refusing to capture ${pane}: this pane (${TMUX_PANE:-?}) is on a different tmux server than the one being addressed, so its ${SHADOW_TARGET_OPTION} binding cannot be verified and a truncated id could name an unrelated live pane. Pass --any-pane to capture ${pane} anyway."
                    ;;
            esac
        fi
    fi

    shadow_capture_pane "$pane" "$capture_lines" | shadow_clean
    # Record when this analysis read the followed pane (freshness anchor, t1104).
    shadow_stamp_analyzed_at "$pane" "$self_state"
}

# Run main only when executed directly (sourcing exposes the functions for
# tests / reuse without triggering a capture).
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
