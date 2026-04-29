"""monitor_shared - Shared widgets and utilities for monitor TUIs.

Provides reusable components used by both the full monitor (monitor_app.py)
and the mini monitor. Extracted to avoid code duplication.
"""
from __future__ import annotations

import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path

# Set up import paths before any local imports
_SCRIPT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_SCRIPT_DIR))
sys.path.insert(0, str(_SCRIPT_DIR / "lib"))
sys.path.insert(0, str(_SCRIPT_DIR / "board"))

from monitor.tmux_monitor import PaneSnapshot  # noqa: E402
from task_yaml import parse_frontmatter  # noqa: E402

from textual.binding import Binding  # noqa: E402
from textual.containers import Container, VerticalScroll  # noqa: E402
from textual.screen import ModalScreen  # noqa: E402
from textual.widgets import Button, Label, Markdown, Static  # noqa: E402
from textual.app import ComposeResult  # noqa: E402
from rich.text import Text  # noqa: E402


# Dark background for terminal preview — hard-coded because we're rendering
# actual tmux terminal content (always dark) regardless of the TUI theme.
_DARK_BG_ANSI = "\033[48;2;26;26;26m"
_ANSI_RESET_RE = re.compile(r'\033\[0?m')
_ANSI_DEFAULT_BG_RE = re.compile(r'\033\[49m')


# Idle-detection compare-mode pseudo-icons used in agent cards across both
# the full monitor and the minimonitor. Single column wide so the compact
# minimonitor layout stays compact.
COMPARE_MODE_ICONS = {
    "stripped": "≈",   # ≈ — fuzzy / ANSI-stripped equality (default)
    "raw": "=",             # = — strict byte-equal
}


def format_compare_mode_glyph(mode: str, is_override: bool) -> str:
    glyph = COMPARE_MODE_ICONS.get(mode, "?")
    color = "yellow" if is_override else "dim"
    return f"[{color}]{glyph}[/]"


def _ansi_to_rich_text(ansi_str: str) -> Text:
    """Convert ANSI text to Rich Text with a forced dark background.

    Pre-processes the raw ANSI to inject a dark background (#1a1a1a) at the
    start and after every SGR reset, so areas that would otherwise show the
    terminal's default background render correctly in the TUI preview.
    """
    # Set dark bg at start of every line
    lines = ansi_str.split("\n")
    patched = []
    for line in lines:
        # Inject dark bg at start
        line = _DARK_BG_ANSI + line
        # After every reset (\033[0m or \033[m), re-apply dark bg
        line = _ANSI_RESET_RE.sub(lambda m: m.group(0) + _DARK_BG_ANSI, line)
        # Replace default-bg-only (\033[49m) with our dark bg
        line = _ANSI_DEFAULT_BG_RE.sub(_DARK_BG_ANSI, line)
        patched.append(line)
    text = Text.from_ansi("\n".join(patched))
    return text


# -- Task context --------------------------------------------------------------

_TASK_ID_RE = re.compile(r'^agent-(?:pick|qa)-(\d+(?:_\d+)?)$')


@dataclass
class TaskInfo:
    """Resolved task metadata and content for display in the monitor."""
    task_id: str
    task_file: str
    title: str
    priority: str
    effort: str
    issue_type: str
    status: str
    body: str
    plan_content: str | None


class TaskInfoCache:
    """Cache for resolved task info — avoids file I/O on every refresh.

    Cross-project aware: when callers provide a tmux ``session_name`` the cache
    resolves the task file from the project root that owns that session (via
    ``session_to_project``). An empty/unknown ``session_name`` falls back to
    the local ``project_root`` — preserving single-session behaviour.
    """

    def __init__(
        self,
        project_root: Path,
        session_to_project: dict[str, Path] | None = None,
    ):
        self._project_root = project_root
        self._session_to_project: dict[str, Path] = dict(session_to_project or {})
        # Keyed by (session_name, task_id) so two projects can both have t100
        # without clobbering each other.
        self._cache: dict[tuple[str, str], TaskInfo | None] = {}
        self._window_to_task_id: dict[str, str | None] = {}

    def update_session_mapping(self, mapping: dict[str, Path]) -> None:
        """Replace the session→project_root mapping (idempotent).

        Clears the resolved-task cache when the mapping changes, since entries
        for a session may have been resolved against a stale (or absent)
        mapping and now point at the wrong project's task data.
        """
        if mapping != self._session_to_project:
            self._session_to_project = dict(mapping)
            self._cache.clear()

    def _root_for_session(self, session_name: str) -> Path:
        """Resolve the project root for a tmux session, falling back to local."""
        if session_name and session_name in self._session_to_project:
            return self._session_to_project[session_name]
        return self._project_root

    def get_task_id(self, window_name: str) -> str | None:
        """Extract task ID from agent window name. Cached."""
        if window_name not in self._window_to_task_id:
            m = _TASK_ID_RE.match(window_name)
            self._window_to_task_id[window_name] = m.group(1) if m else None
        return self._window_to_task_id[window_name]

    def get_task_info(
        self, task_id: str, session_name: str = ""
    ) -> TaskInfo | None:
        """Resolve task info from task ID. Cached after first lookup."""
        key = (session_name, task_id)
        if key not in self._cache:
            self._cache[key] = self._resolve(task_id, session_name)
        return self._cache[key]

    def invalidate(self, task_id: str, session_name: str = "") -> None:
        self._cache.pop((session_name, task_id), None)

    def get_parent_id(self, task_id: str) -> str | None:
        """Extract parent task number from a child task ID."""
        if "_" not in task_id:
            return None
        return task_id.split("_", 1)[0]

    def find_next_sibling(
        self, task_id: str, session_name: str = ""
    ) -> tuple[str, str] | None:
        """Find the next Ready sibling/child task.

        If task_id is a child (e.g. "123_4"), returns the next Ready sibling
        under the same parent, excluding the current task. If task_id is a
        parent (e.g. "123"), returns the first Ready child of that parent.

        Returns (task_id, title) or None.
        """
        if "_" in task_id:
            parent, _child = task_id.split("_", 1)
            exclude_id: str | None = task_id
        else:
            parent = task_id
            exclude_id = None

        root = self._root_for_session(session_name)
        search_dir = root / "aitasks" / f"t{parent}"
        if not search_dir.is_dir():
            return None

        candidates = []
        child_re = re.compile(rf'^t{re.escape(parent)}_(\d+)_')
        for path in sorted(search_dir.glob(f"t{parent}_*_*.md")):
            m = child_re.match(path.stem)
            if not m:
                continue
            sib_child = m.group(1)
            sib_id = f"{parent}_{sib_child}"
            if exclude_id is not None and sib_id == exclude_id:
                continue
            try:
                raw = path.read_text(encoding="utf-8")
            except OSError:
                continue
            parsed = parse_frontmatter(raw)
            if parsed is None:
                continue
            metadata, body, _ = parsed
            if str(metadata.get("status", "")).strip() != "Ready":
                continue
            title = None
            for line in body.splitlines():
                ls = line.strip()
                if ls.startswith("# "):
                    title = ls[2:].strip()
                    break
            if not title:
                parts = path.stem.split("_", 2)
                title = parts[2].replace("_", " ") if len(parts) > 2 else path.stem
            candidates.append((int(sib_child), sib_id, title))

        if not candidates:
            return None
        candidates.sort(key=lambda x: x[0])
        _, sib_id, title = candidates[0]
        return (sib_id, title)

    def _resolve(self, task_id: str, session_name: str = "") -> TaskInfo | None:
        """Look up task file and parse its content. Pure Python, no subprocess."""
        root = self._root_for_session(session_name)
        tasks_dir = root / "aitasks"
        plans_dir = root / "aiplans"

        if "_" in task_id:
            parent, child = task_id.split("_", 1)
            pattern = f"t{parent}_{child}_*.md"
            search_dir = tasks_dir / f"t{parent}"
        else:
            pattern = f"t{task_id}_*.md"
            search_dir = tasks_dir

        if not search_dir.is_dir():
            return None
        matches = list(search_dir.glob(pattern))
        if not matches:
            return None

        task_path = matches[0]
        try:
            raw = task_path.read_text(encoding="utf-8")
        except OSError:
            return None

        parsed = parse_frontmatter(raw)
        if parsed is None:
            return None
        metadata, body, _ = parsed

        # Extract title: first markdown heading or derive from filename
        title = None
        for line in body.splitlines():
            line_s = line.strip()
            if line_s.startswith("# "):
                title = line_s[2:].strip()
                break
        if not title:
            stem = task_path.stem
            parts = stem.split("_", 1)
            title = parts[1].replace("_", " ") if len(parts) > 1 else stem

        # Find plan file
        plan_content = None
        if "_" in task_id:
            parent, child = task_id.split("_", 1)
            plan_pattern = f"p{parent}_{child}_*.md"
            plan_dir = plans_dir / f"p{parent}"
        else:
            plan_pattern = f"p{task_id}_*.md"
            plan_dir = plans_dir

        if plan_dir.is_dir():
            plan_matches = list(plan_dir.glob(plan_pattern))
            if plan_matches:
                try:
                    plan_raw = plan_matches[0].read_text(encoding="utf-8")
                    if plan_raw.startswith("---"):
                        fm_parts = plan_raw.split("---", 2)
                        if len(fm_parts) >= 3:
                            plan_content = fm_parts[2].strip()
                        else:
                            plan_content = plan_raw
                    else:
                        plan_content = plan_raw
                except OSError:
                    pass

        return TaskInfo(
            task_id=task_id,
            task_file=str(task_path.relative_to(root)),
            title=title,
            priority=str(metadata.get("priority", "")),
            effort=str(metadata.get("effort", "")),
            issue_type=str(metadata.get("issue_type", "")),
            status=str(metadata.get("status", "")),
            body=body,
            plan_content=plan_content,
        )


class TaskDetailDialog(ModalScreen):
    """Read-only dialog showing task content and optional plan."""

    BINDINGS = [
        Binding("escape", "dismiss_dialog", "Close", show=False),
        Binding("q", "dismiss_dialog", "Close", show=False),
        Binding("p", "toggle_plan", "Plan/Task", show=True),
    ]

    DEFAULT_CSS = """
    TaskDetailDialog { align: center middle; }
    #task-detail-dialog {
        width: 90%;
        height: 85%;
        background: $surface;
        border: thick $accent;
        padding: 1 2;
    }
    #task-detail-header { text-style: bold; margin: 0 0 1 0; }
    #task-detail-meta { margin: 0 0 1 0; color: $text-muted; }
    #task-detail-scroll { height: 1fr; }
    #task-detail-footer { dock: bottom; height: 1; color: $text-muted; }
    """

    def __init__(self, info: TaskInfo) -> None:
        super().__init__()
        self._info = info
        self._showing_plan = False

    def compose(self) -> ComposeResult:
        info = self._info
        with Container(id="task-detail-dialog"):
            yield Static(
                f"[bold]t{info.task_id}: {info.title}[/]",
                id="task-detail-header",
            )
            yield Static(
                f"Priority: {info.priority}  Effort: {info.effort}  "
                f"Type: {info.issue_type}  Status: {info.status}",
                id="task-detail-meta",
            )
            yield VerticalScroll(
                Markdown(info.body or "*No content*"),
                id="task-detail-scroll",
            )
            plan_hint = "  [dim]p: switch plan/task[/]" if info.plan_content else ""
            yield Static(
                f"[dim]q/Esc: close[/]{plan_hint}",
                id="task-detail-footer",
            )

    def action_dismiss_dialog(self) -> None:
        self.dismiss()

    def action_toggle_plan(self) -> None:
        if not self._info.plan_content:
            self.app.notify("No plan file found", severity="warning")
            return
        self._showing_plan = not self._showing_plan
        content = self._info.plan_content if self._showing_plan else self._info.body
        label = "Plan" if self._showing_plan else "Task"

        scroll = self.query_one("#task-detail-scroll", VerticalScroll)
        for child in list(scroll.children):
            child.remove()
        scroll.mount(Markdown(content or "*No content*"))

        header = self.query_one("#task-detail-header", Static)
        header.update(f"[bold]t{self._info.task_id}: {self._info.title}[/] [{label}]")


class KillConfirmDialog(ModalScreen):
    """Confirmation dialog before killing a tmux pane."""

    BINDINGS = [
        Binding("escape", "dismiss_dialog", "Close", show=False),
    ]

    DEFAULT_CSS = """
    KillConfirmDialog { align: center middle; }
    #kill-dialog {
        width: 80%;
        height: auto;
        max-height: 85%;
        background: $surface;
        border: thick $error;
        padding: 1 2;
    }
    #kill-header { text-style: bold; color: $error; margin: 0 0 1 0; }
    #kill-details { margin: 0 0 1 0; }
    #kill-preview-label { text-style: bold; color: $text-muted; margin: 1 0 0 0; }
    #kill-preview { max-height: 17; margin: 0 0 1 0; background: #1a1a1a; color: #d4d4d4; padding: 0 1; }
    #kill-buttons { width: 100%; height: auto; layout: horizontal; }
    #kill-buttons Button { margin: 0 1; }
    """

    def __init__(self, snap: PaneSnapshot, task_info: TaskInfo | None) -> None:
        super().__init__()
        self._snap = snap
        self._task_info = task_info

    def compose(self) -> ComposeResult:
        snap = self._snap
        pane = snap.pane

        if snap.is_idle:
            idle_s = int(snap.idle_seconds)
            status = f"[yellow]IDLE ({idle_s}s)[/]"
        else:
            status = "[green]Active[/]"

        with Container(id="kill-dialog"):
            yield Static(
                "[bold red]Kill Agent Confirmation[/]",
                id="kill-header",
            )

            detail_parts = [
                f"Window:   [bold]{pane.window_index}:{pane.window_name}[/] (pane {pane.pane_index})",
            ]
            if self._task_info:
                info = self._task_info
                detail_parts.append(
                    f"Task:     [bold]t{info.task_id}[/]: {info.title}"
                )
                detail_parts.append(
                    f"          Priority: {info.priority}  Status: {info.status}"
                )
            detail_parts.append(f"Status:   {status}")
            detail_parts.append(f"Process:  {pane.current_command} (PID {pane.pane_pid})")

            yield Static("\n".join(detail_parts), id="kill-details")

            lines = snap.content.rstrip().splitlines()
            preview_lines = lines[-15:] if len(lines) > 15 else lines
            if preview_lines:
                preview_content = _ansi_to_rich_text("\n".join(preview_lines))
            else:
                preview_content = "(empty)"

            yield Static("[bold]Window Content Preview:[/]", id="kill-preview-label")
            yield Static(preview_content, id="kill-preview")

            with Container(id="kill-buttons"):
                yield Button("Kill", variant="error", id="btn-kill")
                yield Button("Cancel", variant="default", id="btn-cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-kill":
            self.dismiss(True)
        else:
            self.dismiss(False)

    def action_dismiss_dialog(self) -> None:
        self.dismiss(False)
