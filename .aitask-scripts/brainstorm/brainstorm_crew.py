"""Agent registration helpers for the brainstorm engine.

Provides functions to register brainstorm agents (explorer, comparator,
synthesizer, detailer, patcher) into a brainstorm crew with properly
assembled input context.

Each register_* function:
1. Reads node data using brainstorm_dag functions
2. Assembles input markdown via _assemble_input_*
3. Calls ``ait crew addwork`` via subprocess
4. Overwrites the placeholder _input.md with assembled content
5. Returns the agent name
"""

from __future__ import annotations

import hashlib
import os
import subprocess
import sys
from pathlib import Path

# Allow importing sibling packages
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "lib"))

from config_utils import load_layered_config  # noqa: E402
from launch_modes import DEFAULT_LAUNCH_MODE, VALID_LAUNCH_MODES  # noqa: E402

from .brainstorm_dag import (  # noqa: E402
    NODES_DIR,
    PLANS_DIR,
    PROPOSALS_DIR,
    _read_graph_state,
    read_node,
)
from .brainstorm_schemas import extract_dimensions  # noqa: E402

TEMPLATE_DIR = Path(__file__).parent / "templates"

BRAINSTORM_AGENT_TYPES = {
    "explorer": {"agent_string": "claudecode/opus4_6", "max_parallel": 2, "launch_mode": "headless"},
    "comparator": {"agent_string": "claudecode/sonnet4_6", "max_parallel": 1, "launch_mode": "headless"},
    "synthesizer": {"agent_string": "claudecode/opus4_6", "max_parallel": 1, "launch_mode": "headless"},
    "detailer": {"agent_string": "claudecode/opus4_6", "max_parallel": 1, "launch_mode": "interactive"},
    "patcher": {"agent_string": "claudecode/sonnet4_6", "max_parallel": 1, "launch_mode": "headless"},
}

def get_agent_types(config_root: Path | None = None) -> dict[str, dict]:
    """Return brainstorm agent types with overrides from codeagent config.

    Reads brainstorm-<type> and brainstorm-<type>-launch-mode keys from
    codeagent_config.json (layered: project <- local). Falls back to
    BRAINSTORM_AGENT_TYPES hardcoded defaults for missing or invalid keys.

    Args:
        config_root: Repository root path. Defaults to two levels up from this file.
    """
    import copy
    result = copy.deepcopy(BRAINSTORM_AGENT_TYPES)
    if config_root is None:
        config_root = Path(__file__).resolve().parents[2]
    config_path = config_root / "aitasks" / "metadata" / "codeagent_config.json"
    try:
        config = load_layered_config(str(config_path))
        defaults = config.get("defaults", {})
        for agent_type, info in result.items():
            config_key = f"brainstorm-{agent_type}"
            if config_key in defaults:
                info["agent_string"] = defaults[config_key]
            launch_key = f"brainstorm-{agent_type}-launch-mode"
            if launch_key in defaults:
                val = defaults[launch_key]
                if isinstance(val, str) and val in VALID_LAUNCH_MODES:
                    info["launch_mode"] = val
                else:
                    print(
                        f"warning: invalid {launch_key}={val!r}, expected one of "
                        f"{sorted(VALID_LAUNCH_MODES)}; falling back to framework "
                        f"default ({info.get('launch_mode', DEFAULT_LAUNCH_MODE)})",
                        file=sys.stderr,
                    )
    except Exception:
        pass  # Fall back to hardcoded defaults
    return result


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _group_seq(group_name: str) -> str:
    """Extract the sequence part from a group name (e.g., 'explore_001' -> '001')."""
    if "_" in group_name:
        return group_name.split("_", 1)[1]
    return group_name


def _run_addwork(
    crew_id: str,
    agent_name: str,
    agent_type: str,
    group_name: str,
    work2do_path: Path,
    launch_mode: str = DEFAULT_LAUNCH_MODE,
) -> str:
    """Register agent via subprocess call to ait crew addwork.

    Returns:
        Agent name on success.

    Raises:
        RuntimeError: If addwork command fails.
    """
    cmd = [
        "./ait", "crew", "addwork",
        "--crew", crew_id,
        "--name", agent_name,
        "--work2do", str(work2do_path),
        "--type", agent_type,
        "--group", group_name,
        "--batch",
    ]
    type_default = BRAINSTORM_AGENT_TYPES.get(agent_type, {}).get(
        "launch_mode", DEFAULT_LAUNCH_MODE
    )
    if launch_mode != type_default:
        cmd.extend(["--launch-mode", launch_mode])
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(
            f"ait crew addwork failed for agent '{agent_name}': {result.stderr}"
        )
    for line in result.stdout.strip().splitlines():
        if line.startswith("ADDED:"):
            return line.split(":", 1)[1]
    return agent_name


def _write_agent_input(
    session_path: Path,
    agent_name: str,
    input_content: str,
) -> None:
    """Overwrite the agent's _input.md file with assembled content."""
    input_path = session_path / f"{agent_name}_input.md"
    input_path.write_text(input_content, encoding="utf-8")


def _format_reference_files(reference_files: list[str]) -> str:
    """Format reference_files into Local and Remote (cached) sections.

    Separates local file paths from URLs. For URLs, generates cache
    file path references with source URL annotation.
    """
    local_refs: list[str] = []
    remote_refs: list[str] = []
    for ref in reference_files:
        if ref.startswith("http://") or ref.startswith("https://"):
            url_hash = hashlib.md5(ref.encode()).hexdigest()[:8]
            cache_path = f"br_url_cache/{url_hash}.md"
            remote_refs.append(f"- {cache_path} (source: {ref})")
        else:
            local_refs.append(f"- {ref}")

    sections: list[str] = []
    if local_refs:
        sections.append("### Local\n" + "\n".join(local_refs))
    if remote_refs:
        sections.append("### Remote (cached)\n" + "\n".join(remote_refs))
    return "\n\n".join(sections)


# ---------------------------------------------------------------------------
# Input assembly (one per agent type)
# ---------------------------------------------------------------------------


def _assemble_input_explorer(
    session_path: Path,
    base_node_id: str,
    mandate: str,
    active_dimensions: list[str],
) -> str:
    """Assemble explorer _input.md content with file path references."""
    node_data = read_node(session_path, base_node_id)
    ref_files = node_data.get("reference_files", []) or []

    node_yaml_path = f"{session_path}/{NODES_DIR}/{base_node_id}.yaml"
    proposal_path = f"{session_path}/{PROPOSALS_DIR}/{base_node_id}.md"

    lines = [
        "# Explorer Input",
        "",
        "## Exploration Mandate",
        mandate,
        "",
        "## Baseline Node",
        f"- Metadata: {node_yaml_path}",
        f"- Proposal: {proposal_path}",
    ]

    plan_file = session_path / PLANS_DIR / f"{base_node_id}_plan.md"
    if plan_file.is_file():
        lines.append(f"- Plan: {session_path}/{PLANS_DIR}/{base_node_id}_plan.md")

    lines.extend(["", "## Reference Files"])
    if ref_files:
        lines.append(_format_reference_files(ref_files))
    else:
        lines.append("No reference files.")

    lines.extend([
        "",
        "## Active Dimensions",
        ", ".join(active_dimensions) if active_dimensions else "(none)",
    ])

    # Dimension keys for section markers
    dims = extract_dimensions(node_data)
    if dims:
        lines.extend(["", "## Dimension Keys",
                      "Use these dimension keys in section markers:"])
        for k in sorted(dims.keys()):
            lines.append(f"- {k}")

    return "\n".join(lines) + "\n"


def _assemble_input_comparator(
    session_path: Path,
    node_ids: list[str],
    dimensions: list[str],
) -> str:
    """Assemble comparator _input.md with node file paths and dimension list."""
    lines = [
        "# Comparator Input",
        "",
        "## Comparison Request",
        f"Nodes: {', '.join(node_ids)}",
        f"Dimensions: {', '.join(dimensions)}",
        "",
        "## Node Files",
    ]
    for nid in node_ids:
        lines.append(f"- {session_path}/{NODES_DIR}/{nid}.yaml")

    return "\n".join(lines) + "\n"


def _assemble_input_synthesizer(
    session_path: Path,
    parent_node_ids: list[str],
    merge_rules: str,
) -> str:
    """Assemble synthesizer _input.md with source node paths and merge rules."""
    lines = [
        "# Synthesizer Input",
        "",
        "## Merge Rules",
        merge_rules,
        "",
        "## Source Nodes",
    ]

    all_refs: list[str] = []
    seen_refs: set[str] = set()
    all_dims: dict[str, object] = {}

    for nid in parent_node_ids:
        node_data = read_node(session_path, nid)
        lines.extend([
            f"### {nid}",
            f"- Metadata: {session_path}/{NODES_DIR}/{nid}.yaml",
            f"- Proposal: {session_path}/{PROPOSALS_DIR}/{nid}.md",
            "",
        ])
        for ref in node_data.get("reference_files", []) or []:
            if ref not in seen_refs:
                seen_refs.add(ref)
                all_refs.append(ref)
        for dk, dv in extract_dimensions(node_data).items():
            if dk not in all_dims:
                all_dims[dk] = dv

    lines.append("## Reference Files (merged from all source nodes, deduplicated)")
    if all_refs:
        lines.append(_format_reference_files(all_refs))
    else:
        lines.append("No reference files.")

    if all_dims:
        lines.extend(["", "## Dimension Keys",
                      "Use these dimension keys in section markers:"])
        for k in sorted(all_dims.keys()):
            lines.append(f"- {k}")

    return "\n".join(lines) + "\n"


def _assemble_input_detailer(
    session_path: Path,
    node_id: str,
    codebase_paths: list[str],
) -> str:
    """Assemble detailer _input.md with node paths and codebase context."""
    node_data = read_node(session_path, node_id)
    ref_files = node_data.get("reference_files", []) or []

    lines = [
        "# Detailer Input",
        "",
        "## Target Node",
        f"- Metadata: {session_path}/{NODES_DIR}/{node_id}.yaml",
        f"- Proposal: {session_path}/{PROPOSALS_DIR}/{node_id}.md",
        "",
        "## Reference Files",
    ]
    if ref_files:
        lines.append(_format_reference_files(ref_files))
    else:
        lines.append("No reference files.")

    lines.extend(["", "## Project Context"])
    for cp in codebase_paths:
        lines.append(f"- {cp}")

    # Dimension keys for section markers
    dims = extract_dimensions(node_data)
    if dims:
        lines.extend(["", "## Dimension Keys",
                      "Use these dimension keys in section markers:"])
        for k in sorted(dims.keys()):
            lines.append(f"- {k}")

    return "\n".join(lines) + "\n"


def _assemble_input_patcher(
    session_path: Path,
    node_id: str,
    tweak_request: str,
) -> str:
    """Assemble patcher _input.md with current node paths and patch request."""
    lines = [
        "# Patcher Input",
        "",
        "## Patch Request",
        tweak_request,
        "",
        "## Current Node",
        f"- Metadata: {session_path}/{NODES_DIR}/{node_id}.yaml",
    ]

    plan_file = session_path / PLANS_DIR / f"{node_id}_plan.md"
    if plan_file.is_file():
        lines.append(
            f"- Plan: {session_path}/{PLANS_DIR}/{node_id}_plan.md"
            " (this is what the patcher modifies)"
        )

    lines.append(
        f"- Proposal: {session_path}/{PROPOSALS_DIR}/{node_id}.md"
        " (read-only, for impact analysis)"
    )

    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Registration functions
# ---------------------------------------------------------------------------


def register_explorer(
    session_dir: Path,
    crew_id: str,
    mandate: str,
    base_node_id: str,
    group_name: str,
    agent_suffix: str = "",
    launch_mode: str = DEFAULT_LAUNCH_MODE,
) -> str:
    """Register an Explorer agent in the brainstorm crew.

    Args:
        session_dir: Path to crew worktree.
        crew_id: Crew identifier (e.g., "brainstorm-419").
        mandate: Exploration mandate text.
        base_node_id: Node ID to explore from (baseline).
        group_name: Operation group name (e.g., "explore_001").
        agent_suffix: Optional letter suffix for parallel explorers (e.g., "a").
        launch_mode: Launch mode for the agent; one of VALID_LAUNCH_MODES
            (defaults to DEFAULT_LAUNCH_MODE).

    Returns:
        Agent name (e.g., "explorer_001a").
    """
    seq = _group_seq(group_name)
    agent_name = f"explorer_{seq}{agent_suffix}"

    gs = _read_graph_state(session_dir)
    active_dimensions = gs.get("active_dimensions", []) or []

    input_content = _assemble_input_explorer(
        session_dir, base_node_id, mandate, active_dimensions
    )

    work2do_path = TEMPLATE_DIR / "explorer.md"
    _run_addwork(
        crew_id, agent_name, "explorer", group_name, work2do_path,
        launch_mode=launch_mode,
    )
    _write_agent_input(session_dir, agent_name, input_content)

    return agent_name


def register_comparator(
    session_dir: Path,
    crew_id: str,
    node_ids: list[str],
    dimensions: list[str],
    group_name: str,
    launch_mode: str = DEFAULT_LAUNCH_MODE,
) -> str:
    """Register a Comparator agent in the brainstorm crew.

    Args:
        session_dir: Path to crew worktree.
        crew_id: Crew identifier.
        node_ids: List of node IDs to compare.
        dimensions: List of dimension keys to compare across nodes.
        group_name: Operation group name (e.g., "compare_001").
        launch_mode: Launch mode for the agent; one of VALID_LAUNCH_MODES
            (defaults to DEFAULT_LAUNCH_MODE).

    Returns:
        Agent name (e.g., "comparator_001").
    """
    seq = _group_seq(group_name)
    agent_name = f"comparator_{seq}"

    input_content = _assemble_input_comparator(session_dir, node_ids, dimensions)

    work2do_path = TEMPLATE_DIR / "comparator.md"
    _run_addwork(
        crew_id, agent_name, "comparator", group_name, work2do_path,
        launch_mode=launch_mode,
    )
    _write_agent_input(session_dir, agent_name, input_content)

    return agent_name


def register_synthesizer(
    session_dir: Path,
    crew_id: str,
    parent_node_ids: list[str],
    merge_rules: str,
    group_name: str,
    launch_mode: str = DEFAULT_LAUNCH_MODE,
) -> str:
    """Register a Synthesizer agent in the brainstorm crew.

    Args:
        session_dir: Path to crew worktree.
        crew_id: Crew identifier.
        parent_node_ids: List of source node IDs to merge.
        merge_rules: User's merge instructions.
        group_name: Operation group name (e.g., "hybridize_001").
        launch_mode: Launch mode for the agent; one of VALID_LAUNCH_MODES
            (defaults to DEFAULT_LAUNCH_MODE).

    Returns:
        Agent name (e.g., "synthesizer_001").
    """
    seq = _group_seq(group_name)
    agent_name = f"synthesizer_{seq}"

    input_content = _assemble_input_synthesizer(
        session_dir, parent_node_ids, merge_rules
    )

    work2do_path = TEMPLATE_DIR / "synthesizer.md"
    _run_addwork(
        crew_id, agent_name, "synthesizer", group_name, work2do_path,
        launch_mode=launch_mode,
    )
    _write_agent_input(session_dir, agent_name, input_content)

    return agent_name


def register_detailer(
    session_dir: Path,
    crew_id: str,
    node_id: str,
    codebase_paths: list[str],
    group_name: str,
    launch_mode: str = DEFAULT_LAUNCH_MODE,
) -> str:
    """Register a Detailer agent in the brainstorm crew.

    Args:
        session_dir: Path to crew worktree.
        crew_id: Crew identifier.
        node_id: Node ID to create an implementation plan for.
        codebase_paths: List of project context file paths.
        group_name: Operation group name (e.g., "detail_001").
        launch_mode: Launch mode for the agent; one of VALID_LAUNCH_MODES
            (defaults to DEFAULT_LAUNCH_MODE).

    Returns:
        Agent name (e.g., "detailer_001").
    """
    seq = _group_seq(group_name)
    agent_name = f"detailer_{seq}"

    input_content = _assemble_input_detailer(session_dir, node_id, codebase_paths)

    work2do_path = TEMPLATE_DIR / "detailer.md"
    _run_addwork(
        crew_id, agent_name, "detailer", group_name, work2do_path,
        launch_mode=launch_mode,
    )
    _write_agent_input(session_dir, agent_name, input_content)

    return agent_name


def register_patcher(
    session_dir: Path,
    crew_id: str,
    node_id: str,
    tweak_request: str,
    group_name: str,
    launch_mode: str = DEFAULT_LAUNCH_MODE,
) -> str:
    """Register a Plan Patcher agent in the brainstorm crew.

    Args:
        session_dir: Path to crew worktree.
        crew_id: Crew identifier.
        node_id: Node ID whose plan needs patching.
        tweak_request: User's specific edit request.
        group_name: Operation group name (e.g., "patch_001").
        launch_mode: Launch mode for the agent; one of VALID_LAUNCH_MODES
            (defaults to DEFAULT_LAUNCH_MODE).

    Returns:
        Agent name (e.g., "patcher_001").
    """
    seq = _group_seq(group_name)
    agent_name = f"patcher_{seq}"

    input_content = _assemble_input_patcher(session_dir, node_id, tweak_request)

    work2do_path = TEMPLATE_DIR / "patcher.md"
    _run_addwork(
        crew_id, agent_name, "patcher", group_name, work2do_path,
        launch_mode=launch_mode,
    )
    _write_agent_input(session_dir, agent_name, input_content)

    return agent_name
