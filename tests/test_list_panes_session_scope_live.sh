#!/usr/bin/env bash
# test_list_panes_session_scope_live.sh - `list-panes -s` must address a whole
# session with `=<s>:`, never a bare `=<s>` (t1874).
#
# `list-panes` takes a WINDOW-typed -t, so a bare `=alpha` is looked up as a
# window name first, in the current session (clientless: the most recently used
# one). When that session has a window called `alpha`, tmux lists THAT
# session's panes. With `automatic-rename-format '#{b:pane_current_path}'` any
# pane whose cwd basename equals another session's name creates such a window.
#
# Phase A builds that collision on a private server and runs every fix
# assertion while it is live, bracketed by a control that proves the bare form
# still misresolves. Phase B, on separate sessions, shows the bare form is
# right when nothing collides — so the window name is the trigger.
#
# Run: bash tests/test_list_panes_session_scope_live.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# shellcheck source=lib/asserts.sh
. "$PROJECT_DIR/tests/lib/asserts.sh"
# Start from an empty read-only dir, never the invoking one (t1826).
. "$PROJECT_DIR/tests/lib/scratch_cwd.sh"
enter_scratch_cwd

if ! command -v tmux >/dev/null 2>&1; then
    echo "SKIP: tmux not installed"
    exit 0
fi

PYTHON="${PYTHON:-python3}"
[ -x "$HOME/.aitask/venv/bin/python" ] && PYTHON="$HOME/.aitask/venv/bin/python"

TMPROOT="$(mktemp -d /tmp/ait_lps_XXXXXX)"
# Short TMUX_TMPDIR: the socket path has a ~104-byte limit.
TMX="$(mktemp -d /tmp/ait_lpt_XXXXXX)"
SOCK="lps_$$"
priv_tmux() { env -u TMUX -u TMUX_PANE TMUX_TMPDIR="$TMX" tmux -L "$SOCK" "$@"; }
cleanup() { priv_tmux kill-server >/dev/null 2>&1 || true; rm -rf "$TMX" "$TMPROOT"; }
trap cleanup EXIT

# Fake aitasks roots: discovery only recognises a session whose pane cwd walks
# up to aitasks/metadata/project_config.yaml.
for p in pa pb; do
    mkdir -p "$TMPROOT/$p/aitasks/metadata"
    : > "$TMPROOT/$p/aitasks/metadata/project_config.yaml"
done

# Explicit -n pins every window name (and disables automatic-rename for it), and
# -f /dev/null keeps the developer's tmux.conf out of the fixture. `other` is
# created LAST so it is the clientless "current" session, and its window is
# named after session `alpha` — the collision.
priv_tmux -f /dev/null new-session -d -s alpha -n main -c "$TMPROOT/pa" 'sleep 600'
priv_tmux split-window -d -t '=alpha:main' -c "$TMPROOT/pa" 'sleep 600'
priv_tmux new-session -d -s other -n alpha -c "$TMPROOT/pb" 'sleep 600'

bare_session_of() {
    priv_tmux list-panes -s -t "=$1" -F '#{session_name}' 2>/dev/null | sort -u | tr '\n' ' '
}

# --- Phase A.1: negative control (the collision misresolves the bare form) ---
assert_eq "control: bare =alpha lists session other's panes" \
    "other " "$(bare_session_of alpha)"

# --- Phase A.2: fix assertions, collision live -------------------------------
# The Python side prints `CHECK|<name>|<expected>|<actual>` lines; everything
# else it prints is diagnostics.
checks="$(cd "$PROJECT_DIR" && env -u TMUX -u TMUX_PANE \
    TMUX_TMPDIR="$TMX" AITASKS_TMUX_SOCKET="$SOCK" \
    PA="$TMPROOT/pa" PB="$TMPROOT/pb" \
    "$PYTHON" - <<'PYEOF'
import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, ".aitask-scripts/lib")
sys.path.insert(0, ".aitask-scripts")

import agent_freeze  # noqa: E402
from agent_launch_utils import (  # noqa: E402
    discover_aitasks_sessions,
    discover_aitasks_sessions_async,
    discover_aitasks_sessions_checked,
)
from monitor.monitor_core import TmuxMonitor  # noqa: E402
from tmux_exec import TmuxClient, session_scope_target  # noqa: E402

PA, PB = Path(os.environ["PA"]).resolve(), Path(os.environ["PB"]).resolve()
client = TmuxClient()


def check(name, expected, actual):
    print(f"CHECK|{name}|{expected}|{actual}")


def fmt(items):
    return ",".join(sorted(items))


# Ground truth: `list-panes -a` takes no -t, so it cannot misresolve. A real
# tab byte (Python string), and every record must split into two fields.
rc, out = client.run(["list-panes", "-a", "-F", "#{session_name}\t#{pane_id}"])
truth: dict[str, set[str]] = {}
malformed = 0
for line in out.splitlines():
    parts = line.split("\t")
    if len(parts) != 2 or not all(parts):
        malformed += 1
        continue
    truth.setdefault(parts[0], set()).add(parts[1])
check("ground truth: list-panes -a rc", 0, rc)
check("ground truth: every record has 2 fields", 0, malformed)
check("ground truth: sessions", "alpha,other", fmt(truth))
check("ground truth: alpha has 2 panes", 2, len(truth.get("alpha", ())))
alpha_ids, other_ids = truth.get("alpha", set()), truth.get("other", set())

# Raw scope target.
rc, out = client.run(["list-panes", "-s", "-t", session_scope_target("alpha"),
                      "-F", "#{session_name}"])
check("raw =alpha: lists session alpha", "alpha", fmt(set(out.split())))

# Discovery: sync, async, checked.
want = f"alpha={PA};other={PB}"


def mapping(sessions):
    return ";".join(f"{s.session}={s.project_root.resolve()}"
                    for s in sorted(sessions, key=lambda s: s.session))


check("discover_aitasks_sessions maps each session to its own root",
      want, mapping(discover_aitasks_sessions()))
check("discover_aitasks_sessions_async maps each session to its own root",
      want, mapping(asyncio.run(discover_aitasks_sessions_async())))
checked, complete = discover_aitasks_sessions_checked()
check("discover_aitasks_sessions_checked maps each session to its own root",
      want, mapping(checked))
check("discover_aitasks_sessions_checked is complete", True, complete)

# Freeze reconcile enumeration.
ok, observed = agent_freeze._enumerate_session("alpha")
check("freeze _enumerate_session(alpha) ok", True, ok)
check("freeze _enumerate_session(alpha) pane ids",
      fmt(alpha_ids), fmt(o.pane_id for o in observed))
check("freeze _enumerate_session(alpha) sessions",
      "alpha", fmt({o.session for o in observed}))

# Monitor, single-session: sync + async.
mon = TmuxMonitor(session="alpha", multi_session=False, exclude_pane="")
check("monitor single sync: alpha's panes",
      fmt(alpha_ids), fmt(p.pane_id for p in mon.discover_panes()))
panes, _shadows = asyncio.run(mon.discover_panes_with_shadows_async())
check("monitor single async: alpha's panes",
      fmt(alpha_ids), fmt(p.pane_id for p in panes))


# Monitor, multi-session: sync + async. Each pane labelled with its real
# session, none listed twice.
def attribution(panes):
    ids = [p.pane_id for p in panes]
    wrong = [p.pane_id for p in panes
             if p.pane_id not in truth.get(p.session_name, set())]
    return (fmt(ids), len(ids) - len(set(ids)), fmt(wrong))


every = fmt(alpha_ids | other_ids)
for label, panes in (
    ("sync", TmuxMonitor(session="alpha", multi_session=True,
                         exclude_pane="").discover_panes()),
    ("async", asyncio.run(TmuxMonitor(session="alpha", multi_session=True,
                                      exclude_pane="").discover_panes_async())),
):
    ids, dupes, wrong = attribution(panes)
    check(f"monitor multi {label}: every pane discovered", every, ids)
    check(f"monitor multi {label}: no pane listed twice", 0, dupes)
    check(f"monitor multi {label}: no pane under the wrong session", "", wrong)
PYEOF
)" || { echo "FAIL: python checks crashed"; echo "$checks"; assert_record_fail; }

n_checks=0
while IFS='|' read -r tag name expected actual; do
    [ "$tag" = "CHECK" ] || continue
    n_checks=$((n_checks + 1))
    assert_eq "$name" "$expected" "$actual"
done <<<"$checks"
# Guards against a Python side that printed nothing (e.g. an import error that
# still exited 0): the fix assertions must actually have run.
assert_eq "python side reported every check" "20" "$n_checks"

# --- Phase A.3: the collision was live the whole time -----------------------
assert_eq "re-check: bare =alpha still lists session other's panes" \
    "other " "$(bare_session_of alpha)"

# --- Phase B: no collision → the bare form is right (trigger isolation) -----
priv_tmux new-session -d -s beta -n main -c "$TMPROOT/pa" 'sleep 600'
priv_tmux new-session -d -s other2 -n unrelated -c "$TMPROOT/pb" 'sleep 600'
assert_eq "isolation: without a colliding window, bare =beta lists beta" \
    "beta " "$(bare_session_of beta)"

# --- Phase C: a claimed session keeps its root when one pane wanders (t1922) --
# Discovery used to take the FIRST pane that walked up to a project, so one pane
# that `cd`'d into another repo re-rooted the whole session once it was listed
# first. A session claimed by the bootstrap carries @aitask_project_root, which
# discovery treats as authoritative. Real shells, real `cd`, real
# pane_current_path — the fakes in test_session_root_resolution.py cannot vouch
# for what tmux reports after a cd.
BOOT="$PROJECT_DIR/.aitask-scripts/lib/tmux_bootstrap.sh"
priv_claim() {   # priv_claim <root> <session> -> prints the claim's exit code
    local rc=0
    (cd "$PROJECT_DIR" && env -u TMUX -u TMUX_PANE TMUX_TMPDIR="$TMX" \
        AITASKS_TMUX_SOCKET="$SOCK" AITASKS_PROJECTS_INDEX="$TMPROOT/index.yaml" \
        bash -c 'source "$1"; _tmux_bootstrap_set_project_registry "$2" "$3"' \
        _ "$BOOT" "$1" "$2" >/dev/null 2>&1) || rc=$?
    echo "$rc"
}
wander_pane="$(priv_tmux new-session -d -P -F '#{pane_id}' -s gamma -n main \
    -c "$TMPROOT/pa" 'bash --norc --noprofile')"
second_pane="$(priv_tmux split-window -d -P -F '#{pane_id}' -t '=gamma:main' \
    -c "$TMPROOT/pa" 'bash --norc --noprofile')"
assert_eq "wander: A claims its session" "0" "$(priv_claim "$TMPROOT/pa" gamma)"

priv_tmux send-keys -t "$wander_pane" "cd '$TMPROOT/pb'" Enter
want_pb="$(cd "$TMPROOT/pb" && pwd -P)"
for _ in $(seq 1 50); do
    [ "$(priv_tmux display-message -p -t "$wander_pane" '#{pane_current_path}')" = "$want_pb" ] && break
    sleep 0.1
done
assert_eq "wander: the first pane really moved into project B" \
    "$want_pb" "$(priv_tmux display-message -p -t "$wander_pane" '#{pane_current_path}')"

gamma_roots() {
    (cd "$PROJECT_DIR" && env -u TMUX -u TMUX_PANE \
        TMUX_TMPDIR="$TMX" AITASKS_TMUX_SOCKET="$SOCK" \
        "$PYTHON" - <<'PYEOF'
import asyncio
import sys
sys.path.insert(0, ".aitask-scripts/lib")
import agent_launch_utils as alu

def root(sessions):
    return [str(s.project_root.resolve()) for s in sessions if s.session == "gamma"]

print("sync", *root(alu.discover_aitasks_sessions()))
print("async", *root(asyncio.run(alu.discover_aitasks_sessions_async())))
checked, complete = alu.discover_aitasks_sessions_checked()
print("checked", *root(checked), complete)
PYEOF
    )
}
assert_gamma_on_a() {   # assert_gamma_on_a <label>
    local out want_pa
    out="$(gamma_roots)"
    want_pa="$(cd "$TMPROOT/pa" && pwd -P)"
    assert_eq "$1: sync discovery keeps gamma on A" "sync $want_pa" \
        "$(grep '^sync ' <<<"$out")"
    assert_eq "$1: async discovery keeps gamma on A" "async $want_pa" \
        "$(grep '^async ' <<<"$out")"
    assert_eq "$1: checked discovery keeps gamma on A, complete" "checked $want_pa True" \
        "$(grep '^checked ' <<<"$out")"
}
assert_gamma_on_a "wander (first pane in B)"

# Then EVERY pane: no pane vote can still say A — only the stamp can.
priv_tmux send-keys -t "$second_pane" "cd '$TMPROOT/pb'" Enter
for _ in $(seq 1 50); do
    [ "$(priv_tmux display-message -p -t "$second_pane" '#{pane_current_path}')" = "$want_pb" ] && break
    sleep 0.1
done
assert_eq "wander: the second pane moved into project B too" \
    "$want_pb" "$(priv_tmux display-message -p -t "$second_pane" '#{pane_current_path}')"
assert_gamma_on_a "wander (every pane in B)"
assert_eq "wander: B's claim on A's session is refused" "45" \
    "$(priv_claim "$TMPROOT/pb" gamma)"
assert_eq "wander: the stamp still names A" "$TMPROOT/pa" \
    "$(priv_tmux list-sessions -F '#{session_name}	#{@aitask_project_root}' | sed -n 's/^gamma	//p')"

# --- Source guard -------------------------------------------------------------
offenders="$(grep -rnE '"list-panes", "-s", "-t", (tmux_)?session_target\(' \
    "$PROJECT_DIR/.aitask-scripts" --include='*.py' || true)"
assert_eq "no list-panes -s call site uses the bare session target" "" "$offenders"

echo
echo "===================="
echo "Passed: $PASS / $TOTAL"
[[ "$FAIL" -gt 0 ]] && echo "Failed: $FAIL"
echo "===================="
[[ "$FAIL" -eq 0 ]]
