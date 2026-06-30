#!/usr/bin/env python3
"""aitask_shadow_spawn_learner.py - Spawn a learner agent from the shadow (t1071_5).

On user request while shadowing, the advisory-only shadow agent spawns a
*dedicated* learner — `/aitask-learn-skill <followed_pane_id>` — in a NEW tmux
window, WITHOUT running the learn itself (a learn run would occupy the shadow,
and its mandate is read-only). The learn skill (t1071_2) already captures the
followed pane read-only and does the analysis/generation, so this glue reduces
to "resolve the learn command and open a window for it".

Reuses the SAME centralized launcher minimonitor's ``action_launch_shadow`` and
tui_switcher's ``action_shortcut_explore`` use — ``resolve_dry_run_command`` +
``launch_in_tmux`` (via ``TmuxLaunchConfig``) — so cwd handling, exact-match
session targeting, pane-pid capture, and any future launcher defaults are
inherited rather than forked into a bash reimplementation.

The learner is a **first-class, user-managed agent**: it is launched in an
``agent-learn-*`` window so it shows in ``ait monitor`` like any other agent,
carries NO ``@aitask_shadow_target`` classifier, and has NO pane-died cleanup
hook (it is not a shadow companion). The user closes its window when done.

Usage:
    aitask_shadow_spawn_learner.py [--dry-run] <followed_pane_id> [<source_task_id>]

    <followed_pane_id>  tmux pane id (e.g. %5) of the followed agent — captured
                        read-only by the spawned learner.
    <source_task_id>    optional; only used to label the learner window
                        (agent-learn-<task_id>).
    --dry-run           Resolve and print the learn command WITHOUT touching tmux
                        (no session lookup, no spawn). The test/no-live-tmux seam.

Output (one structured line):
    DRY_RUN_SPAWN: window=<base> cmd=<resolved command>   (--dry-run)
    LEARNER_SPAWNED:<pane_id> WINDOW:<window>              (live success)
    SPAWN_FAILED:<reason>                                  (live or resolve error)
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR / "lib"))

from agent_launch_utils import (  # noqa: E402
    TmuxLaunchConfig,
    get_tmux_windows,
    launch_in_tmux,
    pane_session,
    resolve_dry_run_command,
    resolve_pane_id_by_pid,
    unique_window_name,
)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="aitask_shadow_spawn_learner.py",
        description="Spawn a learner agent (/aitask-learn-skill) from the shadow.",
    )
    parser.add_argument("--dry-run", action="store_true",
                        help="Resolve the command without touching tmux.")
    parser.add_argument("followed_pane_id",
                        help="tmux pane id of the followed agent (e.g. %%5).")
    parser.add_argument("source_task_id", nargs="?", default=None,
                        help="Optional task id, used only to label the window.")
    args = parser.parse_args(argv)

    followed_pane = args.followed_pane_id.strip()
    if not followed_pane:
        print("SPAWN_FAILED:empty_pane_id")
        return 2

    # Repo root = parent of .aitask-scripts. resolve_dry_run_command shells
    # `aitask_codeagent.sh --dry-run invoke learn <pane>` — no live tmux needed.
    project_root = SCRIPT_DIR.parent
    cmd = resolve_dry_run_command(project_root, "learn", followed_pane)
    if not cmd:
        print("SPAWN_FAILED:resolve")
        return 1

    task_id = (args.source_task_id or "").strip()
    base = f"agent-learn-{task_id}" if task_id else "agent-learn"

    if args.dry_run:
        # No-tmux seam: prove command resolution independently of live session
        # targeting (works even when <followed_pane_id> does not exist).
        print(f"DRY_RUN_SPAWN: window={base} cmd={cmd}")
        return 0

    sess = pane_session(followed_pane)
    if not sess:
        print("SPAWN_FAILED:no_session")
        return 1

    existing = {name for _idx, name in get_tmux_windows(sess)}
    window = unique_window_name(existing, base)

    cfg = TmuxLaunchConfig(
        session=sess,
        window=window,
        new_session=False,
        new_window=True,
        cwd=str(project_root),
    )
    pane_pid, err = launch_in_tmux(cmd, cfg)
    if err:
        print(f"SPAWN_FAILED:{err}")
        return 1

    pane_id = resolve_pane_id_by_pid(sess, pane_pid) if pane_pid else None
    print(f"LEARNER_SPAWNED:{pane_id or '?'} WINDOW:{window}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
