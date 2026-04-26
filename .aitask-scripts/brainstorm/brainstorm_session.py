"""Session management for the brainstorm engine.

Sessions live in AgentCrew crew worktrees at
.aitask-crews/crew-brainstorm-<task_num>/. The crew worktree is created by
`ait crew init`; this module adds brainstorm-specific files (br_session.yaml,
br_graph_state.yaml, br_groups.yaml) and subdirectories (br_nodes/,
br_proposals/, br_plans/).
"""

from __future__ import annotations

import os
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

import yaml

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from agentcrew.agentcrew_utils import AGENTCREW_DIR, read_yaml, write_yaml  # noqa: E402

from .brainstorm_dag import (  # noqa: E402
    GRAPH_STATE_FILE,
    NODES_DIR,
    PLANS_DIR,
    PROPOSALS_DIR,
    create_node,
    next_node_id,
    set_head,
)

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
    initial_proposal_file: str | None = None,
) -> Path:
    """Initialize brainstorm session files in an existing crew worktree.

    Creates: br_session.yaml, br_graph_state.yaml, br_groups.yaml,
             br_nodes/, br_proposals/, br_plans/ directories.

    If ``initial_proposal_file`` is given, it is recorded in
    br_session.yaml and the seeded n000_init becomes a placeholder
    pending the initializer agent's output. Callers should launch an
    initializer agent (via ``register_initializer``) and, when it
    completes, call :func:`apply_initializer_output` to replace the
    placeholder.

    Raises FileNotFoundError if the crew worktree does not exist, or
    if ``initial_proposal_file`` is given but the file is missing.
    Returns the session (worktree) path.
    """
    wt = crew_worktree(task_num)
    if not wt.is_dir():
        raise FileNotFoundError(
            f"Crew worktree not found: {wt}. "
            f"Run 'ait crew init --id brainstorm-{task_num}' first."
        )

    # Validate and resolve initial_proposal_file up front — no partial
    # sessions on bad input.
    abs_proposal_path: str | None = None
    if initial_proposal_file is not None:
        proposal_path = Path(initial_proposal_file)
        if not proposal_path.is_file():
            raise FileNotFoundError(
                f"initial_proposal_file not found: {initial_proposal_file}"
            )
        abs_proposal_path = str(proposal_path.resolve())

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
    if abs_proposal_path is not None:
        session_data["initial_proposal_file"] = abs_proposal_path
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

    # Create root node (n000_init) so the session is immediately usable.
    # When an imported proposal is pending, seed n000_init with a
    # placeholder; the initializer agent will overwrite it.
    if abs_proposal_path is not None:
        basename = os.path.basename(abs_proposal_path)
        brief = f"Imported proposal (awaiting reformat): {basename}"
        proposal_body = f"Awaiting initializer agent output for `{basename}`.\n"
        reference_files: list[str] | None = [abs_proposal_path]
    else:
        spec_lines = [
            ln for ln in initial_spec.splitlines()
            if ln.strip() and not ln.startswith("---")
        ]
        brief = (
            (spec_lines[0][:80] + "…")
            if spec_lines and len(spec_lines[0]) > 80
            else (spec_lines[0] if spec_lines else "Initial specification")
        )
        proposal_body = initial_spec
        reference_files = None

    create_node(
        session_path=wt,
        node_id="n000_init",
        parents=[],
        description=brief,
        dimensions={},
        proposal_content=proposal_body,
        group_name="bootstrap",
        reference_files=reference_files,
    )
    set_head(wt, "n000_init")
    next_node_id(wt)  # increment counter from 0 → 1

    # Transition session to active
    session_data["status"] = "active"
    write_yaml(str(wt / SESSION_FILE), session_data)

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


def delete_session(task_num: int | str) -> None:
    """Delete a brainstorm session by removing its crew worktree directory.

    Raises FileNotFoundError if the session does not exist.
    """
    wt = crew_worktree(task_num)
    if not (wt / SESSION_FILE).is_file():
        raise FileNotFoundError(f"No brainstorm session for task {task_num}")
    shutil.rmtree(wt)


def _extract_block(text: str, start: str, end: str) -> str:
    """Return the text between ``--- <start> ---`` and ``--- <end> ---``.

    Raises ValueError if either delimiter is missing.
    """
    start_tag = f"--- {start} ---"
    end_tag = f"--- {end} ---"
    si = text.find(start_tag)
    ei = text.find(end_tag, si + len(start_tag)) if si >= 0 else -1
    if si < 0 or ei < 0:
        raise ValueError(f"missing delimiter: {start}/{end}")
    return text[si + len(start_tag):ei].strip("\n")


def n000_needs_apply(task_num: int | str) -> bool:
    """Return True if n000_init is still a placeholder AND an output file exists.

    Used by the brainstorm TUI to decide whether to (re-)attempt
    ``apply_initializer_output`` on session load or after an Error.
    """
    wt = crew_worktree(task_num)
    node_path = wt / NODES_DIR / "n000_init.yaml"
    out_path = wt / "initializer_bootstrap_output.md"
    if not node_path.is_file() or not out_path.is_file():
        return False
    try:
        data = read_yaml(str(node_path))
    except Exception:
        return False
    desc = (data or {}).get("description", "")
    return desc.startswith("Imported proposal (awaiting reformat):")


_PROBLEM_VALUE_RE = re.compile(r'^(\s*[A-Za-z_][\w]*:\s+)((?!["\'\[\{]).+?)\s*$')
_PROBLEM_CHARS_RE = re.compile(r'(—|–| - |#|: )')


def _tolerant_yaml_load(text: str) -> dict:
    """yaml.safe_load with a one-shot quote-the-bad-values fallback.

    On YAMLError, walk lines whose value (after the first ': ') contains an
    em-dash, en-dash, hyphen-space, '#', or a second ': ', and is not already
    quoted or starting a flow collection. Wrap such values in double quotes
    (escaping any embedded "). Retry parsing. Re-raise the ORIGINAL error if
    the fixed text still fails — keeping the original line number is more
    useful for debugging than the line number after auto-quoting.
    """
    try:
        return yaml.safe_load(text)
    except yaml.YAMLError as orig_err:
        fixed_lines = []
        for line in text.splitlines():
            m = _PROBLEM_VALUE_RE.match(line)
            if m and _PROBLEM_CHARS_RE.search(m.group(2)):
                value = m.group(2).replace("\\", "\\\\").replace('"', '\\"')
                fixed_lines.append(f'{m.group(1)}"{value}"')
            else:
                fixed_lines.append(line)
        fixed_text = "\n".join(fixed_lines)
        try:
            return yaml.safe_load(fixed_text)
        except yaml.YAMLError:
            raise orig_err


def apply_initializer_output(task_num: int | str) -> None:
    """Parse ``initializer_bootstrap_output.md`` and overwrite n000_init.

    Parses the four delimited blocks (NODE_YAML + PROPOSAL), validates
    both, and rewrites ``br_nodes/n000_init.yaml`` and
    ``br_proposals/n000_init.md``. Existing files are only overwritten
    if validation passes.

    Raises:
        FileNotFoundError: if the initializer output file is missing.
        ValueError: if any delimiter is missing or either block fails
            validation.
    """
    wt = crew_worktree(task_num)
    out_path = wt / "initializer_bootstrap_output.md"
    if not out_path.is_file():
        raise FileNotFoundError(f"No initializer output at {out_path}")

    text = out_path.read_text(encoding="utf-8")
    node_yaml_text = _extract_block(text, "NODE_YAML_START", "NODE_YAML_END")
    proposal_text = _extract_block(text, "PROPOSAL_START", "PROPOSAL_END")

    from .brainstorm_schemas import validate_node
    from .brainstorm_sections import parse_sections, validate_sections

    try:
        node_data = _tolerant_yaml_load(node_yaml_text)
    except yaml.YAMLError as exc:
        err_log = wt / "initializer_bootstrap_apply_error.log"
        err_log.write_text(
            f"apply_initializer_output failed at "
            f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            f"Original YAML parse error:\n{exc}\n\n"
            f"NODE_YAML block (first 2000 chars):\n{node_yaml_text[:2000]}\n",
            encoding="utf-8",
        )
        raise
    if not isinstance(node_data, dict):
        raise ValueError("initializer NODE_YAML block did not parse as a dict")
    errs = validate_node(node_data)
    if errs:
        raise ValueError(f"initializer node YAML invalid: {errs}")

    parsed = parse_sections(proposal_text)
    serrs = validate_sections(parsed)
    if serrs:
        raise ValueError(f"initializer proposal invalid: {serrs}")

    write_yaml(str(wt / NODES_DIR / "n000_init.yaml"), node_data)
    (wt / PROPOSALS_DIR / "n000_init.md").write_text(
        proposal_text, encoding="utf-8"
    )
