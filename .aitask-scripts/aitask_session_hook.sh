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
#   4. A blank session id is a NO-OP. Recording "" would overwrite a good
#      stored id (see below).
#
# CODEX LIMITATION (established 2026-09-06, codex 0.153.4): SessionStart fires
# under `codex exec` but NOT in the interactive TUI, which is the framework's
# production launch path. Interactive codex sessions therefore capture no
# session id here and fall back to newest_transcript_for(), or to re-pick.
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

# A blank session id is a NO-OP -- never an upsert, never a pane option.
# `--session-id ""` is NOT None to the store, so _apply_upsert_fields would
# overwrite a good codeagent_session_id with "", silently downgrading a
# resumable frozen agent to re-pick only. During a restore it is worse: the ack
# path compares (session_id or "") against the stored id and would persist
# "<nonce>:session_mismatch", aborting a legitimate restore.
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

# One tmux round trip for everything the store needs about this pane.
_info="$(ait_tmux display-message -p -t "$TMUX_PANE" \
    "#{session_name}	#{window_name}	#{pane_id}	#{pane_pid}	#{$AIT_RECORD_OPTION}" 2>/dev/null)" || exit 0
IFS=$'\t' read -r tmux_session window pane_id pane_pid existing_record <<<"$_info"
[ -n "$pane_id" ] && [ -n "$pane_pid" ] || exit 0

# --- 6. operation / task id from the window name ---------------------------
# Same shape as monitor_core._TASK_ID_RE.
operation=""
task_id=""
if [[ "$window" =~ ^agent-(pick|qa|resume)-([0-9]+(_[0-9]+)?)$ ]]; then
    operation="${BASH_REMATCH[1]}"
    task_id="${BASH_REMATCH[2]}"
fi

# --- 7. upsert -------------------------------------------------------------
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
# turn this upsert into the restore ACKNOWLEDGEMENT for the old record.
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
