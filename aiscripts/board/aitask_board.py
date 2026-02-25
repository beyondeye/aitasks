from __future__ import annotations

import os
import re
import sys
import yaml
import json
import glob
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, HorizontalScroll, VerticalScroll
from textual.widgets import Header, Footer, Static, Label, Markdown, Input, Button
from textual.screen import Screen, ModalScreen
from textual.binding import Binding
from textual.message import Message
from textual import on, work
from textual.command import Provider, Hit, Hits, DiscoveryHit

from task_yaml import (
    _TaskSafeLoader, _FlowListDumper, _normalize_task_ids,
    FRONTMATTER_RE, BOARD_KEYS,
    parse_frontmatter, serialize_frontmatter,
)

# --- Configuration & Constants ---

TASKS_DIR = Path("aitasks")
METADATA_FILE = TASKS_DIR / "metadata" / "board_config.json"
TASK_TYPES_FILE = TASKS_DIR / "metadata" / "task_types.txt"
DATA_WORKTREE = Path(".aitask-data")
USERCONFIG_FILE = TASKS_DIR / "metadata" / "userconfig.yaml"
EMAILS_FILE = TASKS_DIR / "metadata" / "emails.txt"

def _task_git_cmd() -> list[str]:
    """Return git command prefix for task data operations.
    In branch mode: ["git", "-C", ".aitask-data"]
    In legacy mode: ["git"]
    """
    if DATA_WORKTREE.exists() and (DATA_WORKTREE / ".git").exists():
        return ["git", "-C", str(DATA_WORKTREE)]
    return ["git"]

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
        self.load()

    def load(self):
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
        except Exception as e:
            self.metadata = {}
            self._original_key_order = []
            self.content = str(e)

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
        """
        current_boardcol = self.metadata.get("boardcol")
        current_boardidx = self.metadata.get("boardidx")
        self.load()
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

class TaskManager:
    def __init__(self):
        self.task_datas: dict[str, Task] = {} # Filename -> Task (parents)
        self.child_task_datas: dict[str, Task] = {} # Filename -> Task (children)
        self.columns: list[dict] = []
        self.column_order: list[str] = []
        self.modified_files: set = set()  # Relative paths of git-modified .md files
        self.lock_map: dict[str, dict] = {}  # task_id -> {locked_by, locked_at, hostname}
        self.settings: dict = {}
        self._ensure_paths()
        self.load_metadata()
        self.load_tasks()

    def _ensure_paths(self):
        TASKS_DIR.mkdir(exist_ok=True)
        METADATA_FILE.parent.mkdir(exist_ok=True)

    def load_metadata(self):
        if METADATA_FILE.exists():
            with open(METADATA_FILE, "r") as f:
                data = json.load(f)
                self.columns = data.get("columns", DEFAULT_COLUMNS)
                self.column_order = data.get("column_order", DEFAULT_ORDER)
                self.settings = data.get("settings", {"auto_refresh_minutes": 5})
        else:
            self.columns = DEFAULT_COLUMNS
            self.column_order = DEFAULT_ORDER
            self.settings = {"auto_refresh_minutes": 5}
            self.save_metadata()

    def save_metadata(self):
        data = {
            "columns": self.columns,
            "column_order": self.column_order,
            "settings": self.settings,
        }
        with open(METADATA_FILE, "w") as f:
            json.dump(data, f, indent=2)

    @property
    def auto_refresh_minutes(self) -> int:
        return self.settings.get("auto_refresh_minutes", 5)

    @auto_refresh_minutes.setter
    def auto_refresh_minutes(self, value: int):
        self.settings["auto_refresh_minutes"] = value

    def load_tasks(self):
        self.task_datas.clear()
        for f in glob.glob(str(TASKS_DIR / "*.md")):
            path = Path(f)
            task = Task(path)
            self.task_datas[path.name] = task
        self.load_child_tasks()

    def load_child_tasks(self):
        self.child_task_datas.clear()
        for f in glob.glob(str(TASKS_DIR / "t*" / "t*_*.md")):
            path = Path(f)
            task = Task(path)
            self.child_task_datas[path.name] = task

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

    def get_child_tasks_for_parent(self, parent_num: str) -> list[Task]:
        """Get all child tasks for a parent like 't47'."""
        prefix = f"{parent_num}_"
        children = []
        for filename, task in self.child_task_datas.items():
            if filename.startswith(prefix):
                children.append(task)
        return sorted(children, key=lambda t: t.filename)

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
                ["./aiscripts/aitask_lock.sh", "--list"],
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

    def delete_column(self, col_id: str):
        """Delete a column and reassign its tasks to 'unordered'."""
        for task in self.get_column_tasks(col_id):
            task.board_col = "unordered"
            task.board_idx = 0
            task.reload_and_save_board_fields()
        self.columns = [c for c in self.columns if c["id"] != col_id]
        if col_id in self.column_order:
            self.column_order.remove(col_id)
        self.save_metadata()

    def get_column_conf(self, col_id: str):
        """Return the config dict for a column, or None."""
        return next((c for c in self.columns if c["id"] == col_id), None)

# --- UI Components ---

class ClickableColumnHeader(Label):
    """A column header label that opens the column edit dialog on click."""

    def __init__(self, col_id: str, title: str, task_count: int):
        super().__init__(f"{title} ({task_count})")
        self.col_id = col_id

    def on_click(self):
        self.app.open_column_edit(self.col_id)

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
            deps = meta.get('depends', [])
            for d in deps:
                d_str = str(d)
                dep_id = d_str if d_str.startswith('t') else f"t{d_str}"
                dep_task = self.manager.find_task_by_id(dep_id)
                if dep_task and dep_task.metadata.get('status') != 'Done':
                    unresolved_deps.append(dep_id)

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

        status_parts = []
        if unresolved_deps:
            status_parts.append("🚫 blocked")
        elif status and not implementing_children:
            status_parts.append(f"📋 {status}")
        if assigned_to: status_parts.append(f"👤 {assigned_to}")
        if status_parts:
            yield Label(" | ".join(status_parts), classes="task-info")

        if unresolved_deps:
            yield Label(f"🔗 {', '.join(unresolved_deps)}", classes="task-info")

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

    def on_mount(self):
        self.styles.border = ("solid", self._priority_border_color())
        self.styles.padding = (0, 1)
        if self.is_child:
            self.styles.margin = (0, 0, 1, 0)
        else:
            self.styles.margin = (0, 0, 1, 0)

    def on_focus(self):
        self.styles.border = ("double", "cyan")
        self.scroll_visible()

    def on_blur(self):
        self.styles.border = ("solid", self._priority_border_color())

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

class KanbanColumn(VerticalScroll):
    """A vertical column of tasks."""

    def __init__(self, col_id: str, title: str, color: str, manager: TaskManager, expanded_tasks: set = None):
        super().__init__()
        self.col_id = col_id
        self.col_title = title
        self.col_color = color
        self.manager = manager
        self.expanded_tasks = expanded_tasks or set()

    def compose(self):
        # Header
        task_count = len(self.manager.get_column_tasks(self.col_id))
        if self.col_id == "unordered":
            header = Label(f"{self.col_title} ({task_count})")
        else:
            header = ClickableColumnHeader(self.col_id, self.col_title, task_count)
        header.styles.background = self.col_color
        header.styles.color = "black"
        header.styles.width = "100%"
        header.styles.text_align = "center"
        yield header

        # Task Cards
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
        return self.manager.find_task_by_id(task_id)

    def _open_dep(self):
        if len(self.deps) == 1:
            task = self._find_task_by_number(self.deps[0])
            if task:
                self.app.push_screen(TaskDetailScreen(task, self.manager))
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
    task.load()  # Reload from disk to pick up external changes
    deps = task.metadata.get("depends", [])
    task.metadata["depends"] = [d for d in deps if d != dep_num]
    task.save_with_timestamp()


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

    def _open_child(self):
        if len(self.children_ids) == 1:
            task = self.manager.find_task_by_id(str(self.children_ids[0]))
            if task:
                self.app.push_screen(TaskDetailScreen(task, self.manager))
        else:
            child_items = []
            for child_id in self.children_ids:
                child_id_str = str(child_id)
                task = self.manager.find_task_by_id(child_id_str)
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
            task = self.manager.find_task_by_id(tid)
            if task:
                self.app.push_screen(
                    TaskDetailScreen(task, self.manager, read_only=True))
        else:
            folded_items = []
            for fid in self.folded_ids:
                fid_str = str(fid)
                tid = fid_str if fid_str.startswith('t') else f"t{fid_str}"
                task = self.manager.find_task_by_id(tid)
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
        task = self.manager.find_task_by_id(tid)
        if task:
            self.app.push_screen(TaskDetailScreen(task, self.manager))

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
        task = self.manager.find_task_by_id(self.parent_num)
        if task:
            self.app.push_screen(TaskDetailScreen(task, self.manager))

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
                self.app.push_screen(TaskDetailScreen(self.dep_task, self.manager))
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
                    TaskDetailScreen(self.child_task, self.manager))
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


class TaskDetailScreen(ModalScreen):
    """Popup to view/edit task details with metadata editing."""

    BINDINGS = [
        Binding("escape", "close_modal", "Close", show=False),
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

    def compose(self):
        task_num, task_name = TaskCard._parse_filename(self.task_data.filename)
        display_title = f"{task_num} {task_name}".strip()
        meta = self.task_data.metadata

        with Container(id="detail_dialog"):
            yield Label(f"\U0001f4c4 {display_title}", id="detail_title")

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
                    yield CycleField("Priority", ["low", "medium", "high"],
                                     meta.get("priority", "medium"), "priority",
                                     id="cf_priority")
                    yield CycleField("Effort", ["low", "medium", "high"],
                                     meta.get("effort", "medium"), "effort",
                                     id="cf_effort")
                    status_options = ["Ready", "Editing", "Implementing", "Postponed"]
                    yield CycleField("Status", status_options,
                                     meta.get("status", "Ready"), "status",
                                     id="cf_status")
                    yield CycleField("Type", _load_task_types(),
                                     meta.get("issue_type", "feature"), "issue_type",
                                     id="cf_issue_type")

            if meta.get("labels"):
                yield ReadOnlyField(f"[b]Labels:[/b] {', '.join(meta['labels'])}", classes="meta-ro")
            if meta.get("depends"):
                deps = meta["depends"]
                if deps and self.manager:
                    yield DependsField(deps, self.manager, self.task_data, classes="meta-ro")
                elif deps:
                    dep_str = ", ".join(str(d) for d in deps)
                    yield ReadOnlyField(f"[b]Depends:[/b] {dep_str}", classes="meta-ro")
            if meta.get("assigned_to"):
                yield ReadOnlyField(f"[b]Assigned to:[/b] {meta['assigned_to']}", classes="meta-ro")
            if meta.get("issue"):
                yield IssueField(meta["issue"], classes="meta-ro")
            dates = []
            if meta.get("created_at"):
                dates.append(f"[b]Created:[/b] {meta['created_at']}")
            if meta.get("updated_at"):
                dates.append(f"[b]Updated:[/b] {meta['updated_at']}")
            if dates:
                yield ReadOnlyField("  |  ".join(dates), classes="meta-ro")
            # Parent field for child tasks
            if self.task_data.filepath.parent != TASKS_DIR and self.manager:
                parent_num = self.manager.get_parent_num_for_child(self.task_data)
                if parent_num:
                    yield ParentField(parent_num, self.manager, classes="meta-ro")
            # Children field for parent tasks
            if meta.get("children_to_implement"):
                children_ids = meta["children_to_implement"]
                if children_ids and self.manager:
                    yield ChildrenField(children_ids, self.manager, self.task_data,
                                       classes="meta-ro")
                elif children_ids:
                    children = ", ".join(str(c) for c in children_ids)
                    yield ReadOnlyField(f"[b]Children:[/b] {children}", classes="meta-ro")
            # Folded tasks field
            if meta.get("folded_tasks"):
                folded_ids = meta["folded_tasks"]
                if folded_ids and self.manager:
                    yield FoldedTasksField(folded_ids, self.manager,
                                           self.task_data, classes="meta-ro")
                elif folded_ids:
                    folded_str = ", ".join(str(f) for f in folded_ids)
                    yield ReadOnlyField(
                        f"[b]Folded Tasks:[/b] {folded_str}", classes="meta-ro")
            # Folded into field
            if meta.get("folded_into"):
                folded_into_num = str(meta["folded_into"])
                if self.manager:
                    yield FoldedIntoField(folded_into_num, self.manager, classes="meta-ro")
                else:
                    yield ReadOnlyField(
                        f"[b]Folded Into:[/b] t{folded_into_num}", classes="meta-ro")

            # Lock status
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
                yield ReadOnlyField(
                    f"[b]\U0001f512 Locked:[/b] {locked_by}{host_str} since {locked_at}{stale_marker}",
                    classes="meta-ro")
            else:
                yield ReadOnlyField(
                    "[b]\U0001f513 Lock:[/b] [dim]Unlocked[/dim]",
                    classes="meta-ro")

            with VerticalScroll(id="md_view"):
                yield Markdown(self.task_data.content)

            # Button rows
            is_locked = self._lock_info is not None
            with Container(id="detail_buttons_area"):
                with Horizontal(id="detail_buttons_workflow"):
                    yield Button("Pick", variant="warning", id="btn_pick", disabled=is_done_or_ro)
                    yield Button("\U0001f512 Lock", variant="primary", id="btn_lock",
                                 disabled=is_done_or_ro or is_locked)
                    yield Button("\U0001f513 Unlock", variant="warning", id="btn_unlock",
                                 disabled=not is_locked)
                    yield Button("Close", variant="default", id="btn_close")
                with Horizontal(id="detail_buttons_file"):
                    yield Button("Save Changes", variant="success", id="btn_save",
                                 disabled=True)
                    is_modified = self.manager.is_modified(self.task_data) if self.manager else False
                    yield Button("Revert", variant="error", id="btn_revert",
                                 disabled=is_done_or_ro or not is_modified)
                    yield Button("Edit", variant="primary", id="btn_edit", disabled=is_done_or_ro)
                    is_child = self.task_data.filepath.parent.name.startswith("t")
                    can_delete = (not is_done and not is_folded and not self.read_only
                                  and self.task_data.metadata.get("status", "") != "Implementing"
                                  and not is_child)
                    yield Button("Delete", variant="error", id="btn_delete",
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
        is_child = self.task_data.filepath.parent.name.startswith("t")
        status = self._current_values.get("status", "")
        btn_delete = self.query_one("#btn_delete", Button)
        btn_delete.disabled = (status == "Implementing" or is_child)

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
        self.task_data.load()
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
        self.dismiss("edit")

    @on(Button.Pressed, "#btn_delete")
    def delete_task(self):
        self.dismiss("delete")

    @on(Button.Pressed, "#btn_pick")
    def pick_task(self):
        self.dismiss("pick")

    @on(Button.Pressed, "#btn_lock")
    def lock_task(self):
        """Lock this task via aitask_lock.sh."""
        task_num, _ = TaskCard._parse_filename(self.task_data.filename)
        task_id = task_num.lstrip("t")
        default_email = _get_user_email()

        def on_email(email):
            if email is None:
                return
            try:
                result = subprocess.run(
                    ["./aiscripts/aitask_lock.sh", "--lock", task_id, "--email", email],
                    capture_output=True, text=True, timeout=15
                )
                if result.returncode == 0:
                    self.app.notify(f"Locked t{task_id}", severity="information")
                    self.dismiss("locked")
                else:
                    error = result.stderr.strip() or result.stdout.strip()
                    self.app.notify(f"Lock failed: {error}", severity="error")
            except (subprocess.TimeoutExpired, FileNotFoundError) as e:
                self.app.notify(f"Lock failed: {e}", severity="error")

        self.app.push_screen(LockEmailScreen(task_id, default_email), on_email)

    @on(Button.Pressed, "#btn_unlock")
    def unlock_task(self):
        """Unlock this task via aitask_lock.sh."""
        task_num, _ = TaskCard._parse_filename(self.task_data.filename)
        task_id = task_num.lstrip("t")

        def do_unlock():
            try:
                result = subprocess.run(
                    ["./aiscripts/aitask_lock.sh", "--unlock", task_id],
                    capture_output=True, text=True, timeout=15
                )
                if result.returncode == 0:
                    self.app.notify(f"Unlocked t{task_id}", severity="information")
                    meta = self.task_data.metadata
                    if meta.get("status") == "Implementing" and meta.get("assigned_to"):
                        assigned_to = meta["assigned_to"]
                        def on_reset_confirmed(confirmed):
                            if confirmed:
                                self.task_data.load()
                                self.task_data.metadata["status"] = "Ready"
                                self.task_data.metadata["assigned_to"] = ""
                                self.task_data.save_with_timestamp()
                            self.dismiss("unlocked")
                        self.app.push_screen(
                            ResetTaskConfirmScreen(task_id, assigned_to),
                            on_reset_confirmed,
                        )
                        return
                    self.dismiss("unlocked")
                else:
                    error = result.stderr.strip() or result.stdout.strip()
                    self.app.notify(f"Unlock failed: {error}", severity="error")
            except (subprocess.TimeoutExpired, FileNotFoundError) as e:
                self.app.notify(f"Unlock failed: {e}", severity="error")

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

    def action_close_modal(self):
        self.dismiss()

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


class SyncConflictScreen(ModalScreen):
    """Modal dialog shown when ait sync detects merge conflicts."""

    BINDINGS = [Binding("escape", "cancel", "Cancel", show=False)]

    def __init__(self, conflicted_files: list[str]):
        super().__init__()
        self.conflicted_files = conflicted_files

    def compose(self):
        file_list = "\n".join(f"  - {f}" for f in self.conflicted_files)
        with Container(id="dep_picker_dialog"):
            yield Label("Sync Conflict Detected", id="dep_picker_title")
            yield Label(
                f"Conflicts between local and remote task data:\n\n{file_list}\n\n"
                "Open interactive terminal to resolve?",
                id="commit_files",
            )
            with Horizontal(id="detail_buttons"):
                yield Button("Resolve Interactively", variant="warning", id="btn_sync_resolve")
                yield Button("Dismiss", variant="default", id="btn_sync_dismiss")

    @on(Button.Pressed, "#btn_sync_resolve")
    def resolve(self):
        self.dismiss(True)

    @on(Button.Pressed, "#btn_sync_dismiss")
    def dismiss_dialog(self):
        self.dismiss(False)

    def action_cancel(self):
        self.dismiss(False)


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
    """Select a column from the list for editing/deleting."""

    BINDINGS = [
        Binding("escape", "cancel", "Close", show=False),
    ]

    def __init__(self, manager: TaskManager, action_label: str):
        super().__init__()
        self.manager = manager
        self.action_label = action_label

    def compose(self):
        with Container(id="dep_picker_dialog"):
            yield Label(f"Select column to {self.action_label.lower()}:", id="dep_picker_title")
            for col in self.manager.columns:
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

class KanbanApp(App):
    CSS = """
    Screen { align: center middle; }
    #detail_dialog {
        width: 80%;
        height: 80%;
        background: $surface;
        border: thick $primary;
        padding: 1 2;
    }
    #detail_title { 
        dock: top; 
        text-align: center; 
        background: $secondary; 
        color: $text; 
        padding: 1;
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
    CycleField { height: 1; width: 100%; padding: 0 1; }
    CycleField.cycle-focused { background: $primary 20%; border-left: thick $accent; }
    .meta-ro { height: 1; width: 100%; padding: 0 2; color: $text-muted; }
    .meta-ro.ro-focused { background: $primary 20%; border-left: thick $accent; }
    #btn_save:disabled { opacity: 50%; }
    #btn_delete:disabled { opacity: 50%; }
    #md_view { margin: 1 0; border: solid $secondary-background; }
    .task-title-row { height: auto; }
    .task-number { color: $accent; text-style: bold; width: auto; margin: 0 1 0 0; }
    .task-modified { color: #FFB86C; }
    .task-title { text-style: bold; width: 1fr; }
    .task-info { color: $text-muted; }
    .child-wrapper { height: auto; }
    .child-wrapper TaskCard { width: 1fr; }
    .child-connector { width: auto; height: auto; padding: 0; margin: 1 0 0 0; color: $text-muted; }
    Input { dock: top; margin: 0 0 1 0; }
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
    """

    TITLE = "aitasks board"

    COMMANDS = App.COMMANDS | {KanbanCommandProvider}

    BINDINGS = [
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
        Binding("enter", "view_details", "View/Edit"),
        Binding("r", "refresh_board", "Refresh"),
        Binding("s", "sync_remote", "Sync"),
        # Git Commit (shown conditionally via check_action)
        Binding("c", "commit_selected", "Commit"),
        Binding("C", "commit_all", "Commit All"),
        # Task Creation
        Binding("n", "create_task", "New Task"),
        # Expand/Collapse children (shown conditionally via check_action)
        Binding("x", "toggle_children", "Toggle Children"),
        # Column Movement
        Binding("ctrl+right", "move_col_right", "Move Col >"),
        Binding("ctrl+left", "move_col_left", "< Move Col"),
        # Settings
        Binding("O", "open_settings", "Options"),
    ]

    def __init__(self):
        super().__init__()
        self.manager = TaskManager()
        self.search_filter = ""
        self.expanded_tasks: set = set()
        self._auto_refresh_timer = None

    def check_action(self, action: str, parameters) -> bool | None:
        """Control visibility of conditional actions in the footer bar."""
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
        elif action in ("move_task_right", "move_task_left", "move_task_up", "move_task_down"):
            focused = self._focused_card()
            if focused and focused.is_child:
                return None  # Hide movement actions for child cards
        return True

    def compose(self):
        header = Header()
        header.can_focus = False
        yield header
        yield Input(placeholder="Search tasks... (Tab to focus, Esc to return to board)", id="search_box")
        yield HorizontalScroll(id="board_container")
        footer = Footer()
        footer.can_focus = False
        yield footer

    def on_mount(self):
        self.refresh_board()
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
        self.refresh_board(refocus_filename=refocus)

    def refresh_board(self, refocus_filename: str = ""):
        self.manager.refresh_git_status()
        self.manager.refresh_lock_map()
        container = self.query_one("#board_container")
        container.remove_children()

        # 1. Unordered/Backlog Column (Dynamic)
        unordered_tasks = self.manager.get_column_tasks("unordered")
        if unordered_tasks:
            container.mount(KanbanColumn("unordered", "Unsorted / Inbox", "gray", self.manager, self.expanded_tasks))

        # 2. Configured Columns
        for col_id in self.manager.column_order:
            conf = next((c for c in self.manager.columns if c["id"] == col_id), None)
            if conf:
                container.mount(KanbanColumn(conf["id"], conf["title"], conf["color"], self.manager, self.expanded_tasks))

        self.apply_filter()

        # Restore focus to the card matching refocus_filename
        if refocus_filename:
            self.call_after_refresh(self._refocus_card, refocus_filename)

    def _refocus_card(self, filename: str):
        for card in self.query(TaskCard):
            if card.task_data.filename == filename:
                card.focus()
                return

    @on(Input.Changed, "#search_box")
    def on_search(self, event: Input.Changed):
        self.search_filter = event.value.lower()
        self.apply_filter()

    def apply_filter(self):
        # iterate all TaskCards and toggle visibility
        for card in self.query(TaskCard):
            search_content = f"{card.task_data.filename} {card.task_data.metadata}".lower()
            if self.search_filter in search_content:
                card.styles.display = "block"
            else:
                card.styles.display = "none"

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
            self.screen.dismiss()
            return
        cards = list(self.query(TaskCard))
        if cards:
            cards[0].focus()

    def _focused_card(self):
        """Return the currently focused TaskCard, or None."""
        results = self.query("TaskCard:focus")
        return results.first() if results else None

    def _get_column_cards(self, col_id: str) -> list:
        """Return TaskCard widgets belonging to a column, in DOM order."""
        return [c for c in self.query(TaskCard) if c.column_id == col_id]

    def _get_visible_col_ids(self) -> list:
        """Return ordered list of column IDs currently on the board."""
        return [col.col_id for col in self.query(KanbanColumn)]

    def _modal_is_active(self):
        return isinstance(self.screen, ModalScreen)

    def action_nav_up(self):
        if self._modal_is_active():
            self.screen.focus_previous()
            return
        focused = self._focused_card()
        if not focused:
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
            self.action_focus_board()
            return
        cards = self._get_column_cards(focused.column_id)
        idx = next((i for i, c in enumerate(cards) if c is focused), -1)
        if idx < len(cards) - 1:
            cards[idx + 1].focus()

    def action_nav_left(self):
        if self._modal_is_active():
            focused = self.screen.focused
            if isinstance(focused, CycleField):
                focused.cycle_prev()
            return
        self._nav_lateral(-1)

    def action_nav_right(self):
        if self._modal_is_active():
            focused = self.screen.focused
            if isinstance(focused, CycleField):
                focused.cycle_next()
            return
        self._nav_lateral(1)

    def _nav_lateral(self, direction: int):
        focused = self._focused_card()
        if not focused:
            self.action_focus_board()
            return
        col_ids = self._get_visible_col_ids()
        cur_col = focused.column_id
        if cur_col not in col_ids:
            return
        cur_idx = col_ids.index(cur_col)
        # Skip over empty columns to find the next column with tasks
        new_idx = cur_idx + direction
        while 0 <= new_idx < len(col_ids):
            target_cards = self._get_column_cards(col_ids[new_idx])
            if target_cards:
                # Try to land on the same vertical position
                old_cards = self._get_column_cards(cur_col)
                old_pos = next((i for i, c in enumerate(old_cards) if c is focused), 0)
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
                elif result == "pick":
                    self.run_aitask_pick(focused.task_data.filename)
                elif result == "delete":
                    display_names, paths = self._collect_delete_files(focused.task_data)
                    def on_delete_confirmed(confirmed):
                        if confirmed:
                            task_num, _ = TaskCard._parse_filename(focused.task_data.filename)
                            self._execute_delete(task_num, paths, focused.task_data)
                        else:
                            self.refresh_board(refocus_filename=focused.task_data.filename)
                    self.push_screen(DeleteConfirmScreen(display_names), on_delete_confirmed)
                    return
                # Refresh board to update git status indicators (asterisk, commit actions)
                self.refresh_board(refocus_filename=focused.task_data.filename)

            self.push_screen(TaskDetailScreen(focused.task_data, self.manager), check_edit)

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

    def _find_terminal(self):
        """Find an available terminal emulator, or return None."""
        terminal = os.environ.get("TERMINAL")
        if terminal and shutil.which(terminal):
            return terminal
        for term in ["x-terminal-emulator", "xdg-terminal-exec", "gnome-terminal",
                     "konsole", "xfce4-terminal", "lxterminal", "mate-terminal", "xterm"]:
            if shutil.which(term):
                return term
        return None

    def action_sync_remote(self):
        """Manually trigger a sync with remote."""
        if self._modal_is_active():
            return
        self._run_sync(show_notification=True)

    @work(exclusive=True)
    async def _run_sync(self, show_notification: bool = True):
        """Run ait sync --batch in background and handle the result."""
        try:
            result = subprocess.run(
                ["./aiscripts/aitask_sync.sh", "--batch"],
                capture_output=True, text=True, timeout=30,
            )
            output = result.stdout.strip().splitlines()
            status_line = output[0] if output else ""
        except subprocess.TimeoutExpired:
            if show_notification:
                self.notify("Sync timed out", severity="warning")
            return
        except FileNotFoundError:
            self.notify("Sync script not found", severity="error")
            return

        if status_line.startswith("CONFLICT:"):
            files = status_line[len("CONFLICT:"):].split(",")
            self.app.call_from_thread(self._show_conflict_dialog, files)
            return
        elif status_line == "NO_NETWORK":
            if show_notification:
                self.notify("Sync: No network", severity="warning")
        elif status_line == "NO_REMOTE":
            if show_notification:
                self.notify("Sync: No remote configured", severity="warning")
        elif status_line == "NOTHING":
            if show_notification:
                self.notify("Already up to date", severity="information")
        elif status_line == "AUTOMERGED":
            if show_notification:
                self.notify("Sync: Auto-merged conflicts", severity="information")
        elif status_line in ("PUSHED", "PULLED", "SYNCED"):
            if show_notification:
                self.notify(f"Sync: {status_line.capitalize()}", severity="information")
        elif status_line.startswith("ERROR:"):
            msg = status_line[len("ERROR:"):]
            self.notify(f"Sync error: {msg}", severity="error")

        self.manager.load_tasks()
        self.refresh_board()

    def _show_conflict_dialog(self, files: list[str]):
        """Show the conflict resolution dialog (must be called on main thread)."""
        def on_result(resolve):
            if resolve:
                self._run_interactive_sync()
            else:
                self.manager.load_tasks()
                self.refresh_board()
        self.push_screen(SyncConflictScreen(files), on_result)

    @work(exclusive=True)
    async def _run_interactive_sync(self):
        """Launch interactive ait sync in a terminal."""
        terminal = self._find_terminal()
        if terminal:
            subprocess.Popen([terminal, "--", "./ait", "sync"])
        else:
            with self.suspend():
                subprocess.call(["./ait", "sync"])
            self.manager.load_tasks()
            self.refresh_board()

    @work(exclusive=True)
    async def run_aitask_pick(self, filename):
        """Launch claude with /aitask-pick for the task."""
        task_num, _ = TaskCard._parse_filename(filename)
        if not task_num:
            return
        num = task_num.lstrip("t")
        terminal = self._find_terminal()
        if terminal:
            subprocess.Popen([terminal, "--", "claude", f"/aitask-pick {num}"])
        else:
            with self.suspend():
                subprocess.call(["claude", f"/aitask-pick {num}"])
            self.manager.load_tasks()
            self.refresh_board(refocus_filename=filename)

    @work(exclusive=True)
    async def action_create_task(self):
        """Create a new task, using a terminal emulator or falling back to suspend."""
        terminal = self._find_terminal()
        if terminal:
            subprocess.Popen([terminal, "--", "./aiscripts/aitask_create.sh"])
        else:
            with self.suspend():
                subprocess.call(["./aiscripts/aitask_create.sh"])
            self.manager.load_tasks()
            self.refresh_board()

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
        self.refresh_board(refocus_filename=fn)

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
        new_idx = idx + direction

        if 0 <= new_idx < len(cols):
            new_col = cols[new_idx]
            self.manager.move_task_col(filename, new_col)
            self.manager.normalize_indices(current_col_id)
            self.manager.normalize_indices(new_col)
            self.refresh_board(refocus_filename=filename)

    def action_move_task_up(self):
        self._move_task_vertical(-1)

    def action_move_task_down(self):
        self._move_task_vertical(1)
        
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
            self.refresh_board(refocus_filename=filename)

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

    def _collect_delete_files(self, task: Task):
        """Collect files to delete for a task (including children and plans).
        Returns (display_names, paths_to_delete)."""
        display_names = []
        paths = []
        task_num, _ = TaskCard._parse_filename(task.filename)

        # Task file itself
        display_names.append(task.filename)
        paths.append(task.filepath)

        # Plan file for parent task: aiplans/p<N>_<name>.md
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

    def _execute_delete(self, task_num: str, paths: list, task: Task = None):
        """Delete files via git rm and commit."""
        try:
            # Unfold folded tasks before deleting
            if task:
                folded = task.metadata.get("folded_tasks", [])
                for fid in folded:
                    fid_str = str(fid).lstrip("t")
                    subprocess.run(
                        ["./aiscripts/aitask_update.sh", "--batch", fid_str,
                         "--status", "Ready", "--folded-into", ""],
                        capture_output=True, text=True, timeout=10
                    )

            for path in paths:
                result = subprocess.run(
                    [*_task_git_cmd(), "rm", "-f", str(path)],
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
                self.notify(f"Deleted task {task_num}", severity="information")
            else:
                error = result.stderr.strip() or result.stdout.strip()
                self.notify(f"Delete commit failed: {error}", severity="error")
        except subprocess.TimeoutExpired:
            self.notify("Git operation timed out", severity="error")
        except FileNotFoundError:
            self.notify("git not found", severity="error")

        self.manager.load_tasks()
        self.refresh_board()

    def _git_commit_tasks(self, tasks: list[Task], message: str):
        """Stage and commit specific task files."""
        try:
            for task in tasks:
                subprocess.run(
                    [*_task_git_cmd(), "add", str(task.filepath)],
                    capture_output=True, text=True, timeout=10
                )
            result = subprocess.run(
                [*_task_git_cmd(), "commit", "-m", message],
                capture_output=True, text=True, timeout=15
            )
            if result.returncode == 0:
                self.notify(f"Committed {len(tasks)} file(s)", severity="information")
            else:
                error = result.stderr.strip() or result.stdout.strip()
                self.notify(f"Commit failed: {error}", severity="error")
        except subprocess.TimeoutExpired:
            self.notify("Git commit timed out", severity="error")
        except FileNotFoundError:
            self.notify("git not found", severity="error")

        focused = self._focused_card()
        refocus = focused.task_data.filename if focused else ""
        self.manager.refresh_git_status()
        self.refresh_board(refocus_filename=refocus)

if __name__ == "__main__":
    app = KanbanApp()
    app.run()