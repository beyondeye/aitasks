#!/usr/bin/env bash
# ide_frozen_offer.sh - `ait ide`'s offer to bring back frozen agents (t1847),
# for every project in the session store (t2039).
#
# After a machine shutdown every frozen stand-in viewer dies with the tmux
# server, while its record survives in the session store as `frozen`. Nothing
# else surfaces those records at startup, so `ait ide` calls
# `ide_offer_frozen_agents` once the project session exists and before it
# attaches:
#
#   ide_offer_frozen_agents <root> <session> <frozen_sh>
#
# The store is global, so it lists the records of EVERY project whose viewer is
# not tracked (`aitask_frozen.sh gone --all-roots`), grouped by project — this
# project first — and asks one question per project it may act on:
#
#   V  recreate their viewers — the agents stay frozen (the default)
#   R  restore every record that can resume; the rest stay as viewers
#   P  re-pick every record that has a task; the rest stay as viewers
#   S  skip (they remain listed by `ait frozenagent`)
#
# WHICH PROJECTS ARE ACTED ON. This project (<root>) always. Any other project
# only when `gone --all-roots` reports its root `ok`: registered in `ait
# projects` (which `ait ide` fills automatically) and still holding the aitasks
# marker. A root that is gone, unregistered, or whose registration could not be
# verified is listed with the reason and never touched — above all, no tmux
# session is ever bootstrapped for it.
#
# WHERE THEY LAND. This project's agents go into <session> (`--session`), exactly
# as before. Another project's go into ITS OWN session: no `--session` is passed,
# so the coordinator resolves the first session discovery attributes to that
# root, or creates one through the canonical bootstrap under its ownership rule
# (t1784). A project's agents live in that project's session, which is what lets
# `ait monitor` map sessions back to roots. Each project is a separate `reopen`
# invocation, so a refused bootstrap (name taken, `session_not_for_root`,
# unreadable `default_session`) is reported under that project and never stops
# the next one.
#
# R and P reopen the viewers FIRST, then RE-CLASSIFY (one `gone --all-roots`,
# covering every project acted on), then restore. A record is restored only when
# it is now tracked (restore then takes its same-pane branch and respawns the
# agent inside the viewer) or still has no viewer anywhere (the gone-pane branch,
# pinned to <session> for this project). A record whose viewer is open but was
# not tracked is skipped and reported: restoring it would launch a second agent
# elsewhere and orphan that viewer.
#
# COMPANIONS. Every path that reached the listing ends with `companions
# --all-roots`, which gives each TRACKED viewer on the server the minimonitor its
# window should have — viewers recreated before the companion guard read its own
# window (t2039) have none, and nothing else would ever repair them. It is
# idempotent: the spawner refuses a live or booting companion under a per-server
# lock. Silent unless it spawned something.
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

# _ide_frozen_hook_note <root> — a missing Claude Code session hook (t1849).
#
# Printed only alongside the frozen-agent list, where it is actually seen (text
# written just before `exec tmux attach` is wiped from view). It is a SEPARATE,
# forward-looking note, never "why these records cannot resume": a `GONE:` line
# carries no agent kind, and a no_session record may equally be a Codex agent
# whose id was not captured at freeze. Never fails.
_ide_frozen_hook_note() {
    # shellcheck source=claude_hook_status.sh
    source "$(dirname "${BASH_SOURCE[0]}")/claude_hook_status.sh" 2>/dev/null || return 0
    case "$(claude_session_hook_status "$1")" in
        MISSING) echo "Separately, about future Claude Code sessions: $(claude_session_hook_hint)" ;;
        INVALID) echo "Separately: $(claude_session_hook_invalid_hint)" ;;
    esac
    return 0
}

# _ide_frozen_gone <frozen_sh> — run `gone --all-roots`; its stdout on success.
_ide_frozen_gone() {
    "$1" gone --all-roots 2>/dev/null
}

# _ide_frozen_companions <frozen_sh> — top up every tracked viewer's companion.
#
# Prints one line only when something was spawned. A non-zero exit warns with the
# last thing the command said that was not a count line.
_ide_frozen_companions() {
    local out rc=0 line n=0 last=""
    out="$("$1" companions --all-roots 2>&1)" || rc=$?
    while IFS= read -r line; do
        case "$line" in
            COMPANION_SPAWNED:*) n=$((n + 1)) ;;
            COMPANION_COUNT:*|"") ;;
            *) last="$line" ;;
        esac
    done <<<"$out"
    if [[ "$rc" -ne 0 ]]; then
        echo "Warning: could not give every frozen viewer its minimonitor (exit $rc): ${last:-no output}" >&2
    fi
    if [[ "$n" -gt 0 ]]; then
        echo "Companions: $n viewer window(s) got their minimonitor back."
    fi
    return 0
}

# _ide_frozen_tail <n> <line> — everything after the <n>-th `|`, verbatim.
#
# The root is the LAST wire field and may itself contain `|`. `read` cannot
# carry it: with a non-whitespace IFS it drops a TRAILING delimiter from the
# last variable, so a root `/p|` would come back as `/p` — another directory,
# and no longer equal to this project's root. Fails (prints nothing, status 1)
# when the line has fewer than <n> delimiters, so a short line is skipped
# rather than read with a field misplaced into the root.
_ide_frozen_tail() {
    local n="$1" rest="$2" k
    for ((k = 0; k < n; k++)); do
        [[ "$rest" == *"|"* ]] || return 1
        rest="${rest#*|}"
    done
    printf '%s' "$rest"
}

# _ide_frozen_label <root> — the project's display name (dynamic scope: rname,
# cur).
_ide_frozen_label() {
    local name="${rname[$1]:-}"
    [[ -n "$name" ]] || name="$(basename "$1")"
    if [[ "$1" == "$cur" ]]; then
        printf '%s (this project)' "$name"
    else
        printf '%s' "$name"
    fi
}

# _ide_frozen_actionable <root> — 0 when `ait ide` may act on this project.
_ide_frozen_actionable() {
    [[ "$1" == "$cur" || "${rstate[$1]:-}" == ok ]]
}

ide_offer_frozen_agents() {
    local root="$1" session="$2" frozen_sh="$3"
    local cur
    cur="$(cd "$root" 2>/dev/null && pwd -P)" || cur="$root"
    local out
    if ! out="$(_ide_frozen_gone "$frozen_sh")"; then
        echo "Warning: could not check for frozen agents; skipping." >&2
        _ide_frozen_companions "$frozen_sh"
        return 0
    fi

    local -a ids=() kinds=() windows=() tasks=() ats=() resumes=() repicks=() roots=()
    local -A rstate=() rname=()
    local line rest id kind window task at resume repick rroot state name
    while IFS= read -r line; do
        case "$line" in
            GONE_ROOT:*)
                rest="${line#GONE_ROOT:}"
                IFS='|' read -r state name _ <<<"$rest"
                rroot="$(_ide_frozen_tail 2 "$rest")" || continue
                [[ -n "$rroot" ]] || continue
                rstate["$rroot"]="$state"
                rname["$rroot"]="$name"
                ;;
            GONE:*)
                rest="${line#GONE:}"
                # The root is the LAST field, taken verbatim (see _ide_frozen_tail).
                IFS='|' read -r id kind window task at resume repick _ <<<"$rest"
                rroot="$(_ide_frozen_tail 7 "$rest")" || continue
                [[ -n "$id" && -n "$rroot" ]] || continue
                ids+=("$id"); kinds+=("$kind"); windows+=("$window")
                tasks+=("$task"); ats+=("$at")
                resumes+=("$resume"); repicks+=("$repick"); roots+=("$rroot")
                ;;
            GONE_ERROR:*)
                rest="${line#GONE_ERROR:}"
                IFS='|' read -r id state _ <<<"$rest"
                echo "Warning: frozen agent $id could not be checked (${state:-unknown})" >&2
                ;;
        esac
    done <<<"$out"

    local n=${#ids[@]}
    if [[ "$n" -eq 0 ]]; then
        _ide_frozen_companions "$frozen_sh"
        return 0
    fi

    # Groups, this project first, then in the listing's order; per-group counts.
    local -a groups=()
    local -A seen=() gn=() gk=() gj=()
    local i g
    for ((i = 0; i < n; i++)); do
        g="${roots[i]}"
        gn["$g"]=$(( ${gn[$g]:-0} + 1 ))
        [[ "${resumes[i]}" == ok ]] && gk["$g"]=$(( ${gk[$g]:-0} + 1 ))
        [[ "${repicks[i]}" == ok ]] && gj["$g"]=$(( ${gj[$g]:-0} + 1 ))
    done
    if [[ -n "${gn[$cur]:-}" ]]; then
        groups+=("$cur"); seen["$cur"]=1
    fi
    for ((i = 0; i < n; i++)); do
        g="${roots[i]}"
        if [[ -z "${seen[$g]:-}" ]]; then
            groups+=("$g"); seen["$g"]=1
        fi
    done

    local here="${gn[$cur]:-0}"
    local other=$(( n - here ))
    local nother=${#groups[@]}
    [[ "$here" -gt 0 ]] && nother=$(( nother - 1 ))

    if ! _ide_frozen_interactive; then
        if [[ "$here" -gt 0 && "$other" -gt 0 ]]; then
            echo "Note: $here frozen agent(s) of this project have no open viewer ($other more in $nother other project(s)) — run 'ait frozenagent' to see them." >&2
        elif [[ "$here" -gt 0 ]]; then
            echo "Note: $here frozen agent(s) of this project have no open viewer — run 'ait frozenagent' to see them." >&2
        else
            echo "Note: $other frozen agent(s) in $nother other project(s) have no open viewer — run 'ait frozenagent' to see them." >&2
        fi
        _ide_frozen_hook_note "$root" >&2
        _ide_frozen_companions "$frozen_sh" >&2
        return 0
    fi

    local marker reason
    echo ""
    echo "Frozen agents whose viewer is gone ($n in ${#groups[@]} project(s)):"
    for g in "${groups[@]}"; do
        echo ""
        if [[ "$g" == "$cur" ]]; then
            reason=""
        else
            case "${rstate[$g]:-}" in
                ok) reason=" · lands in its own tmux session" ;;
                missing) reason=" · project directory gone — not touched; drop them with 'ait frozenagent'" ;;
                unregistered) reason=" · not a registered project — not touched; run 'ait ide' there, or 'ait projects add $g'" ;;
                unverified) reason=" · project registry unreadable — not touched" ;;
                inaccessible) reason=" · project directory unreadable — not touched" ;;
                *) reason=" · project could not be verified — not touched" ;;
            esac
        fi
        echo "  $(_ide_frozen_label "$g") — ${gn[$g]}${reason}"
        for ((i = 0; i < n; i++)); do
            [[ "${roots[i]}" == "$g" ]] || continue
            marker=""
            if [[ "${kinds[i]}" == stranded ]]; then
                marker="  (viewer open, untracked)"
            elif [[ "${kinds[i]}" == survivor ]]; then
                marker="  (an earlier restore's agent is still running, untracked)"
            elif [[ "${resumes[i]}" != ok && "${repicks[i]}" != ok ]]; then
                marker="  (view only)"
            fi
            printf '    %-28s %-10s frozen %-21s restore: %-3s re-pick: %-3s%s\n' \
                "${windows[i]:-?}" "${tasks[i]:+t${tasks[i]}}" "${ats[i]}" \
                "$([[ "${resumes[i]}" == ok ]] && echo yes || echo no)" \
                "$([[ "${repicks[i]}" == ok ]] && echo yes || echo no)" "$marker"
        done
    done
    local hook_note
    hook_note="$(_ide_frozen_hook_note "$root")"
    if [[ -n "$hook_note" ]]; then
        echo ""
        echo "$hook_note"
    fi

    # Every question first, then everything runs: a restore waits for its
    # agent's acknowledgement, so asking in between would leave the user waiting.
    local -A choice=()
    local answer asked=0 label
    for g in "${groups[@]}"; do
        _ide_frozen_actionable "$g" || continue
        asked=$((asked + 1))
        label="$(_ide_frozen_label "$g")"
        echo ""
        echo "  $label:"
        echo "    [V] Recreate viewers for all ${gn[$g]} (default) — the agents stay frozen"
        echo "    [R] Restore ${gk[$g]:-0} of ${gn[$g]} — records that cannot resume stay as viewers"
        echo "    [P] Re-pick ${gj[$g]:-0} of ${gn[$g]} — records without a task stay as viewers"
        echo "    [S] Skip — they stay listed in 'ait frozenagent'"
        printf 'Choice for %s [V/r/p/s]: ' "$label"
        answer=""
        read -r answer || answer=""
        case "$answer" in
            ""|[Vv]) choice["$g"]=V ;;
            [Rr]) choice["$g"]=R ;;
            [Pp]) choice["$g"]=P ;;
            *) choice["$g"]=S ;;
        esac
    done
    if [[ "$asked" -eq 0 ]]; then
        echo ""
        echo "None of these projects can be acted on from here — they stay listed in 'ait frozenagent'."
        _ide_frozen_companions "$frozen_sh"
        return 0
    fi

    local -a acted_other=() skipped_groups=()
    local any_rp=0 reopen_sessions sess
    for g in "${groups[@]}"; do
        case "${choice[$g]:-}" in
            V|R|P)
                sess=""
                [[ "$g" == "$cur" ]] && sess="$session"
                echo ""
                echo "$(_ide_frozen_label "$g"):"
                reopen_sessions=""
                _ide_frozen_reopen "$g" "$sess" "$frozen_sh"
                if [[ "$g" != "$cur" && -n "$reopen_sessions" ]]; then
                    acted_other+=("$(_ide_frozen_label "$g") ($reopen_sessions)")
                fi
                [[ "${choice[$g]}" != V ]] && any_rp=1
                ;;
            S) skipped_groups+=("$(_ide_frozen_label "$g")") ;;
        esac
    done

    if [[ "$any_rp" -eq 1 ]]; then
        # Re-classify: decide on each record's CURRENT state, not on what reopen
        # printed. A record still `stranded` has an open viewer the store does
        # not track — restoring it would launch a second agent and orphan it.
        local -A still=()
        local reclassified=1
        if out="$(_ide_frozen_gone "$frozen_sh")"; then
            while IFS= read -r line; do
                case "$line" in
                    GONE:*)
                        rest="${line#GONE:}"
                        IFS='|' read -r id kind _ <<<"$rest"
                        [[ -n "$id" ]] && still["$id"]="$kind"
                        ;;
                    GONE_ERROR:*)
                        rest="${line#GONE_ERROR:}"
                        still["${rest%%|*}"]="error"
                        ;;
                esac
            done <<<"$out"
        else
            reclassified=0
            echo "Warning: could not re-check the frozen agents; nothing restored." >&2
        fi
        if [[ "$reclassified" -eq 1 ]]; then
            for g in "${groups[@]}"; do
                case "${choice[$g]:-}" in
                    R|P)
                        sess=""
                        [[ "$g" == "$cur" ]] && sess="$session"
                        echo ""
                        echo "$(_ide_frozen_label "$g"):"
                        if [[ "${choice[$g]}" == P ]]; then
                            _ide_frozen_restore "$g" "$sess" "$frozen_sh" "--repick"
                        else
                            _ide_frozen_restore "$g" "$sess" "$frozen_sh" ""
                        fi
                        ;;
                esac
            done
        fi
    fi

    local joined
    if [[ ${#acted_other[@]} -gt 0 ]]; then
        joined="$(printf '%s, ' "${acted_other[@]}")"
        echo ""
        echo "Other projects' agents are in their own tmux sessions: ${joined%, } — switch with j from any TUI, or run 'ait ide' in that project."
    fi
    if [[ ${#skipped_groups[@]} -gt 0 ]]; then
        joined="$(printf '%s, ' "${skipped_groups[@]}")"
        echo ""
        echo "Skipped ${joined%, }: they stay listed in 'ait frozenagent' — view, restore or drop them there."
    fi
    _ide_frozen_companions "$frozen_sh"
    return 0
}

# _ide_frozen_reopen <root> <session-or-empty> <frozen_sh> — echo the result lines.
#
# An empty session passes no `--session`, so another project's viewers land in
# that project's own session. The sessions the viewers landed in are left in the
# caller's `reopen_sessions` (dynamic scope), comma-separated.
#
# The command's exit status is KEPT: a wrapper that could not start Python, or a
# coordinator that crashed before printing a single wire line, must not read as
# "0 reopened, 0 failed". A non-zero exit that no REOPEN_FAILED line explains
# is reported with the last thing the command said.
_ide_frozen_reopen() {
    local -a sess_args=()
    [[ -n "$2" ]] && sess_args=(--session "$2")
    local out rc=0 line ok=0 failed=0 last="" loc where
    local -A landed=()
    out="$("$3" reopen --root "$1" ${sess_args[@]+"${sess_args[@]}"} 2>&1)" || rc=$?
    while IFS= read -r line; do
        [[ -n "$line" ]] && last="$line"
        case "$line" in
            REOPENED:*)
                ok=$((ok + 1)); echo "  $line"
                IFS='|' read -r _ _ loc _ <<<"${line#REOPENED:}"
                where="${loc%%:*}"
                if [[ -n "$where" && -z "${landed[$where]:-}" ]]; then
                    landed["$where"]=1
                    reopen_sessions="${reopen_sessions:+$reopen_sessions, }$where"
                fi
                ;;
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

# _ide_frozen_restore <root> <session-or-empty> <frozen_sh> <"" | --repick>
#
# Restores <root>'s eligible records. Reads the caller's `ids` / `windows` /
# `resumes` / `repicks` / `roots` arrays and its re-classification `still`
# through bash's dynamic scoping — it is only ever called from
# ide_offer_frozen_agents.
_ide_frozen_restore() {
    local root="$1" session="$2" frozen_sh="$3" repick="$4"
    local -a sess_args=()
    [[ -n "$session" ]] && sess_args=(--session "$session")
    local i id restored=0 viewers=0 failed=0 skipped=0 eligible
    for ((i = 0; i < ${#ids[@]}; i++)); do
        [[ "${roots[i]}" == "$root" ]] || continue
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
        if "$frozen_sh" restore "$id" ${repick:+"$repick"} ${sess_args[@]+"${sess_args[@]}"}; then
            restored=$((restored + 1))
        else
            failed=$((failed + 1))
        fi
    done
    echo "Restored $restored, viewers $viewers, failed $failed, skipped $skipped."
    return 0
}
