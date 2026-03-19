"""Session management for the brainstorm engine.

Sessions live in AgentCrew crew worktrees at
.aitask-crews/crew-brainstorm-<task_num>/. The crew worktree is created by
`ait crew init`; this module adds brainstorm-specific files (br_session.yaml,
br_graph_state.yaml, br_groups.yaml) and subdirectories (br_nodes/,
br_proposals/, br_plans/).
"""

from __future__ import annotations

import os
import shutil
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from agentcrew.agentcrew_utils import AGENTCREW_DIR, read_yaml, write_yaml  # noqa: E402

from .brainstorm_dag import GRAPH_STATE_FILE, NODES_DIR, PLANS_DIR, PROPOSALS_DIR  # noqa: E402

SESSION_FILE = "br_session.yaml"
GROUPS_FILE = "br_groups.yaml"


def crew_worktree(task_num: int | str) -> Path:
    """Return path to .aitask-crews/crew-brainstorm-<task_num>/."""
    return Path(AGENTCREW_DIR) / f"crew-brainstorm-{task_num}"


def init_session(
    task_num: int | str,
    task_file: str,
    user_email: str,
    initial_spec: str,
) -> Path:
    """Initialize brainstorm session files in an existing crew worktree.

    Creates: br_session.yaml, br_graph_state.yaml, br_groups.yaml,
             br_nodes/, br_proposals/, br_plans/ directories.

    Raises FileNotFoundError if the crew worktree does not exist.
    Returns the session (worktree) path.
    """
    wt = crew_worktree(task_num)
    if not wt.is_dir():
        raise FileNotFoundError(
            f"Crew worktree not found: {wt}. "
            f"Run 'ait crew init --id brainstorm-{task_num}' first."
        )

    # Create subdirectories
    for subdir in (NODES_DIR, PROPOSALS_DIR, PLANS_DIR):
        (wt / subdir).mkdir(parents=True, exist_ok=True)

    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    # Write br_session.yaml
    session_data = {
        "task_id": int(task_num) if str(task_num).isdigit() else task_num,
        "task_file": task_file,
        "status": "init",
        "crew_id": f"brainstorm-{task_num}",
        "created_at": now,
        "updated_at": now,
        "created_by": user_email,
        "initial_spec": initial_spec,
        "url_cache": "enabled",
    }
    write_yaml(str(wt / SESSION_FILE), session_data)

    # Write br_graph_state.yaml
    graph_state = {
        "current_head": None,
        "history": [],
        "next_node_id": 0,
        "active_dimensions": [],
    }
    write_yaml(str(wt / GRAPH_STATE_FILE), graph_state)

    # Write empty br_groups.yaml
    write_yaml(str(wt / GROUPS_FILE), {"groups": {}})

    return wt


def load_session(task_num: int | str) -> dict:
    """Load and return br_session.yaml as dict."""
    wt = crew_worktree(task_num)
    return read_yaml(str(wt / SESSION_FILE))


def save_session(task_num: int | str, updates: dict) -> None:
    """Update br_session.yaml fields (merge updates, auto-set updated_at)."""
    wt = crew_worktree(task_num)
    path = str(wt / SESSION_FILE)
    data = read_yaml(path)
    data.update(updates)
    data["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    write_yaml(path, data)


def session_exists(task_num: int | str) -> bool:
    """Check if br_session.yaml exists in crew worktree."""
    return (crew_worktree(task_num) / SESSION_FILE).is_file()


def list_sessions() -> list[dict]:
    """List all brainstorm sessions by scanning crew worktrees.

    Returns list of session dicts with task_num added.
    """
    crews_dir = Path(AGENTCREW_DIR)
    if not crews_dir.is_dir():
        return []

    sessions = []
    prefix = "crew-brainstorm-"
    for entry in sorted(crews_dir.iterdir()):
        if not entry.is_dir() or not entry.name.startswith(prefix):
            continue
        session_file = entry / SESSION_FILE
        if not session_file.is_file():
            continue
        data = read_yaml(str(session_file))
        data["task_num"] = entry.name[len(prefix):]
        sessions.append(data)

    return sessions


def finalize_session(task_num: int | str, plan_dest_dir: str = "aiplans") -> str:
    """Copy HEAD node's plan to aiplans/. Mark session completed.

    Returns the destination path of the copied plan file.
    Raises ValueError if HEAD has no plan.
    """
    from .brainstorm_dag import get_head, read_node

    wt = crew_worktree(task_num)

    head = get_head(wt)
    if not head:
        raise ValueError("No HEAD node set — cannot finalize.")

    node_data = read_node(wt, head)
    plan_file = node_data.get("plan_file")
    if not plan_file:
        raise ValueError(f"HEAD node '{head}' has no plan_file.")

    src = wt / plan_file
    if not src.is_file():
        raise FileNotFoundError(f"Plan file not found: {src}")

    dest_dir = Path(plan_dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"p{task_num}_{head}.md"
    shutil.copy2(str(src), str(dest))

    save_session(task_num, {"status": "completed"})

    return str(dest)


def archive_session(task_num: int | str) -> None:
    """Mark session as archived in br_session.yaml."""
    save_session(task_num, {"status": "archived"})
