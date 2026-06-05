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
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Callable

import yaml

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from agentcrew.agentcrew_utils import AGENTCREW_DIR, read_yaml, write_yaml  # noqa: E402

from .brainstorm_dag import (  # noqa: E402
    GRAPH_STATE_FILE,
    NODES_DIR,
    PLANS_DIR,
    PROPOSALS_DIR,
    UMBRELLA_SUBGRAPH,
    create_node,
    get_head,
    is_ancestor_subgraph,
    next_node_id,
    read_node,
    read_proposal,
    set_head,
    update_node,
)
from .brainstorm_sections import (  # noqa: E402
    get_section_by_name,
    get_sections_for_dimension,
    parse_sections,
    validate_sections,
)
from .brainstorm_schemas import extract_dimensions  # noqa: E402

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

    # Write br_graph_state.yaml. The module-decomposition maps (t756) are seeded
    # empty and back-compat: current_head/history are the legacy single-head
    # fields, kept in sync by set_head() as aliases of the _umbrella subgraph.
    # set_head(wt, "n000_init") below populates current_heads["_umbrella"] and
    # history["_umbrella"].
    graph_state = {
        "current_head": None,
        "current_heads": {},
        "history": {},
        "next_node_id": 0,
        "active_dimensions": [],
        "module_tasks": {},
        "last_synced_at": {},
        "module_deferred": {},
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

    # Record the bootstrap operation group. For blank-init the bootstrap
    # is complete the moment n000_init is written; for the proposal-file
    # path the initializer agent will run later and
    # apply_initializer_output flips status to Completed once it finishes.
    record_operation(
        task_num,
        group_name="bootstrap",
        operation="bootstrap",
        agents=[],
        head_at_creation=None,
    )
    update_operation(
        task_num,
        "bootstrap",
        nodes_created="n000_init",
        status="Completed" if abs_proposal_path is None else "Waiting",
    )

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


# ---------------------------------------------------------------------------
# Operation group persistence (br_groups.yaml)
# ---------------------------------------------------------------------------


def _read_groups_file(path: str) -> dict:
    """Read br_groups.yaml; return ``{"groups": {}}`` if absent."""
    if not os.path.isfile(path):
        return {"groups": {}}
    return read_yaml(path) or {"groups": {}}


def record_operation(
    task_num: int | str,
    group_name: str,
    operation: str,
    agents: list[str],
    head_at_creation: str | None,
    subgraph: str = UMBRELLA_SUBGRAPH,
    **extra_fields,
) -> None:
    """Write a fresh group entry to br_groups.yaml.

    Idempotent — overwrites any existing entry with the same name. Status
    is initialized to "Waiting"; callers use ``update_operation`` to flip
    it to "Completed" once the operation finishes. ``subgraph`` records the
    module subgraph the op ran inside (default ``_umbrella``); the apply path
    reads it back to scope ``module_label`` / ``set_head`` for created nodes.
    """
    wt = crew_worktree(task_num)
    path = str(wt / GROUPS_FILE)
    data = _read_groups_file(path)
    groups = data.setdefault("groups", {})
    entry = {
        "operation": operation,
        "agents": list(agents),
        "status": "Waiting",
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "head_at_creation": head_at_creation,
        "nodes_created": [],
        "subgraph": subgraph,
    }
    entry.update(extra_fields)
    groups[group_name] = entry
    write_yaml(path, data)


def _group_subgraph(wt: Path, group_name: str) -> str:
    """Return the subgraph a group's op ran inside (default ``_umbrella``).

    Read by the apply path so a newly-ingested node inherits its op's
    subgraph membership. Legacy groups without a ``subgraph`` field (and the
    bootstrap init group) resolve to ``_umbrella``.
    """
    if not group_name:
        return UMBRELLA_SUBGRAPH
    data = _read_groups_file(str(wt / GROUPS_FILE))
    grp = data.get("groups", {}).get(group_name, {})
    sg = grp.get("subgraph") if isinstance(grp, dict) else None
    return str(sg) if sg else UMBRELLA_SUBGRAPH


def update_operation(task_num: int | str, group_name: str, **fields) -> None:
    """Patch fields on an existing group entry in br_groups.yaml.

    Special-case: ``nodes_created="<nid>"`` appends to the list (unique);
    ``agents_append="<name>"`` appends to the agents list (unique). Any
    other kwarg overwrites the corresponding field.

    Silently no-ops if the group is missing.
    """
    wt = crew_worktree(task_num)
    path = str(wt / GROUPS_FILE)
    data = _read_groups_file(path)
    groups = data.setdefault("groups", {})
    grp = groups.get(group_name)
    if grp is None:
        return
    for k, v in fields.items():
        if k == "nodes_created" and isinstance(v, str):
            lst = grp.setdefault("nodes_created", [])
            if v not in lst:
                lst.append(v)
        elif k == "agents_append" and isinstance(v, str):
            lst = grp.setdefault("agents", [])
            if v not in lst:
                lst.append(v)
        else:
            grp[k] = v
    write_yaml(path, data)


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


_INITIALIZER_DELIMITERS = (
    "NODE_YAML_START",
    "NODE_YAML_END",
    "PROPOSAL_START",
    "PROPOSAL_END",
)


def n000_needs_apply(task_num: int | str) -> bool:
    """Return True iff n000_init is still a placeholder AND the
    initializer output file contains all four delimiter blocks
    expected by ``apply_initializer_output``.

    The delimiter check guards against the placeholder ``_output.md``
    that ``aitask_crew_addwork.sh`` writes at agent-registration time
    (before the agent runs), and against mid-stream agent writes where
    only some delimiters have been emitted so far.
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
    if not desc.startswith("Imported proposal (awaiting reformat):"):
        return False
    try:
        text = out_path.read_text(encoding="utf-8")
    except Exception:
        return False
    return all(token in text for token in _INITIALIZER_DELIMITERS)


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

    # Auto-fill system-generable fields the agent may forget. created_at is a
    # wall-clock timestamp meaningful at apply-time; created_by_group is the
    # bootstrap constant. The remaining NODE_REQUIRED_FIELDS carry semantic
    # content the agent must supply, so we still let validate_node reject those.
    if not node_data.get("created_at"):
        node_data["created_at"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    if not node_data.get("created_by_group"):
        node_data["created_by_group"] = "bootstrap"

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

    update_operation(
        task_num,
        "bootstrap",
        agents_append="initializer_bootstrap",
        status="Completed",
    )


_PATCHER_DELIMITERS = (
    "PATCHED_PLAN_START", "PATCHED_PLAN_END",
    "IMPACT_START", "IMPACT_END",
    "METADATA_START", "METADATA_END",
)

# Structural fields the patcher/explorer/synthesizer emit alongside dimension
# fields. Stripped before the remainder is passed to ``create_node`` as the
# ``dimensions`` dict, so that proposal_file is set authoritatively to
# ``br_proposals/<new>.md`` (the parent's path the agent emits would violate
# validate_node's ``node_id ∈ proposal_file`` invariant).
_NODE_NON_DIMENSION_FIELDS = frozenset({
    "node_id", "parents", "description", "proposal_file",
    "created_at", "created_by_group", "reference_files", "plan_file",
})

_AGENT_NAME_RE = re.compile(r"^([a-z_]+)_([0-9A-Za-z_]+)$")


def resolve_node_group(
    node_id: str, stored_group: str, groups: dict
) -> tuple[str, dict]:
    """Resolve a node's operation group, with defensive fallback.

    Returns ``(resolved_group_name, group_info_dict)``. ``group_info_dict``
    is empty when no match is found.

    Lookup order:

    1. **Direct match.** ``groups.get(stored_group)`` — the happy path
       (and the only path for nodes produced by post-t792 applies).
    2. **nodes_created membership.** Any group whose ``nodes_created``
       list contains ``node_id``. Authoritative when the registration
       happened to succeed even though the node's
       ``created_by_group`` value drifted.
    3. **Suffix match.** Any existing group name that ``stored_group``
       ends with (catches drift like ``op_explore_001`` /
       ``operation_explore_001`` → ``explore_001``).

    Allows graph-tab consumers to render the correct operation for
    nodes whose ``created_by_group`` field was written by a pre-t792
    parallel agent that drifted away from the canonical value.
    """
    ginfo = groups.get(stored_group) or {}
    if ginfo:
        return stored_group, ginfo
    for gname, ginfo_candidate in groups.items():
        if not isinstance(ginfo_candidate, dict):
            continue
        nodes_created = ginfo_candidate.get("nodes_created") or []
        if node_id in nodes_created:
            return gname, ginfo_candidate
    for gname, ginfo_candidate in groups.items():
        if (
            isinstance(ginfo_candidate, dict)
            and gname != stored_group
            and stored_group.endswith(gname)
        ):
            return gname, ginfo_candidate
    return stored_group, {}


def _agent_to_group_name(agent_name: str) -> str:
    """Derive a group name from an agent name.

    ``patcher_001`` → ``patch_001``. Parallel explorers share a group, so
    a trailing single-letter parallel suffix is stripped:
    ``explorer_001a`` → ``explore_001``. Returns the input unchanged if
    the pattern does not match.
    """
    role_to_group = {
        "patcher": "patch",
        "explorer": "explore",
        "synthesizer": "synthesize",
        "detailer": "detail",
        "module_decomposer": "module_decompose",
        "module_merger": "module_merge",
        "module_syncer": "module_sync",
    }
    for role in sorted(role_to_group, key=len, reverse=True):
        prefix = f"{role}_"
        if not agent_name.startswith(prefix):
            continue
        suffix = agent_name[len(prefix):]
        parallel_suffix_match = re.match(r"^(\d+)[a-h]$", suffix)
        if parallel_suffix_match:
            suffix = parallel_suffix_match.group(1)
        return f"{role_to_group[role]}_{suffix}"
    return agent_name


# Agent _status.yaml values that are terminal but yield no applyable
# output — the TUI auto-apply scan/poll stop watching these agents.
_AGENT_FAILED_STATUSES = ("Error", "Aborted")


def _agent_apply_scan_should_track(status: str, needs_apply: bool) -> bool:
    """Decide whether ``_scan_existing_<role>`` should track an agent.

    - Error/Aborted → never (no output will ever come).
    - Completed     → only if its output still needs applying.
    - Anything else (Waiting/Ready/Running/Paused/empty — still in flight)
      → yes, so the poll timer is alive to apply on completion.
      ``needs_apply`` is meaningless mid-run and is ignored.
    """
    if status in _AGENT_FAILED_STATUSES:
        return False
    if status == "Completed":
        return needs_apply
    return True


def _patcher_needs_apply(task_num: int | str, agent_name: str) -> bool:
    """Return True iff ``<agent_name>_output.md`` contains all six patcher
    delimiter tokens AND the new node id parsed from the METADATA block
    does NOT already exist in ``br_nodes/``.

    Guards against the registration-time placeholder ``_output.md``
    written by ``aitask_crew_addwork.sh`` and against double-apply when
    the TUI restarts after a successful apply.
    """
    wt = crew_worktree(task_num)
    out_path = wt / f"{agent_name}_output.md"
    if not out_path.is_file():
        return False
    try:
        text = out_path.read_text(encoding="utf-8")
    except Exception:
        return False
    if not all(token in text for token in _PATCHER_DELIMITERS):
        return False
    try:
        meta_text = _extract_block(text, "METADATA_START", "METADATA_END")
        meta = _tolerant_yaml_load(meta_text)
    except Exception:
        # Delimiters present but body unparseable — let the apply call
        # surface the structured error.
        return True
    if not isinstance(meta, dict):
        return True
    new_node_id = meta.get("node_id")
    if not new_node_id:
        return True
    return not (wt / NODES_DIR / f"{new_node_id}.yaml").exists()


def _classify_impact(impact_text: str) -> tuple[str, str]:
    """Return (impact_type, details) for an IMPACT block.

    impact_type is exactly one of ``"NO_IMPACT"`` or ``"IMPACT_FLAG"``.
    Raises ValueError if the block contains neither marker or both.
    The full block text is returned as ``details`` for banner display.
    """
    has_no_impact = "**NO_IMPACT**" in impact_text
    has_flag = "**IMPACT_FLAG**" in impact_text
    if has_no_impact and has_flag:
        raise ValueError(
            "IMPACT block contains both **NO_IMPACT** and **IMPACT_FLAG**"
        )
    if not has_no_impact and not has_flag:
        raise ValueError(
            "IMPACT block must contain exactly one of "
            "**NO_IMPACT** or **IMPACT_FLAG**"
        )
    return ("NO_IMPACT" if has_no_impact else "IMPACT_FLAG", impact_text.strip())


def _parse_patcher_output(
    text: str,
    err_log: Path,
    expected_role: str,
    *,
    wt: Path,
    source_node_id: str,
) -> tuple[dict, str, dict]:
    """Patcher parser: three-block format (PATCHED_PLAN / IMPACT / METADATA).

    The new node's proposal is the parent's proposal verbatim — the patcher
    edits the plan, never the proposal. ``extras`` carries the plan_text and
    the classified IMPACT for the wrapper to consume.
    """
    plan_text = _extract_block(text, "PATCHED_PLAN_START", "PATCHED_PLAN_END")
    impact_text = _extract_block(text, "IMPACT_START", "IMPACT_END")
    meta_text = _extract_block(text, "METADATA_START", "METADATA_END")

    try:
        node_data = _tolerant_yaml_load(meta_text)
    except yaml.YAMLError as exc:
        err_log.write_text(
            f"apply_{expected_role}_output failed at "
            f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            f"Original YAML parse error:\n{exc}\n\n"
            f"METADATA block (first 2000 chars):\n{meta_text[:2000]}\n",
            encoding="utf-8",
        )
        raise
    if not isinstance(node_data, dict):
        raise ValueError(
            f"{expected_role} METADATA block did not parse as a dict"
        )

    impact_type, impact_details = _classify_impact(impact_text)

    # Reuse the parent's proposal verbatim. Raises FileNotFoundError if
    # the source proposal is missing.
    source_proposal_text = read_proposal(wt, source_node_id)

    extras = {
        "plan_text": plan_text,
        "impact_type": impact_type,
        "impact_details": impact_details,
    }
    return node_data, source_proposal_text, extras


def _write_patcher_plan_file(
    wt: Path, new_node_id: str, _node_data: dict, extras: dict
) -> None:
    """Patcher finalize hook: persist the PATCHED_PLAN block as a plan
    file and record it on the new node. Runs between create_node and
    set_head so the plan_file pointer is in place before head advances.
    """
    plan_rel = f"{PLANS_DIR}/{new_node_id}_plan.md"
    (wt / PLANS_DIR).mkdir(parents=True, exist_ok=True)
    (wt / plan_rel).write_text(extras["plan_text"], encoding="utf-8")
    update_node(wt, new_node_id, {"plan_file": plan_rel})


def apply_patcher_output(
    task_num: int | str,
    agent_name: str,
    source_node_id: str,
) -> tuple[str, str, str]:
    """Parse ``<agent_name>_output.md`` and integrate the patched plan as
    a new node parented on ``source_node_id``.

    Returns:
        ``(new_node_id, impact_type, impact_details)``.
        ``impact_type`` is ``"NO_IMPACT"`` or ``"IMPACT_FLAG"``.
        ``impact_details`` is the IMPACT block text (stripped) so the TUI
        can render the affected dimensions / justification verbatim.

    Raises:
        FileNotFoundError: output file missing OR source proposal missing.
        ValueError: any delimiter missing, METADATA invalid, IMPACT block
            ambiguous, or ``new_node_id`` already exists as a node.
    """
    wt = crew_worktree(task_num)

    def _parser(text: str, err_log: Path, expected_role: str):
        return _parse_patcher_output(
            text, err_log, expected_role,
            wt=wt, source_node_id=source_node_id,
        )

    new_node_id, node_data, extras = _apply_node_output(
        task_num,
        agent_name,
        expected_role="patcher",
        metadata_block_label="METADATA",
        parser=_parser,
        finalize=_write_patcher_plan_file,
        extra_error_context={"source_node_id": source_node_id},
    )

    update_operation(
        task_num,
        node_data["created_by_group"],
        nodes_created=new_node_id,
        status="Completed",
    )

    return new_node_id, extras["impact_type"], extras["impact_details"]


_EXPLORER_DELIMITERS = (
    "NODE_YAML_START",
    "NODE_YAML_END",
    "PROPOSAL_START",
    "PROPOSAL_END",
)

_NEW_DIMENSIONS_TAG = "--- NEW_DIMENSIONS ---"


def _parse_new_dimensions(text: str) -> list[str]:
    """Extract dimension keys from an optional ``--- NEW_DIMENSIONS ---``
    block. The tag has no matching ``_END`` — body extends from the tag to
    EOF (per ``templates/explorer.md``). The literal ``none`` (any case)
    means "no new dimensions". Returns an empty list if the tag is absent
    or the body is empty / ``none``.
    """
    idx = text.find(_NEW_DIMENSIONS_TAG)
    if idx < 0:
        return []
    tail = text[idx + len(_NEW_DIMENSIONS_TAG):].strip()
    if not tail or tail.lower() == "none":
        return []
    items = [s.strip() for s in tail.split(",")]
    return [s for s in items if s and s.lower() != "none"]


def _output_has_all_delimiters(text: str, tokens: tuple[str, ...]) -> bool:
    return all(tok in text for tok in tokens)


def _explorer_needs_apply(task_num: int | str, agent_name: str) -> bool:
    """Return True iff ``<agent_name>_output.md`` contains all four
    NODE_YAML / PROPOSAL delimiters AND the node_id parsed from the
    NODE_YAML block does NOT already exist in ``br_nodes/``.

    Guards against the registration-time placeholder ``_output.md``
    written by ``aitask_crew_addwork.sh`` (which has no delimiters) and
    against double-apply when the TUI restarts after a successful apply.
    """
    wt = crew_worktree(task_num)
    out_path = wt / f"{agent_name}_output.md"
    if not out_path.is_file():
        return False
    try:
        text = out_path.read_text(encoding="utf-8")
    except Exception:
        return False
    if not _output_has_all_delimiters(text, _EXPLORER_DELIMITERS):
        return False
    try:
        node_yaml_text = _extract_block(
            text, "NODE_YAML_START", "NODE_YAML_END"
        )
        node_data = _tolerant_yaml_load(node_yaml_text)
    except Exception:
        # Delimiters present but body unparseable — let the apply call
        # surface the structured error.
        return True
    if not isinstance(node_data, dict):
        return True
    new_node_id = node_data.get("node_id")
    if not new_node_id:
        return True
    return not (wt / NODES_DIR / f"{new_node_id}.yaml").exists()


def _parse_two_block_output(
    text: str,
    err_log: Path,
    expected_role: str,
) -> tuple[dict, str, dict]:
    """Parser for explorer/synthesizer outputs: NODE_YAML + PROPOSAL blocks,
    with an optional ``--- NEW_DIMENSIONS ---`` tail.

    Returns ``(node_data, proposal_text, extras)`` where ``extras['raw_text']``
    is the full output text so the caller can re-scan it for NEW_DIMENSIONS.
    """
    node_yaml_text = _extract_block(text, "NODE_YAML_START", "NODE_YAML_END")
    proposal_text = _extract_block(text, "PROPOSAL_START", "PROPOSAL_END")

    try:
        node_data = _tolerant_yaml_load(node_yaml_text)
    except yaml.YAMLError as exc:
        err_log.write_text(
            f"apply_{expected_role}_output failed at "
            f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            f"Original YAML parse error:\n{exc}\n\n"
            f"NODE_YAML block (first 2000 chars):\n"
            f"{node_yaml_text[:2000]}\n",
            encoding="utf-8",
        )
        raise
    if not isinstance(node_data, dict):
        raise ValueError(
            f"{expected_role} NODE_YAML block did not parse as a dict"
        )

    from .brainstorm_sections import parse_sections, validate_sections

    parsed = parse_sections(proposal_text)
    serrs = validate_sections(parsed)
    if serrs:
        raise ValueError(f"{expected_role} proposal invalid: {serrs}")

    return node_data, proposal_text, {"raw_text": text}


def _apply_node_output(
    task_num: int | str,
    agent_name: str,
    *,
    expected_role: str,
    metadata_block_label: str = "NODE_YAML",
    parser: Callable[
        [str, Path, str], tuple[dict, str, dict]
    ] = _parse_two_block_output,
    finalize: Callable[[Path, str, dict, dict], None] | None = None,
    extra_error_context: dict | None = None,
) -> tuple[str, dict, dict]:
    """Shared apply core for agents whose output produces exactly one new
    node. Used by ``apply_explorer_output``, ``apply_synthesizer_output``,
    and ``apply_patcher_output``.

    The flow-specific parts are injected:

    - ``parser`` parses the raw output text into ``(node_data, proposal_text,
      extras)``. It is responsible for writing a flow-specific YAML error
      log (with the relevant block excerpt) and re-raising on
      :class:`yaml.YAMLError`.
    - ``finalize`` runs between ``create_node`` and ``set_head``. Used by
      the patcher to persist the PATCHED_PLAN block as a plan file before
      head advances.
    - ``extra_error_context`` adds fields to the catch-all error log
      (e.g. ``source_node_id`` for the patcher).

    Args:
        task_num: Brainstorm session task number.
        agent_name: Agent that produced the output (e.g. ``explorer_001a``).
        expected_role: Role string used in failure-log prose
            (``"explorer"`` / ``"synthesizer"`` / ``"patcher"``).
        metadata_block_label: Block name surfaced in validate_node failure
            messages (``"NODE_YAML"`` or ``"METADATA"``).
        parser: Output parser strategy. Defaults to the two-block parser
            used by explorer and synthesizer.
        finalize: Optional hook invoked between ``create_node`` and
            ``set_head`` with ``(wt, new_node_id, node_data, extras)``.
        extra_error_context: Extra ``key: value`` lines appended to the
            catch-all error log.

    Returns:
        ``(new_node_id, node_data, extras)``. ``node_data`` is the mutated
        dict (with ``created_at``, ``created_by_group``, ``proposal_file``
        overrides applied). ``extras`` is the parser's third return value.

    Raises:
        FileNotFoundError: output file missing.
        ValueError: any delimiter missing, YAML/sections invalid, or
            ``node_id`` already exists.
    """
    wt = crew_worktree(task_num)
    out_path = wt / f"{agent_name}_output.md"
    if not out_path.is_file():
        raise FileNotFoundError(
            f"No {expected_role} output at {out_path}"
        )

    err_log = wt / f"{agent_name}_apply_error.log"

    try:
        text = out_path.read_text(encoding="utf-8")
        node_data, proposal_text, extras = parser(text, err_log, expected_role)

        from .brainstorm_schemas import validate_node

        if not node_data.get("created_at"):
            node_data["created_at"] = datetime.now().strftime(
                "%Y-%m-%d %H:%M"
            )
        # created_by_group is authoritative from the agent name — never
        # trust the agent's value (parallel agents drift; see t792).
        node_data["created_by_group"] = _agent_to_group_name(agent_name)

        new_node_id = node_data.get("node_id")
        if new_node_id:
            # Override proposal_file so validate_node sees the canonical
            # ``node_id ∈ proposal_file`` invariant; create_node will set
            # the same value authoritatively below.
            node_data["proposal_file"] = (
                f"{PROPOSALS_DIR}/{new_node_id}.md"
            )

        errs = validate_node(node_data)
        if errs:
            raise ValueError(
                f"{expected_role} {metadata_block_label} invalid: {errs}"
            )

        if (wt / NODES_DIR / f"{new_node_id}.yaml").exists():
            raise ValueError(f"node {new_node_id} already exists")

        dimensions = {
            k: v for k, v in node_data.items()
            if k not in _NODE_NON_DIMENSION_FIELDS
        }

        # The op's group recorded which subgraph it ran inside; the new node
        # inherits that membership and advances that subgraph's HEAD (default
        # _umbrella → byte-identical to pre-module behaviour).
        subgraph = _group_subgraph(wt, node_data["created_by_group"])

        create_node(
            session_path=wt,
            node_id=new_node_id,
            parents=node_data["parents"],
            description=node_data["description"],
            dimensions=dimensions,
            proposal_content=proposal_text,
            group_name=node_data["created_by_group"],
            reference_files=node_data.get("reference_files"),
            module_label=subgraph,
        )

        if finalize is not None:
            finalize(wt, new_node_id, node_data, extras)

        set_head(wt, new_node_id, module=subgraph)
        # next_node_id is consumed at registration time (see
        # register_explorer / register_synthesizer / register_patcher in
        # brainstorm_crew.py).

        return new_node_id, node_data, extras
    except yaml.YAMLError:
        # Already logged with full block context by the parser.
        raise
    except Exception as exc:
        try:
            extra_lines = ""
            if extra_error_context:
                extra_lines = "".join(
                    f"{k}: {v}\n" for k, v in extra_error_context.items()
                )
            err_log.write_text(
                f"apply_{expected_role}_output failed at "
                f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
                f"agent_name: {agent_name}\n"
                f"{extra_lines}\n"
                f"Error: {type(exc).__name__}: {exc}\n",
                encoding="utf-8",
            )
        except Exception:
            pass
        raise


def _merge_new_dimensions(wt: Path, raw_text: str) -> list[str]:
    """Merge any ``--- NEW_DIMENSIONS ---`` entries from ``raw_text`` into
    the session's ``active_dimensions``. Returns the dimensions that were
    newly added (i.e. weren't already present).
    """
    new_dims = _parse_new_dimensions(raw_text)
    if not new_dims:
        return []
    gs_path = wt / GRAPH_STATE_FILE
    gs = read_yaml(str(gs_path))
    active = list(gs.get("active_dimensions", []) or [])
    added: list[str] = []
    for dim in new_dims:
        if dim not in active:
            active.append(dim)
            added.append(dim)
    if added:
        gs["active_dimensions"] = active
        write_yaml(str(gs_path), gs)
    return added


def apply_explorer_output(
    task_num: int | str, agent_name: str
) -> str:
    """Parse ``<agent_name>_output.md`` and integrate it as a new node.

    The explorer emits two delimited blocks (NODE_YAML + PROPOSAL) and an
    optional ``--- NEW_DIMENSIONS ---`` tail. The new node is created with
    parents as declared in NODE_YAML (typically the baseline node), head
    is advanced to it, and the next-node-id counter is incremented.

    Returns:
        The new node_id (parsed from NODE_YAML).

    Raises:
        FileNotFoundError: output file missing.
        ValueError: any delimiter missing, NODE_YAML or proposal invalid,
            or the new node_id already exists.
    """
    new_id, node_data, extras = _apply_node_output(
        task_num, agent_name, expected_role="explorer",
    )
    _merge_new_dimensions(crew_worktree(task_num), extras["raw_text"])
    update_operation(
        task_num,
        node_data["created_by_group"],
        agents_append=agent_name,
        nodes_created=new_id,
        status="Completed",
    )
    return new_id


def _synthesizer_needs_apply(
    task_num: int | str, agent_name: str,
) -> bool:
    """Synthesizer alias for :func:`_explorer_needs_apply` — the
    underlying check is role-neutral (delimiter presence + node_id
    collision). Exists so TUI callers read naturally and mirror the
    explorer / patcher symmetry.
    """
    return _explorer_needs_apply(task_num, agent_name)


def apply_synthesizer_output(
    task_num: int | str, agent_name: str,
) -> str:
    """Parse ``<agent_name>_output.md`` and integrate it as a new
    synthesized node.

    The synthesizer emits two delimited blocks (``NODE_YAML`` +
    ``PROPOSAL``) with no optional ``NEW_DIMENSIONS`` block. The new
    node is parented on every source node listed in NODE_YAML's
    ``parents:`` field (synthesizers merge multiple nodes — see
    ``templates/synthesizer.md``). Head is advanced to the new node
    and the next-node-id counter is incremented.

    Returns:
        The new node_id (parsed from NODE_YAML).

    Raises:
        FileNotFoundError: output file missing.
        ValueError: any delimiter missing, NODE_YAML or proposal invalid,
            or the new node_id already exists.
    """
    new_id, node_data, extras = _apply_node_output(
        task_num, agent_name, expected_role="synthesizer",
    )
    _merge_new_dimensions(crew_worktree(task_num), extras["raw_text"])
    update_operation(
        task_num,
        node_data["created_by_group"],
        agents_append=agent_name,
        nodes_created=new_id,
        status="Completed",
    )
    return new_id


_MODULE_NODE_BLOCK_RE = re.compile(
    r"--- MODULE_NODE_START ---\s*(.*?)\s*--- MODULE_NODE_END ---",
    re.DOTALL,
)


def _module_decomposer_needs_apply(
    task_num: int | str, agent_name: str,
) -> bool:
    wt = crew_worktree(task_num)
    out_path = wt / f"{agent_name}_output.md"
    if not out_path.is_file():
        return False
    try:
        text = out_path.read_text(encoding="utf-8")
    except Exception:
        return False
    if not all(
        token in text
        for token in (
            "MODULE_NODE_START",
            "MODULE_NAME_START",
            "MODULE_NAME_END",
            "NODE_YAML_START",
            "NODE_YAML_END",
            "PROPOSAL_START",
            "PROPOSAL_END",
            "MODULE_NODE_END",
        )
    ):
        return False
    try:
        blocks = [m.group(1) for m in _MODULE_NODE_BLOCK_RE.finditer(text)]
        if not blocks:
            return True
        for block in blocks:
            meta = _tolerant_yaml_load(
                _extract_block(block, "NODE_YAML_START", "NODE_YAML_END")
            )
            new_node_id = meta.get("node_id") if isinstance(meta, dict) else None
            if not new_node_id:
                return True
            if not (wt / NODES_DIR / f"{new_node_id}.yaml").exists():
                return True
    except Exception:
        return True
    return False


def module_decomposer_review_enabled(
    task_num: int | str, agent_name: str,
) -> bool:
    """True iff the decomposer's group requested review-before-apply (t929_1).

    Read from the persisted group entry so the answer survives a TUI reload.
    Absent flag (groups created before this feature) defaults to ``False`` to
    preserve the legacy auto-apply behavior.
    """
    wt = crew_worktree(task_num)
    group_name = _agent_to_group_name(agent_name)
    groups = _read_groups_file(str(wt / GROUPS_FILE)).get("groups", {})
    group_info = groups.get(group_name, {}) if isinstance(groups, dict) else {}
    return bool(group_info.get("review_before_apply", False))


def discard_module_decomposer_output(
    task_num: int | str, agent_name: str, suffix: str = "cancelled",
) -> None:
    """Move a decomposer's ``_output.md`` aside so it is no longer applied.

    Used by the review gate's Cancel / Re-run paths (t929_1) to neutralize a
    superseded proposal **without mutating the graph**. After the rename
    ``_module_decomposer_needs_apply`` returns ``False`` (the output file is
    gone), so neither the poll timer nor a later session-scan re-applies or
    re-prompts for it. The renamed file is kept for forensics. No-op if the
    output is missing.
    """
    wt = crew_worktree(task_num)
    out_path = wt / f"{agent_name}_output.md"
    if not out_path.is_file():
        return
    try:
        out_path.replace(wt / f"{agent_name}_output.{suffix}.md")
    except Exception:
        pass


def _module_merger_needs_apply(
    task_num: int | str, agent_name: str,
) -> bool:
    return _explorer_needs_apply(task_num, agent_name)


def _module_syncer_needs_apply(
    task_num: int | str, agent_name: str,
) -> bool:
    # Single-node output (NODE_YAML + PROPOSAL), same shape as explorer/merger.
    return _explorer_needs_apply(task_num, agent_name)


def _module_tasks_map(wt: Path) -> dict:
    path = wt / GRAPH_STATE_FILE
    gs = read_yaml(str(path))
    tasks = gs.get("module_tasks")
    return tasks if isinstance(tasks, dict) else {}


def _write_module_task(wt: Path, module: str, task_id: str) -> None:
    path = wt / GRAPH_STATE_FILE
    gs = read_yaml(str(path))
    tasks = gs.get("module_tasks")
    if not isinstance(tasks, dict):
        tasks = {}
    tasks[module] = task_id
    gs["module_tasks"] = tasks
    write_yaml(str(path), gs)


def _write_last_synced(wt: Path, module: str, timestamp: str) -> None:
    """Stamp ``last_synced_at[module]`` so a re-sync's scan horizon advances."""
    path = wt / GRAPH_STATE_FILE
    gs = read_yaml(str(path))
    synced = gs.get("last_synced_at")
    if not isinstance(synced, dict):
        synced = {}
    synced[module] = timestamp
    gs["last_synced_at"] = synced
    write_yaml(str(path), gs)


def _module_deferred_map(wt: Path) -> dict:
    """Return the ``module_deferred`` map (<module>:<bool>); {} when unset.

    The UC-2 fluid-status "deferred" marker (t756_5). Mirrors
    ``_module_tasks_map`` so all three module maps read the same way.
    """
    path = wt / GRAPH_STATE_FILE
    gs = read_yaml(str(path))
    deferred = gs.get("module_deferred")
    return deferred if isinstance(deferred, dict) else {}


def _write_module_deferred(wt: Path, module: str, deferred: bool) -> None:
    """Set ``module_deferred[module]`` (UC-2 deferred marker, t756_5).

    Persisted to ``br_graph_state.yaml`` so the marker survives a TUI reload.
    Mirrors ``_write_last_synced`` / ``_write_module_task``.
    """
    path = wt / GRAPH_STATE_FILE
    gs = read_yaml(str(path))
    deferred_map = gs.get("module_deferred")
    if not isinstance(deferred_map, dict):
        deferred_map = {}
    deferred_map[module] = bool(deferred)
    gs["module_deferred"] = deferred_map
    write_yaml(str(path), gs)


def _create_linked_module_task(
    task_num: int | str, module: str, description: str,
) -> str:
    name = f"{module}_module"
    cmd = [
        "./.aitask-scripts/aitask_create.sh",
        "--batch",
        "--commit",
        "--silent",
        "--parent",
        str(task_num),
        "--name",
        name,
        "--desc",
        description,
        "--type",
        "feature",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(
            f"aitask_create.sh failed for module {module!r}: {result.stderr}"
        )
    created_path = result.stdout.strip().splitlines()[-1]
    stem = Path(created_path).stem
    match = re.match(r"^t(\d+_\d+)_", stem) or re.match(r"^t(\d+)_", stem)
    if not match:
        raise ValueError(f"could not parse created task id from {created_path!r}")
    return match.group(1)


def _section_for_module(parsed, module: str):
    section = get_section_by_name(parsed, module)
    if section is not None:
        return section
    dimension = f"component_{module}"
    matches = get_sections_for_dimension(parsed, dimension)
    if matches:
        return matches[-1]
    return None


def apply_module_decompose_from_sections(
    task_num: int | str, group_name: str,
) -> list[str]:
    """Create module roots directly from clean source proposal sections."""
    wt = crew_worktree(task_num)
    groups = _read_groups_file(str(wt / GROUPS_FILE)).get("groups", {})
    group_info = groups.get(group_name, {}) if isinstance(groups, dict) else {}
    modules = [str(m) for m in (group_info.get("modules") or [])]
    if not modules:
        raise ValueError("module_decompose from_sections requires modules")
    source_node_id = group_info.get("head_at_creation")
    if not source_node_id:
        source_node_id = get_head(wt, module=_group_subgraph(wt, group_name))
    if not source_node_id:
        raise ValueError("module_decompose from_sections requires a source head")

    source_data = read_node(wt, source_node_id)
    source_dims = extract_dimensions(source_data)
    source_proposal = read_proposal(wt, source_node_id)
    parsed = parse_sections(source_proposal)
    section_errors = validate_sections(parsed, node_keys=list(source_dims.keys()))
    if section_errors:
        raise ValueError(f"source proposal sections invalid: {section_errors}")

    created: list[str] = []
    for module in modules:
        section = _section_for_module(parsed, module)
        if section is None:
            raise ValueError(
                f"no section found for module {module!r}; expected a section "
                f"named {module!r} or tagged with component_{module}"
            )
        node_num = next_node_id(wt)
        safe_module = "".join(ch if ch.isalnum() else "_" for ch in module).strip("_")
        new_node_id = f"n{node_num:03d}_module_decomposer_sections_{safe_module}"
        dimensions = {
            k: v for k, v in source_dims.items()
            if any(k == tag or (tag.endswith("*") and k.startswith(tag[:-1]))
                   for tag in section.dimensions)
            or k == f"component_{module}"
        }
        if not dimensions and f"component_{module}" in source_dims:
            dimensions[f"component_{module}"] = source_dims[f"component_{module}"]
        proposal_text = "\n".join([
            f"<!-- section: {section.name}"
            + (
                f" [dimensions: {', '.join(section.dimensions)}]"
                if section.dimensions else ""
            )
            + " -->",
            section.content.strip(),
            f"<!-- /section: {section.name} -->",
            "",
        ])
        create_node(
            session_path=wt,
            node_id=new_node_id,
            parents=[source_node_id],
            description=f"{module} module root",
            dimensions=dimensions,
            proposal_content=proposal_text,
            group_name=group_name,
            reference_files=source_data.get("reference_files"),
            module_label=module,
        )
        set_head(wt, new_node_id, module=module)
        update_operation(task_num, group_name, nodes_created=new_node_id)
        created.append(new_node_id)

        if bool(group_info.get("link_to_task")):
            task_id = _create_linked_module_task(
                task_num,
                module,
                f"Implement/refine brainstorm module `{module}` from t{task_num}.",
            )
            _write_module_task(wt, module, task_id)

    update_operation(task_num, group_name, status="Completed")
    return created


def _proposal_excerpt(proposal_text: str, max_lines: int = 12) -> str:
    """First ``max_lines`` non-empty-trimmed lines of a proposal, for preview.

    Used by the review-gate preview to show the operator what each proposed
    module looks like before it is applied. Purely cosmetic — never parsed.
    """
    lines = proposal_text.strip().splitlines()
    head = lines[:max_lines]
    excerpt = "\n".join(head)
    if len(lines) > max_lines:
        excerpt += "\n…"
    return excerpt


def parse_module_decomposer_output(output_text: str) -> list[dict]:
    """Parse module decomposer output into structured proposed blocks.

    **Pure function** — performs NO graph mutation and NO filesystem access. It
    is the parse-only half of ``apply_module_decomposer_output``: the review
    gate (t929_1) calls it to preview the proposed modules before they commit,
    and ``apply_module_decomposer_output`` consumes its result before mutating
    the graph.

    Each returned dict has:
      ``module_name``      - module name exactly as given
      ``node_yaml``        - raw NODE_YAML block text
      ``node_data``        - parsed NODE_YAML mapping
      ``proposal_text``    - full PROPOSAL block text
      ``proposal_excerpt`` - first lines of the proposal, for preview display
      ``node_id``          - assigned node id (from NODE_YAML)

    Raises ``ValueError`` if the output has no blocks or a block is malformed
    (mirrors the parse-time errors ``apply_module_decomposer_output`` raised).
    """
    blocks = [m.group(1) for m in _MODULE_NODE_BLOCK_RE.finditer(output_text)]
    if not blocks:
        raise ValueError("module decomposer output has no MODULE_NODE blocks")
    parsed: list[dict] = []
    for block in blocks:
        module = _extract_block(
            block, "MODULE_NAME_START", "MODULE_NAME_END"
        ).strip()
        if not module:
            raise ValueError("MODULE_NAME block cannot be empty")
        meta_text = _extract_block(block, "NODE_YAML_START", "NODE_YAML_END")
        proposal_text = _extract_block(block, "PROPOSAL_START", "PROPOSAL_END")
        node_data = _tolerant_yaml_load(meta_text)
        if not isinstance(node_data, dict):
            raise ValueError("module NODE_YAML block did not parse as a dict")
        new_node_id = node_data.get("node_id")
        if not new_node_id:
            raise ValueError("module NODE_YAML missing node_id")
        parsed.append({
            "module_name": module,
            "node_yaml": meta_text,
            "node_data": node_data,
            "proposal_text": proposal_text,
            "proposal_excerpt": _proposal_excerpt(proposal_text),
            "node_id": new_node_id,
        })
    return parsed


def assign_inferred_module_node_ids(
    task_num: int | str, agent_name: str,
) -> None:
    """Assign deferred node IDs to an infer-mode decomposer output (t929_2).

    In agent-proposed ("infer") mode the decomposer chooses the module names
    itself, so the orchestrator cannot pre-generate node IDs the way it does for
    the names-given path (``register_module_decomposer``). The agent emits each
    ``MODULE_NODE`` block with a ``MODULE_NAME`` but **no** ``node_id`` in its
    ``NODE_YAML``. This step assigns each such block an
    ``n{num:03d}_{agent_name}_{safe_module}`` id (the same scheme as the
    names-given path) and injects it into the output file, so the downstream
    pure parser, review preview, and ``apply_module_decomposer_output`` all see a
    names-given-shaped output and need no infer-specific branching.

    Only fires for a group that is genuinely in **infer** mode (no module names
    were supplied — persisted ``modules: []``). In the names-given path a block
    that omits ``node_id`` is an agent error and must still surface as the strict
    ``missing node_id`` parse failure, so this is a no-op there.

    Idempotent: a block that already carries a ``node_id`` (a re-entrant call on
    an already-normalized infer output) is left untouched, so the file is
    byte-identical when there is nothing to assign. Malformed/nameless blocks are
    left for the parser to reject. No-op if the output file is missing.
    """
    wt = crew_worktree(task_num)
    out_path = wt / f"{agent_name}_output.md"
    if not out_path.is_file():
        return
    group_name = _agent_to_group_name(agent_name)
    groups = _read_groups_file(str(wt / GROUPS_FILE)).get("groups", {})
    group_info = groups.get(group_name, {}) if isinstance(groups, dict) else {}
    persisted_modules = group_info.get("modules")
    # Infer mode ⇔ the group recorded an explicitly empty module list. A
    # non-empty list (names-given) or an absent key (legacy group) is left to the
    # strict parser, so a dropped node_id there still errors as before.
    if not (isinstance(persisted_modules, list) and not persisted_modules):
        return
    text = out_path.read_text(encoding="utf-8")

    def _assign(match: "re.Match") -> str:
        block = match.group(1)
        try:
            module = _extract_block(
                block, "MODULE_NAME_START", "MODULE_NAME_END"
            ).strip()
            meta_text = _extract_block(block, "NODE_YAML_START", "NODE_YAML_END")
        except ValueError:
            return match.group(0)  # malformed — leave for the parser to reject
        meta = _tolerant_yaml_load(meta_text)
        if isinstance(meta, dict) and meta.get("node_id"):
            return match.group(0)  # already has an id (names-given / re-entrant)
        if not module:
            return match.group(0)  # empty name — leave for the parser to reject
        node_num = next_node_id(wt)
        safe_module = "".join(
            ch if ch.isalnum() else "_" for ch in module
        ).strip("_")
        new_node_id = f"n{node_num:03d}_{agent_name}_{safe_module}"
        start_tag = "--- NODE_YAML_START ---"
        injected = block.replace(
            start_tag, f"{start_tag}\nnode_id: {new_node_id}", 1
        )
        return match.group(0).replace(block, injected, 1)

    new_text = _MODULE_NODE_BLOCK_RE.sub(_assign, text)
    if new_text != text:
        out_path.write_text(new_text, encoding="utf-8")


def apply_module_decomposer_output(
    task_num: int | str, agent_name: str,
) -> list[str]:
    """Integrate module decomposition output as multiple subgraph roots."""
    wt = crew_worktree(task_num)
    out_path = wt / f"{agent_name}_output.md"
    if not out_path.is_file():
        raise FileNotFoundError(f"No module decomposer output at {out_path}")

    err_log = wt / f"{agent_name}_apply_error.log"
    try:
        # Assign deferred IDs for infer-mode output before parsing (t929_2).
        # No-op for the names-given path (blocks already carry node_id).
        assign_inferred_module_node_ids(task_num, agent_name)
        text = out_path.read_text(encoding="utf-8")
        parsed = parse_module_decomposer_output(text)

        group_name = _agent_to_group_name(agent_name)
        groups = _read_groups_file(str(wt / GROUPS_FILE)).get("groups", {})
        group_info = groups.get(group_name, {}) if isinstance(groups, dict) else {}
        source_node_id = group_info.get("head_at_creation")
        if not source_node_id:
            source_node_id = get_head(wt, module=_group_subgraph(wt, group_name))
        if not source_node_id:
            raise ValueError("module_decompose requires a source head")
        link_to_task = bool(group_info.get("link_to_task"))

        created: list[str] = []
        for block in parsed:
            module = block["module_name"]
            proposal_text = block["proposal_text"]
            node_data = block["node_data"]
            new_node_id = block["node_id"]
            if (wt / NODES_DIR / f"{new_node_id}.yaml").exists():
                raise ValueError(f"node {new_node_id} already exists")

            node_data["parents"] = [source_node_id]
            dimensions = extract_dimensions(node_data)
            section_errors = validate_sections(
                parse_sections(proposal_text), node_keys=list(dimensions.keys())
            )
            if section_errors:
                raise ValueError(
                    f"module proposal sections invalid for {module}: {section_errors}"
                )
            create_node(
                session_path=wt,
                node_id=new_node_id,
                parents=[source_node_id],
                description=node_data.get("description", f"{module} module root"),
                dimensions=dimensions,
                proposal_content=proposal_text,
                group_name=group_name,
                reference_files=node_data.get("reference_files"),
                module_label=module,
            )
            set_head(wt, new_node_id, module=module)
            update_operation(task_num, group_name, nodes_created=new_node_id)
            created.append(new_node_id)

            if link_to_task:
                task_id = _create_linked_module_task(
                    task_num,
                    module,
                    f"Implement/refine brainstorm module `{module}` from t{task_num}.",
                )
                _write_module_task(wt, module, task_id)

        update_operation(
            task_num,
            group_name,
            agents_append=agent_name,
            status="Completed",
        )
        return created
    except Exception as exc:
        try:
            err_log.write_text(
                f"apply_module_decomposer_output failed at "
                f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
                f"Error: {type(exc).__name__}: {exc}\n",
                encoding="utf-8",
            )
        except Exception:
            pass
        raise


def apply_module_merger_output(
    task_num: int | str, agent_name: str,
) -> str:
    """Integrate module merge output as a 2-parent destination-subgraph node."""
    wt = crew_worktree(task_num)
    group_name = _agent_to_group_name(agent_name)
    groups = _read_groups_file(str(wt / GROUPS_FILE)).get("groups", {})
    group_info = groups.get(group_name, {}) if isinstance(groups, dict) else {}
    source_module = str(group_info.get("source_subgraph") or "")
    destination_module = str(group_info.get("destination_subgraph") or "")
    if not source_module or not destination_module:
        raise ValueError("module_merge group missing source/destination subgraph")
    if not is_ancestor_subgraph(wt, source_module, destination_module):
        raise ValueError(
            f"module_merge refused: {destination_module!r} is not an ancestor "
            f"of {source_module!r}"
        )
    source_head = get_head(wt, module=source_module)
    destination_head = get_head(wt, module=destination_module)
    if not source_head or not destination_head:
        raise ValueError("module_merge requires source and destination HEADs")

    def parse_module_merger(
        text: str, err_log: Path, expected_role: str
    ) -> tuple[dict, str, dict]:
        node_data, proposal_text, extras = _parse_two_block_output(
            text, err_log, expected_role
        )
        node_data["parents"] = [destination_head, source_head]
        return node_data, proposal_text, extras

    new_id, node_data, extras = _apply_node_output(
        task_num,
        agent_name,
        expected_role="module_merger",
        parser=parse_module_merger,
    )
    _merge_new_dimensions(wt, extras["raw_text"])
    update_operation(
        task_num,
        group_name,
        agents_append=agent_name,
        nodes_created=new_id,
        status="Completed",
    )
    return new_id


def apply_module_syncer_output(
    task_num: int | str, agent_name: str,
) -> str:
    """Integrate module sync output as a single new node in the module subgraph.

    The synced node advances the module's own HEAD (single parent = the prior
    HEAD); ``_apply_node_output`` scopes the subgraph from the op's group, so the
    correct module HEAD is advanced. After apply, ``last_synced_at[module]`` is
    stamped so a re-sync's ``--since`` horizon only sees genuinely-newer commits.
    """
    wt = crew_worktree(task_num)
    group_name = _agent_to_group_name(agent_name)
    module = _group_subgraph(wt, group_name)
    source_head = get_head(wt, module=module)
    if not source_head:
        raise ValueError(f"module_sync requires a HEAD for subgraph {module!r}")

    def parse_module_syncer(
        text: str, err_log: Path, expected_role: str
    ) -> tuple[dict, str, dict]:
        node_data, proposal_text, extras = _parse_two_block_output(
            text, err_log, expected_role
        )
        node_data["parents"] = [source_head]
        return node_data, proposal_text, extras

    new_id, node_data, extras = _apply_node_output(
        task_num,
        agent_name,
        expected_role="module_syncer",
        parser=parse_module_syncer,
    )
    _merge_new_dimensions(wt, extras["raw_text"])
    _write_last_synced(wt, module, datetime.now().strftime("%Y-%m-%d %H:%M"))
    update_operation(
        task_num,
        group_name,
        agents_append=agent_name,
        nodes_created=new_id,
        status="Completed",
    )
    return new_id


_DETAILER_DELIMITERS = ("DETAILED_PLAN_START", "DETAILED_PLAN_END")


def _detailer_needs_apply(
    task_num: int | str, agent_name: str, target_node_id: str,
) -> bool:
    """Return True iff ``<agent_name>_output.md`` contains both DETAILED_PLAN
    delimiters AND its plan body differs from the plan already on disk for
    the target node.

    Guards against the registration-time placeholder ``_output.md`` written
    by ``aitask_crew_addwork.sh`` (no delimiters) and against re-applying an
    output the poller already ingested. The body-content comparison — rather
    than a bare "node already has plan_file" check — keeps re-detailing
    correct: a later detailer on the same node produces different content
    and is still applied.
    """
    wt = crew_worktree(task_num)
    out_path = wt / f"{agent_name}_output.md"
    if not out_path.is_file():
        return False
    try:
        text = out_path.read_text(encoding="utf-8")
    except Exception:
        return False
    if not _output_has_all_delimiters(text, _DETAILER_DELIMITERS):
        return False
    try:
        plan_text = _extract_block(
            text, "DETAILED_PLAN_START", "DETAILED_PLAN_END"
        )
    except ValueError:
        # Delimiters present but malformed — let the apply call log it.
        return True
    plan_path = wt / PLANS_DIR / f"{target_node_id}_plan.md"
    if not plan_path.is_file():
        return True
    try:
        existing = plan_path.read_text(encoding="utf-8")
    except Exception:
        return True
    return existing.strip("\n") != plan_text


def apply_detailer_output(
    task_num: int | str, agent_name: str, target_node_id: str,
) -> str:
    """Parse ``<agent_name>_output.md`` and attach the detailer's plan to an
    existing node.

    The detailer ENRICHES a node — unlike explorer/synthesizer/patcher it does
    NOT create a new node, advance ``current_head``, or consume a node id. The
    single delimited DETAILED_PLAN block is written to
    ``br_plans/<target_node_id>_plan.md`` and the node's ``plan_file`` field is
    set via :func:`update_node`.

    Returns:
        The relative plan path written (e.g. ``br_plans/n001_x_plan.md``).

    Raises:
        FileNotFoundError: output file missing OR target node missing.
        ValueError: DETAILED_PLAN delimiters missing or the plan body empty.
    """
    wt = crew_worktree(task_num)
    out_path = wt / f"{agent_name}_output.md"
    err_log = wt / f"{agent_name}_apply_error.log"
    if not out_path.is_file():
        raise FileNotFoundError(f"No detailer output at {out_path}")
    try:
        node_path = wt / NODES_DIR / f"{target_node_id}.yaml"
        if not node_path.is_file():
            raise FileNotFoundError(
                f"detailer target node not found: {target_node_id}"
            )

        text = out_path.read_text(encoding="utf-8")
        plan_text = _extract_block(
            text, "DETAILED_PLAN_START", "DETAILED_PLAN_END"
        )
        if not plan_text.strip():
            raise ValueError("detailer DETAILED_PLAN block is empty")

        plan_rel = f"{PLANS_DIR}/{target_node_id}_plan.md"
        (wt / PLANS_DIR).mkdir(parents=True, exist_ok=True)
        (wt / plan_rel).write_text(plan_text, encoding="utf-8")
        update_node(wt, target_node_id, {"plan_file": plan_rel})

        # The detailer enriches an existing node — record the agent and flip
        # the detail group Completed, but emit no nodes_created (no new node).
        update_operation(
            task_num,
            _agent_to_group_name(agent_name),
            agents_append=agent_name,
            status="Completed",
        )
        return plan_rel
    except Exception as exc:
        try:
            err_log.write_text(
                f"apply_detailer_output failed at "
                f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
                f"agent_name: {agent_name}\n"
                f"target_node_id: {target_node_id}\n\n"
                f"Error: {type(exc).__name__}: {exc}\n",
                encoding="utf-8",
            )
        except Exception:
            pass
        raise
