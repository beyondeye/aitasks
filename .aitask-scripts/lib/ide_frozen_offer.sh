#!/usr/bin/env bash
# ide_frozen_offer.sh - `ait ide`'s offer to bring back frozen agents (t1847).
#
# After a machine shutdown every frozen stand-in viewer dies with the tmux
# server, while its record survives in the session store as `frozen`. Nothing
# else surfaces those records at startup, so `ait ide` calls
# `ide_offer_frozen_agents` once the project session exists and before it
# attaches:
#
#   ide_offer_frozen_agents <root> <session> <frozen_sh>
#
# It lists the project's records whose viewer is not tracked
# (`aitask_frozen.sh gone --root`) and offers, in the session being opened:
#
#   V  recreate their viewers — the agents stay frozen (the default)
#   R  restore every record that can resume; the rest stay as viewers
#   P  re-pick every record that has a task; the rest stay as viewers
#   S  skip (they remain listed by `ait frozenagent`)
#
# R and P reopen the viewers FIRST, then RE-CLASSIFY, then restore. A record is
# restored only when it is now tracked (restore then takes its same-pane branch
# and respawns the agent inside the viewer) or still has no viewer anywhere (the
# gone-pane branch, pinned to <session>). A record whose viewer is open but was
# not tracked is skipped and reported: restoring it would launch a second agent
# elsewhere and orphan that viewer.
#
# Never blocks startup: no prompt when stdin/stdout is not a terminal (a
# one-line hint instead), and every failure warns and returns 0. <frozen_sh> is
# a parameter so tests can drive this with a stub.
#
# Test seam, honoured only under AITASKS_TEST_MODE=1:
#   AIT_IDE_FROZEN_ASSUME_TTY=1  take the interactive branch without a terminal.

[[ -n "${_AIT_IDE_FROZEN_OFFER_LOADED:-}" ]] && return 0
_AIT_IDE_FROZEN_OFFER_LOADED=1

_ide_frozen_interactive() {
    if [[ "${AITASKS_TEST_MODE:-}" == "1" && "${AIT_IDE_FROZEN_ASSUME_TTY:-}" == "1" ]]; then
        return 0
    fi
    [[ -t 0 && -t 1 ]]
}

# _ide_frozen_gone <root> <frozen_sh> — run `gone`; its stdout on success.
_ide_frozen_gone() {
    "$2" gone --root "$1" 2>/dev/null
}

ide_offer_frozen_agents() {
    local root="$1" session="$2" frozen_sh="$3"
    local out
    if ! out="$(_ide_frozen_gone "$root" "$frozen_sh")"; then
        echo "Warning: could not check for frozen agents; skipping." >&2
        return 0
    fi

    local -a ids=() kinds=() windows=() tasks=() ats=() resumes=() repicks=()
    local line rest id kind window task at resume repick
    while IFS= read -r line; do
        case "$line" in
            GONE:*)
                rest="${line#GONE:}"
                IFS='|' read -r id kind window task at resume repick <<<"$rest"
                [[ -n "$id" ]] || continue
                ids+=("$id"); kinds+=("$kind"); windows+=("$window")
                tasks+=("$task"); ats+=("$at")
                resumes+=("$resume"); repicks+=("$repick")
                ;;
            GONE_ERROR:*)
                echo "Warning: frozen agent ${line#GONE_ERROR:} could not be checked" >&2
                ;;
        esac
    done <<<"$out"

    local n=${#ids[@]}
    [[ "$n" -gt 0 ]] || return 0

    if ! _ide_frozen_interactive; then
        echo "Note: $n frozen agent(s) of this project have no open viewer — run 'ait frozenagent' to see them." >&2
        return 0
    fi

    local i k=0 j=0 marker
    echo ""
    echo "Frozen agents of this project whose viewer is gone ($n):"
    for ((i = 0; i < n; i++)); do
        [[ "${resumes[i]}" == ok ]] && k=$((k + 1))
        [[ "${repicks[i]}" == ok ]] && j=$((j + 1))
        marker=""
        if [[ "${kinds[i]}" == stranded ]]; then
            marker="  (viewer open, untracked)"
        elif [[ "${kinds[i]}" == survivor ]]; then
            marker="  (an earlier restore's agent is still running, untracked)"
        elif [[ "${resumes[i]}" != ok && "${repicks[i]}" != ok ]]; then
            marker="  (view only)"
        fi
        printf '  %-28s %-10s frozen %-21s restore: %-3s re-pick: %-3s%s\n' \
            "${windows[i]:-?}" "${tasks[i]:+t${tasks[i]}}" "${ats[i]}" \
            "$([[ "${resumes[i]}" == ok ]] && echo yes || echo no)" \
            "$([[ "${repicks[i]}" == ok ]] && echo yes || echo no)" "$marker"
    done
    echo ""
    echo "  [V] Recreate viewers for all $n (default) — the agents stay frozen"
    echo "  [R] Restore $k of $n — records that cannot resume stay as viewers"
    echo "  [P] Re-pick $j of $n — records without a task stay as viewers"
    echo "  [S] Skip — they stay listed in 'ait frozenagent'"
    printf 'Choice [V/r/p/s]: '
    local answer=""
    read -r answer || answer=""

    case "$answer" in
        ""|[Vv]) _ide_frozen_reopen "$root" "$session" "$frozen_sh" ;;
        [Rr]) _ide_frozen_restore "$root" "$session" "$frozen_sh" "" ;;
        [Pp]) _ide_frozen_restore "$root" "$session" "$frozen_sh" "--repick" ;;
        *) echo "Skipped. Run 'ait frozenagent' to view, restore or drop them." ;;
    esac
    return 0
}

# _ide_frozen_reopen <root> <session> <frozen_sh> — echo the result lines.
#
# The command's exit status is KEPT: a wrapper that could not start Python, or a
# coordinator that crashed before printing a single wire line, must not read as
# "0 reopened, 0 failed". A non-zero exit that no REOPEN_FAILED line explains
# is reported with the last thing the command said.
_ide_frozen_reopen() {
    local out rc=0 line ok=0 failed=0 last=""
    out="$("$3" reopen --root "$1" --session "$2" 2>&1)" || rc=$?
    while IFS= read -r line; do
        [[ -n "$line" ]] && last="$line"
        case "$line" in
            REOPENED:*) ok=$((ok + 1)); echo "  $line" ;;
            REOPEN_FAILED:*) failed=$((failed + 1)); echo "  $line" ;;
            REOPEN_SKIPPED:*) echo "  $line" ;;
        esac
    done <<<"$out"
    if [[ "$rc" -ne 0 && "$failed" -eq 0 ]]; then
        echo "Warning: bringing the viewers back failed (exit $rc): ${last:-no output}" >&2
    fi
    echo "Viewers: $ok reopened, $failed failed."
    return 0
}

# _ide_frozen_restore <root> <session> <frozen_sh> <"" | --repick>
#
# Reads the caller's `ids` / `windows` / `resumes` / `repicks` arrays through
# bash's dynamic scoping — it is only ever called from ide_offer_frozen_agents.
_ide_frozen_restore() {
    local root="$1" session="$2" frozen_sh="$3" repick="$4"
    _ide_frozen_reopen "$root" "$session" "$frozen_sh"

    # Re-classify: decide on each record's CURRENT state, not on what reopen
    # printed. A record still `stranded` has an open viewer the store does not
    # track — restoring it would launch a second agent and orphan the viewer.
    local out
    if ! out="$(_ide_frozen_gone "$root" "$frozen_sh")"; then
        echo "Warning: could not re-check the frozen agents; nothing restored." >&2
        return 0
    fi
    local -A still=()
    local line rest id kind _w _t _a _r _p
    while IFS= read -r line; do
        case "$line" in
            GONE:*)
                rest="${line#GONE:}"
                IFS='|' read -r id kind _w _t _a _r _p <<<"$rest"
                [[ -n "$id" ]] && still["$id"]="$kind"
                ;;
            GONE_ERROR:*)
                rest="${line#GONE_ERROR:}"
                still["${rest%%|*}"]="error"
                ;;
        esac
    done <<<"$out"

    local i restored=0 viewers=0 failed=0 skipped=0 eligible
    for ((i = 0; i < ${#ids[@]}; i++)); do
        id="${ids[i]}"
        if [[ -n "$repick" ]]; then eligible="${repicks[i]}"; else eligible="${resumes[i]}"; fi
        if [[ "$eligible" != ok ]]; then
            viewers=$((viewers + 1))
            continue
        fi
        case "${still[$id]:-tracked}" in
            stranded)
                skipped=$((skipped + 1))
                echo "  ${windows[i]:-$id}: viewer open but not tracked — not restored; re-run 'ait ide'"
                continue
                ;;
            survivor)
                # t1875: an agent an earlier restore left running, that no record
                # tracks. Restoring would start a second one on its session.
                skipped=$((skipped + 1))
                echo "  ${windows[i]:-$id}: an earlier restore's agent is still running, untracked — not restored; close that window, then re-run 'ait ide'"
                continue
                ;;
            error)
                skipped=$((skipped + 1))
                echo "  ${windows[i]:-$id}: could not be checked — not restored; re-run 'ait ide'"
                continue
                ;;
        esac
        # `restore` prints its own result line; a failure leaves a viewer. Each
        # one waits for the agent's acknowledgement, so say what is running.
        echo "  Restoring ${windows[i]:-$id}…"
        if "$frozen_sh" restore "$id" ${repick:+"$repick"} --session "$session"; then
            restored=$((restored + 1))
        else
            failed=$((failed + 1))
        fi
    done
    echo "Restored $restored, viewers $viewers, failed $failed, skipped $skipped."
    return 0
}
