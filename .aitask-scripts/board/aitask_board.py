from __future__ import annotations

import os
import re
import sys
import yaml
import json
import glob
import subprocess
from datetime import datetime
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))
from rich.markup import escape
from config_utils import load_layered_config, split_config, save_project_config, save_local_config, local_path_for, task_dir
from agent_command_screen import AgentCommandScreen, resolve_skill_profile
from agent_launch_utils import find_terminal, spawn_in_terminal, find_window_by_name, resolve_dry_run_command, resolve_agent_string, TmuxLaunchConfig, launch_in_tmux, launch_or_focus_codebrowser, load_tmux_defaults, maybe_spawn_minimonitor, _lookup_window_name, tmux_window_target
from sync_action_runner import (
    SyncConflictScreen,
    run_sync_batch,
    run_interactive_sync,
    STATUS_AUTOMERGED,
    STATUS_CONFLICT,
    STATUS_ERROR,
    STATUS_NOTHING,
    STATUS_NO_NETWORK,
    STATUS_NO_REMOTE,
    STATUS_NOT_FOUND,
    STATUS_PULLED,
    STATUS_PUSHED,
    STATUS_SYNCED,
    STATUS_TIMEOUT,
)
from tui_switcher import TuiSwitcherMixin, TuiSwitcherOverlay
from shortcuts_mixin import ShortcutsMixin, get_label
from cross_repo_notation import parse as parse_cross_repo_notation
from task_levels import LEVELS_ASCENDING
from archive_iter import find_archived_markdown_by_id
import gate_ledger

from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, HorizontalScroll, VerticalScroll
from textual.widgets import Header, Footer, Static, Label, Markdown, Input, Button, LoadingIndicator, SelectionList, DataTable, Collapsible
from textual.widgets.selection_list import Selection
from textual.screen import Screen, ModalScreen
from textual.binding import Binding
from textual.message import Message
from textual import on, work
from textual.compose import compose as _compose_widgets
from textual.command import Provider, Hit, Hits, DiscoveryHit

from task_yaml import (
    _TaskSafeLoader, _FlowListDumper, _normalize_task_ids,
    FRONTMATTER_RE, BOARD_KEYS,
    parse_frontmatter, serialize_frontmatter,
)

# --- Configuration & Constants ---

TASKS_DIR = task_dir()
METADATA_FILE = TASKS_DIR / "metadata" / "board_config.json"
_PROJECT_KEYS = {"columns", "column_order"}
_USER_KEYS = {"settings"}
TASK_TYPES_FILE = TASKS_DIR / "metadata" / "task_types.txt"
DATA_WORKTREE = Path(".aitask-data")
USERCONFIG_FILE = TASKS_DIR / "metadata" / "userconfig.yaml"
EMAILS_FILE = TASKS_DIR / "metadata" / "emails.txt"
CODEAGENT_SCRIPT = Path(".aitask-scripts") / "aitask_codeagent.sh"
CREATE_SCRIPT = Path(".aitask-scripts") / "aitask_create.sh"
BRAINSTORM_TUI_SCRIPT = Path(".aitask-scripts") / "aitask_brainstorm_tui.sh"
GATES_REGISTRY_FILE = TASKS_DIR / "metadata" / "gates.yaml"


@dataclass
class GateStateResult:
    state: gate_ledger.TaskGateState | None = None
    error: str = ""
    has_ledger: bool = False


@dataclass
class InFlightItem:
    task: "Task"
    task_id: str
    title: str
    group: str
    next_action: str
    gate_summary: str
    human_gates: list[str] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)
    state_error: str = ""
    has_ledger: bool = False

def _task_git_cmd() -> list[str]:
    """Return git command prefix for task data operations.
    In branch mode: ["git", "-C", ".aitask-data"]
    In legacy mode: ["git"]
    """
    if DATA_WORKTREE.exists() and (DATA_WORKTREE / ".git").exists():
        return ["git", "-C", str(DATA_WORKTREE)]
    return ["git"]

def _sanitize_name(name: str) -> str:
    """Sanitize task name: lowercase, underscores, alphanumeric only, max 60 chars."""
    name = name.lower().replace(" ", "_")
    name = re.sub(r'[^a-z0-9_]', '', name)
    name = re.sub(r'_+', '_', name)
    name = name.strip("_")
    return name[:60]


def _task_id_sort_key(task_id: str):
    parts = str(task_id).lstrip("t").split("_")
    key = []
    for part in parts:
        key.append(int(part) if part.isdigit() else part)
    return key

def _load_task_types() -> list:
    """Load valid task types from task_types.txt, with fallback defaults."""
    try:
        if TASK_TYPES_FILE.exists():
            types = sorted(set(
                line.strip() for line in TASK_TYPES_FILE.read_text().splitlines()
                if line.strip()
            ))
            if types:
                return types
    except OSError:
        pass
    return ["bug", "feature", "refactor"]

DEFAULT_COLUMNS = [
    {"id": "now", "title": "Now ⚡", "color": "#FF5555"},
    {"id": "next", "title": "Next Week 📅", "color": "#50FA7B"},
    {"id": "backlog", "title": "Backlog 🗄️", "color": "#BD93F9"},
]
DEFAULT_ORDER = ["now", "next", "backlog"]

def _issue_indicator(url: str) -> str:
    """Return a short colored indicator based on issue URL platform."""
    from urllib.parse import urlparse
    host = urlparse(url).hostname or ""
    if "github" in host:
        return "[blue]GH[/blue]"
    elif "gitlab" in host:
        return "[#e24329]GL[/e24329]"
    elif "bitbucket" in host:
        return "[blue]BB[/blue]"
    return "[blue]Issue[/blue]"

def _pr_indicator(url: str) -> str:
    """Return a short colored indicator based on pull request URL platform."""
    from urllib.parse import urlparse
    host = urlparse(url).hostname or ""
    if "github" in host:
        return "[green]PR:GH[/green]"
    elif "gitlab" in host:
        return "[#e24329]MR:GL[/e24329]"
    elif "bitbucket" in host:
        return "[blue]PR:BB[/blue]"
    return "[green]PR[/green]"

def _get_user_email() -> str:
    """Read the current user's email from userconfig.yaml, falling back to emails.txt."""
    try:
        if USERCONFIG_FILE.exists():
            for line in USERCONFIG_FILE.read_text().splitlines():
                if line.startswith("email:"):
                    email = line.split(":", 1)[1].strip()
                    if email:
                        return email
    except OSError:
        pass
    try:
        if EMAILS_FILE.exists():
            for line in EMAILS_FILE.read_text().splitlines():
                if line.strip():
                    return line.strip()
    except OSError:
        pass
    return ""


# --- Data Models & Logic ---

class Task:
    _BOARD_KEYS = BOARD_KEYS

    def __init__(self, filepath: Path):
        self.filepath = filepath
        self.filename = filepath.name
        self.content = ""
        self.metadata = {}
        self._original_key_order: list = []
        self.archived = False
        self.load()

    @classmethod
    def from_text(cls, filepath: Path, raw: str, archived: bool = False) -> "Task":
        task = cls.__new__(cls)
        task.filepath = filepath
        task.filename = filepath.name
        task.content = ""
        task.metadata = {}
        task._original_key_order = []
        task.archived = archived
        result = parse_frontmatter(raw)
        if result:
            task.metadata, task.content, task._original_key_order = result
        else:
            task.content = raw
        return task

    def load(self):
        """Load task from disk. Returns True on success, False on failure."""
        if self.archived and not self.filepath.exists():
            return True
        try:
            with open(self.filepath, "r", encoding="utf-8") as f:
                raw = f.read()

            result = parse_frontmatter(raw)
            if result:
                self.metadata, self.content, self._original_key_order = result
            else:
                self.metadata = {}
                self._original_key_order = []
                self.content = raw
            return True
        except Exception as e:
            self.metadata = {}
            self._original_key_order = []
            self.content = str(e)
            return False

    def save(self):
        content = serialize_frontmatter(self.metadata, self.content, self._original_key_order)
        with open(self.filepath, "w", encoding="utf-8") as f:
            f.write(content)

    def _update_timestamp(self):
        """Update the updated_at metadata field to current time."""
        self.metadata["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M")

    def save_with_timestamp(self):
        """Save task with updated_at timestamp. Use for semantic metadata changes."""
        self._update_timestamp()
        self.save()

    def reload_and_save_board_fields(self):
        """Reload task from disk, re-apply current board fields, and save.

        Prevents overwriting external changes to non-board fields (e.g. status
        set by Claude Code) during board layout operations.
        Skips save if file no longer exists (e.g. archived/deleted).
        """
        current_boardcol = self.metadata.get("boardcol")
        current_boardidx = self.metadata.get("boardidx")
        if not self.load():
            return  # File gone (archived/deleted) — do NOT recreate it
        if current_boardcol is not None:
            self.metadata["boardcol"] = current_boardcol
        if current_boardidx is not None:
            self.metadata["boardidx"] = current_boardidx
        self.save()

    @property
    def board_col(self):
        return self.metadata.get("boardcol", "unordered")

    @board_col.setter
    def board_col(self, value):
        self.metadata["boardcol"] = value

    @property
    def board_idx(self):
        return self.metadata.get("boardidx", 0)

    @board_idx.setter
    def board_idx(self, value):
        self.metadata["boardidx"] = value


# --- Topic grouping (group-by-anchor) ---
# Pure, import-testable core for the board's by-topic view. No widget
# dependencies — operates on Task objects via their filename + metadata, so it
# is unit-tested in isolation (tests/test_board_topic_group.py).

def _bare_topic_id(value):
    """Canonicalize a task-id / anchor value to bare string form (leading 't'
    stripped). Returns None for empty/None so 'no anchor' reads uniformly."""
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None
    return s.lstrip("t")


def task_own_id(task):
    """Bare own id from a task's filename ('1016' or '1016_4'); '' if unparseable."""
    num, _ = TaskCard._parse_filename(task.filename)
    return num.lstrip("t")


def task_anchor_id(task):
    """Bare anchor id of a task, or None when the task is its own topic root."""
    return _bare_topic_id(task.metadata.get("anchor"))


def topic_key(task, tasks_by_id):
    """Topic-group key for a task.

    ``anchor`` if set; elif the task is a child → its parent's topic key
    (parent.anchor or parent id) as a *display-time* fallback so legacy
    parent+children trees cluster with no file migration; else the task's
    own id. ``tasks_by_id`` maps bare own id → Task (for the parent lookup).
    """
    anchor = task_anchor_id(task)
    if anchor:
        return anchor
    own = task_own_id(task)
    if own and "_" in own:
        parent = own.split("_", 1)[0]
        parent_task = tasks_by_id.get(parent)
        if parent_task is not None:
            return task_anchor_id(parent_task) or parent
        return parent  # parent not loaded → still cluster under its id
    return own


def _topic_lane_label(key, members, tasks_by_id):
    """Lane label: the root task's title when the root is present, else the
    first member's title — the id ``key`` stays the stable lane key either way."""
    root = tasks_by_id.get(key)
    source = root if root is not None else (members[0] if members else None)
    if source is not None:
        _, name = TaskCard._parse_filename(source.filename)
        if name:
            return f"t{key} {name}"
    return f"t{key}"


def _task_recency(task):
    """Recency sort key for a task: the newest of updated_at / created_at, or
    '' when neither is set. Timestamps are 'YYYY-MM-DD HH:MM' strings, so a
    lexicographic comparison is chronological."""
    return str(task.metadata.get("updated_at")
               or task.metadata.get("created_at") or "")


def _lane_recency(members):
    """Recency of a lane = the newest recency among its members."""
    return max((_task_recency(m) for m in members), default="")


def group_tasks_by_topic(tasks):
    """Bucket tasks into per-anchor topic lanes.

    Returns an ordered list of ``(label, [tasks])`` lanes. A bucket with >= 2
    members becomes its own lane; singleton buckets collapse into a trailing
    ``("Ungrouped", [...])`` lane. First-seen order is preserved.
    """
    tasks_by_id = {}
    for task in tasks:
        own = task_own_id(task)
        if own:
            tasks_by_id.setdefault(own, task)

    buckets = {}
    order = []
    for task in tasks:
        key = topic_key(task, tasks_by_id)
        if key not in buckets:
            buckets[key] = []
            order.append(key)
        buckets[key].append(task)

    topic_lanes = []
    ungrouped = []
    for key in order:
        members = buckets[key]
        if len(members) >= 2:
            topic_lanes.append(
                (_topic_lane_label(key, members, tasks_by_id), members))
        else:
            ungrouped.extend(members)

    # Default ordering: most-recently-touched topic first (the newest member's
    # updated_at/created_at). Stable, so topics with equal/absent timestamps keep
    # their first-seen order. Selectable sort modes are a planned follow-up.
    topic_lanes.sort(key=lambda lane: _lane_recency(lane[1]), reverse=True)

    lanes = topic_lanes
    if ungrouped:
        lanes.append(("Ungrouped", ungrouped))
    return lanes


class TaskManager:
    def __init__(self):
        self.task_datas: dict[str, Task] = {} # Filename -> Task (parents)
        self.child_task_datas: dict[str, Task] = {} # Filename -> Task (children)
        self.archived_task_cache: dict[str, Task | None] = {}
        self.columns: list[dict] = []
        self.column_order: list[str] = []
        self.modified_files: set = set()  # Relative paths of git-modified .md files
        self.lock_map: dict[str, dict] = {}  # task_id -> {locked_by, locked_at, hostname}
        # Cross-repo dependency status cache: (repo, task_id) -> status string.
        # Populated lazily during card render and cleared each full refresh so
        # the task-status probe does not fire per redraw.
        self.xdep_status_cache: dict[tuple[str, str], str] = {}
        self.gate_state_cache: dict[str, GateStateResult] = {}
        self.gate_registry_cache: dict[str, dict] | None = None
        self.gate_registry_error = ""
        self.settings: dict = {}
        self._ensure_paths()
        self.load_metadata()
        self.load_tasks()

    def _ensure_paths(self):
        TASKS_DIR.mkdir(exist_ok=True)
        METADATA_FILE.parent.mkdir(exist_ok=True)

    def load_metadata(self):
        defaults = {
            "columns": DEFAULT_COLUMNS,
            "column_order": DEFAULT_ORDER,
            "settings": {"auto_refresh_minutes": 0},
        }
        config = load_layered_config(str(METADATA_FILE), defaults=defaults)
        self.columns = config.get("columns", DEFAULT_COLUMNS)
        self.column_order = config.get("column_order", DEFAULT_ORDER)
        self.settings = config.get("settings", {"auto_refresh_minutes": 0})
        if not METADATA_FILE.exists():
            self.save_metadata()

    def save_metadata(self):
        data = {
            "columns": self.columns,
            "column_order": self.column_order,
            "settings": self.settings,
        }
        project_data, user_data = split_config(data, project_keys=_PROJECT_KEYS, user_keys=_USER_KEYS)
        save_project_config(str(METADATA_FILE), project_data)
        if user_data:
            save_local_config(str(local_path_for(str(METADATA_FILE))), user_data)

    @property
    def auto_refresh_minutes(self) -> int:
        return self.settings.get("auto_refresh_minutes", 0)

    @auto_refresh_minutes.setter
    def auto_refresh_minutes(self, value: int):
        self.settings["auto_refresh_minutes"] = value

    def _is_phantom_stub(self, task):
        """Check if a task file is a phantom stub (only board layout keys)."""
        return not task.metadata or set(task.metadata.keys()) <= set(BOARD_KEYS)

    def load_tasks(self):
        self.task_datas.clear()
        self.archived_task_cache.clear()
        self.clear_gate_cache()
        for f in glob.glob(str(TASKS_DIR / "*.md")):
            path = Path(f)
            task = Task(path)
            if self._is_phantom_stub(task):
                continue
            self.task_datas[path.name] = task
        self.load_child_tasks()

    def load_child_tasks(self):
        self.child_task_datas.clear()
        for f in glob.glob(str(TASKS_DIR / "t*" / "t*_*.md")):
            path = Path(f)
            task = Task(path)
            if self._is_phantom_stub(task):
                continue
            self.child_task_datas[path.name] = task

    def reload_task(self, filename: str) -> bool:
        """Reload a single task from disk. Returns True if present after reload."""
        if filename in self.task_datas:
            task = self.task_datas[filename]
            if not task.filepath.exists() or not task.load() or self._is_phantom_stub(task):
                del self.task_datas[filename]
                return False
            return True
        if filename in self.child_task_datas:
            task = self.child_task_datas[filename]
            if not task.filepath.exists() or not task.load() or self._is_phantom_stub(task):
                del self.child_task_datas[filename]
                return False
            return True
        # Not in memory — try to discover and load as parent
        path = TASKS_DIR / filename
        if path.exists():
            task = Task(path)
            if not self._is_phantom_stub(task):
                self.task_datas[filename] = task
                return True
        # Try child path pattern: t47_1_desc.md → aitasks/t47/t47_1_desc.md
        m = re.match(r'^(t\d+)_\d+_', filename)
        if m:
            child_path = TASKS_DIR / m.group(1) / filename
            if child_path.exists():
                task = Task(child_path)
                if not self._is_phantom_stub(task):
                    self.child_task_datas[filename] = task
                    return True
        return False

    def find_task_by_id(self, task_id: str):
        """Find a task (parent or child) by its ID like 't47' or 't47_1'."""
        prefix = f"{task_id}_"
        for filename, task in self.task_datas.items():
            if filename.startswith(prefix):
                return task
        for filename, task in self.child_task_datas.items():
            if filename.startswith(prefix):
                return task
        return None

    def find_task_including_archived(self, task_id: str):
        """Find an active task first, then lazily resolve archived tasks."""
        active = self.find_task_by_id(task_id)
        if active:
            return active

        normalized = str(task_id).lstrip("t")
        if normalized not in self.archived_task_cache:
            self.archived_task_cache[normalized] = self._load_archived_task(normalized)
        return self.archived_task_cache[normalized]

    def _load_archived_task(self, normalized_task_id: str):
        archived = find_archived_markdown_by_id(
            normalized_task_id,
            TASKS_DIR / "archived",
        )
        if not archived:
            return None
        filename, raw = archived
        if "_" in normalized_task_id:
            parent = normalized_task_id.split("_", 1)[0]
            path = TASKS_DIR / "archived" / f"t{parent}" / filename
        else:
            path = TASKS_DIR / "archived" / filename
        task = Task.from_text(path, raw, archived=True)
        if self._is_phantom_stub(task):
            return None
        return task

    def get_child_tasks_for_parent(self, parent_num: str) -> list[Task]:
        """Get all child tasks for a parent like 't47'."""
        prefix = f"{parent_num}_"
        children = []
        for filename, task in self.child_task_datas.items():
            if filename.startswith(prefix):
                children.append(task)

        def child_sort_key(task: Task):
            match = re.match(rf"^{re.escape(parent_num)}_(\d+)_", task.filename)
            if match:
                return (0, int(match.group(1)), task.filename)
            return (1, 0, task.filename)

        return sorted(children, key=child_sort_key)

    def get_parent_num_for_child(self, child_task: Task) -> str:
        """Determine parent task number from child task filepath.
        e.g., aitasks/t47/t47_1_desc.md -> 't47'"""
        return child_task.filepath.parent.name

    def get_column_tasks(self, col_id: str) -> list[Task]:
        # Filter tasks by column and sort by index
        tasks = [t for t in self.task_datas.values() if t.board_col == col_id]
        return sorted(tasks, key=lambda t: t.board_idx)

    def refresh_git_status(self):
        """Query git for modified files in aitasks/ directory."""
        self.modified_files.clear()
        try:
            result = subprocess.run(
                [*_task_git_cmd(), "status", "--porcelain", "--", "aitasks/"],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                for line in result.stdout.splitlines():
                    if not line or len(line) < 4:
                        continue
                    # Porcelain format: XY <space> filepath
                    # XY is 2 chars (index + worktree status), then a space
                    filepath = line[3:]
                    if filepath.startswith('"') and filepath.endswith('"'):
                        filepath = filepath[1:-1]
                    if filepath.endswith('.md'):
                        self.modified_files.add(filepath)
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

    def refresh_lock_map(self):
        """Query aitask_lock.sh --list to build a map of locked tasks."""
        self.lock_map.clear()
        try:
            result = subprocess.run(
                ["./.aitask-scripts/aitask_lock.sh", "--list"],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0:
                for line in result.stdout.splitlines():
                    m = re.match(
                        r'^t(\S+): locked by (.+?) on (.+?) since (.+)$',
                        line.strip()
                    )
                    if m:
                        self.lock_map[m.group(1)] = {
                            "locked_by": m.group(2),
                            "hostname": m.group(3),
                            "locked_at": m.group(4),
                        }
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            pass

    def clear_gate_cache(self):
        self.gate_state_cache.clear()
        self.gate_registry_cache = None
        self.gate_registry_error = ""

    def gate_registry(self) -> dict[str, dict]:
        """Read gates.yaml once per refresh; missing/invalid registry is safe."""
        if self.gate_registry_cache is not None:
            return self.gate_registry_cache
        try:
            self.gate_registry_cache = gate_ledger.read_registry(str(GATES_REGISTRY_FILE))
            self.gate_registry_error = ""
        except Exception as exc:
            self.gate_registry_cache = {}
            self.gate_registry_error = str(exc)
        return self.gate_registry_cache

    def gate_state_for(self, task: Task) -> GateStateResult:
        """Return cached gate derivation for a task, failing closed on errors."""
        key = str(task.filepath)
        cached = self.gate_state_cache.get(key)
        if cached is not None:
            return cached
        has_ledger = False
        try:
            has_ledger = gate_ledger.has_gate_markers(task.content or "")
            state = gate_ledger.read_task_gate_state(
                str(task.filepath), str(GATES_REGISTRY_FILE)
            )
            result = GateStateResult(state=state, has_ledger=has_ledger)
        except Exception as exc:
            result = GateStateResult(error=str(exc), has_ledger=has_ledger)
        self.gate_state_cache[key] = result
        return result

    def dependency_released_by_gates(self, task: Task) -> bool:
        """Whether an active upstream dependency is satisfied for dependents."""
        result = self.gate_state_for(task)
        return bool(result.state and result.state.dependents_decision == "SATISFIED")

    def unresolved_local_deps(self, task: Task) -> list[str]:
        unresolved = []
        for d in task.metadata.get('depends', []) or []:
            d_str = str(d)
            dep_id = d_str if d_str.startswith('t') else f"t{d_str}"
            dep_task = self.find_task_by_id(dep_id)
            if dep_task and dep_task.metadata.get('status') != 'Done' \
                    and not self.dependency_released_by_gates(dep_task):
                unresolved.append(dep_id)
        return unresolved

    def cross_repo_dep_display(self, task: Task) -> tuple[list[str], bool]:
        xdep_display = []
        xdep_blocked = False
        xdeprepo = task.metadata.get('xdeprepo')
        xdeps = task.metadata.get('xdeps', []) or []
        if xdeprepo and xdeps:
            for xd in xdeps:
                xid = str(xd).lstrip('t')
                ref = f"{xdeprepo}#{xid}"
                xstatus = self.get_xdep_status(xdeprepo, xid)
                if xstatus == 'Done':
                    xdep_display.append(ref)
                elif not xstatus or xstatus == 'NOT_FOUND':
                    xdep_display.append(f"{ref} (UNREACHABLE)")
                    xdep_blocked = True
                else:
                    xdep_display.append(f"{ref} [{xstatus}]")
                    xdep_blocked = True
        return xdep_display, xdep_blocked

    def _gate_summary(self, result: GateStateResult) -> str:
        state = result.state
        if result.error:
            return "gate state unavailable"
        if not result.has_ledger:
            return "no gate ledger"
        if not state or not state.current:
            return "no recorded gates"
        parts = []
        for run in state.current.values():
            parts.append(f"{run.icon} {run.name}:{run.status}")
        return "  ".join(parts)

    def _human_pending_gates(self, result: GateStateResult) -> list[str]:
        state = result.state
        if not state:
            return []
        registry = self.gate_registry()
        gates = []
        for gate in state.declared_gates:
            meta = registry.get(gate, {})
            if meta.get("type") != "human":
                continue
            current = state.current.get(gate)
            if current is None or current.status != "pass":
                gates.append(gate)
        return gates

    def _has_failed_gate(self, result: GateStateResult) -> bool:
        state = result.state
        return bool(state and any(
            run.status in ("fail", "error") for run in state.current.values()
        ))

    def _inflight_item_for(self, task: Task) -> InFlightItem | None:
        if task.metadata.get("status") != "Implementing":
            return None
        task_id, title = TaskCard._parse_filename(task.filename)
        if not task_id:
            return None
        result = self.gate_state_for(task)
        blockers = self.unresolved_local_deps(task)
        xdep_display, xdep_blocked = self.cross_repo_dep_display(task)
        if xdep_blocked:
            blockers.extend(xdep_display)

        human_gates = self._human_pending_gates(result)
        failed = self._has_failed_gate(result)
        state = result.state

        if blockers:
            group = "blocked"
            next_action = "blocked by dependencies"
        elif result.error:
            group = "agent"
            next_action = "gate state unavailable"
        elif not result.has_ledger:
            group = "agent"
            next_action = "no gate ledger — pick/resume"
        elif state and state.archive_decision == "ALL_PASS":
            group = "human"
            next_action = "all gates pass — archive/re-enter"
        elif state and state.resume_point == "POSTIMPL":
            group = "human"
            next_action = "reviewed — post-implementation"
        elif failed:
            group = "human"
            next_action = "failed gate — inspect/sign off or fail"
        elif human_gates:
            group = "human"
            next_action = "pending human gate"
        elif state and state.resume_point == "IMPLEMENT":
            group = "agent"
            next_action = "plan approved — resume implementation"
        else:
            group = "agent"
            next_action = "resume or continue planning"

        return InFlightItem(
            task=task,
            task_id=task_id,
            title=title,
            group=group,
            next_action=next_action,
            gate_summary=self._gate_summary(result),
            human_gates=human_gates,
            blockers=blockers,
            state_error=result.error,
            has_ledger=result.has_ledger,
        )

    def get_inflight_items(self) -> list[InFlightItem]:
        items = []
        for task in self.task_datas.values():
            item = self._inflight_item_for(task)
            if item:
                items.append(item)
        for task in self.child_task_datas.values():
            item = self._inflight_item_for(task)
            if item:
                items.append(item)
        return sorted(items, key=lambda item: _task_id_sort_key(item.task_id))

    def get_xdep_status(self, repo: str, task_id: str) -> str:
        """Live status of a cross-repo dependency, cached per refresh cycle.

        Shells out to ``aitask_query_files.sh --project <repo> task-status
        <id>`` (cross-repo re-exec resolves <repo> via the registry). Returns
        the cross-repo task's status (e.g. ``Implementing``, ``Done``),
        ``NOT_FOUND`` when the project resolves but the task is missing, or
        ``""`` (empty) when the project is unreachable (stale/unregistered)
        or the probe fails — callers treat both empty and ``NOT_FOUND`` as
        UNREACHABLE. Results are cached in ``self.xdep_status_cache`` keyed
        by ``(repo, task_id)`` so the probe does not fire per redraw.
        """
        key = (repo, task_id)
        if key in self.xdep_status_cache:
            return self.xdep_status_cache[key]
        status = ""
        try:
            result = subprocess.run(
                ["./.aitask-scripts/aitask_query_files.sh",
                 "--project", repo, "task-status", task_id],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0:
                for line in result.stdout.splitlines():
                    line = line.strip()
                    if line.startswith("STATUS:"):
                        status = line[len("STATUS:"):].strip()
                        break
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            status = ""
        self.xdep_status_cache[key] = status
        return status

    def is_modified(self, task: Task) -> bool:
        """Check if a task file is modified vs git."""
        return str(task.filepath) in self.modified_files

    def get_modified_tasks(self) -> list[Task]:
        """Get all tasks (parent and child) that have git modifications."""
        modified = []
        for filename, task in self.task_datas.items():
            if self.is_modified(task):
                modified.append(task)
        for filename, task in self.child_task_datas.items():
            if self.is_modified(task):
                modified.append(task)
        return modified

    def move_task_col(self, task_name: str, new_col: str):
        task = self.task_datas.get(task_name)
        if task:
            # Calculate new index before changing column to avoid counting self
            existing = self.get_column_tasks(new_col)
            max_idx = max((t.board_idx for t in existing), default=0)
            task.board_col = new_col
            task.board_idx = max_idx + 10
            task.reload_and_save_board_fields()

    def swap_tasks(self, task1_name: str, task2_name: str):
        t1 = self.task_datas.get(task1_name)
        t2 = self.task_datas.get(task2_name)
        if t1 and t2:
            t1.board_idx, t2.board_idx = t2.board_idx, t1.board_idx
            t1.reload_and_save_board_fields()
            t2.reload_and_save_board_fields()

    def normalize_indices(self, col_id: str):
        """Re-number tasks in a column to 10, 20, 30... to prevent index drift."""
        tasks = self.get_column_tasks(col_id)
        for i, task in enumerate(tasks):
            new_idx = (i + 1) * 10
            if task.board_idx != new_idx:
                task.board_idx = new_idx
                task.reload_and_save_board_fields()

    def add_column(self, col_id: str, title: str, color: str):
        """Add a new column to the board configuration."""
        self.columns.append({"id": col_id, "title": title, "color": color})
        self.column_order.append(col_id)
        self.save_metadata()

    def update_column(self, col_id: str, new_id: str, new_title: str, new_color: str):
        """Update id, title, and color of an existing column."""
        for col in self.columns:
            if col["id"] == col_id:
                col["id"] = new_id
                col["title"] = new_title
                col["color"] = new_color
                break
        if col_id != new_id:
            # Update column_order
            idx = self.column_order.index(col_id) if col_id in self.column_order else -1
            if idx >= 0:
                self.column_order[idx] = new_id
            # Reassign tasks from old ID to new ID
            for task in self.get_column_tasks(col_id):
                task.board_col = new_id
                task.reload_and_save_board_fields()
        self.save_metadata()

    @property
    def collapsed_columns(self) -> list[str]:
        """Return list of currently collapsed column IDs."""
        return self.settings.get("collapsed_columns", [])

    @collapsed_columns.setter
    def collapsed_columns(self, value: list[str]):
        self.settings["collapsed_columns"] = value

    def toggle_column_collapsed(self, col_id: str):
        """Toggle collapse state for a column and persist."""
        collapsed = list(self.collapsed_columns)
        if col_id in collapsed:
            collapsed.remove(col_id)
        else:
            collapsed.append(col_id)
        self.collapsed_columns = collapsed
        self.save_metadata()

    def is_column_collapsed(self, col_id: str) -> bool:
        return col_id in self.collapsed_columns

    def delete_column(self, col_id: str):
        """Delete a column and reassign its tasks to 'unordered'."""
        for task in self.get_column_tasks(col_id):
            task.board_col = "unordered"
            task.board_idx = 0
            task.reload_and_save_board_fields()
        self.columns = [c for c in self.columns if c["id"] != col_id]
        if col_id in self.column_order:
            self.column_order.remove(col_id)
        # Clean up collapsed state
        collapsed = list(self.collapsed_columns)
        if col_id in collapsed:
            collapsed.remove(col_id)
            self.collapsed_columns = collapsed
        self.save_metadata()

    def get_column_conf(self, col_id: str):
        """Return the config dict for a column, or None."""
        return next((c for c in self.columns if c["id"] == col_id), None)

# --- UI Components ---

class CollapseToggleButton(Static):
    """A small button to toggle column collapse/expand."""

    can_focus = False

    def __init__(self, col_id: str, is_collapsed: bool):
        indicator = "\u25b6" if is_collapsed else "\u25bc"  # ▶ or ▼
        super().__init__(indicator, classes="col-header-btn")
        self.col_id = col_id

    def on_click(self, event):
        event.stop()
        self.app.toggle_column_collapse(self.col_id)


class ColumnEditButton(Static):
    """A small button to open the column edit dialog."""

    can_focus = False

    def __init__(self, col_id: str):
        super().__init__("\u270e", classes="col-header-edit-btn")  # ✎
        self.col_id = col_id

    def on_click(self, event):
        event.stop()
        self.app.open_column_edit(self.col_id)


class CollapsedColumnPlaceholder(Static):
    """A focusable placeholder inside collapsed columns, enabling keyboard expand."""

    can_focus = True

    def __init__(self, col_id: str):
        super().__init__("···", classes="collapsed-placeholder")
        self.column_id = col_id

    def on_focus(self):
        self.styles.background = "#444444"

    def on_blur(self):
        self.styles.background = None


class ColumnHeader(Static):
    """A composite column header with title, collapse toggle, and edit button."""

    def __init__(self, col_id: str, title: str, task_count: int, is_collapsed: bool, editable: bool = True):
        super().__init__()
        self.col_id = col_id
        self.col_title = title
        self.task_count = task_count
        self.is_collapsed = is_collapsed
        self.editable = editable

    def compose(self):
        if self.is_collapsed:
            yield Label(self.col_title, classes="col-header-title")
            yield Label(f"({self.task_count})", classes="col-header-count")
            yield CollapseToggleButton(self.col_id, is_collapsed=True)
        else:
            with Horizontal(classes="col-header-row"):
                yield CollapseToggleButton(self.col_id, is_collapsed=False)
                yield Label(f"{self.col_title} ({self.task_count})", classes="col-header-title-expanded")
                if self.editable:
                    yield ColumnEditButton(self.col_id)

class ViewSelector(Static):
    """Shows the current filter state with clickable keyboard shortcuts.

    Layout: ``[a All | l Locked | f Free | i In-Flight]   g Git   t Type``
    - Four mutually-exclusive base filters in brackets (radio).
    - Two independent add-on toggles to the right.
    """

    # (action_id, label, target_id). action_id is the App-level Binding action;
    # target_id is the radio/toggle identifier used by hit-test + click handlers.
    BASES = [
        ("view_all", "All", "all"),
        ("view_locked", "Locked", "locked"),
        ("view_free", "Free", "free"),
        ("view_inflight", "In-Flight", "inflight"),
        ("view_bytopic", "By-Topic", "bytopic"),
    ]
    ADDONS = [
        ("view_git", "Git", "git"),
        ("view_type", "Type", "type"),
    ]
    BASE_SEP = " | "
    ADDON_GAP = "   "

    def __init__(self, base: str = "all", git_on: bool = False, type_on: bool = False, **kwargs):
        super().__init__(**kwargs)
        self.active_base = base
        self.git_on = git_on
        self.type_on = type_on
        # Populated by render(): list of (start_col, end_col, target_id) where
        # target_id is one of the base ids ("all"/"locked"/"free") or addon
        # ids ("git"/"type"). Drives on_click() hit-testing.
        self._click_targets: list[tuple[int, int, str]] = []

    def render(self) -> str:
        parts: list[str] = []
        targets: list[tuple[int, int, str]] = []
        col = 0

        # Opening bracket (dim).
        parts.append(r"[dim]\[[/]")
        col += 1

        # Base radio segments.
        for i, (action_id, label, base_id) in enumerate(self.BASES):
            if i > 0:
                parts.append(f"[dim]{self.BASE_SEP}[/]")
                col += len(self.BASE_SEP)
            seg_text = get_label("board", action_id, label, style="leading")
            if self.active_base == base_id:
                parts.append(f"[bold cyan]{seg_text}[/]")
            else:
                parts.append(f"[dim]{seg_text}[/]")
            targets.append((col, col + len(seg_text), base_id))
            col += len(seg_text)

        # Closing bracket (dim). Rich only requires escaping `[` (with `\[`),
        # not `]` — emit it literally.
        parts.append("[dim]][/]")
        col += 1

        # Add-on toggle segments.
        for action_id, label, addon_id in self.ADDONS:
            parts.append(f"[dim]{self.ADDON_GAP}[/]")
            col += len(self.ADDON_GAP)
            seg_text = get_label("board", action_id, label, style="leading")
            active = (addon_id == "git" and self.git_on) or (addon_id == "type" and self.type_on)
            if active:
                parts.append(f"[bold cyan]{seg_text}[/]")
            else:
                parts.append(f"[dim]{seg_text}[/]")
            targets.append((col, col + len(seg_text), addon_id))
            col += len(seg_text)

        self._click_targets = targets
        return "".join(parts)

    def on_click(self, event):
        # CSS padding 0 1 shifts content by 1 column on the left.
        x = event.x - 1
        for start, end, target in self._click_targets:
            if start <= x < end:
                if target in ("all", "locked", "free", "inflight", "bytopic"):
                    self.app._set_base_filter(target)
                elif target == "git":
                    self.app._toggle_git_filter()
                elif target == "type":
                    self.app._toggle_type_filter()
                return


class TaskCard(Static):
    """A widget representing a single task."""

    def __init__(self, task: Task, manager: "TaskManager" = None, is_child: bool = False, column_id: str = ""):
        super().__init__()
        self.task_data = task
        self.manager = manager
        self.is_child = is_child
        self.column_id = column_id
        self.can_focus = True

    @staticmethod
    def _parse_filename(filename: str):
        """Parse task filenames into (task_num, task_name).
        Child: 't47_1_desc.md' -> ('t47_1', 'desc')
        Parent: 't47_playlists_support.md' -> ('t47', 'playlists support')
        """
        name = filename.removesuffix(".md")
        # Try child pattern first (more specific: second segment is pure digits)
        m = re.match(r'^(t\d+_\d+)_(.+)$', name)
        if m:
            return m.group(1), m.group(2).replace("_", " ")
        # Fall back to parent pattern
        m = re.match(r'^(t\d+)_(.+)$', name)
        if m:
            return m.group(1), m.group(2).replace("_", " ")
        return "", name.replace("_", " ")

    def compose(self):
        meta = self.task_data.metadata
        effort = meta.get('effort', '')
        labels = meta.get('labels', [])
        status = meta.get('status', '')
        assigned_to = meta.get('assigned_to', '')

        task_num, task_name = self._parse_filename(self.task_data.filename)
        is_modified = self.manager.is_modified(self.task_data) if self.manager else False
        with Horizontal(classes="task-title-row"):
            if task_num:
                display_num = f"{task_num} *" if is_modified else task_num
                num_classes = "task-number task-modified" if is_modified else "task-number"
                yield Label(display_num, classes=num_classes)
            yield Label(task_name, classes="task-title")

        info = []
        if effort: info.append(f"💪 {effort}")
        if labels: info.append(f"🏷️ {','.join(labels)}")
        issue = meta.get('issue', '')
        if issue:
            info.append(_issue_indicator(issue))
        pr_url = meta.get('pull_request', '')
        if pr_url:
            info.append(_pr_indicator(pr_url))
        contributor = meta.get('contributor', '')
        if contributor:
            info.append(f"[dim]@{contributor}[/dim]")

        if info:
            yield Label(" | ".join(info), classes="task-info")

        # Lock indicator on its own line
        if self.manager:
            lock_id = task_num.lstrip("t")
            if lock_id in self.manager.lock_map:
                lock_info = self.manager.lock_map[lock_id]
                yield Label(f"\U0001f512 {lock_info['locked_by']}", classes="task-info")

        unresolved_deps = []
        if self.manager:
            unresolved_deps = self.manager.unresolved_local_deps(self.task_data)

        # Cross-repo dependencies (xdeps + xdeprepo, t832_8). Build a per-ref
        # display string with live status; xdep_blocked drives the distinct
        # "blocked by cross-repo" indicator. Both fields must be present
        # (both-or-neither invariant from t832_3). xdeps values are NOT
        # normalized by task_yaml, so coerce/strip the leading 't' here.
        xdep_display = []
        xdep_blocked = False
        xdeprepo = meta.get('xdeprepo')
        xdeps = meta.get('xdeps', []) or []
        if self.manager and xdeprepo and xdeps:
            xdep_display, xdep_blocked = self.manager.cross_repo_dep_display(self.task_data)

        # Determine implementing children for parent tasks
        implementing_children = []
        total_children = 0
        if self.manager and not self.is_child:
            task_num_for_children, _ = self._parse_filename(self.task_data.filename)
            children = self.manager.get_child_tasks_for_parent(task_num_for_children)
            total_children = len(children)
            implementing_children = [
                c for c in children if c.metadata.get('status') == 'Implementing'
            ]

        is_blocked = bool(unresolved_deps) or xdep_blocked
        status_parts = []
        if unresolved_deps:
            status_parts.append("🚫 blocked")
        if xdep_blocked:
            status_parts.append("🌐 blocked (cross-repo)")
        if not is_blocked and status and not implementing_children:
            status_parts.append(f"📋 {status}")
        if assigned_to: status_parts.append(f"👤 {assigned_to}")
        if status_parts:
            yield Label(" | ".join(status_parts), classes="task-info")

        if unresolved_deps:
            yield Label(f"🔗 {', '.join(unresolved_deps)}", classes="task-info")
        if xdep_display:
            yield Label(f"↗ {', '.join(xdep_display)}", classes="task-info")

        folded_into = meta.get('folded_into')
        if folded_into:
            yield Label(f"\U0001f4ce folded into t{folded_into}", classes="task-info")

        if self.manager and not self.is_child:
            if implementing_children:
                for child in implementing_children:
                    child_num, _ = self._parse_filename(child.filename)
                    child_email = child.metadata.get('assigned_to', '')
                    child_label = f"\u26a1 {child_num}"
                    if child_email:
                        child_label += f" \U0001f464 {child_email}"
                    yield Label(child_label, classes="task-info")
                remaining = total_children - len(implementing_children)
                if remaining > 0:
                    yield Label(f"\U0001f476 {remaining} more children", classes="task-info")
            elif total_children > 0:
                yield Label(f"\U0001f476 {total_children} children", classes="task-info")

    def _priority_border_color(self):
        priority = self.task_data.metadata.get('priority', 'normal')
        if priority == "high": return "red"
        if priority == "medium": return "yellow"
        return "gray"

    def _idle_border_style(self):
        return "dashed" if self.is_child else "solid"

    def on_mount(self):
        self.styles.border = (self._idle_border_style(), self._priority_border_color())
        self.styles.padding = (0, 1)
        if self.is_child:
            self.styles.margin = (0, 0, 1, 0)
        else:
            self.styles.margin = (0, 0, 1, 0)

    def on_focus(self):
        self.styles.border = ("double", "cyan")
        self.scroll_visible()

    def on_blur(self):
        self.styles.border = (self._idle_border_style(), self._priority_border_color())

    def on_click(self, event):
        self.focus()
        if event.chain == 2:
            # Collapsed parent with children → expand instead of opening details
            if not self.is_child:
                task_num, _ = TaskCard._parse_filename(self.task_data.filename)
                children = self.manager.get_child_tasks_for_parent(task_num)
                if children and self.task_data.filename not in self.app.expanded_tasks:
                    self.app.action_toggle_children()
                    return
            self.app.action_view_details()


class InFlightTaskCard(TaskCard):
    """Task card variant for the action-grouped In-Flight view."""

    def __init__(self, item: InFlightItem, manager: "TaskManager", column_id: str):
        super().__init__(item.task, manager, is_child="_" in item.task_id, column_id=column_id)
        self.item = item

    def compose(self):
        with Horizontal(classes="task-title-row"):
            yield Label(self.item.task_id, classes="task-number")
            yield Label(self.item.title, classes="task-title")
        yield Label(self.item.next_action, classes="task-info inflight-action")
        if self.item.gate_summary:
            yield Label(self.item.gate_summary, classes="task-info")
        if self.item.blockers:
            yield Label(f"blocked by: {', '.join(self.item.blockers)}", classes="task-info")

        ops = ["p pick"]
        if self.item.has_ledger:
            ops.append("g resume")
        if self.item.human_gates:
            ops.append("s sign-off")
            ops.append("f fail")
        yield Label("  ".join(f"[{op}]" for op in ops), classes="task-info inflight-ops")

    def _priority_border_color(self):
        if self.item.group == "blocked":
            return "red"
        if self.item.group == "human":
            return "yellow"
        return "green"


class InFlightColumn(VerticalScroll):
    """A column in the In-Flight action view."""

    TITLES = {
        "human": "Needs your action",
        "agent": "Agent can continue",
        "blocked": "Blocked",
    }
    COLORS = {
        "human": "#FFB86C",
        "agent": "#50FA7B",
        "blocked": "#FF5555",
    }

    def __init__(self, group: str, items: list[InFlightItem], manager: TaskManager):
        super().__init__()
        self.col_id = f"inflight-{group}"
        self.group = group
        self.items = items
        self.manager = manager

    def compose(self):
        title = self.TITLES[self.group]
        color = self.COLORS[self.group]
        header = ColumnHeader(self.col_id, title, len(self.items), is_collapsed=False, editable=False)
        header.styles.background = color
        header.styles.color = "black"
        header.styles.width = "100%"
        header.styles.text_align = "center"
        yield header
        if not self.items:
            yield Static("No tasks", classes="inflight-empty")
        for item in self.items:
            yield InFlightTaskCard(item, self.manager, column_id=self.col_id)

    def on_mount(self):
        self.styles.width = 44
        self.styles.min_width = 34
        self.styles.border = ("round", self.COLORS[self.group])
        self.styles.margin = (0, 1)


class TopicColumn(VerticalScroll):
    """A swimlane in the by-topic (group-by-anchor) view.

    Models InFlightColumn: a non-collapsible, non-editable column header over a
    set of ordinary TaskCards. The lane label carries the topic root's id+title;
    cards keep their priority borders (lane membership is conveyed by the column).
    """

    def __init__(self, label: str, tasks: list, manager: "TaskManager"):
        super().__init__()
        slug = re.sub(r"[^0-9A-Za-z_]+", "-", label).strip("-").lower()
        self.col_id = f"topic-{slug}" if slug else "topic-lane"
        self.label = label
        self.tasks = tasks
        self.manager = manager

    def compose(self):
        header = ColumnHeader(self.col_id, self.label, len(self.tasks),
                              is_collapsed=False, editable=False)
        header.styles.width = "100%"
        header.styles.text_align = "center"
        yield header
        for task in self.tasks:
            yield TaskCard(task, self.manager, is_child=("_" in task_own_id(task)),
                           column_id=self.col_id)

    def on_mount(self):
        self.styles.width = 44
        self.styles.min_width = 34
        self.styles.border = ("round", "#6272A4")
        self.styles.margin = (0, 1)


class GateChoiceItem(Static):
    """Focusable row for selecting a human gate."""

    can_focus = True

    def __init__(self, gate_name: str):
        super().__init__(gate_name)
        self.gate_name = gate_name

    def on_focus(self):
        self.add_class("dep-item-focused")

    def on_blur(self):
        self.remove_class("dep-item-focused")

    def on_key(self, event):
        if event.key == "enter":
            self.screen.dismiss(self.gate_name)

    def on_click(self, event):
        self.screen.dismiss(self.gate_name)


class GateChoiceScreen(ModalScreen):
    """Modal used when sign-off/fail has more than one possible gate."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=False),
    ]

    def __init__(self, task_id: str, gates: list[str], action_label: str):
        super().__init__()
        self.task_id = task_id
        self.gates = gates
        self.action_label = action_label

    def compose(self):
        with Container(id="dep_picker_dialog"):
            yield Label(
                f"Select human gate to {self.action_label} for {self.task_id}:",
                id="dep_picker_title",
            )
            for gate in self.gates:
                yield GateChoiceItem(gate)
            yield Button("Cancel", id="btn_dep_cancel")

    def on_mount(self):
        items = list(self.query(GateChoiceItem))
        if items:
            items[0].focus()

    @on(Button.Pressed, "#btn_dep_cancel")
    def cancel_button(self):
        self.dismiss(None)

    def action_cancel(self):
        self.dismiss(None)


class KanbanColumn(VerticalScroll):
    """A vertical column of tasks."""

    def __init__(self, col_id: str, title: str, color: str, manager: TaskManager,
                 expanded_tasks: set = None, collapsed: bool = False):
        super().__init__()
        self.col_id = col_id
        self.col_title = title
        self.col_color = color
        self.manager = manager
        self.expanded_tasks = expanded_tasks if expanded_tasks is not None else set()
        self.collapsed = collapsed

    def compose(self):
        # Header
        task_count = len(self.manager.get_column_tasks(self.col_id))
        editable = self.col_id != "unordered"
        header = ColumnHeader(self.col_id, self.col_title, task_count,
                              is_collapsed=self.collapsed, editable=editable)
        header.styles.background = self.col_color
        header.styles.color = "black"
        header.styles.width = "100%"
        header.styles.text_align = "center"
        yield header

        # Task Cards — only render when not collapsed
        if self.collapsed:
            yield CollapsedColumnPlaceholder(self.col_id)
        else:
            tasks = self.manager.get_column_tasks(self.col_id)
            for task in tasks:
                yield TaskCard(task, self.manager, column_id=self.col_id)
                # Render children if parent is expanded
                if task.filename in self.expanded_tasks:
                    task_num, _ = TaskCard._parse_filename(task.filename)
                    children = self.manager.get_child_tasks_for_parent(task_num)
                    for child in children:
                        with Horizontal(classes="child-wrapper"):
                            yield Static("↳", classes="child-connector")
                            yield TaskCard(child, self.manager, is_child=True, column_id=self.col_id)

    def on_mount(self):
        if self.collapsed:
            self.styles.width = 12
            self.styles.min_width = 10
        else:
            self.styles.width = 40
            self.styles.min_width = 30
        self.styles.border = ("round", self.col_color)
        self.styles.margin = (0, 1)

class CycleField(Static):
    """A focusable widget that cycles through predefined options with Left/Right keys."""

    can_focus = True

    class Changed(Message):
        """Posted when the cycle field value changes."""
        def __init__(self, field: "CycleField", value: str):
            super().__init__()
            self.field = field
            self.value = value

    def __init__(self, label: str, options: list, current: str, field_key: str,
                 id: str = None):
        super().__init__(id=id)
        self.label = label
        self.options = options
        self.field_key = field_key
        self.current_index = options.index(current) if current in options else 0

    @property
    def current_value(self) -> str:
        return self.options[self.current_index]

    def render(self) -> str:
        parts = []
        for i, opt in enumerate(self.options):
            if i == self.current_index:
                parts.append(f"[bold reverse] {opt} [/]")
            else:
                parts.append(f" {opt} ")
        options_str = " | ".join(parts)
        return f"  {self.label}:  [dim]\u25c0[/] {options_str} [dim]\u25b6[/]"

    def cycle_prev(self):
        self.current_index = (self.current_index - 1) % len(self.options)
        self.refresh()
        self.post_message(self.Changed(self, self.current_value))

    def cycle_next(self):
        self.current_index = (self.current_index + 1) % len(self.options)
        self.refresh()
        self.post_message(self.Changed(self, self.current_value))

    def _option_index_at(self, cx):
        """Map content x-coordinate to option index, -1 for left arrow, -2 for right arrow."""
        prefix_len = len(f"  {self.label}:  \u25c0 ")
        if cx == prefix_len - 2:
            return -1
        pos = prefix_len
        for i, opt in enumerate(self.options):
            opt_width = len(opt) + 2
            if pos <= cx < pos + opt_width:
                return i
            pos += opt_width
            if i < len(self.options) - 1:
                pos += 3
        if cx == pos + 1:
            return -2
        return None

    def on_click(self, event):
        """Select option directly when clicked."""
        content_offset = event.get_content_offset(self)
        if content_offset is None:
            return
        idx = self._option_index_at(content_offset.x)
        if idx == -1:
            self.cycle_prev()
        elif idx == -2:
            self.cycle_next()
        elif idx is not None and idx != self.current_index:
            self.current_index = idx
            self.refresh()
            self.post_message(self.Changed(self, self.current_value))

    def on_key(self, event):
        if event.key == "left":
            self.cycle_prev()
            event.prevent_default()
            event.stop()
        elif event.key == "right":
            self.cycle_next()
            event.prevent_default()
            event.stop()

    def on_focus(self):
        self.add_class("cycle-focused")

    def on_blur(self):
        self.remove_class("cycle-focused")


class ReadOnlyField(Static):
    """A focusable read-only metadata field with highlight on focus."""

    can_focus = True

    def on_focus(self):
        self.add_class("ro-focused")

    def on_blur(self):
        self.remove_class("ro-focused")


class DependsField(Static):
    """Focusable depends field. Enter opens dependency detail."""

    can_focus = True

    def __init__(self, deps: list, manager: "TaskManager", owner_task: "Task", **kwargs):
        super().__init__(**kwargs)
        self.deps = deps
        self.manager = manager
        self.owner_task = owner_task

    def render(self) -> str:
        dep_str = ", ".join(str(d) for d in self.deps)
        return f"  [b]Depends:[/b] {dep_str}"

    def on_key(self, event):
        if event.key == "enter":
            self._open_dep()
            event.prevent_default()
            event.stop()

    def _find_task_by_number(self, num):
        num_str = str(num)
        task_id = num_str if num_str.startswith('t') else f"t{num_str}"
        return self.manager.find_task_including_archived(task_id)

    def _open_dep(self):
        if len(self.deps) == 1:
            task = self._find_task_by_number(self.deps[0])
            if task:
                self.app.push_screen(
                    TaskDetailScreen(
                        task, self.manager,
                        read_only=getattr(task, "archived", False),
                    )
                )
            else:
                self._ask_remove_dep(self.deps[0])
        else:
            dep_items = []
            for dep_num in self.deps:
                task = self._find_task_by_number(dep_num)
                dep_label = str(dep_num) if str(dep_num).startswith('t') else f"t{dep_num}"
                if task:
                    _, name = TaskCard._parse_filename(task.filename)
                    dep_items.append((dep_num, task, f"{dep_label} {name}"))
                else:
                    dep_items.append((dep_num, None, f"{dep_label} (not found)"))
            self.app.push_screen(
                DependencyPickerScreen(dep_items, self.manager, self.owner_task),
            )

    def _ask_remove_dep(self, dep_num):
        def on_result(remove):
            if remove:
                _remove_dep_from_task(self.owner_task, dep_num)
                _reload_detail_screen(self.app, self.owner_task, self.manager)
        self.app.push_screen(
            RemoveDepConfirmScreen(dep_num),
            on_result,
        )

    def on_focus(self):
        self.add_class("ro-focused")

    def on_blur(self):
        self.remove_class("ro-focused")


def _remove_dep_from_task(task, dep_num):
    """Remove a dependency number from a task's metadata and save."""
    if not task.load():  # Reload from disk to pick up external changes
        return  # File gone (archived/deleted)
    deps = task.metadata.get("depends", [])
    task.metadata["depends"] = [d for d in deps if d != dep_num]
    task.save_with_timestamp()


class VerifiesField(Static):
    """Focusable verifies field. Enter opens verified-task detail."""

    can_focus = True

    def __init__(self, verifies: list, manager: "TaskManager", owner_task: "Task", **kwargs):
        super().__init__(**kwargs)
        self.verifies = verifies
        self.manager = manager
        self.owner_task = owner_task

    def render(self) -> str:
        v_str = ", ".join(str(v) for v in self.verifies)
        return f"  [b]Verifies:[/b] {v_str}"

    def on_key(self, event):
        if event.key == "enter":
            self._open_verify()
            event.prevent_default()
            event.stop()

    def _find_task_by_number(self, num):
        num_str = str(num)
        task_id = num_str if num_str.startswith('t') else f"t{num_str}"
        return self.manager.find_task_including_archived(task_id)

    def _open_verify(self):
        if len(self.verifies) == 1:
            task = self._find_task_by_number(self.verifies[0])
            if task:
                self.app.push_screen(
                    TaskDetailScreen(
                        task, self.manager,
                        read_only=getattr(task, "archived", False),
                    )
                )
            else:
                self._ask_remove_verify(self.verifies[0])
        else:
            items = []
            for v_num in self.verifies:
                task = self._find_task_by_number(v_num)
                v_label = str(v_num) if str(v_num).startswith('t') else f"t{v_num}"
                if task:
                    _, name = TaskCard._parse_filename(task.filename)
                    items.append((v_num, task, f"{v_label} {name}"))
                else:
                    items.append((v_num, None, f"{v_label} (not found)"))
            self.app.push_screen(
                DependencyPickerScreen(items, self.manager, self.owner_task),
            )

    def _ask_remove_verify(self, v_num):
        def on_result(remove):
            if remove:
                _remove_verify_from_task(self.owner_task, v_num)
                _reload_detail_screen(self.app, self.owner_task, self.manager)
        self.app.push_screen(
            RemoveDepConfirmScreen(v_num),
            on_result,
        )

    def on_focus(self):
        self.add_class("ro-focused")

    def on_blur(self):
        self.remove_class("ro-focused")


def _remove_verify_from_task(task, v_num):
    """Remove a verifies entry from a task's metadata and save."""
    if not task.load():
        return
    verifies = task.metadata.get("verifies", [])
    task.metadata["verifies"] = [v for v in verifies if v != v_num]
    task.save_with_timestamp()


class CrossRepoDepsField(Static):
    """Focusable cross-repo dependency field. Enter opens refs read-only."""

    can_focus = True

    def __init__(self, repo: str, xdeps: list, manager: "TaskManager", **kwargs):
        super().__init__(**kwargs)
        self.repo = repo
        self.refs = [(repo, str(xd).lstrip("t")) for xd in (xdeps or [])]
        self.manager = manager

    def render(self) -> str:
        refs = ", ".join(self._format_ref(repo, task_id) for repo, task_id in self.refs)
        return f"  [b]Cross-repo deps:[/b] ↗ {refs}"

    def _format_ref(self, repo: str, task_id: str) -> str:
        ref = f"{repo}#{task_id}"
        status = self.manager.get_xdep_status(repo, task_id)
        if status == "Done":
            return ref
        if not status or status == "NOT_FOUND":
            return f"{ref} (UNREACHABLE)"
        return f"{ref} [{status}]"

    def on_key(self, event):
        if event.key == "enter":
            self._open_ref()
            event.prevent_default()
            event.stop()

    def _open_ref(self):
        if not self.refs:
            return
        if len(self.refs) == 1:
            repo, task_id = self.refs[0]
            self.app._open_cross_repo_task(repo, task_id)
        else:
            self.app.push_screen(CrossRepoRefPickerScreen(self.refs))

    def on_focus(self):
        self.add_class("ro-focused")

    def on_blur(self):
        self.remove_class("ro-focused")


def _reload_detail_screen(app, task, manager):
    """Dismiss the current detail screen and re-push it with updated task data."""
    task.load()
    app.screen.dismiss()
    app.push_screen(TaskDetailScreen(task, manager))


class ChildrenField(Static):
    """Focusable children field. Enter opens child task detail."""

    can_focus = True

    def __init__(self, children_ids: list, manager: "TaskManager",
                 owner_task: "Task", **kwargs):
        super().__init__(**kwargs)
        self.children_ids = children_ids
        self.manager = manager
        self.owner_task = owner_task

    def render(self) -> str:
        children_str = ", ".join(str(c) for c in self.children_ids)
        return f"  [b]Children:[/b] {children_str}"

    def on_key(self, event):
        if event.key == "enter":
            self._open_child()
            event.prevent_default()
            event.stop()

    def _find_task_by_number(self, num):
        num_str = str(num)
        task_id = num_str if num_str.startswith('t') else f"t{num_str}"
        return self.manager.find_task_including_archived(task_id)

    def _open_child(self):
        if len(self.children_ids) == 1:
            task = self._find_task_by_number(self.children_ids[0])
            if task:
                self.app.push_screen(
                    TaskDetailScreen(
                        task, self.manager,
                        read_only=getattr(task, "archived", False),
                    )
                )
        else:
            child_items = []
            for child_id in self.children_ids:
                child_id_str = str(child_id)
                task = self._find_task_by_number(child_id_str)
                if task:
                    _, name = TaskCard._parse_filename(task.filename)
                    child_items.append((child_id_str, task, f"{child_id_str} {name}"))
                else:
                    child_items.append((child_id_str, None, f"{child_id_str} (not found)"))
            self.app.push_screen(
                ChildPickerScreen(child_items, self.manager),
            )

    def on_focus(self):
        self.add_class("ro-focused")

    def on_blur(self):
        self.remove_class("ro-focused")


class FoldedTasksField(Static):
    """Focusable folded tasks field. Enter opens folded task detail (read-only)."""

    can_focus = True

    def __init__(self, folded_ids: list, manager: "TaskManager",
                 owner_task: "Task", **kwargs):
        super().__init__(**kwargs)
        self.folded_ids = folded_ids
        self.manager = manager
        self.owner_task = owner_task

    def render(self) -> str:
        folded_str = ", ".join(str(f) for f in self.folded_ids)
        return f"  [b]Folded Tasks:[/b] {folded_str}"

    def on_key(self, event):
        if event.key == "enter":
            self._open_folded()
            event.prevent_default()
            event.stop()

    def _open_folded(self):
        if len(self.folded_ids) == 1:
            task_id = str(self.folded_ids[0])
            tid = task_id if task_id.startswith('t') else f"t{task_id}"
            task = self.manager.find_task_including_archived(tid)
            if task:
                self.app.push_screen(
                    TaskDetailScreen(task, self.manager, read_only=True))
        else:
            folded_items = []
            for fid in self.folded_ids:
                fid_str = str(fid)
                tid = fid_str if fid_str.startswith('t') else f"t{fid_str}"
                task = self.manager.find_task_including_archived(tid)
                if task:
                    _, name = TaskCard._parse_filename(task.filename)
                    folded_items.append((fid_str, task, f"{tid} {name}"))
                else:
                    folded_items.append((fid_str, None, f"{tid} (not found)"))
            self.app.push_screen(
                FoldedTaskPickerScreen(folded_items, self.manager),
            )

    def on_focus(self):
        self.add_class("ro-focused")

    def on_blur(self):
        self.remove_class("ro-focused")


class AnchorEditScreen(ModalScreen):
    """Modal to edit a task's topic anchor (group key). Empty value clears it.

    Models RenameTaskScreen — reuses the shared #rename_dialog / #detail_buttons
    styling. Dismisses with the typed value (possibly empty) or None on cancel.
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=False),
    ]

    def __init__(self, task_num: str, current_anchor: str):
        super().__init__()
        self.task_num = task_num
        self.current_anchor = current_anchor

    def compose(self):
        with Container(id="rename_dialog"):
            yield Label(f"Set topic anchor for {self.task_num}", id="rename_title")
            yield Label("Root task id (e.g. 130 or 130_2). Empty clears the anchor.")
            yield Input(value=self.current_anchor, id="anchor_input",
                        placeholder="topic root id", select_on_focus=False)
            with Horizontal(id="detail_buttons"):
                yield Button("Save", variant="success", id="btn_do_anchor")
                yield Button("Cancel", variant="default", id="btn_anchor_cancel")

    @on(Button.Pressed, "#btn_do_anchor")
    def do_anchor(self):
        self.dismiss(self.query_one("#anchor_input", Input).value)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self.do_anchor()

    @on(Button.Pressed, "#btn_anchor_cancel")
    def cancel(self):
        self.dismiss(None)

    def action_cancel(self):
        self.dismiss(None)


class AnchorField(Static):
    """Focusable, editable topic-anchor field. Enter edits the anchor (group key).

    Persists by shelling out to ``aitask_update.sh --batch <id> --anchor <val>``
    (the mandated new-field board pattern, NOT the CycleField save_with_timestamp
    path), then reloads the detail screen. Shown even when unset so a root task
    can be given an anchor; rendered read-only via the screen's read_only flag.
    """

    can_focus = True

    def __init__(self, anchor, manager: "TaskManager", owner_task: "Task",
                 read_only: bool = False, **kwargs):
        super().__init__(**kwargs)
        self.anchor = anchor  # bare id string, or None when unset
        self.manager = manager
        self.owner_task = owner_task
        self.read_only = read_only

    def render(self) -> str:
        shown = f"t{self.anchor}" if self.anchor else "[dim](none)[/dim]"
        hint = "" if self.read_only else "  [dim](enter to edit)[/dim]"
        return f"  [b]Anchor:[/b] {shown}{hint}"

    def on_key(self, event):
        if event.key == "enter" and not self.read_only:
            self._edit()
            event.prevent_default()
            event.stop()

    def _edit(self):
        task_num, _ = TaskCard._parse_filename(self.owner_task.filename)

        def on_result(new_value):
            if new_value is None:
                return  # cancelled
            self._apply(task_num.lstrip("t"), new_value.strip())

        self.app.push_screen(
            AnchorEditScreen(task_num, self.anchor or ""), on_result)

    def _apply(self, task_num_bare: str, new_anchor: str):
        result = subprocess.run(
            ["./.aitask-scripts/aitask_update.sh", "--batch", task_num_bare,
             "--anchor", new_anchor, "--silent"],
            capture_output=True, text=True, timeout=15,
        )
        if result.returncode != 0:
            error = (result.stderr.strip() or result.stdout.strip()
                     or "anchor update failed")
            self.app.notify(error, severity="error")
            return
        _reload_detail_screen(self.app, self.owner_task, self.manager)

    def on_focus(self):
        self.add_class("ro-focused")

    def on_blur(self):
        self.remove_class("ro-focused")


def _current_tmux_session() -> str | None:
    """Return the current tmux session name, or None if not in tmux."""
    try:
        result = subprocess.run(
            ["tmux", "display-message", "-p", "#S"],
            capture_output=True, text=True, timeout=2,
        )
        if result.returncode == 0:
            name = result.stdout.strip()
            return name or None
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        pass
    return None


class FileReferencesField(Static):
    """Focusable, read-only file_references field.

    Enter navigates to the entry in codebrowser (picker if multi).
    No add/remove keybindings — use aitask_update.sh --file-ref /
    --remove-file-ref or the codebrowser create-task flow instead.
    """

    can_focus = True

    def __init__(self, file_refs: list, manager: "TaskManager",
                 owner_task: "Task", **kwargs):
        super().__init__(**kwargs)
        self.file_refs = list(file_refs or [])
        self.manager = manager
        self.owner_task = owner_task

    def render(self) -> str:
        if not self.file_refs:
            return "  [b]File Refs:[/b] [dim](none)[/dim]"
        return f"  [b]File Refs:[/b] {', '.join(self.file_refs)}"

    def on_key(self, event):
        if event.key == "enter":
            self._navigate()
            event.prevent_default()
            event.stop()

    def _navigate(self):
        if not self.file_refs:
            return
        if len(self.file_refs) == 1:
            self._launch_codebrowser(self.file_refs[0])
        else:
            def on_picked(entry):
                if entry:
                    self._launch_codebrowser(entry)
            self.app.push_screen(
                FileReferencePickerScreen(self.file_refs),
                on_picked,
            )

    def _launch_codebrowser(self, entry: str):
        session = _current_tmux_session()
        if not session:
            self.app.notify(
                "Codebrowser focus requires tmux", severity="warning")
            return
        ok, err = launch_or_focus_codebrowser(session, entry)
        if not ok:
            self.app.notify(
                f"Codebrowser launch failed: {err}", severity="error")

    def on_focus(self):
        self.add_class("ro-focused")

    def on_blur(self):
        self.remove_class("ro-focused")


class FoldedIntoField(Static):
    """Focusable folded_into field. Enter opens the target task detail."""

    can_focus = True

    def __init__(self, target_num: str, manager: "TaskManager", **kwargs):
        super().__init__(**kwargs)
        self.target_num = target_num
        self.manager = manager

    def render(self) -> str:
        return f"  [b]Folded Into:[/b] t{self.target_num}"

    def on_key(self, event):
        if event.key == "enter":
            self._open_target()
            event.prevent_default()
            event.stop()

    def _open_target(self):
        tid = f"t{self.target_num}" if not str(self.target_num).startswith('t') else str(self.target_num)
        task = self.manager.find_task_including_archived(tid)
        if task:
            self.app.push_screen(
                TaskDetailScreen(
                    task, self.manager,
                    read_only=getattr(task, "archived", False),
                )
            )

    def on_focus(self):
        self.add_class("ro-focused")

    def on_blur(self):
        self.remove_class("ro-focused")


class ParentField(Static):
    """Focusable parent field. Enter opens parent task detail."""

    can_focus = True

    def __init__(self, parent_num: str, manager: "TaskManager", **kwargs):
        super().__init__(**kwargs)
        self.parent_num = parent_num
        self.manager = manager

    def render(self) -> str:
        return f"  [b]Parent:[/b] {self.parent_num}"

    def on_key(self, event):
        if event.key == "enter":
            self._open_parent()
            event.prevent_default()
            event.stop()

    def _open_parent(self):
        task = self.manager.find_task_including_archived(self.parent_num)
        if task:
            self.app.push_screen(
                TaskDetailScreen(
                    task, self.manager,
                    read_only=getattr(task, "archived", False),
                )
            )

    def on_focus(self):
        self.add_class("ro-focused")

    def on_blur(self):
        self.remove_class("ro-focused")


class IssueField(Static):
    """Focusable issue URL field. Press Enter to open in browser."""

    can_focus = True

    def __init__(self, url: str, **kwargs):
        super().__init__(**kwargs)
        self.url = url

    def render(self) -> str:
        return f"  [b]Issue:[/b] {self.url}  [dim](Enter to open)[/dim]"

    def on_key(self, event):
        if event.key == "enter":
            import webbrowser
            webbrowser.open(self.url)
            event.prevent_default()
            event.stop()

    def on_focus(self):
        self.add_class("ro-focused")

    def on_blur(self):
        self.remove_class("ro-focused")


class PullRequestField(Static):
    """Focusable pull request URL field. Press Enter to open in browser."""

    can_focus = True

    def __init__(self, url: str, **kwargs):
        super().__init__(**kwargs)
        self.url = url

    def render(self) -> str:
        indicator = _pr_indicator(self.url)
        return f"  [b]Pull Request:[/b] {indicator} {self.url}  [dim](Enter to open)[/dim]"

    def on_key(self, event):
        if event.key == "enter":
            import webbrowser
            webbrowser.open(self.url)
            event.prevent_default()
            event.stop()

    def on_focus(self):
        self.add_class("ro-focused")

    def on_blur(self):
        self.remove_class("ro-focused")


class RemoveDepConfirmScreen(ModalScreen):
    """Confirmation dialog to remove a missing dependency."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=False),
    ]

    def __init__(self, dep_num):
        super().__init__()
        self.dep_num = dep_num

    def compose(self):
        dep_label = str(self.dep_num) if str(self.dep_num).startswith('t') else f"t{self.dep_num}"
        with Container(id="dep_picker_dialog"):
            yield Label(
                f"Task {dep_label} not found (may be archived).\n"
                f"Remove this dependency?",
                id="dep_picker_title",
            )
            with Horizontal(id="detail_buttons"):
                yield Button("Remove", variant="warning", id="btn_remove_dep")
                yield Button("Cancel", variant="default", id="btn_cancel_dep")

    @on(Button.Pressed, "#btn_remove_dep")
    def confirm_remove(self):
        self.dismiss(True)

    @on(Button.Pressed, "#btn_cancel_dep")
    def cancel_remove(self):
        self.dismiss(False)

    def action_cancel(self):
        self.dismiss(False)


class DeleteConfirmScreen(ModalScreen):
    """Confirmation dialog to delete a task and associated files."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=False),
    ]

    def __init__(self, files_to_delete: list):
        super().__init__()
        self.files_to_delete = files_to_delete

    def compose(self):
        file_list = "\n".join(f"  - {f}" for f in self.files_to_delete)
        with Container(id="dep_picker_dialog"):
            yield Label(
                f"Delete these files?\n{file_list}\n\nThis cannot be undone.",
                id="dep_picker_title",
            )
            with Horizontal(id="detail_buttons"):
                yield Button("Delete", variant="error", id="btn_confirm_delete")
                yield Button("Cancel", variant="default", id="btn_cancel_delete")

    @on(Button.Pressed, "#btn_confirm_delete")
    def confirm_delete(self):
        self.dismiss(True)

    @on(Button.Pressed, "#btn_cancel_delete")
    def cancel_delete(self):
        self.dismiss(False)

    def action_cancel(self):
        self.dismiss(False)


class DeleteArchiveConfirmScreen(ModalScreen):
    """Confirmation dialog offering Delete or Archive for a task.

    Renders explicit ARCHIVED / DELETED sections so the user can see exactly
    what each button will do — never just a flat "files affected" list.
    Disables the Archive button when blocking children prevent a cascade.
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=False),
    ]

    def __init__(self, task_name: str,
                 delete_files: list,
                 archive_kept: list,
                 archive_deleted: list,
                 dep_warnings: list,
                 related_tasks: list,
                 is_child: bool,
                 blocking_files: list = None,
                 blocked_reason: str | None = None):
        super().__init__()
        self.task_name = task_name
        self.delete_files = delete_files or []
        self.archive_kept = archive_kept or []
        self.archive_deleted = archive_deleted or []
        self.dep_warnings = dep_warnings or []
        self.related_tasks = related_tasks or []
        self.is_child = is_child
        self.blocking_files = blocking_files or []
        self.blocked_reason = blocked_reason

    @staticmethod
    def _format_section(title: str, items: list) -> list[str]:
        if not items:
            return []
        out = [title]
        for path, annotation in items:
            if annotation:
                out.append(f"    {path}    [{annotation}]")
            else:
                out.append(f"    {path}")
        return out

    def compose(self):
        lines: list[str] = []

        if self.blocked_reason:
            lines.append(f"[!] {self.blocked_reason}")
            lines.append("")

        if self.dep_warnings:
            lines.append("[!] Explicit dependencies found:")
            for w in self.dep_warnings:
                lines.append(f"    {w}")
        else:
            lines.append("[ok] No explicit dependencies found.")
        lines.append("")

        if self.related_tasks:
            label = "Sibling" if self.is_child else "Related"
            lines.append(f"{label} tasks — please verify no implicit dependencies:")
            for t in self.related_tasks:
                lines.append(f"    {t}")
            lines.append("")

        lines.append("On Delete:")
        if self.delete_files:
            lines.extend(self._format_section("  Files to remove:", self.delete_files))
        else:
            lines.append("  (nothing to remove)")
        lines.append("")

        lines.append("On Archive:")
        if self.blocked_reason:
            lines.append(f"  [!] {self.blocked_reason}")
            if self.blocking_files:
                lines.extend(self._format_section("  Blocking children:", self.blocking_files))
        else:
            if self.archive_kept:
                lines.extend(self._format_section(
                    "  Will be ARCHIVED (moved to archived/):", self.archive_kept))
            if self.archive_deleted:
                lines.extend(self._format_section(
                    "  Will be DELETED (cascade cleanup):", self.archive_deleted))
            if not self.archive_kept and not self.archive_deleted:
                lines.append("  (nothing to archive)")

        with Container(id="dep_picker_dialog"):
            yield Label(
                f"Delete or Archive '{self.task_name}'?\n\n" + "\n".join(lines),
                id="delarch_label",
            )
            with Horizontal(id="detail_buttons"):
                yield Button("Delete", variant="error", id="btn_do_delete")
                archive_btn = Button("Archive", variant="warning", id="btn_do_archive")
                if self.blocked_reason:
                    archive_btn.disabled = True
                yield archive_btn
                yield Button("Cancel", variant="default", id="btn_do_cancel")

    @on(Button.Pressed, "#btn_do_delete")
    def do_delete(self):
        self.dismiss("delete")

    @on(Button.Pressed, "#btn_do_archive")
    def do_archive(self):
        if self.blocked_reason:
            self.app.notify(self.blocked_reason, severity="warning")
            return
        self.dismiss("archive")

    @on(Button.Pressed, "#btn_do_cancel")
    def do_cancel(self):
        self.dismiss("cancel")

    def action_cancel(self):
        self.dismiss("cancel")


class OrphanParentArchiveScreen(ModalScreen):
    """Prompt to archive a parent task that has just become orphaned (its
    last pending child was deleted). Lists the parent file and plan that
    will be moved to archived/."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=False),
    ]

    def __init__(self, parent_name: str, parent_status: str,
                 archive_kept: list):
        super().__init__()
        self.parent_name = parent_name
        self.parent_status = parent_status
        self.archive_kept = archive_kept or []

    def compose(self):
        lines = [
            f"Parent '{self.parent_name}' has no more pending children.",
            "",
            "Will be ARCHIVED (moved to archived/):",
        ]
        for path, annotation in self.archive_kept:
            if annotation:
                lines.append(f"    {path}    [{annotation}]")
            else:
                lines.append(f"    {path}")
        lines.append("")
        lines.append("Archive it as completed now?")

        with Container(id="dep_picker_dialog"):
            yield Label("\n".join(lines), id="orphan_parent_label")
            with Horizontal(id="detail_buttons"):
                yield Button("Yes, archive parent", variant="warning", id="btn_orphan_yes")
                yield Button("No, leave it", variant="default", id="btn_orphan_no")

    @on(Button.Pressed, "#btn_orphan_yes")
    def confirm(self):
        self.dismiss(True)

    @on(Button.Pressed, "#btn_orphan_no")
    def decline(self):
        self.dismiss(False)

    def action_cancel(self):
        self.dismiss(False)


class DepPickerItem(Static):
    """A selectable dependency item in the picker."""

    can_focus = True

    def __init__(self, dep_num, task, display_name, manager, owner_task, **kwargs):
        super().__init__(**kwargs)
        self.dep_num = dep_num
        self.dep_task = task
        self.display_name = display_name
        self.manager = manager
        self.owner_task = owner_task

    def render(self) -> str:
        return f"  {self.display_name}"

    def on_key(self, event):
        if event.key == "enter":
            if self.dep_task:
                self.screen.dismiss()
                self.app.push_screen(
                    TaskDetailScreen(
                        self.dep_task, self.manager,
                        read_only=getattr(self.dep_task, "archived", False),
                    )
                )
            else:
                self._ask_remove_dep()
            event.prevent_default()
            event.stop()

    def _ask_remove_dep(self):
        def on_result(remove):
            if remove:
                _remove_dep_from_task(self.owner_task, self.dep_num)
                # Close picker, then reload the detail screen
                self.screen.dismiss()
                _reload_detail_screen(self.app, self.owner_task, self.manager)
        self.app.push_screen(
            RemoveDepConfirmScreen(self.dep_num),
            on_result,
        )

    def on_focus(self):
        self.add_class("dep-item-focused")

    def on_blur(self):
        self.remove_class("dep-item-focused")


class DependencyPickerScreen(ModalScreen):
    """Popup to select which dependency to open."""

    BINDINGS = [
        Binding("escape", "close_picker", "Close", show=False),
    ]

    def __init__(self, dep_items, manager, owner_task):
        super().__init__()
        self.dep_items = dep_items
        self.manager = manager
        self.owner_task = owner_task

    def compose(self):
        with Container(id="dep_picker_dialog"):
            yield Label("Select dependency to open:", id="dep_picker_title")
            for dep_num, task, display_name in self.dep_items:
                yield DepPickerItem(dep_num, task, display_name, self.manager, self.owner_task)
            yield Button("Cancel", variant="default", id="btn_dep_cancel")

    @on(Button.Pressed, "#btn_dep_cancel")
    def cancel(self):
        self.dismiss()

    def action_close_picker(self):
        self.dismiss()


def _read_cross_repo_task_content(root: Path, tid: str) -> str | None:
    """Return the task text for ``tid`` under ``root`` — active tasks first,
    then the repo's archive store — or ``None`` if absent.

    Mirrors ``TaskManager.find_task_including_archived`` (the same-repo path
    fixed in t992) so an archived cross-repo dependency resolves too. Raises
    ``OSError`` only when an existing *active* file cannot be read; archive
    misses are swallowed by ``find_archived_markdown_by_id`` (returns None).
    """
    if "_" in tid:
        parent = tid.split("_")[0]
        matches = sorted((root / "aitasks" / f"t{parent}").glob(f"t{tid}_*.md"))
    else:
        matches = sorted((root / "aitasks").glob(f"t{tid}_*.md"))
    if matches:
        return matches[0].read_text(encoding="utf-8")
    archived = find_archived_markdown_by_id(tid, root / "aitasks" / "archived")
    if archived:
        return archived[1]
    return None


def _resolve_cross_repo_task(repo: str, task_id: str):
    """Resolve a ``<repo>#<id>`` reference to ``(title, content, is_error)``.

    Read-only: resolves the project root via ``aitask_project_resolve.sh``
    and reads the task file directly — it acquires NO lock and runs no pick
    flow. On any failure (unregistered/stale project, missing task, read
    error) it returns ``is_error=True`` with a human-readable message so the
    popup shows the error instead of crashing the board.
    """
    tid = task_id.lstrip("t")
    title = f"↗ {repo}#{tid}"
    try:
        result = subprocess.run(
            ["./.aitask-scripts/aitask_project_resolve.sh", repo],
            capture_output=True, text=True, timeout=10
        )
        out = result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as e:
        return (title, f"Could not resolve project '{repo}': {e}", True)

    if out.startswith("RESOLVED:"):
        root = Path(out[len("RESOLVED:"):])
    elif out.startswith("STALE:"):
        return (title,
                f"Project '{repo}' is registered but its path is stale "
                f"(missing aitasks/metadata). Fix it with `ait projects`.",
                True)
    elif out.startswith("NOT_FOUND:"):
        return (title,
                f"Project '{repo}' is not registered. Add it with "
                f"`ait projects add`.",
                True)
    else:
        return (title, f"Unexpected resolver output for '{repo}': {out}", True)

    # Locate the task file under the resolved root: active tasks first, then
    # the repo's archive store (mirrors find_task_including_archived for
    # same-repo deps, t992 — so an archived cross-repo dep resolves instead of
    # showing UNREACHABLE).
    try:
        content = _read_cross_repo_task_content(root, tid)
    except OSError as e:
        return (title, f"Could not read task file: {e}", True)
    if content is None:
        return (title, f"Task t{tid} not found in project '{repo}'.", True)
    return (title, content, False)


class CrossRepoRefItem(Static):
    """A selectable cross-repo reference in the picker."""

    can_focus = True

    def __init__(self, repo, task_id, **kwargs):
        super().__init__(**kwargs)
        self.repo = repo
        self.task_id = task_id

    def render(self) -> str:
        return f"  ↗ {self.repo}#{self.task_id}"

    def on_key(self, event):
        if event.key == "enter":
            repo, task_id, app = self.repo, self.task_id, self.app
            self.screen.dismiss()
            app._open_cross_repo_task(repo, task_id)
            event.prevent_default()
            event.stop()

    def on_focus(self):
        self.add_class("xrepo-item-focused")

    def on_blur(self):
        self.remove_class("xrepo-item-focused")


class CrossRepoRefPickerScreen(ModalScreen):
    """Popup to select which cross-repo reference to open (read-only)."""

    DEFAULT_CSS = """
    CrossRepoRefPickerScreen { align: center middle; }
    #xrepo_picker_dialog {
        width: 60%;
        height: auto;
        max-height: 80%;
        background: $surface;
        border: thick $primary;
        padding: 1 2;
    }
    #xrepo_picker_title { text-align: center; padding: 0 0 1 0; }
    CrossRepoRefItem { height: 1; width: 100%; padding: 0 1; }
    CrossRepoRefItem.xrepo-item-focused {
        background: $primary 20%;
        border-left: thick $accent;
    }
    #btn_xrepo_cancel { margin: 1 0 0 0; }
    """

    BINDINGS = [
        Binding("escape", "close_picker", "Close", show=False),
    ]

    def __init__(self, refs):
        super().__init__()
        self._refs = refs

    def compose(self):
        with Container(id="xrepo_picker_dialog"):
            yield Label("Select cross-repo reference to open:", id="xrepo_picker_title")
            for repo, task_id in self._refs:
                yield CrossRepoRefItem(repo, task_id)
            yield Button("Cancel", variant="default", id="btn_xrepo_cancel")

    @on(Button.Pressed, "#btn_xrepo_cancel")
    def cancel(self):
        self.dismiss()

    def action_close_picker(self):
        self.dismiss()


class CrossRepoTaskScreen(ModalScreen):
    """Read-only popup showing a cross-repo task's content (no lock).

    Self-contained DEFAULT_CSS so it renders consistently regardless of the
    App-level stylesheet.
    """

    DEFAULT_CSS = """
    CrossRepoTaskScreen { align: center middle; }
    #xrepo_dialog {
        width: 80%;
        height: 80%;
        background: $surface;
        border: thick $primary;
        padding: 1 2;
    }
    #xrepo_title {
        dock: top;
        text-align: center;
        background: $secondary;
        color: $text;
        padding: 1;
    }
    #xrepo_view { margin: 1 0; border: solid $secondary-background; }
    #xrepo_meta {
        padding: 0 1 1 1;
        color: $text-muted;
        border-bottom: solid $secondary-background;
    }
    #xrepo_error { padding: 1 2; color: $warning; }
    #xrepo_buttons { dock: bottom; height: 3; align: center middle; }
    """

    BINDINGS = [
        Binding("escape", "close", "Close", show=False),
        Binding("c", "close", "Close", show=False),
        Binding("C", "close", "Close", show=False),
    ]

    def __init__(self, title: str, content: str, is_error: bool = False):
        super().__init__()
        self._title = title
        self._content = content
        self._is_error = is_error
        self._metadata = {}
        self._metadata_order = []
        self._body = content
        if not is_error:
            parsed = parse_frontmatter(content)
            if parsed:
                self._metadata, self._body, self._metadata_order = parsed

    def _format_metadata(self) -> str:
        lines = []
        for key in self._metadata_order:
            value = self._metadata.get(key)
            if value in (None, "", []):
                continue
            if isinstance(value, list):
                value = ", ".join(str(item) for item in value)
            lines.append(f"[b]{escape(str(key))}:[/b] {escape(str(value))}")
        return "\n".join(lines)

    def compose(self):
        with Container(id="xrepo_dialog"):
            yield Label(self._title, id="xrepo_title")
            with VerticalScroll(id="xrepo_view"):
                if self._is_error:
                    yield Static(self._content, id="xrepo_error")
                else:
                    if self._metadata:
                        yield Static(self._format_metadata(), id="xrepo_meta")
                    yield Markdown(self._body)
            with Horizontal(id="xrepo_buttons"):
                yield Button("Close", variant="default", id="btn_xrepo_close")

    @on(Button.Pressed, "#btn_xrepo_close")
    def _on_close(self):
        self.dismiss()

    def action_close(self):
        self.dismiss()


class ChildPickerItem(Static):
    """A selectable child task item in the picker."""

    can_focus = True

    def __init__(self, child_id, task, display_name, manager, **kwargs):
        super().__init__(**kwargs)
        self.child_id = child_id
        self.child_task = task
        self.display_name = display_name
        self.manager = manager

    def render(self) -> str:
        return f"  {self.display_name}"

    def on_key(self, event):
        if event.key == "enter":
            if self.child_task:
                self.screen.dismiss()
                self.app.push_screen(
                    TaskDetailScreen(
                        self.child_task, self.manager,
                        read_only=getattr(self.child_task, "archived", False),
                    )
                )
            event.prevent_default()
            event.stop()

    def on_focus(self):
        self.add_class("dep-item-focused")

    def on_blur(self):
        self.remove_class("dep-item-focused")


class ChildPickerScreen(ModalScreen):
    """Popup to select which child task to open."""

    BINDINGS = [
        Binding("escape", "close_picker", "Close", show=False),
    ]

    def __init__(self, child_items, manager):
        super().__init__()
        self.child_items = child_items
        self.manager = manager

    def compose(self):
        with Container(id="dep_picker_dialog"):
            yield Label("Select child task to open:", id="dep_picker_title")
            for child_id, task, display_name in self.child_items:
                yield ChildPickerItem(child_id, task, display_name, self.manager)
            yield Button("Cancel", variant="default", id="btn_dep_cancel")

    @on(Button.Pressed, "#btn_dep_cancel")
    def cancel(self):
        self.dismiss()

    def action_close_picker(self):
        self.dismiss()


class FoldedTaskPickerItem(Static):
    """A selectable folded task item in the picker."""

    can_focus = True

    def __init__(self, folded_id, task, display_name, manager, **kwargs):
        super().__init__(**kwargs)
        self.folded_id = folded_id
        self.folded_task = task
        self.display_name = display_name
        self.manager = manager

    def render(self) -> str:
        return f"  {self.display_name}"

    def on_key(self, event):
        if event.key == "enter":
            if self.folded_task:
                self.screen.dismiss()
                self.app.push_screen(
                    TaskDetailScreen(self.folded_task, self.manager,
                                     read_only=True))
            event.prevent_default()
            event.stop()

    def on_focus(self):
        self.add_class("dep-item-focused")

    def on_blur(self):
        self.remove_class("dep-item-focused")


class FoldedTaskPickerScreen(ModalScreen):
    """Popup to select which folded task to open."""

    BINDINGS = [
        Binding("escape", "close_picker", "Close", show=False),
    ]

    def __init__(self, folded_items, manager):
        super().__init__()
        self.folded_items = folded_items
        self.manager = manager

    def compose(self):
        with Container(id="dep_picker_dialog"):
            yield Label("Select folded task to open:", id="dep_picker_title")
            for folded_id, task, display_name in self.folded_items:
                yield FoldedTaskPickerItem(folded_id, task, display_name,
                                           self.manager)
            yield Button("Cancel", variant="default", id="btn_dep_cancel")

    @on(Button.Pressed, "#btn_dep_cancel")
    def cancel(self):
        self.dismiss()

    def action_close_picker(self):
        self.dismiss()


class FileReferenceItem(Static):
    """A selectable file-reference entry in the picker."""

    can_focus = True

    def __init__(self, entry: str, **kwargs):
        super().__init__(**kwargs)
        self.entry = entry

    def render(self) -> str:
        return f"  {self.entry}"

    def on_key(self, event):
        if event.key == "enter":
            self.screen.dismiss(self.entry)
            event.prevent_default()
            event.stop()

    def on_focus(self):
        self.add_class("dep-item-focused")

    def on_blur(self):
        self.remove_class("dep-item-focused")


class FileReferencePickerScreen(ModalScreen):
    """Popup to select which file_references entry to open."""

    BINDINGS = [
        Binding("escape", "close_picker", "Close", show=False),
    ]

    def __init__(self, entries: list):
        super().__init__()
        self.entries = list(entries)

    def compose(self):
        with Container(id="dep_picker_dialog"):
            yield Label(
                "Select file reference to open:", id="dep_picker_title")
            for entry in self.entries:
                yield FileReferenceItem(entry)
            yield Button("Cancel", variant="default", id="btn_dep_cancel")

    @on(Button.Pressed, "#btn_dep_cancel")
    def cancel(self):
        self.dismiss(None)

    def action_close_picker(self):
        self.dismiss(None)


class IssueTypeFilterScreen(ModalScreen):
    """Modal dialog to multi-select which issue types to show on the board."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=False),
    ]

    def __init__(self, task_types: list, initial: list):
        super().__init__()
        self.task_types = list(task_types)
        self.initial = set(initial)

    def compose(self):
        with Container(id="dep_picker_dialog"):
            yield Label(
                "Filter by issue type — [dim]space to toggle, Enter to confirm, Esc to cancel[/]",
                id="dep_picker_title",
            )
            yield SelectionList[str](
                *(
                    Selection(t, value=t, initial_state=(t in self.initial))
                    for t in self.task_types
                ),
                id="issue_type_filter_list",
            )
            with Horizontal(id="detail_buttons"):
                yield Button("Confirm", variant="primary", id="btn_type_filter_save")
                yield Button("Cancel", variant="default", id="btn_type_filter_cancel")

    def on_mount(self):
        self.query_one("#issue_type_filter_list", SelectionList).focus()

    def _selected(self) -> list:
        sl = self.query_one("#issue_type_filter_list", SelectionList)
        checked = set(sl.selected)
        return [t for t in self.task_types if t in checked]

    @on(Button.Pressed, "#btn_type_filter_save")
    def _btn_save(self):
        self.dismiss(self._selected())

    @on(Button.Pressed, "#btn_type_filter_cancel")
    def _btn_cancel(self):
        self.dismiss(None)

    def action_cancel(self):
        self.dismiss(None)

    def on_key(self, event):
        # SelectionList uses space for toggle and consumes it. Enter is free,
        # so treat it as "confirm selection".
        if event.key == "enter":
            self.dismiss(self._selected())
            event.stop()


class LockEmailScreen(ModalScreen):
    """Modal dialog to enter email for locking a task."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=False),
    ]

    def __init__(self, task_id: str, default_email: str = ""):
        super().__init__()
        self.task_id = task_id
        self.default_email = default_email

    def compose(self):
        with Container(id="dep_picker_dialog"):
            yield Label(f"Lock task t{self.task_id}", id="dep_picker_title")
            yield Label("Enter email for lock ownership:")
            yield Input(
                value=self.default_email,
                placeholder="user@example.com",
                id="lock_email_input",
            )
            with Horizontal(id="detail_buttons"):
                yield Button("Lock", variant="warning", id="btn_confirm_lock")
                yield Button("Cancel", variant="default", id="btn_cancel_lock")

    @on(Button.Pressed, "#btn_confirm_lock")
    def confirm_lock(self):
        email = self.query_one("#lock_email_input", Input).value.strip()
        if email:
            self.dismiss(email)
        else:
            self.app.notify("Email is required", severity="warning")

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self.confirm_lock()

    @on(Button.Pressed, "#btn_cancel_lock")
    def cancel_lock(self):
        self.dismiss(None)

    def action_cancel(self):
        self.dismiss(None)


class UnlockConfirmScreen(ModalScreen):
    """Confirmation dialog to unlock a task locked by another user."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=False),
    ]

    def __init__(self, task_id: str, locked_by: str, locked_at: str, hostname: str):
        super().__init__()
        self.task_id = task_id
        self.locked_by = locked_by
        self.locked_at = locked_at
        self.hostname = hostname

    def compose(self):
        with Container(id="dep_picker_dialog"):
            yield Label(
                f"Task t{self.task_id} is locked by another user",
                id="dep_picker_title",
            )
            yield Label(
                f"Locked by: {self.locked_by}\n"
                f"Hostname: {self.hostname}\n"
                f"Since: {self.locked_at}\n\n"
                f"Force unlock?"
            )
            with Horizontal(id="detail_buttons"):
                yield Button("Force Unlock", variant="error", id="btn_confirm_unlock")
                yield Button("Cancel", variant="default", id="btn_cancel_unlock")

    @on(Button.Pressed, "#btn_confirm_unlock")
    def confirm_unlock(self):
        self.dismiss(True)

    @on(Button.Pressed, "#btn_cancel_unlock")
    def cancel_unlock(self):
        self.dismiss(False)

    def action_cancel(self):
        self.dismiss(False)


class ResetTaskConfirmScreen(ModalScreen):
    """Confirmation dialog to reset task status and assignment after unlock."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=False),
    ]

    def __init__(self, task_id: str, assigned_to: str):
        super().__init__()
        self.task_id = task_id
        self.assigned_to = assigned_to

    def compose(self):
        with Container(id="dep_picker_dialog"):
            yield Label(
                f"Reset task t{self.task_id}?",
                id="dep_picker_title",
            )
            yield Label(
                f"This task is currently:\n"
                f"  Status: Implementing\n"
                f"  Assigned to: {self.assigned_to}\n\n"
                f"Reset status to Ready and clear assignment?"
            )
            with Horizontal(id="detail_buttons"):
                yield Button("Reset to Ready", variant="warning", id="btn_confirm_reset")
                yield Button("Keep current", variant="default", id="btn_cancel_reset")

    @on(Button.Pressed, "#btn_confirm_reset")
    def confirm_reset(self):
        self.dismiss(True)

    @on(Button.Pressed, "#btn_cancel_reset")
    def cancel_reset(self):
        self.dismiss(False)

    def action_cancel(self):
        self.dismiss(False)


class TaskDetailScreen(ShortcutsMixin, ModalScreen):
    """Popup to view/edit task details with metadata editing."""

    _shortcuts_scope = "board.detail"

    BINDINGS = [
        Binding("escape", "close_modal", "Close", show=False),
        Binding("p", "pick", "Pick", show=False),
        Binding("P", "pick", "Pick", show=False),
        Binding("l", "lock", "Lock", show=False),
        Binding("L", "lock", "Lock", show=False),
        Binding("u", "unlock", "Unlock", show=False),
        Binding("U", "unlock", "Unlock", show=False),
        Binding("c", "close", "Close", show=False),
        Binding("C", "close", "Close", show=False),
        Binding("s", "save", "Save", show=False),
        Binding("S", "save", "Save", show=False),
        Binding("r", "revert", "Revert", show=False),
        Binding("R", "revert", "Revert", show=False),
        Binding("e", "edit", "Edit", show=False),
        Binding("E", "edit", "Edit", show=False),
        Binding("d", "delete", "Delete", show=False),
        Binding("D", "delete", "Delete", show=False),
        Binding("n", "rename", "Rename", show=False),
        Binding("N", "rename", "Rename", show=False),
        Binding("v", "toggle_view", "Toggle View", show=False),
        Binding("V", "fullscreen_plan", "Fullscreen plan", show=False),
        Binding("b", "brainstorm", "Brainstorm", show=False),
        Binding("B", "brainstorm", "Brainstorm", show=False),
        Binding("tab", "focus_minimap", "Minimap", show=False),
    ]

    def __init__(self, task: Task, manager: TaskManager = None, read_only: bool = False):
        super().__init__()
        self.task_data = task
        self.manager = manager
        self.read_only = read_only
        self._lock_info = None
        self._original_values = {
            "priority": task.metadata.get("priority", "medium"),
            "effort": task.metadata.get("effort", "medium"),
            "status": task.metadata.get("status", "Ready"),
            "issue_type": task.metadata.get("issue_type", "feature"),
        }
        self._current_values = dict(self._original_values)
        self._showing_plan = False
        self._plan_path = self._resolve_plan_path() if manager else None
        self._plan_parsed = None
        self._plan_text = ""

    def _resolve_plan_path(self):
        """Resolve the plan file path for this task."""
        is_child = self.task_data.filepath.parent.name.startswith("t")
        if is_child:
            parent_num = self.manager.get_parent_num_for_child(self.task_data)
            plan_name = "p" + self.task_data.filename[1:]
            plan_path = Path("aiplans") / parent_num.replace("t", "p", 1) / plan_name
        else:
            plan_name = "p" + self.task_data.filename[1:]
            plan_path = Path("aiplans") / plan_name
        return plan_path if plan_path.exists() else None

    def _build_risk_fields(self, meta):
        """Read-only risk widgets — shown only when explicitly set in metadata.

        Risk has no default: an absent field means unset, so nothing is shown.
        Risk levels are decided by the task workflow / plan, not edited here.
        """
        out = []
        if meta.get("risk_code_health"):
            out.append(ReadOnlyField(
                f"[b]Code-health risk:[/b] {meta.get('risk_code_health')}", classes="meta-ro"))
        if meta.get("risk_goal_achievement"):
            out.append(ReadOnlyField(
                f"[b]Goal risk:[/b] {meta.get('risk_goal_achievement')}", classes="meta-ro"))
        return out

    def _build_relations_fields(self, meta):
        """Dependencies & hierarchy metadata widgets (in display order)."""
        out = []
        if meta.get("depends"):
            deps = meta["depends"]
            if deps and self.manager:
                out.append(DependsField(deps, self.manager, self.task_data, classes="meta-ro"))
            elif deps:
                dep_str = ", ".join(str(d) for d in deps)
                out.append(ReadOnlyField(f"[b]Depends:[/b] {dep_str}", classes="meta-ro"))
        xdeprepo = meta.get("xdeprepo")
        xdeps = meta.get("xdeps", []) or []
        if xdeprepo and xdeps:
            if self.manager:
                out.append(CrossRepoDepsField(xdeprepo, xdeps, self.manager,
                                              classes="meta-ro"))
            else:
                xdep_str = ", ".join(
                    f"{xdeprepo}#{str(xd).lstrip('t')}" for xd in xdeps
                )
                out.append(ReadOnlyField(
                    f"[b]Cross-repo deps:[/b] ↗ {xdep_str}", classes="meta-ro"))
        if meta.get("verifies"):
            verifies = meta["verifies"]
            if verifies and self.manager:
                out.append(VerifiesField(verifies, self.manager, self.task_data, classes="meta-ro"))
            elif verifies:
                v_str = ", ".join(str(v) for v in verifies)
                out.append(ReadOnlyField(f"[b]Verifies:[/b] {v_str}", classes="meta-ro"))
        # Parent field for child tasks
        if self.task_data.filepath.parent != TASKS_DIR and self.manager:
            parent_num = self.manager.get_parent_num_for_child(self.task_data)
            if parent_num:
                out.append(ParentField(parent_num, self.manager, classes="meta-ro"))
        # Children field for parent tasks
        if meta.get("children_to_implement"):
            children_ids = meta["children_to_implement"]
            if children_ids and self.manager:
                out.append(ChildrenField(children_ids, self.manager, self.task_data,
                                         classes="meta-ro"))
            elif children_ids:
                children = ", ".join(str(c) for c in children_ids)
                out.append(ReadOnlyField(f"[b]Children:[/b] {children}", classes="meta-ro"))
        # Folded tasks field
        if meta.get("folded_tasks"):
            folded_ids = meta["folded_tasks"]
            if folded_ids and self.manager:
                out.append(FoldedTasksField(folded_ids, self.manager,
                                            self.task_data, classes="meta-ro"))
            elif folded_ids:
                folded_str = ", ".join(str(f) for f in folded_ids)
                out.append(ReadOnlyField(
                    f"[b]Folded Tasks:[/b] {folded_str}", classes="meta-ro"))
        # Folded into field
        if meta.get("folded_into"):
            folded_into_num = str(meta["folded_into"])
            if self.manager:
                out.append(FoldedIntoField(folded_into_num, self.manager, classes="meta-ro"))
            else:
                out.append(ReadOnlyField(
                    f"[b]Folded Into:[/b] t{folded_into_num}", classes="meta-ro"))
        # Topic anchor (group key) — editable; shown even when unset so a root
        # task can be given an anchor. Read-only screens (archived) show a plain
        # line only when an anchor is actually set.
        anchor_val = _bare_topic_id(meta.get("anchor"))
        if self.manager and not self.read_only:
            out.append(AnchorField(anchor_val, self.manager, self.task_data,
                                   read_only=False, classes="meta-ro"))
        elif anchor_val:
            out.append(ReadOnlyField(f"[b]Anchor:[/b] t{anchor_val}", classes="meta-ro"))
        return out

    def _build_tracking_fields(self, meta):
        """Tracking & provenance metadata widgets (in display order)."""
        out = []
        if meta.get("labels"):
            out.append(ReadOnlyField(f"[b]Labels:[/b] {', '.join(meta['labels'])}", classes="meta-ro"))
        if meta.get("assigned_to"):
            out.append(ReadOnlyField(f"[b]Assigned to:[/b] {meta['assigned_to']}", classes="meta-ro"))
        if meta.get("issue"):
            out.append(IssueField(meta["issue"], classes="meta-ro"))
        if meta.get("pull_request"):
            out.append(PullRequestField(meta["pull_request"], classes="meta-ro"))
        if meta.get("contributor"):
            contributor_text = meta["contributor"]
            if meta.get("contributor_email"):
                contributor_text += f" ({meta['contributor_email']})"
            out.append(ReadOnlyField(f"  [b]Contributor:[/b] @{contributor_text}", classes="meta-ro"))
        if meta.get("implemented_with"):
            out.append(ReadOnlyField(f"[b]Implemented with:[/b] {meta['implemented_with']}", classes="meta-ro"))
        dates = []
        if meta.get("created_at"):
            dates.append(f"[b]Created:[/b] {meta['created_at']}")
        if meta.get("updated_at"):
            dates.append(f"[b]Updated:[/b] {meta['updated_at']}")
        if dates:
            out.append(ReadOnlyField("  |  ".join(dates), classes="meta-ro"))
        return out

    def _build_lockfiles_fields(self, meta):
        """File references + lock status widgets. Side effect: sets self._lock_info."""
        out = []
        # File references field (read-only, navigate via enter)
        if self.manager:
            file_refs = meta.get("file_references") or []
            out.append(FileReferencesField(
                file_refs, self.manager, self.task_data,
                classes="meta-ro"))
        # Lock status (computes self._lock_info, consumed by compose for buttons)
        if self.manager:
            task_num, _ = TaskCard._parse_filename(self.task_data.filename)
            lock_id = task_num.lstrip("t")
            self._lock_info = self.manager.lock_map.get(lock_id)
        if self._lock_info:
            locked_by = self._lock_info["locked_by"]
            locked_at = self._lock_info["locked_at"]
            hostname = self._lock_info.get("hostname", "")
            stale_marker = ""
            try:
                lock_time = datetime.strptime(locked_at, "%Y-%m-%d %H:%M")
                hours_ago = (datetime.now() - lock_time).total_seconds() / 3600
                if hours_ago > 24:
                    stale_marker = " [yellow](may be stale)[/yellow]"
            except (ValueError, TypeError):
                pass
            host_str = f" on {hostname}" if hostname else ""
            out.append(ReadOnlyField(
                f"[b]\U0001f512 Locked:[/b] {locked_by}{host_str} since {locked_at}{stale_marker}",
                classes="meta-ro"))
        else:
            out.append(ReadOnlyField(
                "[b]\U0001f513 Lock:[/b] [dim]Unlocked[/dim]",
                classes="meta-ro"))
        return out

    def compose(self):
        task_num, task_name = TaskCard._parse_filename(self.task_data.filename)
        display_title = f"{task_num} {task_name}".strip()
        meta = self.task_data.metadata

        with Container(id="detail_dialog"):
            with Horizontal(id="detail_title_bar"):
                yield Label(f"\U0001f4c4 {display_title}", id="detail_title")
                # View-mode indicator lives at the end of the title line; its
                # background changes between Task and Plan (see toggle_view).
                yield Label("Task", id="view_indicator", classes="viewing-task")

            is_done = meta.get("status", "") == "Done"
            is_folded = meta.get("status", "") == "Folded"
            is_done_or_ro = is_done or is_folded or self.read_only
            with Container(id="meta_editable"):
                if is_done_or_ro:
                    yield ReadOnlyField(f"[b]Priority:[/b] {meta.get('priority', 'medium')}", classes="meta-ro")
                    yield ReadOnlyField(f"[b]Effort:[/b] {meta.get('effort', 'medium')}", classes="meta-ro")
                    yield ReadOnlyField(f"[b]Status:[/b] {meta.get('status', 'Ready')}", classes="meta-ro")
                    yield ReadOnlyField(f"[b]Type:[/b] {meta.get('issue_type', 'feature')}", classes="meta-ro")
                else:
                    yield CycleField("Priority", list(LEVELS_ASCENDING),
                                     meta.get("priority", "medium"), "priority",
                                     id="cf_priority")
                    yield CycleField("Effort", list(LEVELS_ASCENDING),
                                     meta.get("effort", "medium"), "effort",
                                     id="cf_effort")
                    status_options = ["Ready", "Editing", "Implementing", "Postponed"]
                    yield CycleField("Status", status_options,
                                     meta.get("status", "Ready"), "status",
                                     id="cf_status")
                    yield CycleField("Type", _load_task_types(),
                                     meta.get("issue_type", "feature"), "issue_type",
                                     id="cf_issue_type")

            # --- Grouped, collapsible secondary metadata ---
            # Risk (read-only) — only present when explicitly set in metadata.
            risk = self._build_risk_fields(meta)
            if risk:
                with Collapsible(title=f"Risk ({len(risk)})",
                                 collapsed=True, id="sec_risk", classes="meta-section"):
                    yield from risk

            relations = self._build_relations_fields(meta)
            if relations:
                with Collapsible(title=f"Dependencies & hierarchy ({len(relations)})",
                                 collapsed=True, id="sec_relations", classes="meta-section"):
                    yield from relations

            tracking = self._build_tracking_fields(meta)
            if tracking:
                with Collapsible(title=f"Tracking & provenance ({len(tracking)})",
                                 collapsed=True, id="sec_tracking", classes="meta-section"):
                    yield from tracking

            lockfiles = self._build_lockfiles_fields(meta)
            if lockfiles:
                with Collapsible(title="Lock & files",
                                 collapsed=True, id="sec_lockfiles", classes="meta-section"):
                    yield from lockfiles

            has_plan = self._plan_path is not None

            with VerticalScroll(id="md_view"):
                yield Markdown(self.task_data.content)

            # Button rows
            is_locked = self._lock_info is not None
            with Container(id="detail_buttons_area"):
                with Horizontal(id="detail_buttons_workflow"):
                    yield Button(self.label("pick", "Pick"), variant="warning", id="btn_pick", disabled=is_done_or_ro)
                    yield Button(self.label("brainstorm", "Brainstorm"), variant="primary", id="btn_brainstorm", disabled=is_done_or_ro or is_locked)
                    yield Button("\U0001f512 " + self.label("lock", "Lock"), variant="primary", id="btn_lock",
                                 disabled=is_done_or_ro or is_locked)
                    yield Button("\U0001f513 " + self.label("unlock", "Unlock"), variant="warning", id="btn_unlock",
                                 disabled=not is_locked)
                    yield Button(self.label("close", "Close"), variant="default", id="btn_close")
                with Horizontal(id="detail_buttons_file"):
                    yield Button(self.label("toggle_view", "View Plan"), variant="primary", id="btn_view",
                                 disabled=not has_plan)
                    yield Button(self.label("save", "Save Changes"), variant="success", id="btn_save",
                                 disabled=True)
                    is_modified = self.manager.is_modified(self.task_data) if self.manager else False
                    yield Button(self.label("revert", "Revert"), variant="error", id="btn_revert",
                                 disabled=is_done_or_ro or not is_modified)
                    yield Button(self.label("edit", "Edit"), variant="primary", id="btn_edit", disabled=is_done_or_ro)
                    yield Button(self.label("rename", "Name"), variant="primary", id="btn_rename", disabled=is_done_or_ro or is_locked)
                    can_delete = (not is_done and not is_folded and not self.read_only
                                  and self.task_data.metadata.get("status", "") != "Implementing")
                    yield Button(self.label("delete", "Delete/Archive"), variant="error", id="btn_delete",
                                 disabled=not can_delete)

    @on(CycleField.Changed)
    def on_cycle_changed(self, event: CycleField.Changed):
        self._current_values[event.field.field_key] = event.value
        self._update_save_button()
        self._update_delete_button()

    def _update_save_button(self):
        is_dirty = self._current_values != self._original_values
        btn_save = self.query_one("#btn_save", Button)
        btn_save.disabled = not is_dirty

    def _update_delete_button(self):
        status = self._current_values.get("status", "")
        btn_delete = self.query_one("#btn_delete", Button)
        btn_delete.disabled = (status == "Implementing")

    @on(Button.Pressed, "#btn_save")
    def save_changes(self):
        # Determine which fields the user actually changed
        changed_fields = {
            key: value for key, value in self._current_values.items()
            if value != self._original_values.get(key)
        }
        if not changed_fields:
            return
        # Reload from disk to pick up external changes (e.g. Claude Code)
        if not self.task_data.load():
            self.app.notify("Task file no longer exists", severity="error")
            return
        # Apply only the changed fields
        for key, value in changed_fields.items():
            self.task_data.metadata[key] = value
        self.task_data.save_with_timestamp()
        # Update originals to reflect saved state
        for key in self._current_values:
            self._original_values[key] = self.task_data.metadata.get(key, self._current_values[key])
        self._current_values = dict(self._original_values)
        self._update_save_button()

    @on(Button.Pressed, "#btn_revert")
    def revert_task(self):
        """Revert task file to last committed version in git."""
        try:
            result = subprocess.run(
                [*_task_git_cmd(), "checkout", "--", str(self.task_data.filepath)],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0:
                self.task_data.load()
                self.app.notify("Reverted to last committed version", severity="information")
                self.dismiss("reverted")
            else:
                error = result.stderr.strip() or result.stdout.strip()
                self.app.notify(f"Revert failed: {error}", severity="error")
        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            self.app.notify(f"Revert failed: {e}", severity="error")

    @on(Button.Pressed, "#btn_close")
    def close_dialog(self):
        self.dismiss()

    @on(Button.Pressed, "#btn_edit")
    def edit_task(self):
        if self._showing_plan:
            self.dismiss("edit_plan")
        else:
            self.dismiss("edit")

    def _read_plan_content(self):
        """Return plan content for the current task with YAML frontmatter stripped, or None."""
        if not self._plan_path:
            return None
        content = self._plan_path.read_text(encoding="utf-8")
        if content.startswith("---"):
            parts = content.split("---", 2)
            if len(parts) >= 3:
                content = parts[2].strip()
        return content

    @on(Button.Pressed, "#btn_view")
    def toggle_view(self):
        """Toggle between task content and plan content."""
        if not self._plan_path:
            self.app.notify("No plan file found", severity="warning")
            return
        self._showing_plan = not self._showing_plan
        md_widget = self.query_one("#md_view Markdown", Markdown)
        indicator = self.query_one("#view_indicator", Label)
        btn_view = self.query_one("#btn_view", Button)

        md_view = self.query_one("#md_view", VerticalScroll)

        if self._showing_plan:
            content = self._read_plan_content() or ""
            md_widget.update(content)
            indicator.update("Plan")
            indicator.remove_class("viewing-task")
            indicator.add_class("viewing-plan")
            btn_view.label = "(V)iew Task"
            md_view.styles.border = ("solid", "#FFB86C")
            self._mount_or_update_minimap(md_view, content)
        else:
            md_widget.update(self.task_data.content)
            indicator.update("Task")
            indicator.remove_class("viewing-plan")
            indicator.add_class("viewing-task")
            btn_view.label = "(V)iew Plan"
            md_view.styles.border = None
            self._remove_minimap(md_view)

    def _mount_or_update_minimap(self, md_view, plan_content):
        """Mount or repopulate #board_minimap inside #md_view based on plan sections."""
        try:
            from section_viewer import SectionMinimap, parse_sections
        except Exception as exc:
            self.app.notify(f"Section viewer unavailable: {exc}", severity="warning")
            return
        parsed = parse_sections(plan_content)
        if not parsed.sections:
            self._plan_parsed = None
            self._plan_text = ""
            self._remove_minimap(md_view)
            return
        self._plan_parsed = parsed
        self._plan_text = plan_content
        existing = md_view.query("#board_minimap")
        if not existing:
            minimap = SectionMinimap(id="board_minimap")
            md_view.mount(minimap, before="Markdown")
        md_view.query_one("#board_minimap", SectionMinimap).populate(parsed)

    def _remove_minimap(self, md_view):
        """Remove #board_minimap from #md_view if present."""
        for w in list(md_view.query("#board_minimap")):
            w.remove()

    def on_section_minimap_section_selected(self, event):
        """Scroll the plan Markdown to the selected section."""
        if self._plan_parsed is None or not self._plan_text:
            return
        try:
            from section_viewer import estimate_section_y
        except Exception:
            return
        md_view = self.query_one("#md_view", VerticalScroll)
        total = self._plan_text.count("\n") + 1
        y = estimate_section_y(
            self._plan_parsed, event.section_name, total, md_view.virtual_size.height
        )
        if y is not None:
            md_view.scroll_to(y=y, animate=False)
        event.stop()

    def on_section_minimap_toggle_focus(self, event):
        """Minimap Tab -> focus plan Markdown."""
        try:
            md = self.query_one("#md_view Markdown", Markdown)
        except Exception:
            event.stop()
            return
        md.focus()
        event.stop()

    def action_fullscreen_plan(self):
        """Push the full-screen SectionViewerScreen for the current plan."""
        plan_content = self._read_plan_content()
        if not plan_content:
            self.app.notify("No plan file found", severity="warning")
            return
        try:
            from section_viewer import SectionViewerScreen
        except Exception as exc:
            self.app.notify(f"Section viewer unavailable: {exc}", severity="warning")
            return
        task_num, _ = TaskCard._parse_filename(self.task_data.filename)
        self.app.push_screen(
            SectionViewerScreen(plan_content, title=f"Plan for {task_num}")
        )

    def action_focus_minimap(self):
        """Tab from plan Markdown -> focus minimap. SkipAction guard keeps form Tab-nav intact."""
        from textual.actions import SkipAction
        try:
            md = self.screen.query_one("#md_view Markdown", Markdown)
        except Exception:
            raise SkipAction()
        minimaps = self.screen.query("#board_minimap")
        if self.screen.focused is not md or not minimaps:
            raise SkipAction()
        minimaps.first().focus_first_row()

    @on(Button.Pressed, "#btn_rename")
    def rename_task(self):
        self.dismiss("rename")

    @on(Button.Pressed, "#btn_delete")
    def delete_task(self):
        self.dismiss("delete_archive")

    @on(Button.Pressed, "#btn_pick")
    def pick_task(self):
        self.dismiss("pick")

    @on(Button.Pressed, "#btn_brainstorm")
    def brainstorm_task(self):
        self.dismiss("brainstorm")

    @on(Button.Pressed, "#btn_lock")
    def lock_task(self):
        """Lock this task via aitask_lock.sh."""
        task_num, _ = TaskCard._parse_filename(self.task_data.filename)
        task_id = task_num.lstrip("t")
        default_email = _get_user_email()

        def on_email(email):
            if email is None:
                return
            self.app.push_screen(LoadingOverlay("Locking task..."))
            self._do_lock(task_id, email)

        self.app.push_screen(LockEmailScreen(task_id, default_email), on_email)

    @work(thread=True)
    def _do_lock(self, task_id: str, email: str):
        """Run lock subprocess in a thread worker."""
        try:
            result = subprocess.run(
                ["./.aitask-scripts/aitask_lock.sh", "--lock", task_id, "--email", email],
                capture_output=True, text=True, timeout=15
            )
            self.app.call_from_thread(self.app.pop_screen)  # dismiss LoadingOverlay
            if result.returncode == 0:
                self.app.call_from_thread(self.app.notify, f"Locked t{task_id}", severity="information")
                self.app.call_from_thread(self.dismiss, "locked")
            else:
                error = result.stderr.strip() or result.stdout.strip()
                self.app.call_from_thread(self.app.notify, f"Lock failed: {error}", severity="error")
        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            self.app.call_from_thread(self.app.pop_screen)  # dismiss LoadingOverlay
            self.app.call_from_thread(self.app.notify, f"Lock failed: {e}", severity="error")

    @on(Button.Pressed, "#btn_unlock")
    def unlock_task(self):
        """Unlock this task via aitask_lock.sh."""
        task_num, _ = TaskCard._parse_filename(self.task_data.filename)
        task_id = task_num.lstrip("t")

        def do_unlock():
            self.app.push_screen(LoadingOverlay("Unlocking task..."))
            self._do_unlock(task_id)

        if self._lock_info:
            my_email = _get_user_email()
            locked_by = self._lock_info["locked_by"]
            if my_email and locked_by != my_email:
                def on_confirm(confirmed):
                    if confirmed:
                        do_unlock()
                self.app.push_screen(
                    UnlockConfirmScreen(
                        task_id, locked_by,
                        self._lock_info.get("locked_at", "?"),
                        self._lock_info.get("hostname", "?"),
                    ),
                    on_confirm,
                )
                return

        do_unlock()

    @work(thread=True)
    def _do_unlock(self, task_id: str):
        """Run unlock subprocess in a thread worker."""
        try:
            result = subprocess.run(
                ["./.aitask-scripts/aitask_lock.sh", "--unlock", task_id],
                capture_output=True, text=True, timeout=15
            )
            self.app.call_from_thread(self.app.pop_screen)  # dismiss LoadingOverlay
            if result.returncode == 0:
                self.app.call_from_thread(self.app.notify, f"Unlocked t{task_id}", severity="information")
                meta = self.task_data.metadata
                if meta.get("status") == "Implementing" and meta.get("assigned_to"):
                    assigned_to = meta["assigned_to"]
                    def on_reset_confirmed(confirmed):
                        if confirmed:
                            if not self.task_data.load():
                                self.app.notify("Task file no longer exists", severity="error")
                                self.dismiss("unlocked")
                                return
                            self.task_data.metadata["status"] = "Ready"
                            self.task_data.metadata["assigned_to"] = ""
                            self.task_data.save_with_timestamp()
                        self.dismiss("unlocked")
                    self.app.call_from_thread(
                        self.app.push_screen,
                        ResetTaskConfirmScreen(task_id, assigned_to),
                        on_reset_confirmed,
                    )
                    return
                self.app.call_from_thread(self.dismiss, "unlocked")
            else:
                error = result.stderr.strip() or result.stdout.strip()
                self.app.call_from_thread(self.app.notify, f"Unlock failed: {error}", severity="error")
        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            self.app.call_from_thread(self.app.pop_screen)  # dismiss LoadingOverlay
            self.app.call_from_thread(self.app.notify, f"Unlock failed: {e}", severity="error")

    def action_close_modal(self):
        self.dismiss()

    def action_pick(self):
        btn = self.query_one("#btn_pick", Button)
        if not btn.disabled:
            self.pick_task()

    def action_brainstorm(self):
        btn = self.query_one("#btn_brainstorm", Button)
        if not btn.disabled:
            self.brainstorm_task()

    def action_lock(self):
        btn = self.query_one("#btn_lock", Button)
        if not btn.disabled:
            self.lock_task()

    def action_unlock(self):
        btn = self.query_one("#btn_unlock", Button)
        if not btn.disabled:
            self.unlock_task()

    def action_close(self):
        self.close_dialog()

    def action_save(self):
        btn = self.query_one("#btn_save", Button)
        if not btn.disabled:
            self.save_changes()

    def action_revert(self):
        btn = self.query_one("#btn_revert", Button)
        if not btn.disabled:
            self.revert_task()

    def action_edit(self):
        btn = self.query_one("#btn_edit", Button)
        if not btn.disabled:
            self.edit_task()

    def action_toggle_view(self):
        btn = self.query_one("#btn_view", Button)
        if not btn.disabled:
            self.toggle_view()

    def action_rename(self):
        btn = self.query_one("#btn_rename", Button)
        if not btn.disabled:
            self.rename_task()

    def action_delete(self):
        btn = self.query_one("#btn_delete", Button)
        if not btn.disabled:
            self.delete_task()

class RenameTaskScreen(ModalScreen):
    """Modal dialog to rename a task (change the description part of the filename)."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=False),
    ]

    def __init__(self, task_filename: str):
        super().__init__()
        self.task_filename = task_filename
        self.task_num, self.current_name = TaskCard._parse_filename(task_filename)

    def compose(self):
        with Container(id="rename_dialog"):
            yield Label(f"Rename Task {self.task_num}", id="rename_title")
            yield Label(f"Prefix: [b]{self.task_num}_[/b] (fixed)")
            yield Input(value=self.current_name.replace(" ", "_"), id="rename_input",
                        placeholder="new_task_name", select_on_focus=False)
            with Horizontal(id="detail_buttons"):
                yield Button("Rename", variant="success", id="btn_do_rename")
                yield Button("Cancel", variant="default", id="btn_rename_cancel")

    @on(Button.Pressed, "#btn_do_rename")
    def do_rename(self):
        new_name = self.query_one("#rename_input", Input).value.strip()
        if not new_name:
            return
        self.dismiss(("rename", new_name))

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self.do_rename()

    @on(Button.Pressed, "#btn_rename_cancel")
    def cancel(self):
        self.dismiss(None)

    def action_cancel(self):
        self.dismiss(None)


class CommitMessageScreen(ModalScreen):
    """Modal dialog to enter a commit message and confirm git commit."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=False),
    ]

    def __init__(self, tasks_to_commit: list[Task], manager: TaskManager):
        super().__init__()
        self.tasks_to_commit = tasks_to_commit
        self.manager = manager

    def compose(self):
        if len(self.tasks_to_commit) == 1:
            task = self.tasks_to_commit[0]
            task_num, task_name = TaskCard._parse_filename(task.filename)
            default_msg = f"ait: Update {task_num}: {task_name}"
        else:
            task_nums = []
            for t in self.tasks_to_commit:
                num, _ = TaskCard._parse_filename(t.filename)
                task_nums.append(num)
            default_msg = f"ait: Update tasks: {', '.join(task_nums)}"

        with Container(id="commit_dialog"):
            yield Label("Git Commit", id="commit_title")
            file_list = "\n".join(f"  {str(t.filepath)}" for t in self.tasks_to_commit)
            yield Label(f"Files to commit:\n{file_list}", id="commit_files")
            yield Label("Commit message:")
            yield Input(value=default_msg, id="commit_msg_input")
            with Horizontal(id="detail_buttons"):
                yield Button("Commit", variant="success", id="btn_commit")
                yield Button("Cancel", variant="default", id="btn_commit_cancel")

    @on(Button.Pressed, "#btn_commit")
    def do_commit(self):
        msg = self.query_one("#commit_msg_input", Input).value.strip()
        if not msg:
            return
        self.dismiss(("commit", msg))

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self.do_commit()

    @on(Button.Pressed, "#btn_commit_cancel")
    def cancel(self):
        self.dismiss(None)

    def action_cancel(self):
        self.dismiss(None)

# --- Column Customization Screens ---

PALETTE_COLORS = [
    ("#FF5555", "Red"),
    ("#FFB86C", "Orange"),
    ("#F1FA8C", "Yellow"),
    ("#50FA7B", "Green"),
    ("#8BE9FD", "Cyan"),
    ("#BD93F9", "Purple"),
    ("#FF79C6", "Pink"),
    ("#6272A4", "Gray"),
]


class ColorSwatch(Static):
    """A clickable color swatch for the palette."""

    can_focus = True

    class Selected(Message):
        def __init__(self, color: str):
            super().__init__()
            self.color = color

    def __init__(self, color: str, label: str, selected: bool = False):
        super().__init__()
        self.color = color
        self.label = label
        self.is_selected = selected

    def render(self) -> str:
        marker = "\u25cf" if self.is_selected else "\u25cb"
        return f"[{self.color}]{marker} \u2588\u2588[/]"

    def on_click(self):
        self.post_message(self.Selected(self.color))

    def on_key(self, event):
        if event.key in ("enter", "space"):
            self.post_message(self.Selected(self.color))
            event.prevent_default()
            event.stop()

    def on_focus(self):
        self.styles.border = ("round", self.color)

    def on_blur(self):
        self.styles.border = None


class ColumnEditScreen(ModalScreen):
    """Modal dialog for adding or editing a kanban column."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=False),
    ]

    def __init__(self, manager: TaskManager, col_id: str = None, mode: str = "add"):
        super().__init__()
        self.manager = manager
        self.col_id = col_id
        self.mode = mode
        self.col_conf = manager.get_column_conf(col_id) if col_id else None
        self.selected_color = self.col_conf["color"] if self.col_conf else PALETTE_COLORS[0][0]

    @staticmethod
    def _generate_col_id(name: str, existing_ids: list) -> str:
        """Generate a unique column ID from a display name."""
        # Remove emojis and non-ASCII, lowercase, replace spaces/special with underscore
        slug = re.sub(r'[^\x00-\x7F]+', '', name)  # strip non-ASCII (emojis)
        slug = slug.strip().lower()
        slug = re.sub(r'[^a-z0-9]+', '_', slug)  # replace non-alnum with _
        slug = slug.strip('_')  # trim leading/trailing underscores
        slug = slug[:20]  # limit length
        if not slug:
            slug = "column"
        # Ensure uniqueness
        base = slug
        counter = 2
        while slug in existing_ids:
            slug = f"{base}_{counter}"
            counter += 1
        return slug

    def compose(self):
        title = "Add New Column" if self.mode == "add" else f"Edit Column: {self.col_conf['title']}"
        with Container(id="column_edit_dialog"):
            yield Label(title, id="column_edit_title")
            yield Input(
                value=self.col_conf["title"] if self.col_conf else "",
                placeholder="Column name",
                id="col_title_input",
            )
            with Horizontal(id="color_palette"):
                yield Label("Color ", id="color_label")
                for color, label in PALETTE_COLORS:
                    yield ColorSwatch(color, label, selected=(color == self.selected_color))
            with Horizontal(id="detail_buttons"):
                yield Button("Save", variant="success", id="btn_col_save")
                yield Button("Cancel", variant="default", id="btn_col_cancel")

    @on(ColorSwatch.Selected)
    def on_color_selected(self, event: ColorSwatch.Selected):
        self.selected_color = event.color
        for swatch in self.query(ColorSwatch):
            swatch.is_selected = (swatch.color == event.color)
            swatch.refresh()

    @on(Button.Pressed, "#btn_col_save")
    def save(self):
        title = self.query_one("#col_title_input", Input).value.strip()
        if not title:
            self.app.notify("Title is required", severity="warning")
            return
        color = self.selected_color
        if self.mode == "add":
            existing_ids = [c["id"] for c in self.manager.columns]
            col_id = self._generate_col_id(title, existing_ids)
            self.dismiss(("add", col_id, title, color))
        else:
            self.dismiss(("edit", self.col_id, title, color))

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self.save()

    @on(Button.Pressed, "#btn_col_cancel")
    def cancel(self):
        self.dismiss(None)

    def action_cancel(self):
        self.dismiss(None)


class DeleteColumnConfirmScreen(ModalScreen):
    """Confirmation dialog to delete a column."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=False),
    ]

    def __init__(self, col_conf: dict, task_count: int):
        super().__init__()
        self.col_conf = col_conf
        self.task_count = task_count

    def compose(self):
        msg = f"Delete column '{self.col_conf['title']}'?"
        if self.task_count > 0:
            msg += f"\n\n{self.task_count} task(s) will be moved to Unsorted / Inbox."
        with Container(id="dep_picker_dialog"):
            yield Label(msg, id="dep_picker_title")
            with Horizontal(id="detail_buttons"):
                yield Button("Delete", variant="error", id="btn_confirm_col_delete")
                yield Button("Cancel", variant="default", id="btn_cancel_col_delete")

    @on(Button.Pressed, "#btn_confirm_col_delete")
    def confirm(self):
        self.dismiss(True)

    @on(Button.Pressed, "#btn_cancel_col_delete")
    def cancel(self):
        self.dismiss(False)

    def action_cancel(self):
        self.dismiss(False)


DEFAULT_REFRESH_OPTIONS = ["0", "1", "2", "5", "10", "15", "30"]


class SettingsScreen(ModalScreen):
    """Modal dialog for editing board settings."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=False),
    ]

    def __init__(self, manager: TaskManager):
        super().__init__()
        self.manager = manager

    def compose(self):
        current_minutes = str(self.manager.auto_refresh_minutes)
        if current_minutes not in DEFAULT_REFRESH_OPTIONS:
            current_minutes = "5"
        with Container(id="settings_dialog"):
            yield Label("Board Settings", id="settings_title")
            yield CycleField(
                "Auto-refresh (min)",
                DEFAULT_REFRESH_OPTIONS,
                current_minutes,
                "auto_refresh_minutes",
                id="cf_auto_refresh",
            )
            yield Label("  [dim]0 = disabled[/dim]", classes="settings-hint")
            current_sync = "yes" if self.manager.settings.get("sync_on_refresh", False) else "no"
            yield CycleField(
                "Sync on refresh",
                ["no", "yes"],
                current_sync,
                "sync_on_refresh",
                id="cf_sync_on_refresh",
            )
            yield Label("  [dim]Push/pull task data on each auto-refresh[/dim]", classes="settings-hint")
            with Horizontal(id="detail_buttons"):
                yield Button("Save", variant="success", id="btn_settings_save")
                yield Button("Cancel", variant="default", id="btn_settings_cancel")

    @on(Button.Pressed, "#btn_settings_save")
    def save_settings(self):
        refresh_field = self.query_one("#cf_auto_refresh", CycleField)
        new_minutes = int(refresh_field.current_value)
        sync_field = self.query_one("#cf_sync_on_refresh", CycleField)
        new_sync = sync_field.current_value == "yes"
        self.dismiss({"auto_refresh_minutes": new_minutes, "sync_on_refresh": new_sync})

    @on(Button.Pressed, "#btn_settings_cancel")
    def cancel(self):
        self.dismiss(None)

    def action_cancel(self):
        self.dismiss(None)


class LoadingOverlay(ModalScreen):
    """Modal overlay showing a LoadingIndicator with a message."""

    def __init__(self, message: str = "Working..."):
        super().__init__()
        self._message = message

    def compose(self) -> ComposeResult:
        with Container(id="loading_dialog"):
            yield Label(self._message, id="loading_message")
            yield LoadingIndicator()


class ColumnSelectItem(Static):
    """A selectable column item in the picker."""

    can_focus = True

    def __init__(self, col_conf: dict):
        super().__init__()
        self.col_conf = col_conf

    def render(self) -> str:
        return f"  [{self.col_conf['color']}]\u2588\u2588[/] {self.col_conf['title']} ({self.col_conf['id']})"

    def on_key(self, event):
        if event.key == "enter":
            self.screen.dismiss(self.col_conf["id"])
            event.prevent_default()
            event.stop()

    def on_click(self):
        self.screen.dismiss(self.col_conf["id"])

    def on_focus(self):
        self.add_class("dep-item-focused")

    def on_blur(self):
        self.remove_class("dep-item-focused")


class ColumnSelectScreen(ModalScreen):
    """Select a column from the list for editing/deleting/collapsing/expanding."""

    BINDINGS = [
        Binding("escape", "cancel", "Close", show=False),
    ]

    def __init__(self, manager: TaskManager, action_label: str, columns: list[dict] = None):
        super().__init__()
        self.manager = manager
        self.action_label = action_label
        self.columns_list = columns if columns is not None else manager.columns

    def compose(self):
        with Container(id="dep_picker_dialog"):
            yield Label(f"Select column to {self.action_label.lower()}:", id="dep_picker_title")
            for col in self.columns_list:
                yield ColumnSelectItem(col)

    def action_cancel(self):
        self.dismiss(None)


# --- Command Palette Provider ---

class KanbanCommandProvider(Provider):
    """Provide column management commands to the Textual command palette."""

    async def discover(self) -> Hits:
        app = self.app
        yield DiscoveryHit(
            display="Add Column",
            command=app.action_add_column,
            help="Add a new column to the board",
        )
        yield DiscoveryHit(
            display="Edit Column",
            command=app.action_edit_column,
            help="Edit a column's title and color",
        )
        yield DiscoveryHit(
            display="Delete Column",
            command=app.action_delete_column,
            help="Delete a column (tasks move to Unsorted)",
        )
        yield DiscoveryHit(
            display="Collapse Column",
            command=app.action_collapse_column,
            help="Collapse a column to minimize its width",
        )
        yield DiscoveryHit(
            display="Expand Column",
            command=app.action_expand_column,
            help="Expand a collapsed column to full width",
        )
        yield DiscoveryHit(
            display="Settings",
            command=app.action_open_settings,
            help="Configure board settings (auto-refresh interval)",
        )
        yield DiscoveryHit(
            display="Sync with Remote",
            command=app.action_sync_remote,
            help="Push local changes and pull remote changes",
        )

    async def search(self, query: str) -> Hits:
        matcher = self.matcher(query)
        app = self.app
        commands = [
            ("Add Column", app.action_add_column, "Add a new column to the board"),
            ("Edit Column", app.action_edit_column, "Edit a column's title and color"),
            ("Delete Column", app.action_delete_column, "Delete a column (tasks move to Unsorted)"),
            ("Collapse Column", app.action_collapse_column, "Collapse a column to minimize its width"),
            ("Expand Column", app.action_expand_column, "Expand a collapsed column to full width"),
            ("Settings", app.action_open_settings, "Configure board settings (auto-refresh interval)"),
            ("Sync with Remote", app.action_sync_remote, "Push local changes and pull remote changes"),
        ]
        for display, callback, help_text in commands:
            score = matcher.match(display)
            if score > 0:
                yield Hit(
                    score=score,
                    match_display=matcher.highlight(display),
                    command=callback,
                    help=help_text,
                )


# --- Main Application ---

class KanbanApp(TuiSwitcherMixin, ShortcutsMixin, App):
    _shortcuts_scope = "board"

    CSS = """
    Screen { align: center middle; }
    #detail_dialog {
        width: 80%;
        height: 96%;
        background: $surface;
        border: thick $primary;
        padding: 1 2;
    }
    #detail_title_bar {
        dock: top;
        height: 3;
        background: $secondary;
    }
    #detail_title {
        width: 1fr;
        height: 100%;
        content-align: center middle;
        text-align: center;
        color: $text;
    }
    #detail_buttons {
        dock: bottom;
        height: 3;
        align: center middle;
    }
    #detail_buttons_area {
        dock: bottom;
        height: auto;
        max-height: 7;
    }
    #detail_buttons_workflow {
        height: 3;
        align: center middle;
    }
    #detail_buttons_file {
        height: 3;
        align: center middle;
    }
    #meta_editable { height: auto; padding: 0 1; }
    #detail_dialog .meta-section { padding-bottom: 0; border-top: hkey $secondary-background; }
    #detail_dialog .meta-section Contents { padding: 0 0 0 3; }
    CycleField { height: 1; width: 100%; padding: 0 1; }
    CycleField.cycle-focused { background: $primary 20%; border-left: thick $accent; }
    .meta-ro { height: 1; width: 100%; padding: 0 2; color: $text-muted; }
    .meta-ro.ro-focused { background: $primary 20%; border-left: thick $accent; }
    #btn_save:disabled { opacity: 50%; }
    #btn_delete:disabled { opacity: 50%; }
    #view_indicator { width: auto; height: 100%; content-align: center middle; padding: 0 2; text-style: bold; }
    #view_indicator.viewing-task { background: $primary; color: $text; }
    #view_indicator.viewing-plan { background: #FFB86C; color: $background; }
    #md_view { margin: 1 0; border: solid $secondary-background; }
    .task-title-row { height: auto; }
    .task-number { color: $accent; text-style: bold; width: auto; margin: 0 1 0 0; }
    .task-modified { color: #FFB86C; }
    .task-title { text-style: bold; width: 1fr; }
    .task-info { color: $text-muted; }
    .inflight-action { color: $text; }
    .inflight-ops { color: $accent; }
    .inflight-empty { height: 1; padding: 0 1; color: $text-muted; }
    .child-wrapper { height: auto; }
    .child-wrapper TaskCard { width: 1fr; }
    .child-connector { width: auto; height: auto; padding: 0; margin: 1 0 0 0; color: $text-muted; }
    #filter_area { dock: top; height: auto; margin: 0 0 1 0; }
    #view_col { width: 78; height: auto; }
    #view_label { height: 1; padding: 0 1; color: $text-muted; }
    #view_selector { height: 1; padding: 0 1; }
    .type-filter-summary { height: auto; padding: 0 1; color: $text-muted; }
    .type-filter-summary.hidden { display: none; }
    Input { width: 1fr; }
    .col-header-btn { width: auto; height: 1; padding: 0 1; }
    .col-header-edit-btn { width: auto; height: 1; padding: 0 1; background: black; color: white; }
    .col-header-row { height: auto; width: 100%; }
    .col-header-title { text-align: center; width: 100%; }
    .col-header-title-expanded { width: 1fr; text-align: center; }
    .col-header-count { text-align: center; width: 100%; color: $text-muted; }
    .collapsed-placeholder { height: 1; width: 100%; text-align: center; color: $text-muted; }
    .collapsed-placeholder:focus { background: $primary 30%; }
    #dep_picker_dialog {
        width: 60%;
        height: auto;
        max-height: 50%;
        background: $surface;
        border: thick $accent;
        padding: 1 2;
    }
    #dep_picker_title {
        text-align: center;
        padding: 0 0 1 0;
        text-style: bold;
    }
    #delarch_label {
        text-align: left;
        padding: 0 0 1 0;
    }
    DepPickerItem { height: 1; width: 100%; padding: 0 1; }
    DepPickerItem.dep-item-focused { background: $primary 20%; border-left: thick $accent; }
    ChildPickerItem { height: 1; width: 100%; padding: 0 1; }
    ChildPickerItem.dep-item-focused { background: $primary 20%; border-left: thick $accent; }
    #commit_dialog {
        width: 70%;
        height: auto;
        max-height: 60%;
        background: $surface;
        border: thick $accent;
        padding: 1 2;
    }
    #commit_title {
        text-align: center;
        padding: 0 0 1 0;
        text-style: bold;
    }
    #commit_files {
        padding: 0 1;
        color: $text-muted;
    }
    #rename_dialog {
        width: 60%;
        height: auto;
        max-height: 40%;
        background: $surface;
        border: thick $accent;
        padding: 1 2;
    }
    #rename_title {
        text-align: center;
        padding: 0 0 1 0;
        text-style: bold;
    }
    #column_edit_dialog {
        width: 60%;
        height: auto;
        max-height: 60%;
        background: $surface;
        border: thick $accent;
        padding: 1 2;
    }
    #column_edit_title {
        text-align: center;
        padding: 0 0 1 0;
        text-style: bold;
    }
    #color_palette {
        height: 3;
        width: 100%;
    }
    #color_label {
        width: auto;
        height: 3;
        content-align: left middle;
        padding: 0 1 0 0;
    }
    ColorSwatch {
        width: auto;
        height: 3;
        padding: 0 1;
        content-align: center middle;
    }
    #settings_dialog {
        width: 50%;
        height: auto;
        max-height: 40%;
        background: $surface;
        border: thick $accent;
        padding: 1 2;
    }
    #settings_title {
        text-align: center;
        padding: 0 0 1 0;
        text-style: bold;
    }
    .settings-hint {
        height: 1;
        padding: 0 2;
    }
    #loading_dialog {
        width: 40;
        height: 7;
        background: $surface;
        border: thick $primary;
        padding: 1 2;
        align: center middle;
    }
    #loading_message {
        text-align: center;
        width: 100%;
        height: 1;
        padding: 0 0 1 0;
    }
    #loading_dialog LoadingIndicator {
        height: 3;
    }
    """

    TITLE = "aitasks board"

    COMMANDS = App.COMMANDS | {KanbanCommandProvider}

    BINDINGS = [
        *TuiSwitcherMixin.SWITCHER_BINDINGS,
        *ShortcutsMixin.SHORTCUTS_MIXIN_BINDINGS,
        Binding("q", "quit", "Quit"),
        Binding("tab", "focus_search", "Search", show=False, priority=True),
        Binding("escape", "focus_board", "Board", show=False, priority=True),
        # Card Navigation (priority=True to override scroll container bindings)
        Binding("up", "nav_up", "Up", show=False, priority=True),
        Binding("down", "nav_down", "Down", show=False, priority=True),
        Binding("left", "nav_left", "Left", show=False, priority=True),
        Binding("right", "nav_right", "Right", show=False, priority=True),
        # Task Movement
        Binding("shift+right", "move_task_right", "Task >"),
        Binding("shift+left", "move_task_left", "< Task"),
        Binding("shift+up", "move_task_up", "Task Up"),
        Binding("shift+down", "move_task_down", "Task Down"),
        Binding("ctrl+up", "move_task_top", "Task Top", show=False),
        Binding("ctrl+down", "move_task_bottom", "Task Btm", show=False),
        Binding("enter", "view_details", "View/Edit"),
        Binding("r", "refresh_board", "Refresh"),
        Binding("s", "sync_remote", "Sync"),
        # Git Commit (shown conditionally via check_action)
        Binding("c", "commit_selected", "Commit"),
        Binding("C", "commit_all", "Commit All"),
        # Task Creation
        Binding("n", "create_task", "New Task"),
        # Pick task (shown conditionally via check_action)
        Binding("p", "pick_task", "Pick"),
        # Brainstorm task (shown conditionally via check_action)
        Binding("b", "brainstorm_task", "Brainstorm"),
        # Open cross-repo reference (shown conditionally via check_action)
        Binding("#", "open_cross_repo", "Cross-repo"),
        # Expand/Collapse children (shown conditionally via check_action)
        Binding("x", "toggle_children", "Toggle Children"),
        # Column Movement
        Binding("ctrl+right", "move_col_right", "Move Col >"),
        Binding("ctrl+left", "move_col_left", "< Move Col"),
        # Column Collapse
        Binding("X", "toggle_column_collapsed", "Collapse Col", show=False),
        # Settings
        Binding("O", "open_settings", "Options"),
        # View filters: base radio (a/l/f/i) + add-on toggles (g/t)
        Binding("a", "view_all", "All", show=False),
        Binding("l", "view_locked", "Locked", show=False),
        Binding("f", "view_free", "Free", show=False),
        Binding("i", "view_inflight", "In-Flight", show=False),
        Binding("y", "view_bytopic", "By-Topic", show=False),
        Binding("g", "view_git", "Git", show=False),
        Binding("t", "view_type", "Type", show=False),
    ]

    def __init__(self):
        super().__init__()
        self.current_tui_name = "board"
        self.manager = TaskManager()
        self.search_filter = ""
        self.base_filter = "all"          # "all" | "locked" | "free" | "inflight" | "bytopic"
        self.git_filter_active = False
        self.type_filter_active = False
        self._view_auto_expanded: set = set()
        self.expanded_tasks: set = set()
        self._auto_refresh_timer = None

    def check_action(self, action: str, parameters) -> bool | None:
        """Control visibility of conditional actions in the footer bar."""
        # A modal/overlay screen on top may own its own arrow-key navigation.
        # The board binds arrows with priority=True, which Textual checks before
        # the focused widget, so we selectively disable board nav while a screen
        # is pushed and let the arrow key fall through to the focused widget.
        #
        # Lateral nav (left/right) always falls through to the focused modal
        # widget — e.g. CycleField.on_key cycles its options, and Input moves
        # its text cursor. The board's column nav is board-only.
        if action in ("nav_left", "nav_right") and len(self.screen_stack) > 1:
            return False
        # Vertical nav (up/down) falls through only when the focused modal
        # widget owns row/line navigation itself — currently the shortcut
        # editor's DataTable. For every other modal (TaskDetailScreen metadata
        # fields, the task/dep/child pickers built from focusable Static items,
        # AgentCommandScreen buttons) up/down must reach action_nav_up/down,
        # which moves focus between widgets via focus_previous/next. Widget- and
        # screen-specific fall-throughs (Input, SelectionList, SelectOverlay,
        # TuiSwitcherOverlay, SectionViewerScreen) are handled by the guards
        # below.
        if action in ("nav_up", "nav_down") and len(self.screen_stack) > 1 \
                and isinstance(self.app.focused, DataTable):
            return False
        # Tab normally jumps to the board search box. While a modal is on the
        # stack that yanks focus out of the modal (e.g. the cross-repo ref
        # picker, which then only exposes its first item to the keyboard). Gate
        # it so Tab falls through to default widget focus-cycling inside the
        # modal. Escape is left App-level: action_focus_board is already
        # modal-aware and dismisses the active modal.
        if action == "focus_search" and len(self.screen_stack) > 1:
            return False
        # Let TuiSwitcherOverlay's ListView handle arrow keys natively
        if action in ("nav_up", "nav_down", "nav_left", "nav_right") and isinstance(self.screen, TuiSwitcherOverlay):
            return False
        # Let Input widgets handle arrow keys natively
        if action in ("nav_up", "nav_down", "nav_left", "nav_right") and isinstance(self.app.focused, Input):
            return False
        # Let SelectionList (used by IssueTypeFilterScreen) handle arrow keys
        if action in ("nav_up", "nav_down", "nav_left", "nav_right") and isinstance(self.app.focused, SelectionList):
            return False
        # Let Select dropdown overlay handle arrow keys natively
        if action in ("nav_up", "nav_down"):
            from textual.widgets._select import SelectOverlay
            if isinstance(self.app.focused, SelectOverlay):
                return False
        # SectionViewerScreen owns its own Tab and arrow keys (cycles minimap <-> content,
        # scrolls content, moves between minimap rows). Using type-name to avoid a circular
        # import with section_viewer.
        if type(self.screen).__name__ == "SectionViewerScreen":
            if action in ("focus_search", "nav_up", "nav_down", "nav_left", "nav_right"):
                return False
        if action == "commit_selected":
            focused = self._focused_card()
            if not focused or not self.manager.is_modified(focused.task_data):
                return None  # Hide from footer
        elif action == "commit_all":
            if not self.manager.get_modified_tasks():
                return None  # Hide from footer
        elif action == "toggle_children":
            focused = self._focused_card()
            if not focused:
                return None
            if focused.is_child:
                return True  # Always show for child cards (they have a parent)
            task_num, _ = TaskCard._parse_filename(focused.task_data.filename)
            if not self.manager.get_child_tasks_for_parent(task_num):
                return None
        elif action == "pick_task":
            focused = self._focused_card()
            if not focused:
                return None
        elif action == "brainstorm_task":
            focused = self._focused_card()
            if not focused:
                return None
        elif action == "open_cross_repo":
            focused = self._focused_card()
            if not focused or not self._gather_cross_repo_refs(focused.task_data):
                return None  # Hide unless the focused task has cross-repo refs
        elif action in ("move_task_right", "move_task_left", "move_task_up", "move_task_down",
                        "move_task_top", "move_task_bottom"):
            if self.base_filter == "inflight":
                return None
            focused = self._focused_card()
            if focused and focused.is_child:
                return None  # Hide movement actions for child cards
        elif action in ("move_col_right", "move_col_left", "toggle_column_collapsed"):
            if self.base_filter == "inflight":
                return None
        return True

    def compose(self):
        header = Header()
        header.can_focus = False
        yield header
        with Horizontal(id="filter_area"):
            with Container(id="view_col"):
                yield Static("Task filter", id="view_label")
                yield ViewSelector(
                    self.base_filter,
                    self.git_filter_active,
                    self.type_filter_active,
                    id="view_selector",
                )
                yield Static("", id="type_filter_summary", classes="type-filter-summary hidden")
            yield Input(placeholder="Search tasks... (Tab to focus, Esc to return to board)", id="search_box")
        yield HorizontalScroll(id="board_container")
        footer = Footer()
        footer.can_focus = False
        yield footer

    def on_mount(self):
        self.refresh_board(refresh_locks=True)
        self._start_auto_refresh_timer()
        self._update_subtitle()

    def _start_auto_refresh_timer(self):
        """Start or restart the auto-refresh timer based on current settings."""
        self._stop_auto_refresh_timer()
        minutes = self.manager.auto_refresh_minutes
        if minutes > 0:
            self._auto_refresh_timer = self.set_interval(
                minutes * 60, self._auto_refresh_tick, name="auto_refresh"
            )

    def _stop_auto_refresh_timer(self):
        """Stop the current auto-refresh timer if one is running."""
        if self._auto_refresh_timer is not None:
            self._auto_refresh_timer.stop()
            self._auto_refresh_timer = None

    def _auto_refresh_tick(self):
        """Called by the timer. Refresh only if no modal is active."""
        if self._modal_is_active():
            return
        if self.manager.settings.get("sync_on_refresh", False) and DATA_WORKTREE.exists():
            self._run_sync(show_notification=False)
        else:
            self.action_refresh_board()

    def _update_subtitle(self):
        """Update app subtitle to show auto-refresh status."""
        minutes = self.manager.auto_refresh_minutes
        sync = self.manager.settings.get("sync_on_refresh", False)
        if minutes > 0:
            suffix = " + sync" if sync else ""
            self.sub_title = f"Auto-refresh: {minutes}min{suffix}"
        else:
            self.sub_title = "Auto-refresh: off"

    def action_refresh_board(self):
        """Reload task files from disk and refresh the board."""
        focused = self._focused_card()
        refocus = focused.task_data.filename if focused else ""
        self.manager.load_tasks()
        if self.base_filter == "locked":
            self._auto_expand_locked()
        self.refresh_board(refocus_filename=refocus, refresh_locks=True)

    def refresh_board(self, refocus_filename: str = "", refresh_locks: bool = False):
        self.manager.refresh_git_status()
        if refresh_locks:
            self.manager.refresh_lock_map()
        self.manager.clear_gate_cache()
        # New refresh cycle: drop cached cross-repo dep statuses so cards
        # re-probe live status (cards repopulate the cache on render).
        self.manager.xdep_status_cache.clear()
        container = self.query_one("#board_container")
        container.remove_children()

        if self.base_filter == "inflight":
            grouped = {"human": [], "agent": [], "blocked": []}
            for item in self.manager.get_inflight_items():
                grouped[item.group].append(item)
            for group in ("human", "agent", "blocked"):
                container.mount(InFlightColumn(group, grouped[group], self.manager))
            self.call_after_refresh(self.apply_filter)
            if refocus_filename:
                self.call_after_refresh(self._refocus_card, refocus_filename)
            return

        if self.base_filter == "bytopic":
            all_tasks = (list(self.manager.task_datas.values())
                         + list(self.manager.child_task_datas.values()))
            for label, members in group_tasks_by_topic(all_tasks):
                container.mount(TopicColumn(label, members, self.manager))
            self.call_after_refresh(self.apply_filter)
            if refocus_filename:
                self.call_after_refresh(self._refocus_card, refocus_filename)
            return

        # 1. Unordered/Backlog Column (Dynamic)
        unordered_tasks = self.manager.get_column_tasks("unordered")
        if unordered_tasks:
            is_collapsed = self.manager.is_column_collapsed("unordered")
            container.mount(KanbanColumn(
                "unordered", "Unsorted / Inbox", "gray", self.manager,
                self.expanded_tasks, collapsed=is_collapsed,
            ))

        # 2. Configured Columns
        for col_id in self.manager.column_order:
            conf = next((c for c in self.manager.columns if c["id"] == col_id), None)
            if conf:
                is_collapsed = self.manager.is_column_collapsed(col_id)
                container.mount(KanbanColumn(
                    conf["id"], conf["title"], conf["color"], self.manager,
                    self.expanded_tasks, collapsed=is_collapsed,
                ))

        # Defer until after Textual processes pending mounts so the freshly
        # composed TaskCards are queryable; otherwise view-mode filters silently
        # no-op and every card stays visible.
        self.call_after_refresh(self.apply_filter)

        # Restore focus to the card matching refocus_filename
        if refocus_filename:
            self.call_after_refresh(self._refocus_card, refocus_filename)

    def _refocus_card(self, filename: str):
        for card in self.query(TaskCard):
            if card.task_data.filename == filename:
                card.focus()
                return

    def _recompose_column(self, col_widget: KanbanColumn):
        """Replace a column's children in-place using textual.compose.

        Keeps the KanbanColumn shell in the DOM (no layout shift) and only
        swaps its inner content (header + task cards).
        """
        col_widget.collapsed = self.manager.is_column_collapsed(col_widget.col_id)
        col_widget.remove_children()
        new_children = _compose_widgets(col_widget)
        col_widget.mount_all(new_children)

    def refresh_column(self, col_id: str, refocus_filename: str = ""):
        """Re-render a single column's contents without layout changes."""
        old_col = None
        for col in self.query(KanbanColumn):
            if col.col_id == col_id:
                old_col = col
                break

        if old_col is None:
            # Column not on screen — check if it should appear
            if col_id == "unordered" and self.manager.get_column_tasks("unordered"):
                self.refresh_board(refocus_filename=refocus_filename)
            return

        # Check if unordered column should disappear
        if col_id == "unordered" and not self.manager.get_column_tasks("unordered"):
            old_col.remove()
            if refocus_filename:
                self.call_after_refresh(self._refocus_card, refocus_filename)
            return

        self._recompose_column(old_col)

        # Defer (see refresh_board for rationale): _recompose_column remounts
        # cards, so applying the filter synchronously here would race compose.
        self.call_after_refresh(self.apply_filter)
        if refocus_filename:
            self.call_after_refresh(self._refocus_card, refocus_filename)

    def refresh_columns(self, col_ids: set, refocus_filename: str = ""):
        """Re-render multiple columns. Falls back to full refresh for structural changes."""
        # Check if unordered needs structural add/remove
        if "unordered" in col_ids:
            has_widget = any(c.col_id == "unordered" for c in self.query(KanbanColumn))
            has_tasks = bool(self.manager.get_column_tasks("unordered"))
            if has_widget != has_tasks:
                self.refresh_board(refocus_filename=refocus_filename)
                return

        for col_id in col_ids:
            for col in self.query(KanbanColumn):
                if col.col_id == col_id:
                    self._recompose_column(col)
                    break

        # Defer (see refresh_board for rationale): _recompose_column remounts
        # cards, so applying the filter synchronously here would race compose.
        self.call_after_refresh(self.apply_filter)
        if refocus_filename:
            self.call_after_refresh(self._refocus_card, refocus_filename)

    @on(Input.Changed, "#search_box")
    def on_search(self, event: Input.Changed):
        self.search_filter = event.value.lower()
        self.apply_filter()

    def apply_filter(self):
        """Apply base filter ∩ active add-ons ∩ search to all cards."""
        if self.base_filter in ("inflight", "bytopic"):
            visible = None
        elif self.base_filter == "locked":
            visible = self._locked_visible_set()
        elif self.base_filter == "free":
            visible = self._free_visible_set()
        else:  # "all"
            visible = None  # sentinel — all cards eligible

        if self.git_filter_active:
            git_set = self._git_visible_set()
            visible = git_set if visible is None else visible & git_set

        if self.type_filter_active:
            type_set = self._type_visible_set()
            visible = type_set if visible is None else visible & type_set

        for card in self.query(TaskCard):
            v = True
            if visible is not None and card.task_data.filename not in visible:
                v = False
            if v and self.search_filter:
                search_content = f"{card.task_data.filename} {card.task_data.metadata}".lower()
                if self.search_filter not in search_content:
                    v = False
            card.styles.display = "block" if v else "none"

    def _is_busy(self, filename: str, task) -> bool:
        """A task is busy when status==Implementing OR present in lock_map."""
        if task.metadata.get('status') == 'Implementing':
            return True
        task_num, _ = TaskCard._parse_filename(filename)
        return task_num.lstrip('t') in self.manager.lock_map

    def _locked_visible_set(self) -> set:
        """Tasks visible in locked view: busy tasks plus context grouping.

        A task is busy when status==Implementing OR present in lock_map.
        When a *child* is busy, also include the parent and all siblings —
        preserves the existing context-view UX (see what's in flight + its
        surrounding work). Inverse of `_free_visible_set()` at the leaf level.
        """
        visible = set()

        # Parent tasks that are themselves busy.
        for filename, task in self.manager.task_datas.items():
            if self._is_busy(filename, task):
                visible.add(filename)

        # Busy children + parent + sibling grouping.
        for filename, task in self.manager.child_task_datas.items():
            if self._is_busy(filename, task):
                visible.add(filename)
                parent_num = self.manager.get_parent_num_for_child(task)
                parent = self.manager.find_task_by_id(parent_num)
                if parent:
                    visible.add(parent.filename)
                for sib in self.manager.get_child_tasks_for_parent(parent_num):
                    visible.add(sib.filename)

        return visible

    def _free_visible_set(self) -> set:
        """Tasks visible in free view: not busy, with parent cascade.

        Children: shown when the child itself is not busy.
        Parents: shown only when the parent itself is not busy AND no child
        is busy.
        """
        visible = set()

        for filename, task in self.manager.child_task_datas.items():
            if not self._is_busy(filename, task):
                visible.add(filename)

        for filename, task in self.manager.task_datas.items():
            if self._is_busy(filename, task):
                continue
            task_num, _ = TaskCard._parse_filename(filename)
            children = self.manager.get_child_tasks_for_parent(task_num)
            if any(self._is_busy(c.filename, c) for c in children):
                continue
            visible.add(filename)

        return visible

    def _git_visible_set(self) -> set:
        """Tasks visible in git/integration view."""
        visible = set()
        for filename, task in self.manager.task_datas.items():
            if task.metadata.get('issue') or task.metadata.get('pull_request'):
                visible.add(filename)
        for filename, task in self.manager.child_task_datas.items():
            if task.metadata.get('issue') or task.metadata.get('pull_request'):
                visible.add(filename)
        return visible

    def _type_visible_set(self) -> set:
        """Tasks visible in issue-type view (matches selected types)."""
        selected = set(self.manager.settings.get("filter_issue_types", []))
        if not selected:
            return set()
        visible = set()
        for filename, task in self.manager.task_datas.items():
            if task.metadata.get('issue_type', 'feature') in selected:
                visible.add(filename)
        for filename, task in self.manager.child_task_datas.items():
            if task.metadata.get('issue_type', 'feature') in selected:
                visible.add(filename)
        return visible

    def _refresh_type_filter_summary(self):
        """Show selected types under the ViewSelector when type add-on is on."""
        try:
            summary = self.query_one("#type_filter_summary", Static)
        except Exception:
            return
        selected = self.manager.settings.get("filter_issue_types", [])
        if self.type_filter_active and selected:
            summary.update(f"types: {', '.join(sorted(selected))}")
            summary.remove_class("hidden")
        else:
            summary.update("")
            summary.add_class("hidden")

    # --- View Filters: base radio + add-on toggles ---

    def action_view_all(self):
        self._set_base_filter("all")

    def action_view_locked(self):
        self._set_base_filter("locked")

    def action_view_free(self):
        if self.base_filter == "inflight" and isinstance(self._focused_card(), InFlightTaskCard):
            self._record_focused_human_gate("fail")
            return
        self._set_base_filter("free")

    def action_view_inflight(self):
        self._set_base_filter("inflight")

    def action_view_bytopic(self):
        self._set_base_filter("bytopic")

    def action_view_git(self):
        if self.base_filter == "inflight" and isinstance(self._focused_card(), InFlightTaskCard):
            self.action_gate_resume()
            return
        self._toggle_git_filter()

    def action_view_type(self):
        self._toggle_type_filter()

    def _open_type_filter_dialog(self):
        """Open the type-picker modal. Used both when toggling type on and
        when the user wants to reconfirm/edit the type selection."""
        types = _load_task_types()
        initial = self.manager.settings.get("filter_issue_types", [])

        def on_dismiss(result):
            if result is None:
                # Cancel / Esc — keep current state & selection unchanged.
                return
            if not result:
                # Empty confirm → clear selection and disable the add-on.
                self.manager.settings["filter_issue_types"] = []
                self.manager.save_metadata()
                self.type_filter_active = False
                self._refresh_selector()
                self._refresh_type_filter_summary()
                self._update_search_placeholder()
                self.apply_filter()
                return
            self.manager.settings["filter_issue_types"] = sorted(result)
            self.manager.save_metadata()
            self.type_filter_active = True
            self._refresh_selector()
            self._refresh_type_filter_summary()
            self._update_search_placeholder()
            self.apply_filter()

        self.push_screen(IssueTypeFilterScreen(types, initial), on_dismiss)

    def _set_base_filter(self, name: str):
        """Switch the base radio (a/l/f). No-op when already active."""
        if name == self.base_filter:
            return
        old = self.base_filter
        self.base_filter = name

        # Manage auto-expansion for the locked context-view.
        if old == "locked":
            self.expanded_tasks -= self._view_auto_expanded
            self._view_auto_expanded.clear()
        if name == "locked":
            self._auto_expand_locked()

        # The inflight view reads live on-disk gate state, so entering it should
        # re-read task files + refresh the lock map (refresh_board already
        # refreshes git status and clears the gate cache). This is the same data
        # refresh as pressing 'r'. Only the transition INTO the view refreshes —
        # re-selecting it is a no-op via the early return above.
        #
        # By-topic deliberately does NOT force a disk reload: it builds from the
        # in-memory tasks like all/locked/free (anchor edits already update them
        # in-memory; 'r' / auto-refresh pick up external changes). Forcing a
        # full re-read here made entering the view noticeably slow.
        refresh_locks = False
        if name == "inflight":
            self.manager.load_tasks()
            refresh_locks = True

        self._refresh_selector()
        self._update_search_placeholder()

        # Re-render board with new expansion state, then filter.
        focused = self._focused_card()
        refocus = focused.task_data.filename if focused else ""
        self.refresh_board(refocus_filename=refocus, refresh_locks=refresh_locks)

    def _toggle_git_filter(self):
        """Flip the git add-on. No board re-render needed."""
        self.git_filter_active = not self.git_filter_active
        self._refresh_selector()
        self._update_search_placeholder()
        self.apply_filter()

    def _toggle_type_filter(self):
        """Flip the type add-on.

        Turning ON always re-opens the type-picker dialog so the user can
        reconfirm or edit the selection. Turning OFF requires no dialog.
        """
        if self.type_filter_active:
            self.type_filter_active = False
            self._refresh_selector()
            self._refresh_type_filter_summary()
            self._update_search_placeholder()
            self.apply_filter()
        else:
            self._open_type_filter_dialog()

    def _refresh_selector(self):
        """Push current filter state into the ViewSelector widget."""
        try:
            selector = self.query_one("#view_selector", ViewSelector)
        except Exception:
            return
        selector.active_base = self.base_filter
        selector.git_on = self.git_filter_active
        selector.type_on = self.type_filter_active
        selector.refresh()

    def _compute_search_placeholder(self) -> str:
        if self.base_filter == "inflight":
            base = "Search in-flight tasks"
        elif self.base_filter == "locked":
            base = "Search locked tasks"
        elif self.base_filter == "free":
            base = "Search free tasks"
        elif self.base_filter == "bytopic":
            base = "Search topics"
        else:
            base = "Search tasks..."
        addons = []
        if self.git_filter_active:
            addons.append("git")
        if self.type_filter_active:
            addons.append("type")
        if addons:
            base += " + " + " + ".join(addons)
        if self.base_filter == "all" and not addons:
            base += " (Tab to focus, Esc to return to board)"
        else:
            base += " (a/l/f/i/y to switch base)"
        return base

    def _update_search_placeholder(self):
        try:
            search_box = self.query_one("#search_box", Input)
        except Exception:
            return
        search_box.placeholder = self._compute_search_placeholder()

    def _auto_expand_locked(self):
        """Auto-expand parents that have busy (locked or Implementing) children."""
        self._view_auto_expanded.clear()
        for filename, task in self.manager.task_datas.items():
            task_num, _ = TaskCard._parse_filename(filename)
            children = self.manager.get_child_tasks_for_parent(task_num)
            has_busy = any(self._is_busy(c.filename, c) for c in children)
            if has_busy and filename not in self.expanded_tasks:
                self._view_auto_expanded.add(filename)
                self.expanded_tasks.add(filename)

    # --- Focus & Navigation ---

    def action_focus_search(self):
        """Toggle focus between search box and board."""
        search_box = self.query_one("#search_box", Input)
        if search_box.has_focus:
            self.action_focus_board()
        else:
            search_box.focus()

    def action_focus_board(self):
        """Escape: close modal if active, otherwise return to board from search."""
        if self._modal_is_active():
            if hasattr(self.screen, "handle_escape"):
                self.screen.handle_escape()
            else:
                self.screen.dismiss()
            return
        cards = list(self.query(TaskCard))
        if cards:
            cards[0].focus()
            return
        # Fall back to first collapsed column placeholder
        placeholders = list(self.query(CollapsedColumnPlaceholder))
        if placeholders:
            placeholders[0].focus()

    def _focused_card(self):
        """Return the currently focused TaskCard, or None."""
        results = self.query("TaskCard:focus")
        return results.first() if results else None

    def _get_column_cards(self, col_id: str) -> list:
        """Return TaskCard widgets belonging to a column, in DOM order."""
        return [c for c in self.query(TaskCard) if c.column_id == col_id]

    def _get_visible_col_ids(self) -> list:
        """Return ordered list of column IDs currently on the board."""
        cols = (list(self.query(KanbanColumn))
                + list(self.query(InFlightColumn))
                + list(self.query(TopicColumn)))
        return [col.col_id for col in cols]

    def _modal_is_active(self):
        return isinstance(self.screen, ModalScreen)

    def action_nav_up(self):
        if self._modal_is_active():
            self.screen.focus_previous()
            return
        focused = self._focused_card()
        if not focused:
            # If on a collapsed placeholder, up/down is a no-op
            if self._focused_collapsed_placeholder():
                return
            self.action_focus_board()
            return
        cards = self._get_column_cards(focused.column_id)
        idx = next((i for i, c in enumerate(cards) if c is focused), -1)
        if idx > 0:
            cards[idx - 1].focus()

    def action_nav_down(self):
        if self._modal_is_active():
            self.screen.focus_next()
            return
        focused = self._focused_card()
        if not focused:
            if self._focused_collapsed_placeholder():
                return
            self.action_focus_board()
            return
        cards = self._get_column_cards(focused.column_id)
        idx = next((i for i, c in enumerate(cards) if c is focused), -1)
        if idx < len(cards) - 1:
            cards[idx + 1].focus()

    def action_nav_left(self):
        if self._modal_is_active():
            focused = self.screen.focused
            # Duck-type: any widget exposing cycle_prev() qualifies.
            # The board defines its own CycleField; modal screens pushed by
            # the board (e.g. ProfileEditScreen from lib/profile_editor.py)
            # define a separate CycleField with the same API. isinstance
            # against the board-local class would miss the modal's.
            cycle_prev = getattr(focused, "cycle_prev", None)
            if callable(cycle_prev):
                cycle_prev()
            return
        self._nav_lateral(-1)

    def action_nav_right(self):
        if self._modal_is_active():
            focused = self.screen.focused
            cycle_next = getattr(focused, "cycle_next", None)
            if callable(cycle_next):
                cycle_next()
            return
        self._nav_lateral(1)

    def _get_focused_col_id(self):
        """Return the column ID of the currently focused element (card or placeholder)."""
        focused = self._focused_card()
        if focused:
            return focused.column_id
        placeholder = self._focused_collapsed_placeholder()
        if placeholder:
            return placeholder.column_id
        return None

    def _nav_lateral(self, direction: int):
        cur_col = self._get_focused_col_id()
        if not cur_col:
            self.action_focus_board()
            return
        col_ids = self._get_visible_col_ids()
        if cur_col not in col_ids:
            return
        cur_idx = col_ids.index(cur_col)
        focused = self._focused_card()
        # Find the next column with focusable content
        new_idx = cur_idx + direction
        while 0 <= new_idx < len(col_ids):
            target_col_id = col_ids[new_idx]
            # Check for collapsed column placeholder
            placeholders = [p for p in self.query(CollapsedColumnPlaceholder)
                           if p.column_id == target_col_id]
            if placeholders:
                placeholders[0].focus()
                return
            target_cards = self._get_column_cards(target_col_id)
            if target_cards:
                # Try to land on the same vertical position
                old_cards = self._get_column_cards(cur_col)
                old_pos = next((i for i, c in enumerate(old_cards) if c is focused), 0) if focused else 0
                target_pos = min(old_pos, len(target_cards) - 1)
                target_cards[target_pos].focus()
                return
            new_idx += direction

    # --- Actions ---

    def action_view_details(self):
        focused = self._focused_card()
        if focused:
            def check_edit(result):
                if result == "edit":
                    self.run_editor(focused.task_data.filepath)
                elif result == "edit_plan":
                    plan_path = self._resolve_plan_path_for(focused.task_data)
                    if plan_path:
                        self.run_editor(plan_path)
                elif result == "pick":
                    task_num, _ = TaskCard._parse_filename(focused.task_data.filename)
                    if task_num:
                        full_cmd = self._resolve_pick_command(task_num)
                        if full_cmd:
                            num = task_num.lstrip("t")
                            prompt_str = f"/aitask-pick {num}"
                            agent_string = resolve_agent_string(Path("."), "pick")
                            screen = AgentCommandScreen(
                                f"Pick Task t{num}", full_cmd, prompt_str,
                                default_window_name=f"agent-pick-{num}",
                                project_root=Path("."),
                                operation="pick",
                                operation_args=[num],
                                default_agent_string=agent_string,
                                skill_name="pick",
                                default_profile=self._resolve_pick_profile(),
                            )
                            def on_pick_result(pick_result):
                                if pick_result == "run":
                                    self.run_aitask_pick(focused.task_data.filename)
                                elif isinstance(pick_result, TmuxLaunchConfig):
                                    _, err = launch_in_tmux(screen.full_command, pick_result)
                                    if err:
                                        self.notify(err, severity="error")
                                    elif pick_result.new_window:
                                        maybe_spawn_minimonitor(pick_result.session, pick_result.window)
                                self.refresh_board(refocus_filename=focused.task_data.filename)
                            self.push_screen(screen, on_pick_result)
                            return
                    self.run_aitask_pick(focused.task_data.filename)
                elif result == "brainstorm":
                    task_num, _ = TaskCard._parse_filename(focused.task_data.filename)
                    if task_num:
                        num = task_num.lstrip("t")
                        self._launch_brainstorm(num, focused.task_data.filename)
                        return
                elif result == "rename":
                    def on_rename_result(rename_result):
                        if rename_result and rename_result[0] == "rename":
                            new_name = rename_result[1]
                            self._rename_task(focused.task_data, new_name)
                    self.push_screen(
                        RenameTaskScreen(focused.task_data.filename), on_rename_result)
                    return
                elif result == "delete_archive":
                    task_num, _ = TaskCard._parse_filename(focused.task_data.filename)
                    is_child = focused.task_data.filepath.parent.name.startswith("t")
                    _, paths = self._collect_delete_files(focused.task_data)
                    dep_warnings, related = self._check_task_dependencies(focused.task_data, is_child)
                    fate = self._build_fate_buckets(focused.task_data)
                    cascade_children = fate["cascade_children"]
                    captured_task = focused.task_data

                    def on_action_chosen(action):
                        if action == "delete":
                            self._execute_delete(task_num, paths, captured_task)
                        elif action == "archive":
                            self._execute_archive(task_num, captured_task,
                                                  cascade_children=cascade_children)
                        else:
                            self.apply_filter()
                            self.call_after_refresh(self._refocus_card, captured_task.filename)

                    self.push_screen(
                        DeleteArchiveConfirmScreen(
                            focused.task_data.filename,
                            delete_files=fate["delete_files"],
                            archive_kept=fate["archive_kept"],
                            archive_deleted=fate["archive_deleted"],
                            dep_warnings=dep_warnings,
                            related_tasks=related,
                            is_child=is_child,
                            blocking_files=fate["blocking_files"],
                            blocked_reason=fate["blocked_reason"],
                        ),
                        on_action_chosen,
                    )
                    return
                # Granular refresh: reload single task + refresh affected column(s)
                needs_locks = result in ("locked", "unlocked")
                filename = focused.task_data.filename
                old_col = focused.column_id
                self.manager.reload_task(filename)
                self.manager.refresh_git_status()
                if needs_locks:
                    self.manager.refresh_lock_map()
                task = self.manager.task_datas.get(filename) or self.manager.child_task_datas.get(filename)
                new_col = task.board_col if task else old_col
                if new_col != old_col:
                    self.refresh_columns({old_col, new_col}, refocus_filename=filename)
                else:
                    self.refresh_column(old_col, refocus_filename=filename)

            self.push_screen(TaskDetailScreen(focused.task_data, self.manager), check_edit)

    def _gather_cross_repo_refs(self, task):
        """Collect ordered, de-duplicated (repo, id) cross-repo references for
        a task: its xdeps/xdeprepo frontmatter (canonical) plus any
        ``<repo>#<id>`` notation found in the task body."""
        refs = []
        seen = set()
        meta = task.metadata
        xdeprepo = meta.get('xdeprepo')
        xdeps = meta.get('xdeps', []) or []
        if xdeprepo and xdeps:
            for xd in xdeps:
                key = (xdeprepo, str(xd).lstrip('t'))
                if key not in seen:
                    seen.add(key)
                    refs.append(key)
        for repo, task_id in parse_cross_repo_notation(task.content or ""):
            key = (repo, task_id)
            if key not in seen:
                seen.add(key)
                refs.append(key)
        return refs

    def _open_cross_repo_task(self, repo, task_id):
        """Resolve a cross-repo reference read-only and show it in a popup."""
        title, content, is_error = _resolve_cross_repo_task(repo, task_id)
        self.push_screen(CrossRepoTaskScreen(title, content, is_error))

    def action_open_cross_repo(self):
        """Open a cross-repo reference from the focused task (read-only).

        Gathers references from the task's xdeps frontmatter and body
        notation. Opens directly when there is exactly one; otherwise shows
        a picker. Never acquires a lock on the cross-repo task.
        """
        if self._modal_is_active():
            return
        focused = self._focused_card()
        if not focused:
            return
        refs = self._gather_cross_repo_refs(focused.task_data)
        if not refs:
            self.notify("No cross-repo references in this task.",
                        severity="information")
            return
        if len(refs) == 1:
            repo, task_id = refs[0]
            self._open_cross_repo_task(repo, task_id)
        else:
            self.push_screen(CrossRepoRefPickerScreen(refs))

    def action_pick_task(self):
        """Open pick command dialog for the focused task."""
        if self._modal_is_active():
            return
        focused = self._focused_card()
        if not focused:
            return
        task_num, _ = TaskCard._parse_filename(focused.task_data.filename)
        if not task_num:
            return
        num = task_num.lstrip("t")
        if self._focus_existing_agent_window(num):
            self.refresh_board(refocus_filename=focused.task_data.filename)
            return
        full_cmd = self._resolve_pick_command(task_num)
        if full_cmd:
            prompt_str = f"/aitask-pick {num}"
            agent_string = resolve_agent_string(Path("."), "pick")
            screen = AgentCommandScreen(
                f"Pick Task t{num}", full_cmd, prompt_str,
                default_window_name=f"agent-pick-{num}",
                project_root=Path("."),
                operation="pick",
                operation_args=[num],
                default_agent_string=agent_string,
                skill_name="pick",
                default_profile=self._resolve_pick_profile(),
            )
            def on_pick_result(pick_result):
                if pick_result == "run":
                    self.run_aitask_pick(focused.task_data.filename)
                elif isinstance(pick_result, TmuxLaunchConfig):
                    _, err = launch_in_tmux(screen.full_command, pick_result)
                    if err:
                        self.notify(err, severity="error")
                    elif pick_result.new_window:
                        maybe_spawn_minimonitor(pick_result.session, pick_result.window)
                self.refresh_board(refocus_filename=focused.task_data.filename)
            self.push_screen(screen, on_pick_result)
        else:
            self.run_aitask_pick(focused.task_data.filename)

    def _launch_brainstorm(self, num: str, filename: str):
        """Launch brainstorm, switching to existing tmux window if found."""
        window_name = f"brainstorm-{num}"
        session = (
            _current_tmux_session()
            or load_tmux_defaults(Path.cwd())["default_session"]
        )
        existing = find_window_by_name(window_name, session)
        if existing:
            sess, idx = existing
            subprocess.Popen(
                ["tmux", "select-window", "-t", tmux_window_target(sess, idx)],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
            self.notify(f"Switched to existing brainstorm for t{num}")
            self.refresh_board(refocus_filename=filename)
            return
        full_cmd = f"./{BRAINSTORM_TUI_SCRIPT} {num}"
        prompt_str = f"ait brainstorm {num}"
        screen = AgentCommandScreen(
            f"Brainstorm Task t{num}", full_cmd, prompt_str,
            default_window_name=window_name,
        )
        def on_brainstorm_result(brainstorm_result):
            if brainstorm_result == "run":
                self._run_brainstorm_in_terminal(num, filename)
            elif isinstance(brainstorm_result, TmuxLaunchConfig):
                _, err = launch_in_tmux(screen.full_command, brainstorm_result)
                if err:
                    self.notify(err, severity="error")
            self.refresh_board(refocus_filename=filename)
        self.push_screen(screen, on_brainstorm_result)

    def action_brainstorm_task(self):
        """Open brainstorm command dialog for the focused task."""
        if self._modal_is_active():
            return
        focused = self._focused_card()
        if not focused:
            return
        task_num, _ = TaskCard._parse_filename(focused.task_data.filename)
        if not task_num:
            return
        num = task_num.lstrip("t")
        if num in self.manager.lock_map:
            self.notify("Task is locked — brainstorm disabled", severity="warning")
            return
        self._launch_brainstorm(num, focused.task_data.filename)

    @work(exclusive=True)
    async def run_editor(self, filepath):
        """Suspend app and run system editor."""
        editor = os.environ.get("EDITOR", "nano")
        if sys.platform == "win32":
            editor = os.environ.get("EDITOR", "notepad")

        filename = Path(filepath).name
        with self.suspend():
            subprocess.call([editor, str(filepath)])

        self.manager.load_tasks()
        self.refresh_board(refocus_filename=filename)

    def action_sync_remote(self):
        """Manually trigger a sync with remote."""
        if self._modal_is_active():
            return
        if self.base_filter == "inflight" and isinstance(self._focused_card(), InFlightTaskCard):
            self._record_focused_human_gate("pass")
            return
        self.push_screen(LoadingOverlay("Syncing with remote..."))
        self._run_sync(show_notification=True, show_overlay=True)

    @work(exclusive=True, thread=True)
    def _run_sync(self, show_notification: bool = True, show_overlay: bool = False):
        """Run ait sync --batch in background and handle the result."""
        result = run_sync_batch()

        if show_overlay:
            self.app.call_from_thread(self.pop_screen)

        status = result.status

        if status == STATUS_CONFLICT:
            self.app.call_from_thread(self._show_conflict_dialog, result.conflicted_files)
            return
        if status == STATUS_TIMEOUT:
            if show_notification:
                self.app.call_from_thread(self.notify, "Sync timed out", severity="warning")
            return
        if status == STATUS_NOT_FOUND:
            self.app.call_from_thread(self.notify, "Sync script not found", severity="error")
            return

        if status == STATUS_NO_NETWORK:
            if show_notification:
                self.app.call_from_thread(self.notify, "Sync: No network", severity="warning")
        elif status == STATUS_NO_REMOTE:
            if show_notification:
                self.app.call_from_thread(self.notify, "Sync: No remote configured", severity="warning")
        elif status == STATUS_NOTHING:
            if show_notification:
                self.app.call_from_thread(self.notify, "Already up to date", severity="information")
        elif status == STATUS_AUTOMERGED:
            if show_notification:
                self.app.call_from_thread(self.notify, "Sync: Auto-merged conflicts", severity="information")
        elif status in (STATUS_PUSHED, STATUS_PULLED, STATUS_SYNCED):
            if show_notification:
                self.app.call_from_thread(self.notify, f"Sync: {status.capitalize()}", severity="information")
        elif status == STATUS_ERROR:
            self.app.call_from_thread(self.notify, f"Sync error: {result.error_message}", severity="error")

        self.app.call_from_thread(self.manager.load_tasks)
        self.app.call_from_thread(self.refresh_board, refresh_locks=True)

    def _show_conflict_dialog(self, files: list[str]):
        """Show the conflict resolution dialog (must be called on main thread)."""
        def on_result(resolve):
            if resolve:
                self._run_interactive_sync_shared()
            else:
                self.manager.load_tasks()
                self.refresh_board()
        self.push_screen(SyncConflictScreen(files), on_result)

    @work(exclusive=True)
    async def _run_interactive_sync_shared(self):
        """Run shared interactive sync helper, then refresh board state."""
        def reload():
            self.manager.load_tasks()
            self.refresh_board(refresh_locks=True)
        run_interactive_sync(self.app, on_done=reload)

    def _resolve_pick_command(self, task_num: str):
        """Resolve the full pick command via --dry-run, return command string or None."""
        num = task_num.lstrip("t")
        return resolve_dry_run_command(Path("."), "pick", num)

    def _resolve_pick_profile(self) -> str:
        """Resolve the active profile name for the pick skill."""
        return resolve_skill_profile("pick")

    def _resolve_resume_command(self, task_num: str):
        """Resolve the full resume command via --dry-run, return command string or None."""
        num = task_num.lstrip("t")
        return resolve_dry_run_command(Path("."), "resume", num)

    def _resolve_resume_profile(self) -> str:
        """Resolve the active profile name for the resume skill."""
        return resolve_skill_profile("resume")

    def _focus_existing_agent_window(self, num: str) -> bool:
        session = (
            _current_tmux_session()
            or load_tmux_defaults(Path.cwd())["default_session"]
        )
        for window_name in (f"agent-pick-{num}", f"agent-resume-{num}"):
            existing = find_window_by_name(window_name, session)
            if existing:
                sess, idx = existing
                subprocess.Popen(
                    ["tmux", "select-window", "-t", tmux_window_target(sess, idx)],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                )
                self.notify(f"Switched to existing agent window for t{num}")
                return True
        return False

    def action_gate_resume(self):
        """Open resume command dialog for the focused In-Flight task."""
        if self._modal_is_active():
            return
        focused = self._focused_card()
        if not isinstance(focused, InFlightTaskCard):
            return
        task_num, _ = TaskCard._parse_filename(focused.task_data.filename)
        if not task_num:
            return
        num = task_num.lstrip("t")
        if self._focus_existing_agent_window(num):
            self.refresh_board(refocus_filename=focused.task_data.filename)
            return
        full_cmd = self._resolve_resume_command(task_num)
        if full_cmd:
            prompt_str = f"/aitask-resume {num}"
            agent_string = resolve_agent_string(Path("."), "resume")
            screen = AgentCommandScreen(
                f"Resume Task t{num}", full_cmd, prompt_str,
                default_window_name=f"agent-resume-{num}",
                project_root=Path("."),
                operation="resume",
                operation_args=[num],
                default_agent_string=agent_string,
                skill_name="resume",
                default_profile=self._resolve_resume_profile(),
            )
            def on_resume_result(resume_result):
                if resume_result == "run":
                    self.run_codeagent_operation("resume", focused.task_data.filename)
                elif isinstance(resume_result, TmuxLaunchConfig):
                    _, err = launch_in_tmux(screen.full_command, resume_result)
                    if err:
                        self.notify(err, severity="error")
                    elif resume_result.new_window:
                        maybe_spawn_minimonitor(resume_result.session, resume_result.window)
                self.refresh_board(refocus_filename=focused.task_data.filename)
            self.push_screen(screen, on_resume_result)
        else:
            self.run_codeagent_operation("resume", focused.task_data.filename)

    def _record_focused_human_gate(self, status: str):
        focused = self._focused_card()
        if not isinstance(focused, InFlightTaskCard):
            return
        gates = focused.item.human_gates
        if not gates:
            self.notify("No pending human gate for this task.", severity="warning")
            return
        if len(gates) == 1:
            self._append_human_gate(focused, gates[0], status)
            return

        action_label = "sign off" if status == "pass" else "fail"
        def on_gate(gate):
            if gate:
                self._append_human_gate(focused, gate, status)
        self.push_screen(GateChoiceScreen(focused.item.task_id, gates, action_label), on_gate)

    def _append_human_gate(self, focused: InFlightTaskCard, gate: str, status: str):
        task_id = focused.item.task_id.lstrip("t")
        try:
            result = subprocess.run(
                [
                    "./.aitask-scripts/aitask_gate.sh",
                    "append",
                    task_id,
                    gate,
                    status,
                    "type=human",
                ],
                capture_output=True,
                text=True,
                timeout=15,
            )
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as exc:
            self.notify(f"Gate update failed: {exc}", severity="error")
            return
        if result.returncode != 0:
            msg = result.stderr.strip() or result.stdout.strip() or "unknown error"
            self.notify(f"Gate update failed: {msg}", severity="error")
            return
        self.notify(f"Recorded {status} for {gate} on {focused.item.task_id}")
        self.manager.reload_task(focused.task_data.filename)
        self.refresh_board(refocus_filename=focused.task_data.filename)

    @work(exclusive=True)
    async def run_aitask_pick(self, filename):
        """Launch code agent with /aitask-pick for the task."""
        task_num, _ = TaskCard._parse_filename(filename)
        if not task_num:
            return
        num = task_num.lstrip("t")
        wrapper = str(CODEAGENT_SCRIPT)
        terminal = find_terminal()
        if terminal:
            spawn_in_terminal(terminal, [wrapper, "invoke", "pick", num])
        else:
            with self.suspend():
                ret = subprocess.call([wrapper, "invoke", "pick", num])
            if ret != 0:
                self.notify("Code agent invocation failed — check model configuration", severity="error")
            self.manager.load_tasks()
            self.refresh_board(refocus_filename=filename)

    @work(exclusive=True)
    async def run_codeagent_operation(self, operation: str, filename: str):
        """Launch code agent operation for a task in a terminal or suspended app."""
        task_num, _ = TaskCard._parse_filename(filename)
        if not task_num:
            return
        num = task_num.lstrip("t")
        wrapper = str(CODEAGENT_SCRIPT)
        terminal = find_terminal()
        if terminal:
            spawn_in_terminal(terminal, [wrapper, "invoke", operation, num])
        else:
            with self.suspend():
                ret = subprocess.call([wrapper, "invoke", operation, num])
            if ret != 0:
                self.notify("Code agent invocation failed — check model configuration", severity="error")
            self.manager.load_tasks()
            self.refresh_board(refocus_filename=filename)

    def action_create_task(self):
        """Open create task dialog with terminal/tmux options."""
        if self._modal_is_active():
            return
        full_cmd = f"./{CREATE_SCRIPT}"
        prompt_str = "ait create"
        screen = AgentCommandScreen(
            "Create Task", full_cmd, prompt_str,
            default_window_name="create-task",
        )
        def on_create_result(create_result):
            if create_result == "run":
                self._run_create_in_terminal()
            elif isinstance(create_result, TmuxLaunchConfig):
                _, err = launch_in_tmux(screen.full_command, create_result)
                if err:
                    self.notify(err, severity="error")
                elif create_result.new_window:
                    maybe_spawn_minimonitor(create_result.session, create_result.window)
                else:
                    win_name = _lookup_window_name(create_result.session, create_result.window)
                    if win_name:
                        maybe_spawn_minimonitor(
                            create_result.session, win_name,
                            window_index=create_result.window,
                        )
            self.manager.load_tasks()
            self.refresh_board()
        self.push_screen(screen, on_create_result)

    @work(exclusive=True)
    async def _run_create_in_terminal(self):
        """Launch aitask_create.sh in a terminal or via suspend."""
        terminal = find_terminal()
        if terminal:
            spawn_in_terminal(terminal, [str(CREATE_SCRIPT)])
        else:
            with self.suspend():
                subprocess.call([str(CREATE_SCRIPT)])
            self.manager.load_tasks()
            self.refresh_board()

    @work(exclusive=True)
    async def _run_brainstorm_in_terminal(self, task_num: str, filename: str):
        """Launch brainstorm TUI in a terminal or via suspend."""
        terminal = find_terminal()
        brainstorm_cmd = str(BRAINSTORM_TUI_SCRIPT)
        if terminal:
            spawn_in_terminal(terminal, [brainstorm_cmd, task_num])
        else:
            with self.suspend():
                subprocess.call([brainstorm_cmd, task_num])
            self.manager.load_tasks()
            self.refresh_board(refocus_filename=filename)

    # --- Expand/Collapse Children ---

    def _toggle_expand(self):
        """Toggle showing child tasks under the focused parent task."""
        focused = self._focused_card()
        if not focused:
            return
        if focused.is_child:
            # Child card: find parent and toggle parent's expansion
            parent_num = self.manager.get_parent_num_for_child(focused.task_data)
            parent_task = self.manager.find_task_by_id(parent_num)
            if not parent_task:
                return
            fn = parent_task.filename
        else:
            # Parent card: toggle own expansion
            task_num, _ = TaskCard._parse_filename(focused.task_data.filename)
            children = self.manager.get_child_tasks_for_parent(task_num)
            if not children:
                return
            fn = focused.task_data.filename
        if fn in self.expanded_tasks:
            self.expanded_tasks.discard(fn)
        else:
            self.expanded_tasks.add(fn)
        col_id = focused.column_id
        self.refresh_column(col_id, refocus_filename=fn)

    def action_toggle_children(self):
        self._toggle_expand()

    # --- Task Movement ---

    def action_move_task_right(self):
        self._move_task_lateral(1)

    def action_move_task_left(self):
        self._move_task_lateral(-1)

    def _move_task_lateral(self, direction):
        focused = self._focused_card()
        if not focused: return
        if focused.is_child: return

        filename = focused.task_data.filename
        current_col_id = focused.task_data.board_col
        # Build list of active columns including 'unordered'
        cols = ["unordered"] if self.manager.get_column_tasks("unordered") else []
        cols.extend(self.manager.column_order)

        if current_col_id not in cols: return

        idx = cols.index(current_col_id)
        # Skip over collapsed columns
        new_idx = idx + direction
        while 0 <= new_idx < len(cols):
            if not self.manager.is_column_collapsed(cols[new_idx]):
                break
            new_idx += direction
        else:
            return

        if 0 <= new_idx < len(cols):
            new_col = cols[new_idx]
            self.manager.move_task_col(filename, new_col)
            self.manager.normalize_indices(current_col_id)
            self.manager.normalize_indices(new_col)
            self.manager.refresh_git_status()
            self.refresh_columns({current_col_id, new_col}, refocus_filename=filename)

    def action_move_task_up(self):
        self._move_task_vertical(-1)

    def action_move_task_down(self):
        self._move_task_vertical(1)

    def _swap_adjacent_cards(self, col_widget, card_above, card_below):
        """Swap two adjacent TaskCard blocks in the DOM without rebuilding.

        A 'block' is a TaskCard followed by zero or more child-wrapper
        Horizontal widgets (present when a parent task is expanded).
        """
        children = list(col_widget.children)

        def _block(card):
            idx = children.index(card)
            block = [card]
            for i in range(idx + 1, len(children)):
                w = children[i]
                if isinstance(w, Horizontal) and w.has_class("child-wrapper"):
                    block.append(w)
                else:
                    break
            return block

        below_block = _block(card_below)
        anchor = card_above
        for widget in below_block:
            col_widget.move_child(widget, before=anchor)

        self.apply_filter()

    def _move_task_vertical(self, direction):
        focused = self._focused_card()
        if focused and focused.is_child: return
        if not focused: return

        filename = focused.task_data.filename
        col_id = focused.task_data.board_col
        tasks = self.manager.get_column_tasks(col_id)

        try:
            current_idx = next(i for i, t in enumerate(tasks) if t.filename == filename)
        except StopIteration:
            return

        swap_idx = current_idx + direction
        if 0 <= swap_idx < len(tasks):
            target_task = tasks[swap_idx]
            self.manager.swap_tasks(filename, target_task.filename)
            self.manager.normalize_indices(col_id)
            self.manager.refresh_git_status()

            # DOM swap: reorder widgets in-place instead of rebuilding column
            col_widget = None
            for col in self.query(KanbanColumn):
                if col.col_id == col_id:
                    col_widget = col
                    break

            target_card = None
            if col_widget is not None:
                for card in col_widget.query(TaskCard):
                    if not card.is_child and card.task_data.filename == target_task.filename:
                        target_card = card
                        break

            if col_widget is not None and target_card is not None:
                if direction == -1:  # moving up: focused was below, target above
                    self._swap_adjacent_cards(col_widget, target_card, focused)
                else:  # moving down: focused was above, target below
                    self._swap_adjacent_cards(col_widget, focused, target_card)
                self.call_after_refresh(self._refocus_card, filename)
            else:
                self.refresh_column(col_id, refocus_filename=filename)

    def action_move_task_top(self):
        self._move_task_to_extreme(-1)

    def action_move_task_bottom(self):
        self._move_task_to_extreme(1)

    def _move_task_to_extreme(self, direction):
        """Move focused task to top (direction=-1) or bottom (direction=1) of its column."""
        focused = self._focused_card()
        if not focused or focused.is_child:
            return
        filename = focused.task_data.filename
        col_id = focused.task_data.board_col
        tasks = self.manager.get_column_tasks(col_id)
        if len(tasks) <= 1:
            return
        try:
            current_idx = next(i for i, t in enumerate(tasks) if t.filename == filename)
        except StopIteration:
            return
        if direction == -1 and current_idx == 0:
            return
        if direction == 1 and current_idx == len(tasks) - 1:
            return
        if direction == -1:
            focused.task_data.board_idx = tasks[0].board_idx - 10
        else:
            focused.task_data.board_idx = tasks[-1].board_idx + 10
        focused.task_data.reload_and_save_board_fields()
        self.manager.normalize_indices(col_id)
        self.manager.refresh_git_status()
        self.refresh_column(col_id, refocus_filename=filename)

    # --- Column Reordering ---

    def action_move_col_right(self):
        self._shift_column(1)
        
    def action_move_col_left(self):
        self._shift_column(-1)

    def _shift_column(self, direction):
        focused = self._focused_card()
        if not focused: return

        filename = focused.task_data.filename
        col_id = focused.task_data.board_col
        if col_id == "unordered": return

        order = self.manager.column_order
        if col_id not in order: return

        idx = order.index(col_id)
        new_idx = idx + direction

        if 0 <= new_idx < len(order):
            order[idx], order[new_idx] = order[new_idx], order[idx]
            self.manager.save_metadata()
            self.refresh_board(refocus_filename=filename)

    # --- Column Customization ---

    def _handle_column_edit_result(self, result):
        """Callback for ColumnEditScreen dismiss."""
        if not result:
            return
        action = result[0]
        if action == "add":
            _, col_id, title, color = result
            self.manager.add_column(col_id, title, color)
            self.notify(f"Added column: {title}", severity="information")
        elif action == "edit":
            _, col_id, title, color = result
            self.manager.update_column(col_id, col_id, title, color)
            self.notify(f"Updated column: {title}", severity="information")
        self.refresh_board()

    def action_add_column(self):
        """Open the Add Column dialog."""
        self.push_screen(
            ColumnEditScreen(self.manager, mode="add"),
            self._handle_column_edit_result,
        )

    def action_edit_column(self):
        """Open column picker, then edit dialog."""
        def on_col_selected(col_id):
            if col_id:
                self.push_screen(
                    ColumnEditScreen(self.manager, col_id=col_id, mode="edit"),
                    self._handle_column_edit_result,
                )
        self.push_screen(ColumnSelectScreen(self.manager, "Edit"), on_col_selected)

    def action_delete_column(self):
        """Open column picker, then confirm deletion."""
        def on_col_selected(col_id):
            if not col_id:
                return
            col_conf = self.manager.get_column_conf(col_id)
            task_count = len(self.manager.get_column_tasks(col_id))
            def on_confirmed(confirmed):
                if confirmed:
                    self.manager.delete_column(col_id)
                    self.notify(f"Deleted column: {col_conf['title']}", severity="information")
                    self.refresh_board()
            self.push_screen(
                DeleteColumnConfirmScreen(col_conf, task_count),
                on_confirmed,
            )
        self.push_screen(ColumnSelectScreen(self.manager, "Delete"), on_col_selected)

    def open_column_edit(self, col_id: str):
        """Open the edit dialog for a specific column (called from header click)."""
        self.push_screen(
            ColumnEditScreen(self.manager, col_id=col_id, mode="edit"),
            self._handle_column_edit_result,
        )

    # --- Column Collapse/Expand ---

    def toggle_column_collapse(self, col_id: str):
        """Toggle collapse/expand state for a column."""
        is_now_collapsed = not self.manager.is_column_collapsed(col_id)
        self.manager.toggle_column_collapsed(col_id)
        focused = self._focused_card()
        refocus = ""
        if focused and focused.column_id == col_id and is_now_collapsed:
            # Card is in the column being collapsed — no refocus target
            pass
        elif focused:
            refocus = focused.task_data.filename
        self.refresh_board(refocus_filename=refocus)

    def _focused_collapsed_placeholder(self):
        """Return the focused CollapsedColumnPlaceholder, or None."""
        results = self.query("CollapsedColumnPlaceholder:focus")
        return results.first() if results else None

    def action_toggle_column_collapsed(self):
        """Toggle collapse for the column of the currently focused task (Shift+X)."""
        if self._modal_is_active():
            return
        focused = self._focused_card()
        if focused:
            self.toggle_column_collapse(focused.column_id)
            return
        # Check if a collapsed column placeholder is focused
        placeholder = self._focused_collapsed_placeholder()
        if placeholder:
            self.toggle_column_collapse(placeholder.column_id)
            return
        self.notify("No task selected", severity="warning")

    def action_collapse_column(self):
        """Open column picker to collapse a column (command palette)."""
        if self._modal_is_active():
            return
        expanded_cols = [c for c in self.manager.columns
                         if not self.manager.is_column_collapsed(c["id"])]
        # Include unordered if it has tasks and is not collapsed
        unordered_tasks = self.manager.get_column_tasks("unordered")
        if unordered_tasks and not self.manager.is_column_collapsed("unordered"):
            expanded_cols.insert(0, {"id": "unordered", "title": "Unsorted / Inbox", "color": "gray"})
        if not expanded_cols:
            self.notify("No columns to collapse", severity="warning")
            return

        def on_col_selected(col_id):
            if col_id:
                self.toggle_column_collapse(col_id)
                conf = self.manager.get_column_conf(col_id)
                title = conf["title"] if conf else col_id
                self.notify(f"Collapsed: {title}", severity="information")

        self.push_screen(
            ColumnSelectScreen(self.manager, "Collapse", columns=expanded_cols),
            on_col_selected,
        )

    def action_expand_column(self):
        """Open column picker to expand a collapsed column (command palette)."""
        if self._modal_is_active():
            return
        collapsed_cols = [c for c in self.manager.columns
                          if self.manager.is_column_collapsed(c["id"])]
        # Include unordered if collapsed
        if self.manager.is_column_collapsed("unordered"):
            collapsed_cols.insert(0, {"id": "unordered", "title": "Unsorted / Inbox", "color": "gray"})
        if not collapsed_cols:
            self.notify("No columns to expand", severity="warning")
            return

        def on_col_selected(col_id):
            if col_id:
                self.toggle_column_collapse(col_id)
                conf = self.manager.get_column_conf(col_id)
                title = conf["title"] if conf else col_id
                self.notify(f"Expanded: {title}", severity="information")

        self.push_screen(
            ColumnSelectScreen(self.manager, "Expand", columns=collapsed_cols),
            on_col_selected,
        )

    # --- Settings ---

    def action_open_settings(self):
        """Open the settings dialog."""
        if self._modal_is_active():
            return
        self.push_screen(
            SettingsScreen(self.manager),
            self._handle_settings_result,
        )

    def _handle_settings_result(self, result):
        """Callback for SettingsScreen dismiss."""
        if result is None:
            return
        self.manager.settings.update(result)
        self.manager.save_metadata()
        self._start_auto_refresh_timer()
        self._update_subtitle()
        minutes = result["auto_refresh_minutes"]
        if minutes > 0:
            self.notify(f"Auto-refresh: {minutes}min", severity="information")
        else:
            self.notify("Auto-refresh: disabled", severity="information")

    # --- Git Commit ---

    def action_commit_selected(self):
        """Commit the currently selected task if it has git modifications."""
        if self._modal_is_active():
            return
        focused = self._focused_card()
        if not focused:
            self.notify("No task selected", severity="warning")
            return
        if not self.manager.is_modified(focused.task_data):
            self.notify("Selected task has no modifications", severity="warning")
            return

        def handle_commit_result(result):
            if result and result[0] == "commit":
                self._git_commit_tasks([focused.task_data], result[1])

        self.push_screen(
            CommitMessageScreen([focused.task_data], self.manager),
            handle_commit_result
        )

    def action_commit_all(self):
        """Commit all tasks with git modifications."""
        if self._modal_is_active():
            return
        modified_tasks = self.manager.get_modified_tasks()
        if not modified_tasks:
            self.notify("No modified tasks to commit", severity="warning")
            return

        def handle_commit_result(result):
            if result and result[0] == "commit":
                self._git_commit_tasks(modified_tasks, result[1])

        self.push_screen(
            CommitMessageScreen(modified_tasks, self.manager),
            handle_commit_result
        )

    def _resolve_plan_path_for(self, task: Task):
        """Resolve the plan file path for a given task."""
        is_child = task.filepath.parent.name.startswith("t")
        if is_child:
            parent_num = self.manager.get_parent_num_for_child(task)
            plan_name = "p" + task.filename[1:]
            plan_path = Path("aiplans") / parent_num.replace("t", "p", 1) / plan_name
        else:
            plan_name = "p" + task.filename[1:]
            plan_path = Path("aiplans") / plan_name
        return plan_path if plan_path.exists() else None

    def _categorize_pending_children(self, parent_num: str) -> dict:
        """Bucket a parent's pending children by status.

        Returns a dict with keys:
          - "disposable":      Ready / Postponed / Editing (safe to cascade-delete)
          - "blocking":        Implementing (cascade refused)
          - "unarchived_done": Done but not yet archived (cascade refused)
        """
        buckets = {"disposable": [], "blocking": [], "unarchived_done": []}
        for child in self.manager.get_child_tasks_for_parent(parent_num):
            status = child.metadata.get("status", "Ready")
            if status in ("Ready", "Postponed", "Editing"):
                buckets["disposable"].append(child)
            elif status == "Implementing":
                buckets["blocking"].append(child)
            elif status == "Done":
                buckets["unarchived_done"].append(child)
            else:
                buckets["blocking"].append(child)
        return buckets

    def _build_fate_buckets(self, task: Task):
        """Build (delete_files, archive_kept, archive_deleted, blocking_files) for
        a task as labelled (path, annotation) tuples. Used by DeleteArchiveConfirmScreen
        and by the cascade execution path so they share one source of truth.

        Returns a dict with:
          - delete_files:   files removed when user clicks Delete
          - archive_kept:   files moved to archived/ when user clicks Archive
          - archive_deleted: files removed when user clicks Archive (cascade)
          - blocking_files: blocking children that prevent archive
          - cascade_children: list[Task] of disposable children for the cascade executor
          - blocked_reason: str | None — reason archive is blocked, or None
        """
        task_num, _ = TaskCard._parse_filename(task.filename)
        is_child = task.filepath.parent.name.startswith("t")
        status = task.metadata.get("status", "Ready")

        delete_files = []
        archive_kept = []
        archive_deleted = []
        blocking_files = []
        cascade_children = []
        blocked_reason = None

        if is_child:
            # Self
            self_annot = f"child — {status}"
            delete_files.append((str(task.filepath), self_annot))
            archive_kept.append((str(task.filepath), self_annot))
            plan_path = self._resolve_plan_path_for(task)
            if plan_path:
                delete_files.append((str(plan_path), ""))
                archive_kept.append((str(plan_path), ""))
        else:
            # Parent self
            self_annot = f"parent — {status}"
            delete_files.append((str(task.filepath), self_annot))
            archive_kept.append((str(task.filepath), self_annot))
            parent_plan = self._resolve_plan_path_for(task)
            if parent_plan:
                delete_files.append((str(parent_plan), ""))
                archive_kept.append((str(parent_plan), ""))

            # Pending children
            buckets = self._categorize_pending_children(task_num)
            for child in buckets["disposable"]:
                child_status = child.metadata.get("status", "Ready")
                delete_files.append((str(child.filepath), child_status))
                archive_deleted.append((str(child.filepath), child_status))
                child_plan = self._resolve_plan_path_for(child)
                if child_plan:
                    delete_files.append((str(child_plan), ""))
                    archive_deleted.append((str(child_plan), ""))
                cascade_children.append(child)
            for child in buckets["blocking"]:
                child_status = child.metadata.get("status", "Ready")
                delete_files.append((str(child.filepath), child_status))
                blocking_files.append((str(child.filepath), child_status))
            for child in buckets["unarchived_done"]:
                delete_files.append((str(child.filepath), "Done — archive it first"))
                blocking_files.append((str(child.filepath), "Done — archive it first"))

            n_blocking = len(buckets["blocking"])
            n_done = len(buckets["unarchived_done"])
            if n_blocking or n_done:
                parts = []
                if n_blocking:
                    parts.append(f"{n_blocking} child(ren) Implementing")
                if n_done:
                    parts.append(f"{n_done} child(ren) Done but unarchived (archive them first)")
                blocked_reason = "Cannot archive parent: " + "; ".join(parts) + "."

        return {
            "delete_files": delete_files,
            "archive_kept": archive_kept,
            "archive_deleted": archive_deleted,
            "blocking_files": blocking_files,
            "cascade_children": cascade_children,
            "blocked_reason": blocked_reason,
        }

    def _collect_delete_files(self, task: Task):
        """Collect files to delete for a task (including children and plans).
        Returns (display_names, paths_to_delete)."""
        display_names = []
        paths = []
        task_num, _ = TaskCard._parse_filename(task.filename)

        # Task file itself
        display_names.append(task.filename)
        paths.append(task.filepath)

        is_child = task.filepath.parent.name.startswith("t")

        if is_child:
            # Child task: plan is in aiplans/p<parent>/p<parent>_<child>_<name>.md
            parent_num = self.manager.get_parent_num_for_child(task)
            plan_name = "p" + task.filename[1:]
            plan_path = Path("aiplans") / parent_num.replace("t", "p", 1) / plan_name
            if plan_path.exists():
                display_names.append(str(plan_path))
                paths.append(plan_path)
        else:
            # Parent task: plan is in aiplans/p<N>_<name>.md
            plan_name = "p" + task.filename[1:]
            plan_path = Path("aiplans") / plan_name
            if plan_path.exists():
                display_names.append(str(plan_path))
                paths.append(plan_path)

            # Child tasks and their plans
            children = self.manager.get_child_tasks_for_parent(task_num)
            for child in children:
                display_names.append(child.filename)
                paths.append(child.filepath)
                child_plan_name = "p" + child.filename[1:]
                child_plan_path = Path("aiplans") / task_num.replace("t", "p", 1) / child_plan_name
                if child_plan_path.exists():
                    display_names.append(str(child_plan_path))
                    paths.append(child_plan_path)

        return display_names, paths

    def _check_task_dependencies(self, task: Task, is_child: bool):
        """Check if other tasks depend on this task.
        Returns (dep_warnings: list[str], related_summaries: list[str])."""
        task_num_str, _ = TaskCard._parse_filename(task.filename)
        dep_warnings = []
        related_summaries = []

        if is_child:
            # Check sibling dependencies
            # Depends may use bare number (1), full ID (t398_1), or number-only ID (398_1)
            parent_num = self.manager.get_parent_num_for_child(task)
            siblings = self.manager.get_child_tasks_for_parent(parent_num)
            child_local = task_num_str.split("_")[-1]
            match_variants = {child_local, task_num_str, task_num_str.lstrip("t")}

            for sib in siblings:
                if sib.filepath == task.filepath:
                    continue
                sib_status = sib.metadata.get("status", "Ready")
                sib_depends = {str(d) for d in sib.metadata.get("depends", [])}
                if match_variants & sib_depends:
                    dep_warnings.append(
                        f"{sib.filename} ({sib_status}) explicitly depends on this task"
                    )
                else:
                    related_summaries.append(f"{sib.filename} [{sib_status}]")
        else:
            # Check all parent tasks for dependencies on this task number
            # Depends may use bare number (42) or with prefix (t42)
            task_local = task_num_str.lstrip("t")
            match_variants = {task_local, task_num_str}
            for fname, other in self.manager.task_datas.items():
                if other.filepath == task.filepath:
                    continue
                other_status = other.metadata.get("status", "Ready")
                other_depends = {str(d) for d in other.metadata.get("depends", [])}
                if match_variants & other_depends:
                    dep_warnings.append(
                        f"{other.filename} ({other_status}) explicitly depends on this task"
                    )

        return dep_warnings, related_summaries

    def _execute_archive(self, task_num: str, task: Task,
                         cascade_children: list = None):
        """Archive a task as superseded (shows loading overlay).

        If cascade_children is non-empty, those disposable children are
        removed from the parent's children_to_implement and their files
        deleted before the archive script runs (so the archived parent has
        a clean children_to_implement and the deletions land in the same
        archive commit).
        """
        cascade_paths = []
        cascade_ids = []
        for child in cascade_children or []:
            child_id, _ = TaskCard._parse_filename(child.filename)
            cascade_ids.append(child_id)
            cascade_paths.append(str(child.filepath))
            child_plan = self._resolve_plan_path_for(child)
            if child_plan:
                cascade_paths.append(str(child_plan))
        self.push_screen(LoadingOverlay("Archiving task..."))
        self._do_archive(task_num, cascade_ids, cascade_paths)

    @work(thread=True)
    def _do_archive(self, task_num: str,
                    cascade_ids: list[str], cascade_paths: list[str]):
        """Run archive subprocess in a thread worker.

        cascade_ids:   child task IDs (with 't' prefix, e.g. 't475_3') to remove
                       from the parent's children_to_implement before archiving.
        cascade_paths: child task/plan file paths to git-rm before archiving.
        """
        try:
            parent_num_bare = task_num.lstrip("t")

            # Remove disposable children from parent's children_to_implement
            # (does not commit — runs without --commit; the archive script's
            #  commit will pick up the staged changes).
            for child_id in cascade_ids:
                subprocess.run(
                    ["./.aitask-scripts/aitask_update.sh", "--batch", parent_num_bare,
                     "--remove-child", child_id, "--silent"],
                    capture_output=True, text=True, timeout=10
                )

            # git rm the disposable child files (task + plan)
            for path in cascade_paths:
                rm_result = subprocess.run(
                    [*_task_git_cmd(), "rm", "-f", path],
                    capture_output=True, text=True, timeout=10
                )
                if rm_result.returncode != 0:
                    try:
                        os.remove(path)
                    except OSError:
                        pass

            # Best-effort cleanup of empty child directories
            if cascade_paths:
                child_task_dir = TASKS_DIR / task_num
                if child_task_dir.is_dir():
                    try:
                        os.rmdir(child_task_dir)
                    except OSError:
                        pass
                child_plan_dir = Path("aiplans") / task_num.replace("t", "p", 1)
                if child_plan_dir.is_dir():
                    try:
                        os.rmdir(child_plan_dir)
                    except OSError:
                        pass

            result = subprocess.run(
                ["./.aitask-scripts/aitask_archive.sh", "--superseded", task_num],
                capture_output=True, text=True, timeout=30
            )
            if result.returncode == 0:
                msg = f"Archived {task_num} as superseded"
                if cascade_ids:
                    msg += f" (cascade-deleted {len(cascade_ids)} child(ren))"
                self.app.call_from_thread(self.notify, msg, severity="information")
            else:
                error = result.stderr.strip() or result.stdout.strip()
                self.app.call_from_thread(self.notify, f"Archive failed: {error}", severity="error")
        except subprocess.TimeoutExpired:
            self.app.call_from_thread(self.notify, "Archive operation timed out", severity="error")
        except FileNotFoundError:
            self.app.call_from_thread(self.notify, "Archive script not found", severity="error")
        finally:
            self.app.call_from_thread(self.pop_screen)

        self.app.call_from_thread(self.manager.load_tasks)
        self.app.call_from_thread(self.refresh_board)

    def _execute_delete(self, task_num: str, paths: list, task: Task = None):
        """Delete task files (shows loading overlay)."""
        paths_str = [str(p) for p in paths]
        folded_ids = []
        parent_num = None
        if task:
            folded_ids = [str(fid).lstrip("t") for fid in task.metadata.get("folded_tasks", [])]
            if task.filepath.parent.name.startswith("t"):
                parent_num = task.filepath.parent.name
        self.push_screen(LoadingOverlay("Deleting task..."))
        self._do_delete(task_num, paths_str, folded_ids, parent_num)

    @work(thread=True)
    def _do_delete(self, task_num: str, paths: list[str], folded_ids: list[str],
                   parent_num: str | None):
        """Run delete subprocess in a thread worker.

        If parent_num is set, this is a child-task delete: the child is
        first removed from the parent's children_to_implement (so the
        parent's metadata stays consistent), and after the commit lands
        the parent is checked for orphan status to prompt archival.
        """
        try:
            # Unfold folded tasks before deleting
            for fid_str in folded_ids:
                subprocess.run(
                    ["./.aitask-scripts/aitask_update.sh", "--batch", fid_str,
                     "--status", "Ready", "--folded-into", ""],
                    capture_output=True, text=True, timeout=10
                )

            # If deleting a child task, remove its reference from the parent's
            # children_to_implement list before the file disappears.
            if parent_num:
                parent_bare = parent_num.lstrip("t")
                subprocess.run(
                    ["./.aitask-scripts/aitask_update.sh", "--batch", parent_bare,
                     "--remove-child", task_num, "--silent"],
                    capture_output=True, text=True, timeout=10
                )

            for path in paths:
                result = subprocess.run(
                    [*_task_git_cmd(), "rm", "-f", path],
                    capture_output=True, text=True, timeout=10
                )
                if result.returncode != 0:
                    # Fallback for untracked files
                    try:
                        os.remove(path)
                    except OSError:
                        pass

            # Remove empty child directories
            child_task_dir = TASKS_DIR / task_num
            if child_task_dir.is_dir():
                try:
                    os.rmdir(child_task_dir)
                except OSError:
                    pass
            child_plan_dir = Path("aiplans") / task_num.replace("t", "p", 1)
            if child_plan_dir.is_dir():
                try:
                    os.rmdir(child_plan_dir)
                except OSError:
                    pass

            result = subprocess.run(
                [*_task_git_cmd(), "commit", "-m", f"ait: Delete task {task_num} and associated files"],
                capture_output=True, text=True, timeout=15
            )
            if result.returncode == 0:
                self.app.call_from_thread(self.notify, f"Deleted task {task_num}", severity="information")
            else:
                error = result.stderr.strip() or result.stdout.strip()
                self.app.call_from_thread(self.notify, f"Delete commit failed: {error}", severity="error")
        except subprocess.TimeoutExpired:
            self.app.call_from_thread(self.notify, "Git operation timed out", severity="error")
        except FileNotFoundError:
            self.app.call_from_thread(self.notify, "git not found", severity="error")
        finally:
            self.app.call_from_thread(self.pop_screen)

        self.app.call_from_thread(self.manager.load_tasks)
        self.app.call_from_thread(self.refresh_board)

        # After the parent has been reloaded, check for orphan-archive prompt.
        if parent_num:
            self.app.call_from_thread(self._maybe_prompt_orphan_parent_archive, parent_num)

    def _maybe_prompt_orphan_parent_archive(self, parent_num: str):
        """If the parent has no more pending children and is not Done,
        offer to archive it as completed."""
        parent_task = self.manager.find_task_by_id(parent_num)
        if parent_task is None:
            return
        children_to_implement = parent_task.metadata.get("children_to_implement") or []
        if children_to_implement:
            return
        if parent_task.metadata.get("status") == "Done":
            return
        # Also skip if there are still discoverable child files on disk
        # (defensive — children_to_implement may be stale)
        if self.manager.get_child_tasks_for_parent(parent_num):
            return

        parent_status = parent_task.metadata.get("status", "Ready")
        archive_kept = [(str(parent_task.filepath), f"parent — {parent_status}")]
        parent_plan = self._resolve_plan_path_for(parent_task)
        if parent_plan:
            archive_kept.append((str(parent_plan), ""))

        def on_orphan_decision(confirmed):
            if confirmed:
                self._execute_archive(parent_num, parent_task, cascade_children=None)

        self.push_screen(
            OrphanParentArchiveScreen(parent_task.filename, parent_status, archive_kept),
            on_orphan_decision,
        )

    def _rename_task(self, task: Task, new_name: str):
        """Rename a task (and its plan file if present), commit, and sync."""
        sanitized = _sanitize_name(new_name)
        if not sanitized:
            self.notify("Invalid name after sanitization", severity="error")
            return

        task_num, _ = TaskCard._parse_filename(task.filename)
        new_task_filename = f"{task_num}_{sanitized}.md"

        if new_task_filename == task.filename:
            self.notify("Name unchanged", severity="warning")
            return

        # Compute new task path (preserving parent directory for child tasks)
        new_task_path = task.filepath.parent / new_task_filename

        # Compute plan paths
        old_plan_path = self._resolve_plan_path_for(task)
        new_plan_path = None
        if old_plan_path and old_plan_path.exists():
            new_plan_filename = "p" + new_task_filename[1:]
            new_plan_path = old_plan_path.parent / new_plan_filename

        self.push_screen(LoadingOverlay("Renaming..."))
        self._do_rename_task(
            task.filepath, new_task_path,
            old_plan_path, new_plan_path,
            task_num, sanitized.replace("_", " "),
            new_task_filename,
        )

    @work(thread=True)
    def _do_rename_task(self, old_task: Path, new_task: Path,
                        old_plan: Path | None, new_plan: Path | None,
                        task_num: str, humanized_name: str,
                        new_filename: str):
        """Rename task/plan files, commit, and sync in a background thread."""
        try:
            # Rename task file
            old_task.rename(new_task)

            # Git add old (removal) and new task paths
            subprocess.run(
                [*_task_git_cmd(), "add", str(old_task), str(new_task)],
                capture_output=True, text=True, timeout=10,
            )

            # Rename plan file if present
            if old_plan and new_plan:
                old_plan.rename(new_plan)
                subprocess.run(
                    [*_task_git_cmd(), "add", str(old_plan), str(new_plan)],
                    capture_output=True, text=True, timeout=10,
                )

            # Commit
            commit_msg = f"ait: Rename {task_num}: {humanized_name}"
            result = subprocess.run(
                [*_task_git_cmd(), "commit", "-m", commit_msg],
                capture_output=True, text=True, timeout=15,
            )
            if result.returncode == 0:
                self.app.call_from_thread(
                    self.notify, f"Renamed to {new_filename}", severity="information")
            else:
                error = result.stderr.strip() or result.stdout.strip()
                self.app.call_from_thread(
                    self.notify, f"Commit failed: {error}", severity="error")
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as e:
            self.app.call_from_thread(
                self.notify, f"Rename failed: {e}", severity="error")
        finally:
            self.app.call_from_thread(self.pop_screen)  # dismiss LoadingOverlay

        # Sync
        self._run_sync(show_notification=True)

        # Reload and refresh board
        self.app.call_from_thread(self.manager.load_tasks)
        self.app.call_from_thread(self.refresh_board, refocus_filename=new_filename)

    def _git_commit_tasks(self, tasks: list[Task], message: str):
        """Stage and commit specific task files (shows loading overlay)."""
        focused = self._focused_card()
        refocus = focused.task_data.filename if focused else ""
        filepaths = [str(t.filepath) for t in tasks]
        count = len(tasks)
        self.push_screen(LoadingOverlay("Committing..."))
        self._do_git_commit_tasks(filepaths, count, message, refocus)

    @work(thread=True)
    def _do_git_commit_tasks(self, filepaths: list[str], count: int, message: str, refocus: str):
        """Run git add+commit in a thread worker."""
        try:
            for fp in filepaths:
                subprocess.run(
                    [*_task_git_cmd(), "add", fp],
                    capture_output=True, text=True, timeout=10
                )
            result = subprocess.run(
                [*_task_git_cmd(), "commit", "-m", message],
                capture_output=True, text=True, timeout=15
            )
            if result.returncode == 0:
                self.app.call_from_thread(self.notify, f"Committed {count} file(s)", severity="information")
            else:
                error = result.stderr.strip() or result.stdout.strip()
                self.app.call_from_thread(self.notify, f"Commit failed: {error}", severity="error")
        except subprocess.TimeoutExpired:
            self.app.call_from_thread(self.notify, "Git commit timed out", severity="error")
        except FileNotFoundError:
            self.app.call_from_thread(self.notify, "git not found", severity="error")
        finally:
            self.app.call_from_thread(self.pop_screen)

        self.app.call_from_thread(self.manager.refresh_git_status)
        self.app.call_from_thread(self.refresh_board, refocus_filename=refocus)

if __name__ == "__main__":
    app = KanbanApp()
    app.run()
