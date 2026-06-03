#!/usr/bin/env bash
# test_tui_switcher_brainstorm_session.sh — Regression for t814: the TUI
# switcher must attribute on-disk brainstorm sessions to the SELECTED tmux
# session's project, not to whichever project the attached session's process
# happens to run from.
#
# Covers:
#   * _discover_brainstorm_sessions(project_root): scans the passed project's
#     .aitask-crews/ — two distinct project roots yield distinct results.
#   * crew-brainstorm-* dirs without br_session.yaml are ignored.
#   * No-arg call falls back to Path.cwd() (legacy / single-session callers).
#   * Missing .aitask-crews/ dir returns [].
#   * _populate_list_for(session) passes the SELECTED session's project_root
#     to _discover_brainstorm_sessions (the end-to-end fix for both bugs:
#     brainstorms appearing under the wrong session and missing under the
#     right one).
#
# Run: bash tests/test_tui_switcher_brainstorm_session.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# Shared assertion helpers (see tests/lib/asserts.sh).
# shellcheck source=lib/asserts.sh
. "$PROJECT_DIR/tests/lib/asserts.sh"
LIB_DIR="$PROJECT_DIR/.aitask-scripts/lib"

# shellcheck source=lib/venv_python.sh
. "$SCRIPT_DIR/lib/venv_python.sh"

# Logic-only test: no tmux, no Textual runtime. Safe to run from anywhere.

PASS=0
FAIL=0
TOTAL=0


out=$(PYTHONPATH="$LIB_DIR" "$AITASK_PYTHON" <<'PY'
import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import tui_switcher as ts
from agent_launch_utils import AitasksSession


def make_crew(root: Path, task_num: str, with_session_file: bool = True) -> None:
    """Create root/.aitask-crews/crew-brainstorm-<task_num>/ for the test."""
    d = root / ".aitask-crews" / f"crew-brainstorm-{task_num}"
    d.mkdir(parents=True, exist_ok=True)
    if with_session_file:
        (d / "br_session.yaml").write_text(f"task: {task_num}\n")


with tempfile.TemporaryDirectory() as tmp:
    proot_a = Path(tmp) / "proj_a"
    proot_b = Path(tmp) / "proj_b"
    proot_a.mkdir()
    proot_b.mkdir()
    make_crew(proot_a, "100")
    make_crew(proot_a, "101")
    make_crew(proot_b, "200")
    # crew dir with no br_session.yaml — must be skipped
    make_crew(proot_b, "299", with_session_file=False)

    # --- per-project scan: result follows the passed project_root ---
    print("DISC_A:" + ",".join(ts._discover_brainstorm_sessions(proot_a)))
    print("DISC_B:" + ",".join(ts._discover_brainstorm_sessions(proot_b)))

    # --- no-arg call falls back to cwd (legacy / single-session regression) ---
    old_cwd = os.getcwd()
    try:
        os.chdir(proot_a)
        print("DISC_CWD:" + ",".join(ts._discover_brainstorm_sessions()))
    finally:
        os.chdir(old_cwd)

    # --- missing .aitask-crews/ dir → [] ---
    print("DISC_MISSING:" + ",".join(
        ts._discover_brainstorm_sessions(Path(tmp) / "no_such_project")))

    # --- _populate_list_for passes the SELECTED session's project_root ---
    ov = ts.TuiSwitcherOverlay(session="s1", current_tui="")
    ov._session = "s2"            # browsed away to s2
    ov._attached_session = "s1"   # client is still attached to s1
    ov._all_sessions = [
        AitasksSession("s1", proot_a, "proj_a"),
        AitasksSession("s2", proot_b, "proj_b"),
    ]
    ov.query_one = MagicMock(return_value=MagicMock())
    with patch("tui_switcher.get_tmux_windows", return_value=[]), \
         patch("tui_switcher._build_tui_list", return_value=[]), \
         patch("tui_switcher._GroupHeader", MagicMock()), \
         patch("tui_switcher._discover_brainstorm_sessions",
               return_value=[]) as mock_disc:
        ov._populate_list_for("s2")
    disc_arg = mock_disc.call_args.args[0] if mock_disc.call_args.args else None
    print("POPULATE_DISC_CALLS:" + str(mock_disc.call_count))
    print("POPULATE_DISC_MATCH:" + str(disc_arg == proot_b))
PY
)

mapfile -t lines <<<"$out"

declare -A R
for line in "${lines[@]}"; do
    key="${line%%:*}"
    val="${line#*:}"
    R["$key"]="$val"
done

assert_eq "scan of project A returns A's brainstorm task nums" \
    "100,101" "${R[DISC_A]:-}"
assert_eq "scan of project B returns B's brainstorm task nums (299 skipped — no br_session.yaml)" \
    "200" "${R[DISC_B]:-}"
assert_eq "no-arg call falls back to cwd (legacy regression)" \
    "100,101" "${R[DISC_CWD]:-}"
assert_eq "missing .aitask-crews/ dir returns empty list" \
    "" "${R[DISC_MISSING]:-}"
assert_eq "_populate_list_for calls _discover_brainstorm_sessions once" \
    "1" "${R[POPULATE_DISC_CALLS]:-}"
assert_eq "_populate_list_for passes the SELECTED session's project_root" \
    "True" "${R[POPULATE_DISC_MATCH]:-}"

echo ""
echo "===================="
echo "Passed: $PASS / $TOTAL"
[[ $FAIL -gt 0 ]] && echo "Failed: $FAIL"
if [[ $FAIL -gt 0 ]]; then
    exit 1
else
    exit 0
fi
