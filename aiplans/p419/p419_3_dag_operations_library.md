---
Task: t419_3_dag_operations_library.md
Parent Task: aitasks/t419_ait_brainstorm_architecture_design.md
Sibling Tasks: aitasks/t419/t419_1_*.md, aitasks/t419/t419_2_*.md, aitasks/t419/t419_4_*.md, aitasks/t419/t419_5_*.md, aitasks/t419/t419_6_*.md
Archived Sibling Plans: aiplans/archived/p419/p419_1_*.md
Worktree: (current branch)
Branch: (current branch)
Base branch: main
---

# Plan: DAG Operations Library

## Context
Python library for managing the brainstorm design space DAG. Depends on t419_1 (architecture spec) for data format definitions. Used by t419_4 (CLI scripts) and t419_6 (TUI).

## Steps

### Step 1: Create Module Structure
```bash
mkdir -p .aitask-scripts/brainstorm
```
Create `__init__.py` with version string.

### Step 2: brainstorm_schemas.py
Define schema constants and validation functions:

```python
NODE_REQUIRED_FIELDS = ["node_id", "parents", "description", "proposal_file"]
NODE_OPTIONAL_FIELDS = ["plan_file", "created_at", "created_by_group"]
# Dimension fields use prefixes: requirements_*, assumption_*, component_*, tradeoff_*

GRAPH_STATE_FIELDS = ["current_head", "history", "next_node_id", "active_dimensions"]

SESSION_FIELDS = ["task_id", "task_file", "status", "crew_id",
                  "created_at", "updated_at", "created_by", "initial_spec"]
SESSION_STATUSES = ["active", "paused", "completed", "archived"]

def validate_node(data: dict) -> list[str]:
    """Return list of validation errors (empty = valid)."""

def validate_graph_state(data: dict) -> list[str]:

def validate_session(data: dict) -> list[str]:
```

### Step 3: brainstorm_dag.py
Core DAG operations. Use `yaml.safe_load`/`yaml.safe_dump` for YAML I/O (same pattern as `agentcrew_utils.py`).

```python
from __future__ import annotations
import os
from pathlib import Path
import yaml
from datetime import datetime

def session_dir(task_num: int | str) -> Path:
    """Return path to .aitask-brainstorm/<task_num>/"""

def create_node(session_path: Path, node_id: str, parents: list[str],
                description: str, dimensions: dict,
                proposal_content: str, group_name: str = "") -> Path:
    """Create node YAML in nodes/ and proposal MD in proposals/. Returns node YAML path."""

def read_node(session_path: Path, node_id: str) -> dict:
    """Read and return node YAML as dict."""

def update_node(session_path: Path, node_id: str, updates: dict) -> None:
    """Update specific fields in node YAML."""

def list_nodes(session_path: Path) -> list[str]:
    """Return all node IDs sorted by filename (creation order)."""

def get_head(session_path: Path) -> str | None:
    """Read graph_state.yaml and return current HEAD node ID."""

def set_head(session_path: Path, node_id: str) -> None:
    """Update HEAD in graph_state.yaml and append to history."""

def get_parents(session_path: Path, node_id: str) -> list[str]:
    """Return parent node IDs from node YAML."""

def get_children(session_path: Path, node_id: str) -> list[str]:
    """Find all nodes that list this node as a parent."""

def next_node_id(session_path: Path) -> int:
    """Read, increment, and return next_node_id from graph_state.yaml."""

def get_node_lineage(session_path: Path, node_id: str) -> list[str]:
    """Trace ancestry back to root node (BFS). Returns list from root to node."""

def read_proposal(session_path: Path, node_id: str) -> str:
    """Read the proposal markdown file for a node."""

def read_plan(session_path: Path, node_id: str) -> str | None:
    """Read the plan markdown file for a node (None if doesn't exist)."""
```

### Step 4: brainstorm_session.py
Session lifecycle management.

```python
from __future__ import annotations
from pathlib import Path
import yaml
import shutil

BRAINSTORM_DIR = ".aitask-brainstorm"

def init_session(task_num: int | str, task_file: str,
                 user_email: str, initial_spec: str) -> Path:
    """Create session directory structure:
    .aitask-brainstorm/<task_num>/
      session.yaml, graph_state.yaml, nodes/, proposals/, plans/
    Returns session directory path."""

def load_session(task_num: int | str) -> dict:
    """Load and return session.yaml as dict."""

def save_session(task_num: int | str, updates: dict) -> None:
    """Update session.yaml fields (preserves existing, merges updates)."""

def session_exists(task_num: int | str) -> bool:
    """Check if session directory exists."""

def list_sessions() -> list[dict]:
    """List all sessions. Returns list of session.yaml dicts with task_num added."""

def finalize_session(task_num: int | str, plan_dest_dir: str = "aiplans") -> str:
    """Copy HEAD node's plan to aiplans/p<task_num>_<name>.md.
    Returns destination path."""

def archive_session(task_num: int | str) -> None:
    """Mark session as archived. Optionally move to archived location."""
```

### Step 5: Unit Tests
Create `tests/test_brainstorm_dag.sh`:
- Test init_session creates correct directory structure
- Test create_node creates both YAML and MD files
- Test read_node returns correct data
- Test set_head updates graph_state and appends to history
- Test get_children finds reverse references
- Test next_node_id increments correctly
- Test list_nodes returns sorted node IDs
- Test finalize_session copies plan to aiplans/

Use a temp directory for test isolation.

## Key Files
- `.aitask-scripts/brainstorm/__init__.py` — module init
- `.aitask-scripts/brainstorm/brainstorm_schemas.py` — validation
- `.aitask-scripts/brainstorm/brainstorm_dag.py` — DAG operations
- `.aitask-scripts/brainstorm/brainstorm_session.py` — session management
- `.aitask-scripts/agentcrew/agentcrew_utils.py` — reference for YAML I/O patterns

## Verification
- All unit tests pass
- create_node + read_node roundtrip preserves all fields
- set_head correctly maintains history list
- get_children correctly traverses parent references
- finalize_session produces valid aiplan file
- No import errors when importing from other scripts

## Post-Implementation
- Step 9: archive task, push changes
