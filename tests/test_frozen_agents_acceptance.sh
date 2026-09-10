#!/usr/bin/env bash
# tests/test_frozen_agents_acceptance.sh — the composed acceptance test for
# frozen code agents (t1705_8).
#
# Children t1705_2..t1705_7 each prove their own seam. This file proves they
# AGREE, end to end, THROUGH THE SHIPPED WRAPPERS ONLY, on an isolated tmux
# server, with a fake agent binary so it runs unattended. It is the parent's
# mitigation for cross-child drift: per-child tests can all pass while the joins
# between them are incompatible.
#
# WHAT "THROUGH THE SHIPPED WRAPPERS" MEANS. No case calls a Python mutator
# directly. The path is:
#
#   install.sh --local-tarball (a tarball of THIS tree)
#     -> setup_claude_hooks (the real hook installer, t1705_3)
#     -> a pane running `aitask_codeagent.sh --agent-string ... invoke raw`
#     -> which execs the fake `claude` on PATH with the REAL argv
#     -> which execs the REAL aitask_session_hook.sh with a synthetic payload
#     -> which upserts into the REAL store
#     -> aitask_frozen.sh freeze
#     -> the REAL `ait frozenagent --record` viewer in the pane (NOT a stand-in:
#        AITASKS_FROZEN_STANDIN_CMD is deliberately unset here, which is what
#        distinguishes this suite from test_restore_flows_live.sh)
#     -> aitask_frozen.sh restore, including as a real detached `run-shell -b`
#        coordinator driven from the viewer's own `R` key
#     -> drop.
#
# THE AGENT IS LAUNCHED THROUGH THE WRAPPER ITSELF, NOT THROUGH ITS `--dry-run`
# ARGV. `cmd_invoke` returns at aitask_codeagent.sh:637 under `--dry-run`,
# BEFORE the `export AITASK_AGENT_STRING` at :646 — so launching the printed
# argv would exercise the binary but never the export path, and the
# `agent_string` this suite asserts on would be empty. Running the wrapper as
# the pane command exercises both, and `exec` keeps the pid, so `#{pane_pid}`
# still names the agent (t1465).
#
# GROUND TRUTH IS THE SERVER AND THE FILESYSTEM, never the store's own claims
# alone: every case cross-checks a store field against `display-message` /
# `list-panes` output or against a file on disk.
#
# ENV SEAMS ARE EXPORTED BEFORE THE SERVER STARTS. `respawn-pane` and
# `run-shell -b` run their commands in the TMUX SERVER's environment, captured
# at server start — not the calling shell's at call time. The restore
# coordinator is a detached `run-shell -b` job, so AITASKS_TEST_MODE,
# AITASKS_STALE_OP_GRACE and AITASKS_RESTORE_ACK_GRACE reach it only that way.
# Per-case AGENT behaviour cannot ride the environment at all and goes through
# $AGENT_ENV_FILE (see `agent_env` in tests/lib/frozen_fixtures.sh).
#
# THE REAL $HOME IS NEVER WRITTEN. `install.sh` builds no venv; the timed run
# reaches the hook installer through the sanctioned `--source-only` seam. Only
# the opt-in level-3 check runs a full `ait setup`, and it redirects HOME.
#
# Structure
#   Probes A-E  the env/config seams take effect AT ALL (see "why probes")
#   Cases 1-9   launch, freeze, the three restore outcomes, gone pane, two
#               dead-coordinator recoveries, ambiguous relocation
#   Cases 10a/b the two drop verbs, which have DIFFERENT contracts
#
# TMUX-STRESS. Run from a shell that is NOT inside tmux, with the dedicated
# `-L ait` server stopped; `require_clean_ait_server` refuses otherwise.
#
# Run: bash tests/test_frozen_agents_acceptance.sh
#      AIT_ACCEPTANCE_FULL_SETUP=1 bash tests/...   # + the untimed level-3 check
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

command -v tmux >/dev/null 2>&1 || { echo "SKIP: tmux not available"; exit 0; }

# shellcheck source=lib/asserts.sh
. "$PROJECT_DIR/tests/lib/asserts.sh"
# Cases run inside ( … ) subshells; without the file-backed counters their
# PASS/FAIL increments die at subshell exit and this file exits 0 whatever
# happened (CLAUDE.md, t1207).
assert_counters_init

# ORDER IS LOAD-BEARING (tests/lib/tmux_isolation.sh).
# shellcheck source=lib/tmux_isolation.sh
. "$PROJECT_DIR/tests/lib/tmux_isolation.sh"
require_clean_ait_server     # FIRST
require_isolated_tmux        # SECOND

# shellcheck source=../.aitask-scripts/lib/python_resolve.sh
. "$PROJECT_DIR/.aitask-scripts/lib/python_resolve.sh"
PYTHON_BIN="$(require_ait_python)"

REAL_PATH="$PATH"
REAL_TMUX="$(command -v tmux)"

START_TS=$(date +%s)

# ===========================================================================
# Composed environment
# ===========================================================================

# `pwd -P` because the store realpaths the root on both sides, and $TMPDIR is a
# symlink on macOS (/var -> /private/var). A non-realpathed root here would make
# every `(root, window)` lookup miss.
SCRATCH="$(cd "$(mktemp -d "${TMPDIR:-/tmp}/ait_acceptance_XXXXXX")" && pwd -P)"
TARBALL="$SCRATCH.tar.gz"

# A tarball of THIS tree, not a GitHub release: install.sh downloads without
# --local-tarball, which would make this suite need the network AND test the
# released framework rather than the one being changed.
( cd "$PROJECT_DIR" && tar czhf "$TARBALL" \
    .aitask-scripts/ \
    aitasks/metadata/labels.txt \
    aitasks/metadata/task_types.txt \
    aitasks/metadata/claude_settings.seed.json \
    aitasks/metadata/profiles/ \
    ait seed/ packaging/ 2>/dev/null )

# HOME IS REDIRECTED FOR THE INSTALLER, and this is not optional: install.sh
# ends by calling `install_global_shim`, which copies packaging/shim/ait into
# $HOME/.local/bin. Without the redirect this suite would rewrite the
# developer's REAL global `ait` — quietly harmless when it happens to be the
# same tree, and an overwrite of their working shim when it is not.
#
# The redirect is scoped to this ONE command rather than exported for the run:
# the framework resolves its Python interpreter from $HOME/.aitask/venv, so a
# suite-wide redirect would leave the real `ait frozenagent` viewer with no
# Textual and it would never boot — which is the one thing this suite exists to
# exercise.
mkdir -p "$SCRATCH/home"
HOME="$SCRATCH/home" bash "$PROJECT_DIR/install.sh" \
    --dir "$SCRATCH" --local-tarball "$TARBALL" \
    </dev/null >"$SCRATCH.install.log" 2>&1
INSTALL_RC=$?

# Ground truth for the "we never wrote the real $HOME" promise: remember the
# real shim's fingerprint now and re-check it at the end of the run.
REAL_SHIM="$HOME/.local/bin/ait"
REAL_SHIM_BEFORE="$( [ -f "$REAL_SHIM" ] && cksum < "$REAL_SHIM" || echo absent )"

SESSIONS_SH="$SCRATCH/.aitask-scripts/aitask_agent_sessions.sh"
FROZEN_SH="$SCRATCH/.aitask-scripts/aitask_frozen.sh"
CODEAGENT_SH="$SCRATCH/.aitask-scripts/aitask_codeagent.sh"
AIT="$SCRATCH/ait"

# The store and the capture tree, redirected into the scratch project.
export AITASKS_AGENT_SESSIONS_FILE="$SCRATCH/.sessions.json"
export AITASKS_FROZEN_DIR="$SCRATCH/.frozen"
export AITASKS_TEST_MODE=1
# ENV-ONLY. `agent_sessions._stale_op_grace()` reads this variable and nothing
# else — it never opens project_config.yaml — so a `frozen: stale_op_grace:` key
# would be a silent no-op and every takeover case would wait out the real 60 s
# default instead, blowing the budget by ~120 s on its own.
export AITASKS_STALE_OP_GRACE=2
# Deliberately DIFFERENT from the configured 8 and the default 20, so probes C1
# and C2 can attribute an elapsed time to one specific layer.
export AITASKS_RESTORE_ACK_GRACE=5
export AITASKS_FAKE_AGENT_HOOK="$SCRATCH/.aitask-scripts/aitask_session_hook.sh"
export FAKE_AGENT_HOOK_LOG="$SCRATCH/hook.log"
# THE REAL VIEWER MUST BOOT. Setting this is what test_restore_flows_live.sh
# does; not setting it is the whole point of this suite.
unset AITASKS_FROZEN_STANDIN_CMD
export TMUX_TMPDIR="$SCRATCH/tmux"
mkdir -p "$TMUX_TMPDIR"

# The per-case control wrapper — a WRAPPER, not a symlink to the fixture. See
# the env-seam note in the header and `agent_env` in frozen_fixtures.sh.
AGENT_ENV_FILE="$SCRATCH/agent_env"
mkdir -p "$SCRATCH/bin"
for _n in claude codex; do
    cat > "$SCRATCH/bin/$_n" <<WRAPPER
#!/usr/bin/env bash
# Sources a per-case control file, then execs the fixture. \`respawn-pane\` runs
# in the SERVER's environment (captured at server start), so per-case knobs set
# in the test shell never reach the replacement agent. \`exec\` keeps the pid.
[ -f "$AGENT_ENV_FILE" ] && . "$AGENT_ENV_FILE"
exec "$PROJECT_DIR/tests/lib/fake_agent.sh" "\$@"
WRAPPER
    chmod +x "$SCRATCH/bin/$_n"
done
export PATH="$SCRATCH/bin:$PATH"
: > "$AGENT_ENV_FILE"

chmod +x "$PROJECT_DIR/tests/lib/fake_agent.sh" 2>/dev/null || true

FIXTURE_DIR="$SCRATCH"
FAKE_AGENT="$PROJECT_DIR/tests/lib/fake_agent.sh"
# shellcheck source=lib/frozen_fixtures.sh
. "$PROJECT_DIR/tests/lib/frozen_fixtures.sh"

acceptance_cleanup() {
    PATH="$REAL_PATH" "$REAL_TMUX" kill-server 2>/dev/null || true
    rm -rf "$SCRATCH" "$TARBALL" "$SCRATCH.install.log" 2>/dev/null || true
}
trap acceptance_cleanup EXIT

SESSION="ait_acceptance_$$"

# ---------------------------------------------------------------------------
section "Setup coverage — three levels, because one is not enough"
# ---------------------------------------------------------------------------
# Level 2 alone (sourcing setup_claude_hooks) would let this suite go green
# while `ait setup` is broken for every user; a full `ait setup` cannot run in
# the timed region because setup_python_venv precedes the hook step and costs
# minutes of pip. So: level 1 proves the CLI dispatch, level 2 the installer,
# level 3 (opt-in, untimed, HOME-redirected) the whole thing.
assert_eq "install.sh into the scratch project succeeds" "0" "$INSTALL_RC"
assert_eq "the scratch project has the shipped ait dispatcher" "yes" \
    "$([ -x "$AIT" ] && echo yes || echo no)"
assert_eq "the hooks seed was installed into metadata" "yes" \
    "$([ -f "$SCRATCH/aitasks/metadata/claude_settings.hooks.json" ] && echo yes || echo no)"

# --- level 1: the real CLI entry point, with zero side effects --------------
# `ait:229` is `setup) shift; exec "$SCRIPTS_DIR/aitask_setup.sh" "$@"`, and
# --help is handled before any setup step runs. Proves routing, exec and argv
# forwarding end to end, and costs nothing.
"$AIT" setup --help </dev/null >"$SCRATCH/setup_help.out" 2>&1
assert_eq "level 1: \`ait setup --help\` exits 0 through the real dispatch" "0" "$?"
assert_eq "level 1: it reached aitask_setup.sh's usage" "yes" \
    "$(grep -qi 'usage' "$SCRATCH/setup_help.out" && echo yes || echo no)"
assert_eq "level 1: --help ran NO setup step (no .claude/settings.json)" "no" \
    "$([ -f "$SCRATCH/.claude/settings.json" ] && echo yes || echo no)"

# --- level 2: the real hook installer ---------------------------------------
# The sanctioned --source-only seam (aitask_setup.sh:4488), driven exactly as
# t1705_3's own tests/test_session_hook_install.sh drives it.
(
    # shellcheck source=/dev/null
    . "$SCRATCH/.aitask-scripts/aitask_setup.sh" --source-only
    # Sourcing turns errexit ON in this shell (the file runs `set -euo pipefail`
    # at file scope); a later probing command would abort the subshell silently.
    set +eu
    setup_claude_hooks </dev/null >/dev/null 2>&1
)
assert_eq "level 2: setup_claude_hooks created .claude/settings.json" "yes" \
    "$([ -f "$SCRATCH/.claude/settings.json" ] && echo yes || echo no)"

count_sessionstart_groups() {
    "$PYTHON_BIN" - "$1" <<'PY'
import json, sys
try:
    d = json.load(open(sys.argv[1]))
except Exception:
    print(-1); raise SystemExit
groups = [
    g for g in d.get("hooks", {}).get("SessionStart", [])
    if any("aitask_session_hook" in h.get("command", "") for h in g.get("hooks", []))
]
print(len(groups))
PY
}
assert_eq "level 2: exactly one aitasks SessionStart group" "1" \
    "$(count_sessionstart_groups "$SCRATCH/.claude/settings.json")"

# A repeat run must not duplicate the group. This is t1705_3's guarantee
# re-checked in the COMPOSED environment (the old case 11), folded in here for
# the price of one function call rather than a second full setup.
(
    # shellcheck source=/dev/null
    . "$SCRATCH/.aitask-scripts/aitask_setup.sh" --source-only
    set +eu
    setup_claude_hooks </dev/null >/dev/null 2>&1
)
assert_eq "level 2: STILL exactly one group after a repeat install" "1" \
    "$(count_sessionstart_groups "$SCRATCH/.claude/settings.json")"

# ---------------------------------------------------------------------------
# The scratch `frozen:` config — written EXPLICITLY, with distinct values
# ---------------------------------------------------------------------------
# install.sh seeds project_config.yaml from seed/, which carries no `frozen:`
# block, so without this every config read silently takes its default and a
# malformed block would be indistinguishable from a correct one. The values are
# three-way distinct (config 8 / env 5 / default 20) so probes C1 and C2 can
# attribute an outcome to one layer.
cat >> "$SCRATCH/aitasks/metadata/project_config.yaml" <<'YAML'
frozen:
  capture_max_lines: 120     # env-free knob — the config-read proof (probe C1)
  restore_ack_grace: 8       # distinct from env 5 AND from the default 20 (C2)
  # stale_op_grace is NOT settable here: env-only under AITASKS_TEST_MODE.
YAML

assert_eq "the scratch project config carries a frozen: block" "yes" \
    "$(grep -q '^frozen:' "$SCRATCH/aitasks/metadata/project_config.yaml" && echo yes || echo no)"

# ===========================================================================
# The isolated server — started only NOW, so it captures every export above
# ===========================================================================
tm new-session -d -s "$SESSION" -n scratch -c "$SCRATCH" "sleep 1000"
sleep 0.4

# --- helpers ---------------------------------------------------------------

# Launch an agent through the SHIPPED launcher and the SHIPPED wrapper, then
# arm the real companion-cleanup hook. Echoes "<agent_pane> <companion_pane>".
launch_agent() {
    local window="$1"
    local agent companion comp_pid
    "$PYTHON_BIN" - "$SCRATCH" "$SESSION" "$window" "$CODEAGENT_SH" <<'PY' >/dev/null 2>&1
import os, sys
scratch, session, window, codeagent = sys.argv[1:5]
sys.path.insert(0, os.path.join(scratch, ".aitask-scripts", "lib"))
from agent_launch_utils import TmuxLaunchConfig, launch_in_tmux
cfg = TmuxLaunchConfig(
    session=session, window=window,
    new_session=False, new_window=True, select_window=False, cwd=scratch,
)
pid, err = launch_in_tmux(
    f"{codeagent} --agent-string claudecode/opus5 invoke raw", cfg)
raise SystemExit(1 if err else 0)
PY
    agent="$(tm list-panes -t "=$SESSION:$window" -F '#{pane_id}' 2>/dev/null | head -1)"
    companion="$(tm split-window -d -t "$agent" -c "$SCRATCH" \
        -P -F '#{pane_id}' "sleep 1000")"
    comp_pid="$(pane_fmt "$companion" '#{pane_pid}')"
    tm set-option -p -t "$companion" @aitask_monitor_kind "minimonitor:$comp_pid"
    # The real `pane-died` companion-cleanup hook, armed the shipped way.
    "$PYTHON_BIN" - "$SCRATCH" "$agent" "$companion" <<'PY' >/dev/null 2>&1
import os, sys
scratch, agent, companion = sys.argv[1:4]
sys.path.insert(0, os.path.join(scratch, ".aitask-scripts", "lib"))
from agent_launch_utils import attach_companion_cleanup_hook
attach_companion_cleanup_hook(agent, companion)
PY
    printf '%s %s\n' "$agent" "$companion"
}

# Wait until the hook has bound a record to the pane, and echo the record id.
wait_for_record_stamp() {
    local pane="$1" i=0 rid=""
    while [ "$i" -lt 150 ]; do
        rid="$(record_of_pane "$pane")"
        [ -n "$rid" ] && { printf '%s\n' "$rid"; return 0; }
        sleep 0.1
        i=$((i + 1))
    done
    return 1
}

# A launched, hook-bound agent. Echoes "<record_id> <agent_pane> <companion>".
make_live_agent() {
    local window="$1"
    local agent companion rid
    read -r agent companion < <(launch_agent "$window")
    rid="$(wait_for_record_stamp "$agent")" || rid=""
    printf '%s %s %s\n' "$rid" "$agent" "$companion"
}

# Freeze and wait for the REAL viewer to stamp itself ready.
freeze_and_wait() {
    local pane="$1" rid="$2"
    "$FROZEN_SH" freeze "$pane" >/dev/null 2>&1
    wait_for_ready "$pane" "$rid"
}

elapsed_since() { echo $(($(date +%s) - $1)); }

# Assert an integer is within [lo, hi). Used by every timing probe, where the
# BOUND is the assertion: a value inside the window can only be explained by the
# configured grace, not by the default.
assert_between() {
    local label="$1" lo="$2" hi="$3" got="$4"
    if [ "$got" -ge "$lo" ] && [ "$got" -lt "$hi" ] 2>/dev/null; then
        assert_record_pass
    else
        assert_record_fail
        echo "FAIL: $label — expected ${lo} <= n < ${hi}, got '$got'"
    fi
}

# The record ids this run created, so a case cannot leak into the next one.
drop_record() { store drop "$1" >/dev/null 2>&1 || true; }

# ===========================================================================
# PROBES — do the seams actually BITE?
# ===========================================================================
# A timing assertion alone proves nothing: a normal hook ack finishes well
# inside either grace, so every case would pass with the override ignored. Each
# probe therefore has a STIMULUS that forbids the fast path, a TERMINAL VERDICT,
# and a BOUND that excludes the default. This is the V1-class defect made
# visible — a missed seam silently restores the default and only the end-of-run
# budget would ever notice.

# ---------------------------------------------------------------------------
section "Probe A — the ack grace is the ENV's 5 s, not the 20 s default"
# ---------------------------------------------------------------------------
(
    read -r RID PANE _ < <(make_live_agent "agent-pick-probea")
    assert_eq "probe A: the agent was recorded" "8" "${#RID}"
    freeze_and_wait "$PANE" "$RID"

    # Stimulus: the replacement never calls the hook, so no ack can EVER arrive
    # and the coordinator is forced onto the liveness path.
    agent_env FAKE_AGENT_NO_HOOK=1
    t0=$(date +%s)
    out="$("$FROZEN_SH" restore "$RID" 2>&1)"
    el=$(elapsed_since "$t0")
    agent_env_clear

    assert_contains "probe A: the liveness fallback is what confirmed it" \
        "RESTORED:$RID|liveness" "$out"
    assert_eq "probe A: the record records the liveness ack" "liveness" \
        "$(record_field "$RID" ack)"
    # The ack-less contract: a restore nobody verified KEEPS the capture.
    assert_eq "probe A: an unverified restore KEEPS the capture" "yes" \
        "$([ -f "$AITASKS_FROZEN_DIR/$RID/capture.txt" ] && echo yes || echo no)"
    assert_between "probe A: waited the configured 5 s, not the 20 s default" \
        5 15 "$el"
    drop_record "$RID"
)

# ---------------------------------------------------------------------------
section "Probe B — the stale-op grace is the ENV's 2 s, not the 60 s default"
# ---------------------------------------------------------------------------
(
    read -r RID PANE _ < <(make_live_agent "agent-pick-probeb")
    freeze_and_wait "$PANE" "$RID"

    # Stimulus: strand a lease with a DEAD owner. The agent exits at once, so
    # the coordinator reaches its abort stage, where it SIGSTOPs itself; we then
    # SIGKILL it, leaving a lease no live process owns.
    agent_env FAKE_AGENT_EXIT=1
    AITASKS_FROZEN_PAUSE_AT=aborting "$FROZEN_SH" restore "$RID" >/dev/null 2>&1 &
    coord=$!
    paused=""
    for _ in $(seq 1 100); do
        pid="$(pgrep -f "aitask_frozen.sh restore $RID" 2>/dev/null | head -1)"
        if [ -n "$pid" ] && wait_stopped "$pid"; then paused="$pid"; break; fi
        sleep 0.1
    done
    assert_eq "probe B: the coordinator paused at its abort stage" "yes" \
        "$([ -n "$paused" ] && echo yes || echo no)"

    if [ -n "$paused" ]; then
        # A second restore must be refused while the (still-leased) record is
        # mid-transaction — the lease is what makes that a refusal and not a race.
        out2="$("$FROZEN_SH" restore "$RID" 2>&1)"
        assert_contains "probe B: a second restore is refused while leased" \
            "TRANSITION_REFUSED" "$out2"
        kill -9 "$paused" 2>/dev/null || true
    fi
    kill -9 "$coord" 2>/dev/null || true
    wait "$coord" 2>/dev/null || true
    agent_env_clear

    # Past the 2 s grace the lease is stale and reconcile may take it over.
    # Under the 60 s default reconcile would skip the record as in-flight and it
    # would still be unsettled when this bound expires — so the bound
    # DISCRIMINATES rather than merely timing a fast path.
    sleep 3
    t0=$(date +%s)
    "$FROZEN_SH" reconcile >/dev/null 2>&1
    settled="no"
    wait_for_record_state "$RID" frozen && settled="yes"
    el=$(elapsed_since "$t0")
    assert_eq "probe B: reconcile settled the stranded record to frozen" "yes" "$settled"
    assert_between "probe B: it settled well inside the 60 s default" 0 15 "$el"
    assert_eq "probe B: the killed coordinator's lease is gone" "" \
        "$(record_field "$RID" op_nonce)"
    drop_record "$RID"
)

# ---------------------------------------------------------------------------
section "Probe C1 — capture_max_lines proves the scratch CONFIG was read"
# ---------------------------------------------------------------------------
# This is the one `frozen:` knob with NO environment override, so on its own it
# proves both that the config file was found and that the project root resolved
# to $SCRATCH. The fake emits 300 lines; the config caps at 120; the default is
# 50000, under which all 300 would survive. The two outcomes are unmistakable.
(
    # The knob must be in place BEFORE the agent launches: the wrapper sources
    # $AGENT_ENV_FILE once, at exec time.
    agent_env FAKE_AGENT_OUTPUT_LINES=300
    read -r RID PANE _ < <(make_live_agent "agent-pick-probec1")
    sleep 1
    freeze_and_wait "$PANE" "$RID"
    agent_env_clear

    lines="$(wc -l < "$AITASKS_FROZEN_DIR/$RID/capture.txt" 2>/dev/null | tr -d ' ')"
    # `capture_max_lines` is SCROLLBACK DEPTH, not a total: the engine passes
    # `-S -<cap>`, which starts <cap> lines back in history and runs through the
    # bottom of the VISIBLE pane. So the file holds cap + pane_height lines, and
    # asserting a bare 120 would fail against correct behaviour. Deriving the
    # expected value from the live pane height keeps this pinned to the
    # mechanism rather than to one terminal geometry.
    height="$(pane_fmt "$PANE" '#{pane_height}')"
    assert_eq "probe C1: the capture is the CONFIGURED 120 of history + the visible pane" \
        "$((120 + height))" "$lines"
    assert_eq "probe C1: the record agrees with the file" "$((120 + height))" \
        "$(record_field "$RID" capture_lines)"
    # The discrimination, stated separately from the arithmetic: 300 lines were
    # emitted, and under the 50000-line default all of them would survive. Any
    # count this far below 300 can only be the configured cap.
    assert_between "probe C1: far below the 300 emitted, so the default did NOT apply" \
        120 200 "$lines"
    # Ground truth from the filesystem, not the store: 0600 is the at-rest
    # contract for a capture that may hold a whole session's output.
    assert_eq "probe C1: capture.txt is 0600" "600" \
        "$(stat -f '%OLp' "$AITASKS_FROZEN_DIR/$RID/capture.txt" 2>/dev/null \
           || stat -c '%a' "$AITASKS_FROZEN_DIR/$RID/capture.txt" 2>/dev/null)"
    assert_eq "probe C1: capture.ansi is 0600" "600" \
        "$(stat -f '%OLp' "$AITASKS_FROZEN_DIR/$RID/capture.ansi" 2>/dev/null \
           || stat -c '%a' "$AITASKS_FROZEN_DIR/$RID/capture.ansi" 2>/dev/null)"
    drop_record "$RID"
)

# ---------------------------------------------------------------------------
section "Probe C2 — with the env override REMOVED, the configured 8 s governs"
# ---------------------------------------------------------------------------
# Under test_mode a positive AITASKS_RESTORE_ACK_GRACE returns at
# agent_frozen_ops.py:144-151 BEFORE the config is opened, so every other case
# in this file leaves the config path for this setting untested. `env -u`
# removes the higher-precedence layer so the configured value is the only thing
# that can explain the result — and the coordinator is invoked DIRECTLY, so it
# inherits this shell (an `env -u` would not reach a `run-shell -b` job, which
# takes the server's environment).
(
    read -r RID PANE _ < <(make_live_agent "agent-pick-probec2")
    freeze_and_wait "$PANE" "$RID"

    agent_env FAKE_AGENT_NO_HOOK=1
    t0=$(date +%s)
    out="$(env -u AITASKS_RESTORE_ACK_GRACE "$FROZEN_SH" restore "$RID" 2>&1)"
    el=$(elapsed_since "$t0")
    agent_env_clear

    assert_contains "probe C2: still a liveness confirm" "RESTORED:$RID|liveness" "$out"
    # 7..15 implicates the configured 8 and excludes BOTH the env 5 and the
    # default 20.
    assert_between "probe C2: waited the CONFIGURED 8 s (not env 5, not default 20)" \
        7 15 "$el"
    drop_record "$RID"
)

# ---------------------------------------------------------------------------
section "Probe D — the seams reach a REAL detached run-shell -b coordinator"
# ---------------------------------------------------------------------------
# Every probe above invokes the coordinator as a child of the test shell, which
# inherits this environment. The shipped dispatch is `run-shell -b`, whose
# environment comes from the SERVER. This is the only probe that proves the
# override reaches the coordinator users actually get — and it drives it from
# the viewer's own `R` key, so the viewer's key path is exercised live.
(
    read -r RID PANE _ < <(make_live_agent "agent-pick-probed")
    freeze_and_wait "$PANE" "$RID"

    agent_env FAKE_AGENT_NO_HOOK=1
    t0=$(date +%s)
    tm send-keys -t "$PANE" R
    # The viewer dispatches `run-shell -b`, so there is no stdout to read: the
    # RECORD is the channel, exactly as the monitor and minimonitor observe it.
    settled="no"
    for _ in $(seq 1 200); do
        [ "$(record_field "$RID" state)" = "live" ] && { settled="yes"; break; }
        sleep 0.1
    done
    el=$(elapsed_since "$t0")
    agent_env_clear

    assert_eq "probe D: the viewer's R key drove a restore to completion" "yes" "$settled"
    assert_eq "probe D: it was the liveness path (no hook ever acked)" "liveness" \
        "$(record_field "$RID" ack)"
    assert_between "probe D: the detached coordinator honoured the 5 s env grace" \
        5 20 "$el"
    drop_record "$RID"
)

# ===========================================================================
# CASES
# ===========================================================================

# ---------------------------------------------------------------------------
section "Case 1 — launch through the wrappers binds ONE live record"
# ---------------------------------------------------------------------------
(
    W="agent-pick-1"
    read -r RID PANE COMPANION < <(make_live_agent "$W")

    assert_eq "case 1: the hook stamped a canonical record id on the pane" "8" "${#RID}"
    assert_eq "case 1: exactly one record exists for it" "1" \
        "$(store list 2>/dev/null | grep -c "^SESSION:$RID|")"
    assert_eq "case 1: the record is live" "live" "$(record_field "$RID" state)"
    # Ground truth: the store's pane_pid must equal what the SERVER reports.
    assert_eq "case 1: pane_pid matches the server's #{pane_pid}" \
        "$(pane_fmt "$PANE" '#{pane_pid}')" "$(record_field "$RID" pane_pid)"
    assert_eq "case 1: the root is the scratch project" "$SCRATCH" \
        "$(record_field "$RID" root)"
    assert_eq "case 1: the window name was recorded" "$W" "$(record_field "$RID" window)"
    assert_eq "case 1: the first agent in a window takes slot 0" "0" \
        "$(record_field "$RID" window_slot)"
    # This is the AITASK_AGENT_STRING export path, and it only exists because
    # the agent was launched through the WRAPPER rather than its --dry-run argv.
    assert_eq "case 1: the agent string came through the wrapper's export" \
        "claudecode/opus5" "$(record_field "$RID" agent_string)"
    # The fake reports `fakesess-<pid>`; the pane option and the store must agree.
    assert_eq "case 1: the codeagent session id was captured" "yes" \
        "$([ -n "$(record_field "$RID" codeagent_session_id)" ] && echo yes || echo no)"
    assert_eq "case 1: @aitask_agent_session agrees with the store" \
        "$(record_field "$RID" codeagent_session_id)" \
        "$(pane_fmt "$PANE" '#{@aitask_agent_session}')"
    assert_eq "case 1: the companion pane is alive" "yes" \
        "$(pane_exists "$COMPANION" && echo yes || echo no)"
    drop_record "$RID"
)

# ---------------------------------------------------------------------------
section "Case 2 — freeze puts the REAL viewer in the pane"
# ---------------------------------------------------------------------------
(
    W="agent-pick-2"
    agent_env FAKE_AGENT_OUTPUT_LINES=300
    read -r RID PANE COMPANION < <(make_live_agent "$W")
    sleep 1
    agent_pid="$(pane_fmt "$PANE" '#{pane_pid}')"

    out="$("$FROZEN_SH" freeze "$PANE" 2>&1)"
    assert_contains "case 2: freeze reports FROZEN" "FROZEN:$RID" "$out"
    assert_eq "case 2: the record is frozen" "frozen" "$(record_field "$RID" state)"
    assert_eq "case 2: the frozen stamp names the record" "$RID" \
        "$(pane_fmt "$PANE" '#{@aitask_frozen}')"

    ready="no"; wait_for_ready "$PANE" "$RID" && ready="yes"
    assert_eq "case 2: the REAL viewer booted and stamped itself ready" "yes" "$ready"

    # `respawn-pane -k` keeps the pane id and replaces the process; asserting the
    # id alone would pass even if nothing had been respawned.
    standin_pid="$(pane_fmt "$PANE" '#{pane_pid}')"
    assert_eq "case 2: the pane id is unchanged" "$PANE" "$(pane_fmt "$PANE" '#{pane_id}')"
    if [ "$standin_pid" != "$agent_pid" ]; then assert_record_pass; else
        assert_record_fail
        echo "FAIL: case 2: #{pane_pid} did not change — nothing was respawned"
    fi
    assert_eq "case 2: standin_pid is the respawned viewer" "$standin_pid" \
        "$(record_field "$RID" standin_pid)"
    assert_eq "case 2: capture files exist" "yes" \
        "$([ -f "$AITASKS_FROZEN_DIR/$RID/capture.txt" ] && echo yes || echo no)"
    # cap + pane_height — see the arithmetic note in probe C1.
    assert_eq "case 2: the capture is the CONFIGURED 120 of history + the visible pane" \
        "$((120 + $(pane_fmt "$PANE" '#{pane_height}')))" \
        "$(wc -l < "$AITASKS_FROZEN_DIR/$RID/capture.txt" | tr -d ' ')"
    assert_eq "case 2: the companion survived the respawn" "yes" \
        "$(pane_exists "$COMPANION" && echo yes || echo no)"
    # What the user actually sees: the viewer's header, naming this window.
    assert_contains "case 2: the viewer's header names the window" "$W" \
        "$(tm capture-pane -p -t "$PANE" 2>/dev/null)"
    agent_env_clear
    drop_record "$RID"
)

# ---------------------------------------------------------------------------
section "Case 3 — a replacement that exits at once: agent_exited, viewer back"
# ---------------------------------------------------------------------------
(
    read -r RID PANE _ < <(make_live_agent "agent-pick-3")
    freeze_and_wait "$PANE" "$RID"

    agent_env FAKE_AGENT_EXIT=1
    t0=$(date +%s)
    out="$("$FROZEN_SH" restore "$RID" 2>&1)"
    el=$(elapsed_since "$t0")
    agent_env_clear

    assert_contains "case 3: the failure is attributed to the agent exiting" \
        "RESTORE_FAILED:$RID|agent_exited" "$out"
    assert_eq "case 3: the record is frozen again" "frozen" "$(record_field "$RID" state)"
    assert_eq "case 3: THE CAPTURE SURVIVED a failed restore" "yes" \
        "$([ -f "$AITASKS_FROZEN_DIR/$RID/capture.txt" ] && echo yes || echo no)"
    assert_eq "case 3: the attempt was counted" "1" "$(record_field "$RID" restore_attempts)"
    ready="no"; wait_for_ready "$PANE" "$RID" && ready="yes"
    assert_eq "case 3: the viewer is back and ready" "yes" "$ready"
    # A dead pane is detected, not waited out: this must NOT cost the ack grace.
    assert_between "case 3: it failed fast, without waiting out the grace" 0 5 "$el"
    drop_record "$RID"
)

# ---------------------------------------------------------------------------
section "Case 4 — a MISMATCHED session aborts via last_error, not liveness"
# ---------------------------------------------------------------------------
# The hook has no return channel to the detached coordinator, so the RECORD is
# the channel: the store persists `<nonce>:session_mismatch` and the coordinator
# reads it. The load-bearing negative is that the liveness fallback never fires.
(
    read -r RID PANE _ < <(make_live_agent "agent-pick-4")
    freeze_and_wait "$PANE" "$RID"

    agent_env FAKE_AGENT_SESSION=a-different-session
    t0=$(date +%s)
    out="$("$FROZEN_SH" restore "$RID" 2>&1)"
    el=$(elapsed_since "$t0")
    agent_env_clear

    assert_contains "case 4: the mismatch is named as the reason" \
        "RESTORE_FAILED:$RID|session_mismatch" "$out"
    assert_eq "case 4: the record is frozen again" "frozen" "$(record_field "$RID" state)"
    assert_eq "case 4: the capture survived" "yes" \
        "$([ -f "$AITASKS_FROZEN_DIR/$RID/capture.txt" ] && echo yes || echo no)"
    # THE point of the case: an ack of "" means liveness never confirmed it.
    assert_eq "case 4: the liveness fallback did NOT fire" "" "$(record_field "$RID" ack)"
    assert_between "case 4: it aborted WITHOUT waiting out the 5 s grace" 0 5 "$el"
    ready="no"; wait_for_ready "$PANE" "$RID" && ready="yes"
    assert_eq "case 4: the viewer is back" "yes" "$ready"
    drop_record "$RID"
)

# ---------------------------------------------------------------------------
section "Case 5 — the happy restore: ack=hook, captures deleted, join intact"
# ---------------------------------------------------------------------------
(
    read -r RID PANE _ < <(make_live_agent "agent-pick-5")
    sid_before="$(record_field "$RID" codeagent_session_id)"
    freeze_and_wait "$PANE" "$RID"
    standin_pid="$(pane_fmt "$PANE" '#{pane_pid}')"

    out="$("$FROZEN_SH" restore "$RID" 2>&1)"
    assert_contains "case 5: the HOOK verified the restore" "RESTORED:$RID|hook" "$out"
    assert_eq "case 5: the record is live again" "live" "$(record_field "$RID" state)"
    assert_eq "case 5: the ack names the hook" "hook" "$(record_field "$RID" ack)"
    assert_eq "case 5: a VERIFIED restore deletes the captures" "no" \
        "$([ -f "$AITASKS_FROZEN_DIR/$RID/capture.txt" ] && echo yes || echo no)"
    assert_eq "case 5: the frozen stamp was cleared" "" \
        "$(pane_fmt "$PANE" '#{@aitask_frozen}')"
    # The amendment from t1705_2: the pane->record join must SURVIVE the cycle.
    # Pane user options outlive `respawn-pane`, so a missing stamp here is what
    # later makes the freeze engine create a SECOND record for a recorded agent.
    assert_eq "case 5: @aitask_record still names the SAME record" "$RID" \
        "$(record_of_pane "$PANE")"
    new_pid="$(pane_fmt "$PANE" '#{pane_pid}')"
    if [ "$new_pid" != "$standin_pid" ]; then assert_record_pass; else
        assert_record_fail
        echo "FAIL: case 5: the viewer was never replaced by the agent"
    fi
    assert_eq "case 5: pane_pid was updated to the replacement" "$new_pid" \
        "$(record_field "$RID" pane_pid)"
    # A resume must return to the SAME session, not start a new one.
    assert_eq "case 5: the resumed session id is unchanged" "$sid_before" \
        "$(record_field "$RID" codeagent_session_id)"
    assert_contains "case 5: the agent was told to resume that session" \
        "$sid_before" "$(tm capture-pane -p -t "$PANE" 2>/dev/null)"
    drop_record "$RID"
)

# ---------------------------------------------------------------------------
section "Case 6a — a gone-pane record restores into a NEW window"
# ---------------------------------------------------------------------------
# The gone-pane branch (`_launch_into_new_window`) is reached when the record's
# `pane_id` is EMPTY, and the one shipped path that empties it is the `freezing`
# + pane-gone reconcile row, which commits `--pane "" --pane-pid 0` precisely
# "so the record becomes restorable into a NEW window"
# (agent_freeze.py:696). So this case drives that: pause the freeze before its
# commit, close the window underneath it, kill the coordinator, and let
# reconcile do the gone-pane commit.
(
    W="agent-pick-6a"
    read -r RID PANE _ < <(make_live_agent "$W")
    before="$(store list 2>/dev/null | grep -c '^SESSION:')"
    slot_before="$(record_field "$RID" window_slot)"

    AITASKS_FROZEN_PAUSE_AT=commit "$FROZEN_SH" freeze "$PANE" >/dev/null 2>&1 &
    coord=$!
    paused=""
    for _ in $(seq 1 100); do
        pid="$(pgrep -f "aitask_frozen.sh freeze $PANE" 2>/dev/null | head -1)"
        if [ -n "$pid" ] && wait_stopped "$pid"; then paused="$pid"; break; fi
        sleep 0.1
    done
    assert_eq "case 6a: the freeze paused before its commit" "yes" \
        "$([ -n "$paused" ] && echo yes || echo no)"
    assert_eq "case 6a: the record is mid-transaction" "freezing" \
        "$(record_field "$RID" state)"

    tm kill-window -t "$PANE" 2>/dev/null || true
    sleep 0.5
    assert_eq "case 6a: the window really is gone" "no" \
        "$(window_exists "$W" "$SESSION" && echo yes || echo no)"
    [ -n "$paused" ] && kill -9 "$paused" 2>/dev/null
    kill -9 "$coord" 2>/dev/null || true
    wait "$coord" 2>/dev/null || true

    sleep 3     # past the 2 s stale-op grace, so reconcile may take the lease
    "$FROZEN_SH" reconcile >/dev/null 2>&1
    assert_eq "case 6a: reconcile committed the gone-pane freeze" "frozen" \
        "$(record_field "$RID" state)"
    assert_eq "case 6a: and cleared the pane location" "" \
        "$(record_field "$RID" pane_id)"

    out="$("$FROZEN_SH" restore "$RID" 2>&1)"
    assert_contains "case 6a: the restore succeeded into a new window" "RESTORED:$RID" "$out"
    assert_eq "case 6a: a window with the recorded name is back" "yes" \
        "$(window_exists "$W" "$SESSION" && echo yes || echo no)"
    # The whole point: the OLD record was acknowledged from a brand-new pane
    # (the id travelled in the environment), not a second one created.
    assert_eq "case 6a: no second record was created" "$before" \
        "$(store list 2>/dev/null | grep -c '^SESSION:')"
    assert_eq "case 6a: the record is live" "live" "$(record_field "$RID" state)"
    assert_eq "case 6a: the window slot is unchanged" "$slot_before" \
        "$(record_field "$RID" window_slot)"
    assert_eq "case 6a: the captures were deleted" "no" \
        "$([ -d "$AITASKS_FROZEN_DIR/$RID" ] && echo yes || echo no)"
    drop_record "$RID"
)

# ---------------------------------------------------------------------------
section "Case 6b — a COMMITTED frozen record whose window is closed (t1773)"
# ---------------------------------------------------------------------------
# THE ORDINARY USER ROUTE, and the one 6a cannot reach. Freeze normally, then
# close the window (or restart tmux): `_reconcile_frozen` returns
# `KEEP:<id>|pane_gone` and writes NOTHING, so unlike 6a the record keeps its
# dead `%N` forever. Before t1773 `agent_restore.restore` branched on that
# RECORDED id — never on whether the pane still existed — and respawned the
# corpse, so the record could never be restored again.
#
# The fix resolves the recorded id against the SERVER first, the same rule
# `drop_record()`'s docstring already stated ("`pane_id` is durable but NOT
# authoritative … the record stays restorable into a fresh window") and that
# `drop` already applied to its own preflight. So 6b now asserts the same
# outcome as 6a, reached by the route users actually take.
(
    W="agent-pick-6b"
    read -r RID PANE _ < <(make_live_agent "$W")
    before="$(store list 2>/dev/null | grep -c '^SESSION:')"
    slot_before="$(record_field "$RID" window_slot)"
    freeze_and_wait "$PANE" "$RID"

    tm kill-window -t "$PANE" 2>/dev/null || true
    sleep 0.5
    # The premise: unlike 6a, NOTHING cleared the pane location. This is what
    # makes 6b a different case and not a duplicate of it.
    assert_eq "case 6b: the record still names the now-dead pane" "$PANE" \
        "$(record_field "$RID" pane_id)"
    assert_eq "case 6b: the window really is gone" "no" \
        "$(window_exists "$W" "$SESSION" && echo yes || echo no)"

    out="$("$FROZEN_SH" restore "$RID" 2>&1)"
    assert_contains "case 6b: the restore succeeded into a new window" \
        "RESTORED:$RID" "$out"
    assert_eq "case 6b: a window with the recorded name is back" "yes" \
        "$(window_exists "$W" "$SESSION" && echo yes || echo no)"
    assert_eq "case 6b: the record is live" "live" "$(record_field "$RID" state)"
    # The record must now name a pane that EXISTS and is not the corpse.
    new_pane="$(record_field "$RID" pane_id)"
    if [ -n "$new_pane" ] && [ "$new_pane" != "$PANE" ]; then assert_record_pass; else
        assert_record_fail
        echo "FAIL: case 6b: pane_id still names the dead pane ($new_pane)"
    fi
    assert_eq "case 6b: and that pane is real" "yes" \
        "$(pane_exists "$new_pane" && echo yes || echo no)"
    assert_eq "case 6b: no second record was created" "$before" \
        "$(store list 2>/dev/null | grep -c '^SESSION:')"
    assert_eq "case 6b: the window slot is unchanged" "$slot_before" \
        "$(record_field "$RID" window_slot)"
    assert_eq "case 6b: the captures were deleted" "no" \
        "$([ -d "$AITASKS_FROZEN_DIR/$RID" ] && echo yes || echo no)"
    drop_record "$RID"
)

# ---------------------------------------------------------------------------
section "Case 7 — a coordinator killed while aborting is settled by reconcile"
# ---------------------------------------------------------------------------
(
    read -r RID PANE _ < <(make_live_agent "agent-pick-7")
    freeze_and_wait "$PANE" "$RID"

    agent_env FAKE_AGENT_EXIT=1
    AITASKS_FROZEN_PAUSE_AT=aborting "$FROZEN_SH" restore "$RID" >/dev/null 2>&1 &
    coord=$!
    paused=""
    for _ in $(seq 1 100); do
        pid="$(pgrep -f "aitask_frozen.sh restore $RID" 2>/dev/null | head -1)"
        if [ -n "$pid" ] && wait_stopped "$pid"; then paused="$pid"; break; fi
        sleep 0.1
    done
    assert_eq "case 7: the coordinator paused mid-abort" "yes" \
        "$([ -n "$paused" ] && echo yes || echo no)"
    nonce_before="$(record_field "$RID" op_nonce)"

    out2="$("$FROZEN_SH" restore "$RID" 2>&1)"
    assert_contains "case 7: a second restore is refused mid-transaction" \
        "TRANSITION_REFUSED" "$out2"

    [ -n "$paused" ] && kill -9 "$paused" 2>/dev/null
    kill -9 "$coord" 2>/dev/null || true
    wait "$coord" 2>/dev/null || true
    agent_env_clear

    sleep 3     # past the 2 s stale-op grace
    "$FROZEN_SH" reconcile >/dev/null 2>&1
    settled="no"; wait_for_record_state "$RID" frozen && settled="yes"
    assert_eq "case 7: reconcile settled it back to frozen" "yes" "$settled"
    ready="no"; wait_for_ready "$PANE" "$RID" && ready="yes"
    assert_eq "case 7: the viewer is back and ready" "yes" "$ready"
    assert_eq "case 7: the dead coordinator's lease was cleared" "" \
        "$(record_field "$RID" op_nonce)"
    if [ -n "$nonce_before" ]; then assert_record_pass; else
        assert_record_fail
        echo "FAIL: case 7: no lease was ever minted, so nothing was proven"
    fi
    assert_eq "case 7: the capture survived the whole ordeal" "yes" \
        "$([ -f "$AITASKS_FROZEN_DIR/$RID/capture.txt" ] && echo yes || echo no)"
    drop_record "$RID"
)

# ---------------------------------------------------------------------------
section "Case 8 — killed after the respawn, before restore-launched"
# ---------------------------------------------------------------------------
# The nastiest window, and it is NOT the one the plan named: `pause_at("respawn")`
# sits at agent_restore.py:407, AFTER the respawn at :395, so "killed before the
# respawn" is not reachable through this seam — there is no stage between
# clearing the ready mark and respawning. What IS reachable, and is the row that
# actually matters, is the gap between the respawn and `restore-launched`: the
# ready mark is cleared, the viewer is gone, a replacement is running, and the
# record carries `launch_pid == 0` — so reconcile has NO nonce-bound evidence
# that this process is the one the coordinator started.
#
# The contract is that it must NOT liveness-confirm on that evidence-free state
# (§C: "a liveness confirm requires POSITIVE evidence") and must instead roll
# back to the viewer after stale_op_grace x2.
#
# FAKE_AGENT_NO_HOOK=1 is load-bearing: without it the replacement's own hook
# acks the record to `live` on its own — correct behaviour, and it would leave
# this row untested.
#
# AITASKS_FROZEN_PAUSE_AT is set on THIS INVOCATION ONLY, never exported: the
# stage name `respawn` is used by BOTH agent_freeze.py:392 and
# agent_restore.py:407, so an exported value would stop the FREEZE at its own
# respawn stage and this case would never reach a restore at all.
(
    read -r RID PANE _ < <(make_live_agent "agent-pick-8")
    freeze_and_wait "$PANE" "$RID"
    standin_before="$(record_field "$RID" standin_pid)"

    agent_env FAKE_AGENT_NO_HOOK=1
    AITASKS_FROZEN_PAUSE_AT=respawn "$FROZEN_SH" restore "$RID" >/dev/null 2>&1 &
    coord=$!
    paused=""
    for _ in $(seq 1 100); do
        pid="$(pgrep -f "aitask_frozen.sh restore $RID" 2>/dev/null | head -1)"
        if [ -n "$pid" ] && wait_stopped "$pid"; then paused="$pid"; break; fi
        sleep 0.1
    done
    assert_eq "case 8: the coordinator paused just past its respawn" "yes" \
        "$([ -n "$paused" ] && echo yes || echo no)"
    assert_eq "case 8: the ready mark was cleared before the respawn" "" \
        "$(pane_fmt "$PANE" '#{@aitask_standin_ready}')"
    assert_eq "case 8: the record is mid-restore" "restoring" \
        "$(record_field "$RID" state)"
    # The evidence gap this case is about: the respawn happened, but the
    # nonce-bound record of it has not been written yet.
    assert_eq "case 8: no launch evidence was recorded yet" "0" \
        "$(record_field "$RID" launch_pid)"
    if [ "$(pane_fmt "$PANE" '#{pane_pid}')" != "$standin_before" ]; then
        assert_record_pass
    else
        assert_record_fail
        echo "FAIL: case 8: the viewer was never replaced, so the gap was not reached"
    fi

    [ -n "$paused" ] && kill -9 "$paused" 2>/dev/null
    kill -9 "$coord" 2>/dev/null || true
    wait "$coord" 2>/dev/null || true

    # Past stale_op_grace x2 (2 s x 2), which is what this row waits out before
    # giving up on an in-flight respawn.
    sleep 6
    "$FROZEN_SH" reconcile >/dev/null 2>&1
    settled="no"; wait_for_record_state "$RID" frozen && settled="yes"
    if [ "$settled" != "yes" ]; then
        sleep 2; "$FROZEN_SH" reconcile >/dev/null 2>&1
        wait_for_record_state "$RID" frozen && settled="yes"
    fi
    agent_env_clear

    assert_eq "case 8: reconcile rolled the evidence-free restore back to frozen" \
        "yes" "$settled"
    ready="no"; wait_for_ready "$PANE" "$RID" && ready="yes"
    assert_eq "case 8: the viewer is back and re-stamped itself ready" "yes" "$ready"
    # THE point: with no launch_pid it must never liveness-confirm, however
    # alive the process in the pane looks.
    assert_eq "case 8: it never confirmed a restore" "" "$(record_field "$RID" ack)"
    assert_eq "case 8: the capture survived" "yes" \
        "$([ -f "$AITASKS_FROZEN_DIR/$RID/capture.txt" ] && echo yes || echo no)"
    drop_record "$RID"
)

# ---------------------------------------------------------------------------
section "Case 9 — an AMBIGUOUS relocation fails closed and is then purged"
# ---------------------------------------------------------------------------
# Two agents shared one window before a server restart. Nothing on the caller's
# side can tell them apart afterwards, so the store must create beside them
# rather than guess which one relocated.
(
    W="agent-pick-9"
    read -r RID_A PANE_A _ < <(make_live_agent "$W")
    # A second agent in the SAME window -> slot 1.
    PANE_B="$(tm split-window -d -t "$PANE_A" -c "$SCRATCH" -P -F '#{pane_id}' \
        "$CODEAGENT_SH --agent-string claudecode/opus5 invoke raw")"
    RID_B="$(wait_for_record_stamp "$PANE_B")" || RID_B=""

    assert_eq "case 9: the second agent got its own record" "yes" \
        "$([ -n "$RID_B" ] && [ "$RID_B" != "$RID_A" ] && echo yes || echo no)"
    assert_eq "case 9: it took the next free slot" "1" "$(record_field "$RID_B" window_slot)"

    # "Server restart": kill the isolated server and rebuild the window with ONE
    # agent. Both old records are now live-but-dead-paned, and both are
    # candidates for the same (root, window).
    PATH="$REAL_PATH" "$REAL_TMUX" kill-server 2>/dev/null || true
    sleep 0.5
    tm new-session -d -s "$SESSION" -n scratch -c "$SCRATCH" "sleep 1000"
    sleep 0.4
    read -r RID_C _ _ < <(make_live_agent "$W")

    assert_eq "case 9: the ambiguous case created a THIRD record, not a guess" "yes" \
        "$([ -n "$RID_C" ] && [ "$RID_C" != "$RID_A" ] && [ "$RID_C" != "$RID_B" ] \
           && echo yes || echo no)"
    assert_eq "case 9: it was placed beside them, at slot 2" "2" \
        "$(record_field "$RID_C" window_slot)"
    assert_eq "case 9: both stale records are still there, awaiting purge" "2" \
        "$(store list 2>/dev/null | grep -cE "^SESSION:($RID_A|$RID_B)\|")"

    # reconcile builds its own observation file, so retirement does not depend
    # on a TUI being open.
    "$FROZEN_SH" reconcile >/dev/null 2>&1
    sleep 0.5
    assert_eq "case 9: reconcile purged both dead-paned records" "0" \
        "$(store list 2>/dev/null | grep -cE "^SESSION:($RID_A|$RID_B)\|")"
    assert_eq "case 9: the live record was NOT purged" "live" \
        "$(record_field "$RID_C" state)"
    drop_record "$RID_C"
)

# ---------------------------------------------------------------------------
section "Case 10a — the STORE's drop is tmux-free and leaves the pane alone"
# ---------------------------------------------------------------------------
# `lib/agent_sessions.py` opens with "THIS MODULE NEVER TOUCHES TMUX", so
# `aitask_agent_sessions.sh drop` removes the record and the captures and leaves
# the stand-in running with all its stamps. That is the store's real contract,
# and this case exists to pin it — asserting that the pane options were cleared
# here would be asserting a coincidence that never happens.
(
    read -r RID PANE _ < <(make_live_agent "agent-pick-10a")
    freeze_and_wait "$PANE" "$RID"

    out="$(store drop "$RID" 2>&1)"
    assert_contains "case 10a: the store reports the drop" "DROPPED:$RID" "$out"
    assert_eq "case 10a: the record is gone" "0" \
        "$(store list 2>/dev/null | grep -c "^SESSION:$RID|")"
    assert_eq "case 10a: the capture directory is gone" "no" \
        "$([ -d "$AITASKS_FROZEN_DIR/$RID" ] && echo yes || echo no)"
    # The contract: the tmux-free store CANNOT and does not retire the pane.
    assert_eq "case 10a: the stand-in pane is STILL ALIVE" "yes" \
        "$(pane_exists "$PANE" && echo yes || echo no)"
    assert_eq "case 10a: and still carries @aitask_record" "$RID" "$(record_of_pane "$PANE")"
    assert_eq "case 10a: and still carries @aitask_frozen" "$RID" \
        "$(pane_fmt "$PANE" '#{@aitask_frozen}')"

    # Teardown is part of the case: an orphaned stamped pane left running would
    # contaminate case 10b's kill-window-vs-kill-pane decision.
    tm kill-window -t "$PANE" 2>/dev/null || true
    sleep 0.4
    assert_eq "case 10a: the orphan was torn down before 10b" "no" \
        "$(pane_exists "$PANE" && echo yes || echo no)"
)

# ---------------------------------------------------------------------------
section "Case 10b — the FREEZE engine's drop retires the pane too"
# ---------------------------------------------------------------------------
# A fresh cycle with its own record: 10a deleted its record, so a 10b reusing it
# would have nothing to drop.
(
    read -r RID PANE _ < <(make_live_agent "agent-pick-10b")
    freeze_and_wait "$PANE" "$RID"

    out="$("$FROZEN_SH" drop "$RID" 2>&1)"
    assert_contains "case 10b: the engine reports the drop" "DROPPED:$RID" "$out"
    assert_eq "case 10b: the record is gone" "0" \
        "$(store list 2>/dev/null | grep -c "^SESSION:$RID|")"
    assert_eq "case 10b: the capture directory is gone" "no" \
        "$([ -d "$AITASKS_FROZEN_DIR/$RID" ] && echo yes || echo no)"
    sleep 0.5
    # Assert the PANE IS GONE — not that its options were unset, which never
    # happens: pane options are pane-scoped and die with the pane, so there is
    # no unstamp step that could fail (agent_freeze.py:946).
    assert_eq "case 10b: the stand-in pane was retired" "no" \
        "$(pane_exists "$PANE" && echo yes || echo no)"
)

# ===========================================================================
# Budget
# ===========================================================================
ACCEPTANCE_ELAPSED=$(elapsed_since "$START_TS")
echo
echo "ACCEPTANCE_ELAPSED:$ACCEPTANCE_ELAPSED"
if [ "$ACCEPTANCE_ELAPSED" -lt 180 ]; then
    assert_record_pass
else
    assert_record_fail
    echo "FAIL: the composed run took ${ACCEPTANCE_ELAPSED}s, over the 180s budget."
    echo "      The usual cause is a grace seam that did not take effect, so a"
    echo "      wait fell back to its 20 s / 60 s default. Check probes A-D."
fi

# ===========================================================================
# Level 3 — the genuine end-to-end setup backstop (opt-in, UNTIMED)
# ===========================================================================
# Deliberately after the budget assertion: `ait setup` runs setup_python_venv
# BEFORE the hook step, so reaching setup_claude_hooks through the CLI costs
# minutes of pip and fails outright offline. HOME is redirected because
# VENV_DIR is $HOME-derived — without it this would build into the developer's
# real ~/.aitask/venv, which is the one thing this suite promises not to touch.
if [ "${AIT_ACCEPTANCE_FULL_SETUP:-0}" = "1" ]; then
    section "Level 3 — a full HOME-redirected \`ait setup\` (opt-in, untimed)"
    FULL="$SCRATCH/full_setup"
    mkdir -p "$FULL/home"
    ( cd "$PROJECT_DIR" && tar czhf "$SCRATCH/full.tar.gz" \
        .aitask-scripts/ aitasks/metadata/labels.txt aitasks/metadata/task_types.txt \
        aitasks/metadata/claude_settings.seed.json aitasks/metadata/profiles/ \
        ait seed/ packaging/ 2>/dev/null )
    # The SAME redirected HOME for the installer and for setup. It has to be the
    # same one: install.sh consumes packaging/shim/ait and then deletes
    # packaging/ (cleanup_packaging_leftover), so a setup that still needs to
    # install a shim would fail with "Cannot locate shim source". Under one HOME
    # the installer has already put the shim there and setup finds it in place.
    HOME="$FULL/home" bash "$PROJECT_DIR/install.sh" \
        --dir "$FULL" --local-tarball "$SCRATCH/full.tar.gz" \
        </dev/null >/dev/null 2>&1
    HOME="$FULL/home" "$FULL/ait" setup </dev/null >"$SCRATCH/full_setup.log" 2>&1
    assert_eq "level 3: a full \`ait setup\` exits 0" "0" "$?"
    assert_eq "level 3: it installed exactly one aitasks SessionStart group" "1" \
        "$(count_sessionstart_groups "$FULL/.claude/settings.json")"
    # The venv is $HOME-derived, so its presence in the REDIRECTED home is the
    # positive proof that the redirect held for the expensive half of setup.
    assert_eq "level 3: the venv was built into the REDIRECTED home" "yes" \
        "$([ -d "$FULL/home/.aitask/venv" ] && echo yes || echo no)"
else
    echo
    echo "NOTE: level-3 full-\`ait setup\` check skipped."
    echo "      Set AIT_ACCEPTANCE_FULL_SETUP=1 to run it (untimed; builds a venv"
    echo "      into a redirected HOME). CI should set it."
fi

# ---------------------------------------------------------------------------
section "The real \$HOME is still untouched"
# ---------------------------------------------------------------------------
# Promise (b), measured rather than asserted by construction. install.sh ends in
# `install_global_shim`, which copies packaging/shim/ait into $HOME/.local/bin,
# so every install in this file runs under a redirected HOME. This compares the
# real shim against the fingerprint taken before the first install: if a future
# edit drops a redirect, the developer's global `ait` gets silently rewritten
# and only this check would notice.
assert_eq "the real \$HOME/.local/bin/ait was not rewritten" \
    "$REAL_SHIM_BEFORE" \
    "$( [ -f "$REAL_SHIM" ] && cksum < "$REAL_SHIM" || echo absent )"

# ===========================================================================
section "Summary"
# ===========================================================================
assert_counters_load
echo "Passed: $PASS / $TOTAL"
if [ "$FAIL" -eq 0 ]; then
    echo "ALL TESTS PASSED"
    exit 0
else
    echo "FAILED: $FAIL"
    exit 1
fi
