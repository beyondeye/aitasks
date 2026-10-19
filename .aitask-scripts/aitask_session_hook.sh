#!/usr/bin/env bash
# aitask_session_hook.sh - SessionStart hook: bind a code agent to its store record.
#
# Installed by `ait setup` into a project's agent config (Claude Code:
# .claude/settings.json `hooks.SessionStart`; Codex: `[hooks]` in
# .codex/config.toml) and run by the agent when a session starts. It reads the
# agent's JSON payload on stdin, resolves the pane it is running in, and records
# the codeagent session id into the framework session store (t1705_2) so a
# frozen agent can later be restored with `claude --resume <id>` /
# `codex resume <id>`.
#
# ---------------------------------------------------------------------------
# HARD CONTRACTS (each has a test in tests/test_session_hook.sh)
#
#   1. ALWAYS exit 0.  A broken hook must never break or block an agent
#      session. Hence `set -uo pipefail` and NOT `-e`.
#   2. NEVER write to stdout.  A SessionStart hook's stdout is injected into
#      the agent's context. Every diagnostic goes to stderr; the store's own
#      output is captured into a variable, never echoed.
#   3. Stamp the pane ONLY after a successful upsert (t1705_2 A8). The store
#      never touches tmux, so establishing the @aitask_record join is this
#      caller's obligation -- discharged via ait_stamp_record.
#   4. A blank session id is a NO-OP. The store ignores a blank id on an
#      ordinary update, but on a restore ack it reads as a session mismatch
#      (see below).
#   5. Record ONLY from inside the pane's own process tree (t2047). $TMUX_PANE
#      is inherited, not proven, so nothing is upserted or stamped unless the
#      pane's #{pane_pid} is an ancestor of this hook AND no process between
#      them is the codex app-server daemon (see DAEMON ROUTING below). Refusing
#      is the fail-safe direction: the freeze engine's fallback upsert covers an
#      unrecorded agent. An agent in a different PID namespace from the tmux
#      server (a container started from the pane) is refused too; accepted.
#
# CODEX TIMING (measured 2026-10-16 on codex 0.163.0): the interactive TUI fires
# SessionStart at a session's FIRST TURN, not at launch. That is `source=startup`
# for a new session, and `source=resume` with the same id after `codex resume`.
# An in-process TUI (every framework launch: CODEX_TUI_OVERRIDES carries
# tui.alternate_screen=never) runs it as a direct child of the pane's own codex
# process, with the right TMUX_PANE. Codex 0.153.4 fired it only under `codex
# exec`, never in the TUI. The first version that fires it lies in between and
# was not bisected.
#
# DAEMON ROUTING (measured 2026-10-19 on codex 0.163.0, t2047): a codex started
# by hand without that override is routed through the shared app-server daemon,
# and the DAEMON runs every routed session's hook, with the TMUX_PANE of the pane
# that started it. While that pane's codex lives, the daemon is its direct CHILD
# (own session, not reparented), so a second pane's session passes the ancestry
# walk attributed to the first pane. Once the starter exits the daemon is
# reparented to init/systemd and fails the walk instead. Either way such a hook
# must not record. Three identifier forms, each matched against the live daemon
# and against no hop of an in-process codex:
#   (a) its executable lies under $CODEX_HOME/packages/app-server-daemon/;
#   (b) it is the process $CODEX_HOME/app-server-daemon/daemon.pid (or
#       daemon-updater.pid) declares, by pid AND processIdentity (bootId ==
#       /proc/sys/kernel/random/boot_id, startTicks == /proc/<pid>/stat field
#       22). A bare pid is never enough: the file outlives its process;
#   (c) the daemon's own invocation: argv0 `codex`, argv[1] exactly
#       `app-server` (the subcommand position, so `codex exec app-server`, a
#       prompt, does not count) and a later `--managed-daemon` element
#       (measured: `.../bin/codex app-server --listen unix://
#       --analytics-default-enabled --managed-daemon`). Read NUL-delimited from
#       /proc, so a multiline argument cannot fake it; declined where the
#       element boundaries are unavailable (no /proc).
#
# So a codex session id may still be missing here: on an older codex, before the
# first turn, or after a `/new` the hook did not report. The FREEZE engine
# covers an older codex and an unreported `/new` (t1804, Linux only): it reads the
# rollout the agent's own process holds open (`codex_session_for_pid`) while it
# is still alive. Before the first turn there is no rollout either, so an agent
# frozen then has no session at all and restores via re-pick.
#
# A restored codex therefore acks LATE, when the user first types, long after the
# restore settled (verified by its open rollout, or by liveness). The store never
# refuses that late ack (t2040). A matching one upgrades a liveness confirm to
# verified, and anything else is an ordinary upsert, so the pane is stamped
# either way.
# ---------------------------------------------------------------------------

set -uo pipefail

# --- 1. tmux presence ------------------------------------------------------
# Not in a tmux pane => nothing to bind a record to.
[ -n "${TMUX_PANE:-}" ] || exit 0

# --- 2. socket resolution --------------------------------------------------
# Talk to the server THIS pane lives on. A tmux server hands its panes the
# environment it captured at server start, so AITASKS_TMUX_SOCKET is not
# reliably present here and the gateway's `-L ait` default can address the
# WRONG server. Derive it from $TMUX (format "<socket-path>,<pid>,<session>").
# Set it ONLY when unset: the test harness (require_isolated_tmux) exports it
# set-but-empty as the no-flag escape hatch, and that must survive.
if [ -z "${AITASKS_TMUX_SOCKET+x}" ] && [ -n "${TMUX:-}" ]; then
    AITASKS_TMUX_SOCKET="$(basename "${TMUX%%,*}")"
    export AITASKS_TMUX_SOCKET
fi

# --- 3. payload ------------------------------------------------------------
payload="$(cat)"

# NUL-delimited, NOT whitespace-split. A space-joined `read -r a b c d` shifts
# every field the moment cwd or transcript_path contains a space -- and the
# claude project-dir encoding preserves spaces, so this is reachable in normal
# use. NUL is the one byte a POSIX path cannot contain.
_fields=()
while IFS= read -r -d '' _f; do
    _fields+=("$_f")
done < <(printf '%s' "$payload" | python3 -c '
import json, sys
d = json.load(sys.stdin)
if not isinstance(d, dict):
    raise SystemExit(1)
keys = ("session_id", "transcript_path", "cwd", "source")
sys.stdout.write("\0".join(str(d.get(k) or "") for k in keys) + "\0")
' 2>/dev/null)

# Malformed / unparseable / non-object payload, or no python3 at all.
if [ "${#_fields[@]}" -ne 4 ]; then
    echo "aitask_session_hook: unparseable payload; nothing recorded" >&2
    exit 0
fi
session_id="${_fields[0]}"
transcript_path="${_fields[1]}"
payload_cwd="${_fields[2]}"
# shellcheck disable=SC2034  # Captured for completeness / future use.
source_kind="${_fields[3]}"

# A blank session id is a NO-OP -- never an upsert, never a pane option. The
# store treats a blank id as "not supplied" on an ordinary update (t1807), so
# recording one would at best be a wasted upsert and stamp for a session nobody
# can resume. During a restore it is harmful: the ack path compares
# (session_id or "") against the stored id BEFORE applying any field, so a
# blank would persist "<nonce>:session_mismatch", aborting a legitimate restore.
if [ -z "$session_id" ]; then
    echo "aitask_session_hook: empty session_id; nothing recorded" >&2
    exit 0
fi

# --- 4. project root -------------------------------------------------------
# Nearest ancestor of the payload cwd holding aitasks/metadata/project_config.yaml.
# Mirrors agent_launch_utils._walk_up_to_aitasks.
root=""
_dir="${payload_cwd:-$PWD}"
[ -d "$_dir" ] || _dir="$PWD"
_dir="$(cd "$_dir" 2>/dev/null && pwd -P)" || exit 0
while [ -n "$_dir" ]; do
    if [ -f "$_dir/aitasks/metadata/project_config.yaml" ]; then
        root="$_dir"
        break
    fi
    [ "$_dir" = "/" ] && break
    _dir="$(dirname "$_dir")"
done
# Not an aitasks project => nothing to record.
[ -n "$root" ] || exit 0
[ -x "$root/.aitask-scripts/aitask_agent_sessions.sh" ] || exit 0

# --- 5. gateway ------------------------------------------------------------
# shellcheck source=lib/agent_sessions.sh disable=SC1091
source "$root/.aitask-scripts/lib/agent_sessions.sh" 2>/dev/null || exit 0
# shellcheck source=lib/pid_anchor.sh disable=SC1091
source "$root/.aitask-scripts/lib/pid_anchor.sh" 2>/dev/null || exit 0

# One tmux round trip for everything the store needs about this pane.
_info="$(ait_tmux display-message -p -t "$TMUX_PANE" \
    "#{session_name}	#{window_name}	#{pane_id}	#{pane_pid}	#{$AIT_RECORD_OPTION}" 2>/dev/null)" || exit 0
IFS=$'\t' read -r tmux_session window pane_id pane_pid existing_record <<<"$_info"
[ -n "$pane_id" ] && [ -n "$pane_pid" ] || exit 0

# --- 5b. process-tree guard (HARD CONTRACT 5) -------------------------------
# Runs before anything is recorded: the upsert, the @aitask_record stamp and the
# @aitask_agent_session write below are all behind it.

# _json_field <json> <key> — the value of a scalar "key" in a one-line JSON
# record (number or string, unquoted). Empty when absent.
_json_field() {
    printf '%s' "$1" | sed -n 's/.*"'"$2"'":"\{0,1\}\([0-9A-Za-z-]*\).*/\1/p' | head -n1
}

# _codex_daemon_hop <pid> — is <pid> the codex app-server daemon?
# 0 = yes (form in $_hop_form), 1 = no, 2 = its identity could not be read.
_hop_form=""
_codex_daemon_hop() {
    local pid="$1" exe argv_rc home f rec boot ticks
    exe="$(get_pid_exe "$pid")" || exe=""
    pid_argv_match "$pid" codex app-server --managed-daemon; argv_rc=$?
    # Neither the executable nor the argv can be read: unidentifiable.
    [ -n "$exe" ] || [ "$argv_rc" -ne 2 ] || return 2
    case "$exe" in
        */packages/app-server-daemon/*) _hop_form=a; return 0 ;;
    esac
    # Form c needs exact argv element boundaries; without them (no /proc) it is
    # declined, never guessed (pid_argv_match answers 2, not 0).
    if [ "$argv_rc" -eq 0 ]; then
        _hop_form=c; return 0
    fi
    home="${CODEX_HOME:-${HOME:+$HOME/.codex}}"
    [ -n "$home" ] || return 1
    boot="$(cat /proc/sys/kernel/random/boot_id 2>/dev/null)" || boot=""
    ticks="$(_pid_starttime_proc "$pid" 2>/dev/null)" || ticks=""
    [ -n "$boot" ] && [ -n "$ticks" ] || return 1
    for f in "$home/app-server-daemon/daemon.pid" "$home/app-server-daemon/daemon-updater.pid"; do
        rec="$(cat "$f" 2>/dev/null)" || continue
        [ "$(_json_field "$rec" pid)" = "$pid" ] || continue
        [ "$(_json_field "$rec" bootId)" = "$boot" ] || continue
        [ "$(_json_field "$rec" startTicks)" = "$ticks" ] || continue
        _hop_form=b; return 0
    done
    return 1
}

_chain="$(pid_chain_to "$pane_pid" "$PPID")"; _anc=$?
_chain_txt="$(printf '%s' "$_chain" | tr '\n' ' ')"
if [ "$_anc" -ne 0 ]; then
    if [ "$_anc" -eq 1 ]; then
        echo "aitask_session_hook: pane $pane_id (pid $pane_pid) is not an ancestor of this hook (chain: ${_chain_txt:-none}); nothing recorded" >&2
    else
        echo "aitask_session_hook: could not establish this hook's process ancestry (chain: ${_chain_txt:-none}); nothing recorded" >&2
    fi
    exit 0
fi
while IFS= read -r _hop; do
    [ -n "$_hop" ] || continue
    _codex_daemon_hop "$_hop"; _rc=$?
    if [ "$_rc" -eq 0 ]; then
        echo "aitask_session_hook: hook runs under the codex app-server daemon (pid $_hop, form $_hop_form); nothing recorded" >&2
        exit 0
    elif [ "$_rc" -ne 1 ]; then
        echo "aitask_session_hook: could not identify process $_hop between this hook and its pane; nothing recorded" >&2
        exit 0
    fi
done <<<"$_chain"

# --- 6. operation / task id from the window name ---------------------------
# Same shape as monitor_core._TASK_ID_RE.
operation=""
task_id=""
if [[ "$window" =~ ^agent-(pick|qa|resume)-([0-9]+(_[0-9]+)?)$ ]]; then
    operation="${BASH_REMATCH[1]}"
    task_id="${BASH_REMATCH[2]}"
fi

# --- 7. upsert -------------------------------------------------------------
# A blank AITASK_AGENT_STRING (an agent not started through the wrapper) is a
# no-op in the store, not a clear: the record keeps the string it already has
# (t1802). The restore coordinator delivers the variable to its replacements.
args=(upsert
      --root "$root"
      --window "$window"
      --pane "$pane_id"
      --pane-pid "$pane_pid"
      --session "$tmux_session"
      --session-id "$session_id"
      --transcript "$transcript_path"
      --agent-string "${AITASK_AGENT_STRING:-}"
      --operation "$operation"
      --task-id "$task_id")
[ -n "$existing_record" ] && args+=(--id "$existing_record")
# A restore launch (see the restore coordinator, t1705_5) exports these; they
# turn this upsert into the restore ACKNOWLEDGEMENT for the old record. They stay
# in the agent's environment for its whole life, so every later SessionStart
# (codex's first turn, `/new`) forwards them again. The store answers those on a
# settled record as described in the CODEX TIMING note above: an upgrade
# (`UPSERTED:<id>|restored_late`) or an ordinary update, never a refusal.
if [ -n "${AITASK_RESTORE_RECORD:-}" ]; then
    args+=(--restore-of "$AITASK_RESTORE_RECORD" --nonce "${AITASK_RESTORE_NONCE:-}")
fi

out="$("$root/.aitask-scripts/aitask_agent_sessions.sh" "${args[@]}" 2>&1)"
rc=$?
# 3 = LOCK_BUSY: another writer held the mutex and NOTHING was written. One
# short retry, then give up (the freeze engine's fallback upsert covers a
# missed record).
if [ "$rc" -eq 3 ]; then
    sleep 0.2
    out="$("$root/.aitask-scripts/aitask_agent_sessions.sh" "${args[@]}" 2>&1)"
    rc=$?
fi
[ "$rc" -eq 0 ] || echo "aitask_session_hook: $out" >&2

# --- 8. stamp the pane -> record join (t1705_2 A8) -------------------------
# Match the LINE, not a prefix of $out: the wrapper merges python's stdout and
# stderr into one stream, so a warning ahead of the UPSERTED: line would defeat
# a prefix test -- and a skipped stamp is SILENT, surfacing much later as the
# freeze engine creating a SECOND record for an already-recorded agent.
# UPSERT_REFUSED / NONCE_MISMATCH / a non-zero exit all yield an empty id and
# no stamp, which is the "only on success, never on a refusal" half of A8.
record_id="$(printf '%s\n' "$out" | sed -n 's/^UPSERTED:\([0-9a-f]\{8\}\)|.*$/\1/p' | tail -n1)"
if [ -n "$record_id" ]; then
    ait_stamp_record "$TMUX_PANE" "$record_id" 2>/dev/null || \
        echo "aitask_session_hook: could not stamp $AIT_RECORD_OPTION" >&2
fi

# --- 9. pane-visible session id -------------------------------------------
# The freeze engine's fallback when the store has no session id for the record.
ait_tmux set-option -p -t "$TMUX_PANE" "$AIT_AGENT_SESSION_OPTION" "$session_id" 2>/dev/null || true

exit 0
