#!/usr/bin/env bash
# test_no_raw_tmux.sh — anti-regression guard for the t952 tmux-centralization.
#
# After t952_1..t952_5, the ONLY sanctioned places that spawn a raw `tmux`
# process are the two gateways (`lib/tmux_exec.py` / `lib/tmux_exec.sh`) plus a
# small, documented allowlist. This test greps `.aitask-scripts/` for raw tmux
# spawns and FAILS if any NON-allowlisted file issues one — blocking new raw
# calls from creeping back in and bypassing the gateway's socket policy.
#
# It is a FREEZE, not a migration: existing sanctioned raw sites are allowlisted
# (with a per-entry reason), not rewritten.
#
# Detection scope (documented on purpose — a guard that overclaims is worse than
# one with a known boundary):
#   * Python — a `"tmux"`/`'tmux'` element at the head of an argv list literal
#     (`[... "tmux" ...]`) or an asyncio `create_subprocess_exec("tmux", …)`.
#     Gateway-routed calls (`_TMUX.run(["list-sessions", …])`) carry no "tmux"
#     argv literal and are therefore invisible to the guard by construction.
#   * Shell — a command-position `tmux` followed by a flag (`-L`) or a
#     hyphenated subcommand (`new-session`, `kill-pane`, `has-session`, …). The
#     `ait_tmux` gateway helper is skipped automatically (its `tmux` is preceded
#     by `_`). Prose like "tmux is not installed" / "tmux session" does not match.
#   * NOT scanned: `tests/` (fixtures legitimately construct raw tmux argv) and
#     non-hyphenated bare verbs (`tmux attach`) — none exist in the tree today.
#
# Run: bash tests/test_no_raw_tmux.sh
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# shellcheck source=lib/asserts.sh
. "$PROJECT_DIR/tests/lib/asserts.sh"

PASS=0
FAIL=0
TOTAL=0

# --- Allowlist -------------------------------------------------------------
# Repo-relative paths sanctioned to issue a raw tmux call, each with its reason.
# Layer A = tmux-as-backend (must reach the gateway socket eventually);
# B/ambient = a `$TMUX` self-probe of the user's *default* server (NOT the
# aitasks backend socket — routing it through the dedicated-socket gateway would
# query the wrong server); gateway = the chokepoint itself.
# `TODO(socket-move)` marks Layer-A holdouts a future dedicated-socket task
# should route through the gateway; they are sanctioned for THIS guard.
ALLOWLIST=(
  ".aitask-scripts/lib/tmux_exec.py"               # gateway: THE python chokepoint
  ".aitask-scripts/lib/tmux_exec.sh"               # gateway: THE shell chokepoint
  ".aitask-scripts/monitor/tmux_control.py"        # A: control-mode `tmux -C attach` client
  ".aitask-scripts/monitor/tmux_monitor.py"        # A: raw per-tick fallback helpers
  ".aitask-scripts/aitask_companion_cleanup.sh"    # A: minimal-env cleanup hook, raw by design
  ".aitask-scripts/monitor/monitor_app.py"         # B/ambient _detect probes; TODO(socket-move): rename/has-session
  ".aitask-scripts/monitor/minimonitor_app.py"     # B/ambient _detect probe + self display-message
  ".aitask-scripts/codebrowser/codebrowser_app.py" # B/ambient _detect probes; TODO(socket-move): show/set-environment
  ".aitask-scripts/board/aitask_board.py"          # B/ambient _detect probe; B-nav select-window (local-only)
  ".aitask-scripts/stats/stats_app.py"             # B/ambient _detect probe
)

# Python: argv-list-literal head (a `"tmux"` element FOLLOWED BY A COMMA — i.e.
# more argv elements; this excludes dict subscripts like `data["tmux"]`), or the
# asyncio varargs form `create_subprocess_exec("tmux", …)`.
PY_PATTERN='(\[[[:space:]]*["'\'']tmux["'\''][[:space:]]*,)|(create_subprocess_exec\([[:space:]]*["'\'']tmux["'\''])'
# Shell: a COMMAND-POSITION tmux (line start, or after `;` `|` `&` `(` `` ` ``
# `$(`, or `exec`/`then`/`do`/`else`) followed by a flag (`-L`) or a hyphenated
# verb (`new-session`, `kill-pane`, …). Anchoring to command position keeps
# tmux verbs that appear INSIDE strings (e.g. `echo "tmux new-session failed"`)
# from matching. The `ait_tmux` gateway helper is skipped automatically (its
# `tmux` is preceded by `_`, which is not a command-position lead-in).
SH_PATTERN='(^[[:space:]]*|[;&|(`]|\$\(|exec[[:space:]]+|then[[:space:]]+|do[[:space:]]+|else[[:space:]]+)tmux[[:space:]]+(-[A-Za-z]|[a-z][a-z]*-[a-z])'

is_allowed() {
  local f="$1" a
  for a in "${ALLOWLIST[@]}"; do
    [[ "$f" == "$a" ]] && return 0
  done
  return 1
}

# scan_dir ROOT — emit "<relpath>:<line>:<text>" for each raw-tmux hit in a
# non-allowlisted .py/.sh file under ROOT/.aitask-scripts. Pure-comment shell
# lines are dropped.
scan_dir() {
  local root="$1" f rel
  while IFS= read -r -d '' f; do
    rel="${f#"$root"/}"
    is_allowed "$rel" && continue
    case "$f" in
      *.py)
        grep -nE "$PY_PATTERN" "$f" 2>/dev/null | sed "s|^|$rel:|"
        ;;
      *.sh)
        grep -nE "$SH_PATTERN" "$f" 2>/dev/null \
          | grep -vE '^[0-9]+:[[:space:]]*#' \
          | sed "s|^|$rel:|"
        ;;
    esac
  done < <(find "$root/.aitask-scripts" -type f \( -name '*.py' -o -name '*.sh' \) -print0)
}

# --- Test 1: the real tree is clean ----------------------------------------
violations="$(scan_dir "$PROJECT_DIR")"
TOTAL=$((TOTAL + 1))
if [[ -z "$violations" ]]; then
  PASS=$((PASS + 1))
else
  FAIL=$((FAIL + 1))
  echo "FAIL: raw tmux spawn(s) found outside the gateway/allowlist:"
  printf '  RAW TMUX: %s\n' "$violations"
  echo "  -> route the call through the tmux gateway (lib/tmux_exec.{py,sh}),"
  echo "     or, if genuinely sanctioned, add the file to ALLOWLIST with a reason."
fi

# --- Negative tests: the guard actually catches a regression ---------------
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
mkdir -p "$TMP/.aitask-scripts/lib"

# (2) a raw tmux spawn in a NON-allowlisted python file is flagged.
cat >"$TMP/.aitask-scripts/aitask_rogue.py" <<'PY'
import subprocess
subprocess.run(["tmux", "kill-server"])
PY
neg_py="$(scan_dir "$TMP")"
assert_contains "negative: rogue python raw tmux is flagged" "aitask_rogue.py" "$neg_py"

# (3) the SAME raw call in an allowlisted file is NOT flagged.
cat >"$TMP/.aitask-scripts/lib/tmux_exec.py" <<'PY'
import subprocess
subprocess.run(["tmux", "kill-server"])
PY
neg_allow="$(scan_dir "$TMP")"
assert_not_contains "allowlisted file with raw tmux is not flagged" "tmux_exec.py" "$neg_allow"

# (4) shell: a real command is flagged, but a comment and prose are not.
cat >"$TMP/.aitask-scripts/aitask_rogue.sh" <<'SH'
#!/usr/bin/env bash
# tmux kill-server   <- this comment must NOT trip the guard
echo "tmux is not installed"   # prose must NOT trip the guard
tmux kill-server
ait_tmux new-window             # gateway helper must NOT trip the guard
SH
neg_sh="$(scan_dir "$TMP")"
assert_contains "negative: rogue shell raw tmux is flagged" "aitask_rogue.sh" "$neg_sh"
# Exactly one shell hit (the real `tmux kill-server`), not the comment/prose/helper.
sh_hits="$(printf '%s\n' "$neg_sh" | grep -c 'aitask_rogue.sh')"
assert_eq "shell: only the real command line is flagged (1 hit)" "1" "$sh_hits"

# --- Summary ---------------------------------------------------------------
echo "Results: $PASS passed, $FAIL failed, $TOTAL total"
if [[ $FAIL -eq 0 ]]; then
  echo "ALL TESTS PASSED"
else
  echo "SOME TESTS FAILED"
  exit 1
fi
