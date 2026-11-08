#!/usr/bin/env bash
# test_tmux_utf8_client_live.sh - every framework tmux client runs as a UTF-8
# client (`tmux -u`), and the Python gateway carries tmux text across every
# boundary without the locale codec (t2236, tmux_gateway.md policy 5).
#
# A tmux client with no UTF-8 locale rewrites every non-printable / non-ASCII
# output byte to `_` — the TAB of `_SESSION_LIST_FORMAT` included, so discovery
# finds nothing — and `-u` alone then exposes Python's locale-codec decoding.
# This test builds a private server holding accented names and paths (and one
# path byte that is not valid UTF-8) and drives discovery, argument round
# trips, the control channel, captured screen text and a native start dir
# through the real gateway, in locale lanes chosen by PROBES, never by
# assumption (Python on macOS uses a UTF-8 fs encoding whatever the locale):
#
#   L0  a UTF-8 locale from `locale -a`          (SKIP-LANE when none)
#   L1  LC_ALL=C                                  (Python UTF-8 mode on)
#   L2  LC_ALL=C PYTHONUTF8=0 PYTHONCOERCECLOCALE=0
#   L3  a single-byte locale from `locale -a`     (SKIP-LANE when none)
#
# Expectations come from the PROBED codec. A fixture name is "limited" when
# the lane's fs codec can encode it but not as UTF-8 (`wïn` under Latin-1):
# policy 5's documented limitation makes such an unstamped session absent from
# discovery and untargetable. Under UTF-8 and ascii codecs no name is limited.
#
# Pre-fix controls prove each lane triggers what it claims to test:
#   A  blank TMUX_CLIENT_FLAGS: discovery goes wrong wherever a raw `tmux`
#      probe without -u shows mangling in that lane;
#   B  (fs encoding ascii only) the old decoders: `text=True` raises
#      UnicodeDecodeError, and an fsdecode-decoded name through the old
#      strict-UTF-8 control line raises UnicodeEncodeError.
#
# Knobs (test self-checks only), to exercise the macOS-shaped branches on
# Linux: T_FORCE_FS_PROBE=<enc> overrides the L2 fs probe; T_FORCE_NO_RAWB=1
# behaves as if the filesystem rejected a non-UTF-8 file name (APFS).
#
# Run: bash tests/test_tmux_utf8_client_live.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# shellcheck source=lib/asserts.sh
. "$PROJECT_DIR/tests/lib/asserts.sh"
# File-local counters (asserts.sh mutates them). Every assert runs in THIS
# shell — the lane loop reads a here-string, never a pipe — so no file-backed
# counters are needed; an unset FAIL would make the footer guard pass.
PASS=0
FAIL=0
TOTAL=0
# Start from an empty read-only dir, never the invoking one (t1826).
# shellcheck source=lib/scratch_cwd.sh
. "$PROJECT_DIR/tests/lib/scratch_cwd.sh"
enter_scratch_cwd

if ! command -v tmux >/dev/null 2>&1; then
    echo "SKIP: tmux not installed"
    exit 0
fi

PYTHON="${PYTHON:-python3}"
[ -x "$HOME/.aitask/venv/bin/python" ] && PYTHON="$HOME/.aitask/venv/bin/python"

TMPROOT="$(mktemp -d /tmp/ait_u8r_XXXXXX)"
# Short TMUX_TMPDIR: the socket path has a ~104-byte limit.
TMX="$(mktemp -d /tmp/ait_u8t_XXXXXX)"
SOCK="u8_$$"
# Fixture setup always passes -u, so it is independent of the lane under test.
priv_tmux() { env -u TMUX -u TMUX_PANE TMUX_TMPDIR="$TMX" tmux -u -L "$SOCK" "$@"; }
cleanup() { priv_tmux kill-server >/dev/null 2>&1 || true; rm -rf "$TMX" "$TMPROOT"; }
trap cleanup EXIT

# --- fixture ------------------------------------------------------------------
# Byte-exact names, built with printf so no step depends on a locale.
PROJ="$TMPROOT/$(printf 'pr\303\263j')"          # prój
RAWB="$TMPROOT/$(printf 'b\377d')"               # not valid UTF-8
PLAIN="$TMPROOT/plain"
N_WIN="$(printf 'w\303\257n')"                   # wïn
N_EUR="$(printf '\342\202\254wn')"               # €wn
mkdir -p "$PROJ/aitasks/metadata"
: > "$PROJ/aitasks/metadata/project_config.yaml"
# Probe: can this filesystem hold a name that is not valid UTF-8? APFS (macOS)
# rejects one outright. Where it cannot, only the `rawb` session and its
# dependent expectations are dropped; invalid-byte CODEC coverage stays in the
# unit table (tests/test_tmux_exec.py), which needs no filesystem.
HAVE_RAWB=0
if [ -z "${T_FORCE_NO_RAWB:-}" ] && mkdir -p "$RAWB/aitasks/metadata" 2>/dev/null \
        && : > "$RAWB/aitasks/metadata/project_config.yaml" 2>/dev/null; then
    HAVE_RAWB=1
else
    echo "SKIP-PART: rawb (this filesystem rejects a non-UTF-8 file name)"
fi
mkdir -p "$PLAIN"
# A valid concern block (the parser's real fences) whose text holds `prój`.
CONCERN_FILE="$TMPROOT/concern.txt"
printf '%s\n' "===AITASK-CONCERNS===" \
    "- [high | $(printf 'pr\303\263j') check] The path $(printf 'pr\303\263j') must stay readable." \
    "===END-CONCERNS===" > "$CONCERN_FILE"

# -f /dev/null keeps the developer's tmux.conf out of the fixture.
priv_tmux -f /dev/null new-session -d -s stamped -n main -c "$PROJ" 'sleep 600'
# `=<s>:`: set-option's -t is pane-typed (tmux_gateway.md, Target formatting).
priv_tmux set-option -t '=stamped:' @aitask_project_root "$PROJ"
priv_tmux new-window -d -t '=stamped:' -n concern -c "$PLAIN" "cat '$CONCERN_FILE'; sleep 600"
priv_tmux new-session -d -s voted -n main -c "$PROJ" 'sleep 600'
priv_tmux new-session -d -s legacy -n main -c "$PLAIN" 'sleep 600'
priv_tmux set-environment -g AITASKS_PROJECT_legacy "$PROJ"
priv_tmux new-session -d -s "$N_WIN" -n main -c "$PROJ" 'sleep 600'
priv_tmux new-session -d -s "$N_EUR" -n main -c "$PROJ" 'sleep 600'
if [ "$HAVE_RAWB" = 1 ]; then
    priv_tmux new-session -d -s rawb -n main -c "$RAWB" 'sleep 600'
    priv_tmux set-option -t '=rawb:' @aitask_project_root "$RAWB"
fi
sleep 0.3   # let `cat` draw the concern block before any capture

hex() { printf '%s' "$1" | od -An -v -tx1 | tr -d ' \n'; }

# --- shell side: no locale at all (the shell exposure) ------------------------
# The TAB separator is a REAL byte ($'\t'): tmux keeps a single-quoted `\t`
# literally, which would test nothing.
sh_fmt="#{session_name}"$'\t'"#{@aitask_project_root}"
sh_run() {
    env -i PATH="$PATH" HOME="$HOME" TMUX_TMPDIR="$TMX" AITASKS_TMUX_SOCKET="$SOCK" \
        bash -c 'source "$1/.aitask-scripts/lib/tmux_exec.sh"; shift; eval "$1"; shift; ait_tmux "$@"' \
        _ "$PROJECT_DIR" "$1" list-sessions -F "$sh_fmt"
}
sh_out="$(sh_run ':')"
sh_rows="$(printf '%s\n' "$sh_out" | grep -c . || true)"
sh_tab_rows="$(printf '%s\n' "$sh_out" | grep -c $'\t' || true)"
assert_eq "shell, no locale: every row keeps its TAB byte" "$sh_rows" "$sh_tab_rows"
assert_eq "shell, no locale: one row per session" "$((5 + HAVE_RAWB))" "$sh_rows"
assert_contains "shell, no locale: the stamped root's bytes survive" \
    "$(hex "stamped"$'\t'"$PROJ")" "$(printf '%s\n' "$sh_out" | od -An -v -tx1 | tr -d ' \n')"
assert_contains "shell, no locale: a non-ASCII session name survives" \
    "$(hex "$N_WIN"$'\t')" "$(printf '%s\n' "$sh_out" | od -An -v -tx1 | tr -d ' \n')"
ctl_out="$(sh_run 'AIT_TMUX_CLIENT_FLAGS=()')"
assert_eq "shell control (no -u): the TAB is gone from every row" "0" \
    "$(printf '%s\n' "$ctl_out" | grep -c $'\t' || true)"
assert_contains "shell control (no -u): rewritten to _" "stamped_" "$ctl_out"
assert_eq "shell: ait_tmux_client_args emits -u then the socket flag" "-u|-L|$SOCK" \
    "$(env -i PATH="$PATH" HOME="$HOME" AITASKS_TMUX_SOCKET="$SOCK" bash -c \
        'source "$1/.aitask-scripts/lib/tmux_exec.sh"; ait_tmux_client_args | paste -sd"|" -' _ "$PROJECT_DIR")"

# --- python side: probe-selected lanes ----------------------------------------
pick_locale() {  # first locale -a entry matching an ERE, case-insensitive
    locale -a 2>/dev/null | grep -iE "$1" | head -n1 || true
}
UTF8_LOC=""
for want in '^C\.UTF-?8$' '^en_US\.UTF-?8$'; do
    UTF8_LOC="$(pick_locale "$want")"
    [ -n "$UTF8_LOC" ] && break
done
LATIN_LOC="$(pick_locale '(iso-?8859-?1|iso88591)$')"

BASE_ENV=(env -u TMUX -u TMUX_PANE -u LANG -u LC_CTYPE -u LC_ALL
          -u PYTHONUTF8 -u PYTHONCOERCECLOCALE -u PYTHONIOENCODING
          TMUX_TMPDIR="$TMX" AITASKS_TMUX_SOCKET="$SOCK")

# The checks the script emits in every lane, plus the ascii-only controls. The
# script's count is compared with these, never self-reported.
# 4 argument-round-trip checks per fixture name: 6 names, or 5 without rawb.
GENERIC_CHECKS=$((35 + 4 * HAVE_RAWB))
ASCII_CHECKS=2

SIGS=""
run_lane() {
    local label="$1"; shift
    local -a lane=("$@")
    # Probe 1: the lane's actual Python fs encoding (bare python, no gateway).
    # NOT `-I` / `-E`: both ignore PYTHONUTF8 / PYTHONCOERCECLOCALE, which are
    # exactly what the L2 lane sets. The cwd is the empty scratch dir.
    local fs
    fs="$("${BASE_ENV[@]}" "${lane[@]}" "$PYTHON" -c \
        'import sys; print(sys.getfilesystemencoding())')"
    if [ "$label" = "L2" ] && [ -n "${T_FORCE_FS_PROBE:-}" ]; then
        fs="$T_FORCE_FS_PROBE"
    fi
    local is_ascii=0
    case "$fs" in ascii|ANSI_X3.4-1968|us-ascii) is_ascii=1 ;; esac
    # Probe 2: does a raw tmux client WITHOUT -u mangle the TAB in this lane?
    local raw mangles=0
    raw="$("${BASE_ENV[@]}" "${lane[@]}" tmux -L "$SOCK" list-sessions \
        -F "#{session_name}"$'\t'"#{session_id}" 2>/dev/null || true)"
    printf '%s\n' "$raw" | grep -q $'\t' || mangles=1
    [ "$is_ascii" = 1 ] || echo "LANE-NOTE: $label fs=$fs, ascii checks n/a"

    local out expected=$GENERIC_CHECKS
    [ "$is_ascii" = 1 ] && expected=$((GENERIC_CHECKS + ASCII_CHECKS))
    out="$(cd "$PROJECT_DIR" && "${BASE_ENV[@]}" "${lane[@]}" \
        T_PROJ="$(hex "$PROJ")" T_PLAIN="$(hex "$PLAIN")" \
        T_RAWB="$([ "$HAVE_RAWB" = 1 ] && hex "$RAWB")" \
        T_WIN="$(hex "$N_WIN")" T_EUR="$(hex "$N_EUR")" \
        T_ASCII="$is_ascii" T_MANGLES="$mangles" T_FS="$fs" \
        PYTHONIOENCODING="ascii:backslashreplace" \
        "$PYTHON" - <<'PYEOF'
import asyncio
import os
import subprocess
import sys

sys.path.insert(0, ".aitask-scripts/lib")
sys.path.insert(0, ".aitask-scripts")

import tmux_exec  # noqa: E402
from agent_launch_utils import (  # noqa: E402
    _SESSION_LIST_FORMAT,
    discover_aitasks_sessions,
    discover_aitasks_sessions_async,
    discover_aitasks_sessions_checked,
)
from monitor import monitor_core  # noqa: E402
from monitor.concern_parser import concern_block_signature  # noqa: E402
from monitor.monitor_core import TmuxControlClient, TmuxMonitor  # noqa: E402
from tmux_exec import TmuxClient, session_scope_target, session_target  # noqa: E402

U8 = ("utf-8", "surrogateescape")
B = {k: bytes.fromhex(os.environ["T_" + k]) for k in ("PROJ", "RAWB", "PLAIN", "WIN", "EUR")}
HAVE_RAWB = bool(B["RAWB"])  # empty: the filesystem rejected the name
ASCII = os.environ["T_ASCII"] == "1"
MANGLES = os.environ["T_MANGLES"] == "1"


def check(name, expected, actual):
    print(f"CHECK|{name}|{expected!a}|{actual!a}")


# Fixture name bytes -> the cwd bytes each session's panes hold.
NAMES = {b"stamped": B["PROJ"], b"voted": B["PROJ"], b"legacy": B["PLAIN"],
         B["WIN"]: B["PROJ"], B["EUR"]: B["PROJ"], b"rawb": B["RAWB"]}
ROOTS = {b"stamped": B["PROJ"], b"voted": B["PROJ"], b"legacy": B["PROJ"],
         B["WIN"]: B["PROJ"], B["EUR"]: B["PROJ"], b"rawb": B["RAWB"]}
STAMPED = {b"stamped", b"rawb"}
if not HAVE_RAWB:
    del NAMES[b"rawb"], ROOTS[b"rawb"]


def limited(name: bytes) -> bool:
    """The policy-5 oracle, from Python's own fs codec (never the gateway)."""
    text = name.decode("utf-8")
    try:
        native = os.fsencode(text)
    except UnicodeEncodeError:
        return False
    return native != name


EXPECTED = sorted(n for n in NAMES if n in STAMPED or not limited(n))
client = TmuxClient()


def name_bytes(s):
    return s.session.encode(*U8)


def found(sessions):
    return sorted(name_bytes(s) for s in sessions)


def root_problems(sessions):
    bad = []
    for s in sessions:
        n = name_bytes(s)
        if os.fsencode(s.project_root) != ROOTS.get(n) or not s.project_root.is_dir():
            bad.append(n)
    return sorted(bad)


# --- discovery ---------------------------------------------------------------
sync = discover_aitasks_sessions()
asyn = asyncio.run(discover_aitasks_sessions_async())
checked, complete = discover_aitasks_sessions_checked()
check("discovery sync: expected set", EXPECTED, found(sync))
check("discovery async: expected set", EXPECTED, found(asyn))
check("discovery checked: expected set", EXPECTED, found(checked))
check("discovery checked: complete", True, complete)
check("discovery sync: roots byte-exact and is_dir", [], root_problems(sync))
check("discovery async: roots byte-exact and is_dir", [], root_problems(asyn))

# --- argument round trip, every name read back from list-sessions ------------
rc, out = client.run(["list-sessions", "-F", "#{session_name}"])
readback = {n.encode(*U8): n for n in out.splitlines() if n}
for nb, cwd in sorted(NAMES.items()):
    name = readback.get(nb, nb.decode(*U8))
    ok = not limited(nb)
    label = nb.decode("utf-8", "backslashreplace")
    rc, _ = client.run(["has-session", "-t", session_target(name)])
    check(f"run has-session {label}", ok, rc == 0)
    res = client.run_checked(["list-panes", "-t", session_scope_target(name),
                              "-F", "#{pane_current_path}"])
    check(f"run_checked list-panes {label}", ok, res.outcome == "ok")
    got = res.stdout.splitlines()[0].encode(*U8) if res.outcome == "ok" else None
    check(f"run_checked pane path bytes {label}", cwd if ok else None, got)
    rc, aout = asyncio.run(client.run_async(
        ["list-panes", "-t", session_scope_target(name), "-F", "#{pane_current_path}"]))
    agot = aout.splitlines()[0].encode(*U8) if rc == 0 and aout else None
    check(f"run_async pane path bytes {label}", cwd if ok else None, agot)


# --- control channel ----------------------------------------------------------
async def control(name):
    c = TmuxControlClient(session=name)
    try:
        if not await c.start():
            return "nostart"
        rc, got = await c.request(["display-message", "-p", "-t",
                                   session_scope_target(name), "#{session_name}"])
        return f"ok:{got.strip()}" if rc == 0 else f"rc:{rc}"
    finally:
        await c.close()

for nb in (B["WIN"], B["EUR"]):
    name = nb.decode(*U8)
    want = "nostart" if limited(nb) else f"ok:{name}"
    check(f"control attach + request {nb.decode('utf-8', 'backslashreplace')}",
          want, asyncio.run(control(name)))


async def control_set_option():
    # The reviewer's shape: a target the codec may not represent beside a
    # native OS-path value, in ONE control command (attach to an ASCII session).
    c = TmuxControlClient(session="stamped")
    try:
        assert await c.start()
        return await c.request(["set-option", "-t", session_scope_target(B["EUR"].decode(*U8)),
                                "@aitask_t2236_probe", os.fsdecode(B["PROJ"])])
    finally:
        await c.close()

crc, _ = asyncio.run(control_set_option())
rc, val = client.run(["show-options", "-t", session_scope_target(B["EUR"].decode(*U8)),
                      "-v", "@aitask_t2236_probe"])
check("control set-option: native path bytes stored",
      B["PROJ"], val.rstrip("\n").encode(*U8) if crc == 0 and rc == 0 else (crc, rc))

# --- captured screen text -----------------------------------------------------
rc, panes = client.run(["list-panes", "-t", "=stamped:concern", "-F", "#{pane_id}"])
pane = panes.split()[0]
rc, cap = client.run(["capture-pane", "-p", "-t", pane])
check("capture-pane: accented text readable", True, "prój check" in cap)
sig = concern_block_signature(cap)
check("concern signature over the capture is not None", True, sig is not None)
mon = TmuxMonitor(session="stamped", all_sessions=False)
mon.discover_panes()
snap = mon.capture_pane(pane)
check("monitor capture path: same signature", sig,
      concern_block_signature(snap.content) if snap else "no-snapshot")
print(f"SIG|{sig}")

# --- separator ----------------------------------------------------------------
rc, out = client.run(["list-sessions", "-F", _SESSION_LIST_FORMAT])
check("list-sessions: exactly one real TAB per row", 0,
      sum(1 for line in out.splitlines() if line.count("\t") != 1))

# --- native start dir (OS-path argument keeps its native bytes) ---------------
argv = client.new_session_argv("nat", "w", "sleep 600",
                               cwd_args=["-c", os.fsdecode(B["PROJ"])])
subprocess.Popen(tmux_exec.encode_tmux_argv(argv), env=client.spawn_env()).wait()
rc, out = client.run(["list-panes", "-t", "=nat:", "-F", "#{pane_current_path}"])
check("native start dir: pane cwd byte-exact", B["PROJ"],
      out.splitlines()[0].encode(*U8) if rc == 0 and out else None)
client.run(["kill-session", "-t", "=nat"])

# --- control A: the -u flag ---------------------------------------------------
tmux_exec.TMUX_CLIENT_FLAGS = ()
try:
    bare = found(discover_aitasks_sessions())
finally:
    tmux_exec.TMUX_CLIENT_FLAGS = ("-u",)
check("control A (no -u): discovery wrong exactly where tmux mangles",
      "wrong" if MANGLES else "right", "right" if bare == EXPECTED else "wrong")

# --- control B: the old decoders (fs encoding ascii only) ---------------------
if ASCII:
    real_kwargs, real_argv = tmux_exec.tmux_text_kwargs, tmux_exec.encode_tmux_argv
    tmux_exec.tmux_text_kwargs = lambda: {"text": True}
    tmux_exec.encode_tmux_argv = lambda argv: list(argv)
    try:
        discover_aitasks_sessions()
        b1 = "no error"
    except UnicodeDecodeError:
        b1 = "UnicodeDecodeError"
    finally:
        tmux_exec.tmux_text_kwargs, tmux_exec.encode_tmux_argv = real_kwargs, real_argv
    check("control B: text=True decoding raises", "UnicodeDecodeError", b1)

    real_line = monitor_core._control_line
    monitor_core._control_line = lambda args: (
        " ".join(monitor_core._quote_arg(a) for a in args) + "\n").encode("utf-8")
    try:
        asyncio.run(control(os.fsdecode(B["EUR"])))
        b2 = "no error"
    except UnicodeEncodeError:
        b2 = "UnicodeEncodeError"
    finally:
        monitor_core._control_line = real_line
    check("control B: fsdecode name + strict control line raises", "UnicodeEncodeError", b2)
PYEOF
)" || { echo "FAIL: $label python side crashed"; echo "$out"; assert_record_fail; return 0; }

    local n=0 tag name exp act
    while IFS='|' read -r tag name exp act; do
        case "$tag" in
            CHECK) n=$((n + 1)); assert_eq "$label: $name" "$exp" "$act" ;;
            SIG) SIGS="$SIGS $name" ;;
        esac
    done <<<"$out"
    assert_eq "$label: python side reported every check (fs=$fs, mangles=$mangles)" \
        "$expected" "$n"
}

if [ -n "$UTF8_LOC" ]; then run_lane L0 LC_ALL="$UTF8_LOC"; else echo "SKIP-LANE: L0 (no UTF-8 locale in locale -a)"; fi
run_lane L1 LC_ALL=C
run_lane L2 LC_ALL=C PYTHONUTF8=0 PYTHONCOERCECLOCALE=0
if [ -n "$LATIN_LOC" ]; then run_lane L3 LC_ALL="$LATIN_LOC" PYTHONUTF8=0; else echo "SKIP-LANE: L3 (no single-byte locale in locale -a)"; fi

# The captured block hashes identically in every lane that ran.
uniq_sigs="$(printf '%s\n' $SIGS | sort -u | grep -c . || true)"
assert_eq "concern signature identical across lanes" "1" "$uniq_sigs"
assert_not_contains "concern signature present in every lane" "None" "$SIGS"

echo ""
echo "Results: $PASS passed, $FAIL failed, $TOTAL total"
[[ "$FAIL" -eq 0 ]]
