"""The task editor: `TaskDetailScreen`, its field widgets and the pickers and
modals only it opens (t1794_7).

Extracted verbatim from ``aitask_board.py`` (parent plan t1794). The board
re-exports every name, so ``ab.TaskDetailScreen`` / ``ab.CycleField`` keep
resolving; inside this module the classes and helpers reach each other through
THIS namespace, so a stub of a name they call (``subprocess``,
``_reload_detail_screen`` …) must target ``board_detail_screen``, not the board.
``CycleField`` (also used by the board's settings dialog) and
``CrossRepoRefPickerScreen`` (also pushed by ``KanbanApp``) live here because
the editor needs them and may not import them back.

Contracts (see ``board/__init__.py`` and the parent plan):

* C1 — imported by bare name; never imports ``aitask_board``. The three board
  helpers the editor calls — task types, the user's email, the tmux session —
  are injected as required keyword-only callables
  (``TaskDetailScreen(…, task_types_provider=, user_email_provider=,
  tmux_session_provider=)``); ``aitask_board.make_task_detail_screen()`` binds
  them. ``section_viewer`` / ``webbrowser`` / ``SkipAction`` stay lazy imports.
* C2 — resolves no task directory: the parent-field check compares against the
  manager's ``tasks_dir``.

The editor's CSS stays in ``KanbanApp.CSS`` (the board is the only App that
pushes it; several rules are shared with board modals). The shortcut scope
``board.detail`` moves with the class, so ``lib/shortcut_scopes.py`` lists this
file as its source.
"""

from __future__ import annotations

import subprocess
from datetime import datetime

from rich.markup import escape
from rich.text import Text
from textual import on, work
from textual.binding import Binding
from textual.containers import Container, Horizontal, VerticalScroll
from textual.message import Message
from textual.screen import ModalScreen
from textual.widgets import Button, Collapsible, Input, Label, Markdown, Static

from agent_launch_utils import launch_or_focus_codebrowser
from followup_kinds import (
    FOLLOWUP_KINDS, label_for, marker_for, normalize_followup_kind,
)
from shortcuts_mixin import ShortcutsMixin
from task_levels import LEVELS_ASCENDING
from topic_semantics import _bare_topic_id

from board_widgets import (
    LoadingOverlay, PickerItem, TaskCard, _followup_glyph_text,
    _followup_marker, _plan_approved_marker, _pr_indicator,
)
from board_task_model import Task
from board_task_manager import TaskManager, _task_git_cmd
from board_workflow_phase import (
    _failed_active_gates, _gate_progress, _pending_procedure_gates,
    _resolve_plan_path_for_task, derive_workflow_phase, phase_chip_text,
)


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
                self.app.open_task_detail(task)
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
                self.app.open_task_detail(task)
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
    app.replace_screen_with_detail(task)


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
                self.app.open_task_detail(task)
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
                self.app.open_task_detail(task, read_only=True)
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


class FollowupKindPickerItem(PickerItem):
    """Focusable row for one follow-up kind -- or for clearing the field.

    ``kind`` is the value that will be persisted: a vocabulary key, or ``""``
    for the clear row. Dismisses the SCREEN, not itself (mirrors
    ``GateChoiceItem``) -- a row that dismissed itself would leave the modal
    standing.

    Deliberately does NOT define ``on_focus`` / ``on_blur``: ``PickerItem``
    owns the focus-visibility contract and Textual dispatches handlers down the
    MRO, so both would fire.
    """

    def __init__(self, kind: str, current: bool):
        super().__init__()
        self.kind = kind
        self.current = current

    def render(self) -> Text:
        out = Text("✓ " if self.current else "  ")
        if not self.kind:
            out.append("(none) — not a follow-up")
            return out
        out.append_text(_followup_glyph_text(marker_for(self.kind)))
        out.append(f" {label_for(self.kind)}  ")
        out.append(self.kind, style="dim")   # raw key, for CLI correlation
        return out

    def on_key(self, event):
        if event.key == "enter":
            self.screen.dismiss(self.kind)
            event.prevent_default()
            event.stop()

    def on_click(self, event):
        self.screen.dismiss(self.kind)


class FollowupKindPickerScreen(ModalScreen):
    """Pick a task's follow-up kind, or clear it (t1468_8).

    Dismisses with the value to persist -- a vocabulary key, or ``""`` to clear
    (key removal; there is no tombstone) -- or ``None`` on cancel. ``""`` and
    ``None`` are therefore NOT interchangeable: the caller must test
    ``is None``, not falsiness, or every cancel would silently clear the field.

    **An unrecognised current value focuses Cancel, not a row.** A hand-edited
    or future-vocabulary kind matches no row, and the clear row would otherwise
    take default focus -- making one reflexive `Enter` delete the very value the
    user opened this dialog to diagnose. The title names the value instead.
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=False),
    ]

    def __init__(self, task_num: str, current_kind: str):
        super().__init__()
        self.task_num = task_num
        self.current_kind = current_kind
        # Present but outside the vocabulary. A direct membership test against
        # the canonical map -- not a second copy of the rule.
        self.unrecognised = bool(current_kind) and current_kind not in FOLLOWUP_KINDS

    def compose(self):
        with Container(id="dep_picker_dialog", classes="picker-dialog"):
            # A `Text`, never a markup string: `current_kind` is hand-editable
            # frontmatter, so `followup_kind: "[bold]x"` would otherwise be
            # markup-parsed by Label (markup=True is the default) -- silently
            # swallowed at best, a markup error at worst.
            title = Text(f"Set follow-up kind for {self.task_num}:")
            if self.unrecognised:
                title.append("  current value ")
                title.append(self.current_kind, style="bold")
                title.append(" is not a recognised kind")
            yield Label(title, id="dep_picker_title")
            # Clear row first: the common correction after the t1468_6
            # heuristic backfill is "this isn't a follow-up at all".
            yield FollowupKindPickerItem("", not self.current_kind)
            for kind in FOLLOWUP_KINDS:          # canonical declaration order
                yield FollowupKindPickerItem(kind, kind == self.current_kind)
            yield Button("Cancel", id="btn_dep_cancel")

    def on_mount(self):
        if self.unrecognised:
            # Safe default: Enter presses Cancel -> dismiss(None) -> no write.
            self.query_one("#btn_dep_cancel", Button).focus()
            return
        items = list(self.query(FollowupKindPickerItem))
        current = [it for it in items if it.current]
        (current[0] if current else items[0]).focus()

    @on(Button.Pressed, "#btn_dep_cancel")
    def cancel_button(self):
        self.dismiss(None)

    def action_cancel(self):
        self.dismiss(None)


class FollowupKindField(Static):
    """Focusable follow-up-provenance field. Enter opens the kind picker.

    Persists by shelling out to
    ``aitask_update.sh --batch <id> --followup-kind <val> --silent`` -- the
    mandated new-field board pattern (see ``AnchorField``), NOT the CycleField
    ``save_with_timestamp`` path. Three consequences, all load-bearing:

    * **Clearing is key removal.** ``--followup-kind ""`` makes the shell's
      emit skip the line; there is no tombstone. ``save_changes`` can only ever
      *assign*, and an assigned ``""`` would round-trip back through
      ``normalize_followup_kind`` as a present-but-unrecognised kind, painting
      the `·` fallback on every task the user had just cleared.
    * **The screen cannot go dirty on open.** This field is deliberately absent
      from ``TaskDetailScreen._original_values`` / ``_current_values``, so
      opening a task that has no ``followup_kind`` cannot light up the Save
      button. A seeded default in that dict -- the shape the other four
      editable fields use -- would do exactly that, because this field is
      legitimately absent on most tasks.
    * **The write is immediate, so it is blocked while the screen is dirty.**
      Success calls ``_reload_detail_screen``, which REPLACES the screen with a
      fresh instance and therefore discards any pending CycleField edit.
      ``blocked`` is pushed in by ``TaskDetailScreen._update_save_button``; when
      set, the hint says so and ``Enter`` notifies the remedy instead of
      opening the picker.

    The ``manual_verification`` cross-field invariant (that kind requires
    ``issue_type: manual_verification``) is enforced by the shell and its
    message surfaced verbatim. It is deliberately NOT re-declared here: a copy
    in the board would be a second authority over a rule the CLI already owns.
    """

    can_focus = True

    def __init__(self, kind, manager: "TaskManager", owner_task: "Task",
                 read_only: bool = False, **kwargs):
        super().__init__(**kwargs)
        # Normalised once: frontmatter is type-honest, so a hand-edited list,
        # int or bool arrives here verbatim. "" means "not a follow-up".
        self.kind = normalize_followup_kind(kind)
        self.manager = manager
        self.owner_task = owner_task
        self.read_only = read_only
        self.blocked = False

    def set_blocked(self, blocked: bool) -> None:
        """Called by the screen when its unsaved-edit state changes."""
        if blocked != self.blocked:
            self.blocked = blocked
            self.refresh()

    def render(self) -> Text:
        out = Text("  ")
        out.append("Follow-up:", style="bold")
        out.append(" ")
        marker = marker_for(self.kind)
        if not marker:
            out.append("(none)", style="dim")
        else:
            out.append_text(_followup_glyph_text(marker))
            out.append(" ")
            # `label_for` answers "" for an unrecognised kind; show the raw
            # value then, so a typo is diagnosable from the screen that can fix
            # it. The glyph is already the `·` fallback -- the same
            # degradation the card shows.
            out.append(label_for(self.kind) or self.kind)
        if self.read_only:
            return out
        if self.blocked:
            out.append("  (save or revert pending edits first)", style="dim")
        else:
            out.append("  (enter to change)" if marker else "  (enter to set)",
                       style="dim")
        return out

    def on_key(self, event):
        if event.key != "enter" or self.read_only:
            return
        event.prevent_default()
        event.stop()
        if self.blocked:
            self.app.notify(
                "Save or revert your pending changes first — setting a "
                "follow-up kind writes immediately and reloads this screen.",
                severity="warning")
            return
        self._edit()

    def _edit(self):
        task_num, _ = TaskCard._parse_filename(self.owner_task.filename)

        def on_result(new_kind):
            # `is None` is cancel; `""` is an intentional clear. Testing
            # falsiness here would turn every Escape into a clear.
            if new_kind is None or new_kind == self.kind:
                return
            self._apply(task_num.lstrip("t"), new_kind)

        self.app.push_screen(
            FollowupKindPickerScreen(task_num, self.kind), on_result)

    def _apply(self, task_num_bare: str, new_kind: str):
        result = subprocess.run(
            ["./.aitask-scripts/aitask_update.sh", "--batch", task_num_bare,
             "--followup-kind", new_kind, "--silent"],
            capture_output=True, text=True, timeout=15,
        )
        if result.returncode != 0:
            error = (result.stderr.strip() or result.stdout.strip()
                     or "followup_kind update failed")
            self.app.notify(error, severity="error")
            return
        _reload_detail_screen(self.app, self.owner_task, self.manager)

    def on_focus(self):
        self.add_class("ro-focused")

    def on_blur(self):
        self.remove_class("ro-focused")


class FileReferencesField(Static):
    """Focusable, read-only file_references field.

    Enter navigates to the entry in codebrowser (picker if multi).
    No add/remove keybindings — use aitask_update.sh --file-ref /
    --remove-file-ref or the codebrowser create-task flow instead.
    """

    can_focus = True

    def __init__(self, file_refs: list, manager: "TaskManager",
                 owner_task: "Task", *, tmux_session_provider, **kwargs):
        super().__init__(**kwargs)
        self.file_refs = list(file_refs or [])
        self.manager = manager
        self.owner_task = owner_task
        self._tmux_session_provider = tmux_session_provider

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
        session = self._tmux_session_provider()
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
            self.app.open_task_detail(task)

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
            self.app.open_task_detail(task)

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


class DepPickerItem(PickerItem):
    """A selectable dependency item in the picker."""

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
                self.app.replace_screen_with_detail(self.dep_task)
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
        with Container(id="dep_picker_dialog", classes="picker-dialog"):
            yield Label("Select dependency to open:", id="dep_picker_title")
            for dep_num, task, display_name in self.dep_items:
                yield DepPickerItem(dep_num, task, display_name, self.manager, self.owner_task)
            yield Button("Cancel", variant="default", id="btn_dep_cancel")

    @on(Button.Pressed, "#btn_dep_cancel")
    def cancel(self):
        self.dismiss()

    def action_close_picker(self):
        self.dismiss()


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


class ChildPickerItem(PickerItem):
    """A selectable child task item in the picker."""

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
                self.app.replace_screen_with_detail(self.child_task)
            event.prevent_default()
            event.stop()


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
        with Container(id="dep_picker_dialog", classes="picker-dialog"):
            yield Label("Select child task to open:", id="dep_picker_title")
            for child_id, task, display_name in self.child_items:
                yield ChildPickerItem(child_id, task, display_name, self.manager)
            yield Button("Cancel", variant="default", id="btn_dep_cancel")

    @on(Button.Pressed, "#btn_dep_cancel")
    def cancel(self):
        self.dismiss()

    def action_close_picker(self):
        self.dismiss()


class FoldedTaskPickerItem(PickerItem):
    """A selectable folded task item in the picker."""

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
                self.app.replace_screen_with_detail(self.folded_task, read_only=True)
            event.prevent_default()
            event.stop()


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
        with Container(id="dep_picker_dialog", classes="picker-dialog"):
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


class FileReferenceItem(PickerItem):
    """A selectable file-reference entry in the picker."""

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


class FileReferencePickerScreen(ModalScreen):
    """Popup to select which file_references entry to open."""

    BINDINGS = [
        Binding("escape", "close_picker", "Close", show=False),
    ]

    def __init__(self, entries: list):
        super().__init__()
        self.entries = list(entries)

    def compose(self):
        with Container(id="dep_picker_dialog", classes="picker-dialog"):
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

    def __init__(self, task: Task, manager: TaskManager = None, read_only: bool = False,
                 *, task_types_provider, user_email_provider, tmux_session_provider):
        super().__init__()
        # Board helpers, injected (t1794_7, C1): they stay in aitask_board.py,
        # which this module must not import. `make_task_detail_screen()` there
        # binds them.
        self._task_types_provider = task_types_provider
        self._user_email_provider = user_email_provider
        self._tmux_session_provider = tmux_session_provider
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
        return _resolve_plan_path_for_task(self.task_data, self.manager)

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

    def _build_gate_fields(self):
        """``(rows, fraction)`` for the Gates section — the expanded gate
        surface (t1603_4). ``rows`` empty means no section is mounted.

        The compact chip on an In-Flight card and this list must never describe
        the same ledger differently, so **nothing here is derived locally**: the
        fraction comes from `derive_workflow_phase`, the degraded and error
        strings from `phase_chip_text`, the failed set from
        `_failed_active_gates` and the attended-agent set from
        `_pending_procedure_gates`. Satisfied-vs-pending is decided by
        membership in ``archive_pending`` — the list the archival guard reads —
        and a gate's raw ``current`` run only chooses the glyph *within* each
        side. A count computed here instead would be a second implementation of
        `_gate_progress`, which is what its docstring exists to forbid.
        """
        if self.manager is None:
            return [], None
        result = self.manager.gate_state_for(self.task_data)
        state = result.state

        # An unreadable ledger is ONE row and nothing else — no phase row
        # beside it. This must run BEFORE the phase row: `derive_workflow_phase`
        # branch B0 returns `error` provenance for an `Implementing` task, and
        # `phase_chip_text` renders that as this very string, so ordering the
        # phase row first would print it twice.
        if result.error:
            return [ReadOnlyField(
                escape(phase_chip_text("implementing", "error", None,
                                       error=result.error)),
                classes="meta-ro")], None

        has_gates = bool(state and (state.active_gates or state.filtered_gates))
        if not (has_gates or result.has_ledger):
            return [], None

        registry = self.manager.gate_registry()
        phase = derive_workflow_phase(
            self.task_data, result, registry,
            # Already resolved in __init__ — no new disk access, and the
            # laziness t1656 introduced is preserved.
            plan_exists_probe=lambda: self._plan_path is not None)

        # A fraction is a progress claim, so it requires a ledger. Deferring to
        # `phase.progress` inherits that rule from `derive_workflow_phase` for
        # free: it is None on the no-ledger branch and on the marker branch, and
        # the card prints no fraction in either. Recomputing here would print
        # `0/N` beside "No gate ledger", the fabricated fraction `WorkflowPhase`
        # documents as never a stand-in for `None`.
        if phase is not None:
            fraction = phase.progress
        elif result.has_ledger and state is not None:
            fraction = _gate_progress(state)[0]
        else:
            fraction = None

        out = []
        if phase is not None:
            out.append(ReadOnlyField(
                escape(phase_chip_text(phase.phase, phase.provenance,
                                       phase.progress)),
                classes="meta-ro"))
        if state is None:
            return out, fraction

        pending = set(state.archive_pending)
        failed = set(_failed_active_gates(state))
        procedure = set(_pending_procedure_gates(state, registry))
        for gate in state.active_gates:
            run = state.current.get(gate)   # may be None: a declared gate that
            status = run.status if run else None   # never ran has no entry
            name = escape(gate)
            if gate in pending:
                if gate in state.stale_signed:
                    # BOTH facts, never one without the other: the ledger really
                    # does say `pass`, and the signature no longer binds the
                    # code (gate_ledger.py:167-174).
                    row = f"⚠ {name} — pass, signature stale; needs re-sign"
                elif gate in failed:
                    row = f"✗ {name} — failed"
                elif gate in procedure:
                    row = f"◈ {name} — pending; needs attended agent"
                else:
                    # The ordinary state of a freshly claimed task, not a
                    # fallback: every declared gate lands here until it runs.
                    row = f"· {name} — pending"
            elif status == "skip":
                # Terminal-satisfied, but distinct from pass, as in the ledger.
                row = f"⊘ {name} — skipped (not applicable)"
            else:
                row = f"✓ {name} — passed"
            out.append(ReadOnlyField(row, classes="meta-ro"))

        if state.filtered_gates:
            out.append(ReadOnlyField(
                "[dim]filtered by profile (audit only)[/dim]", classes="meta-ro"))
            for gate in state.filtered_gates:
                out.append(ReadOnlyField(
                    f"[dim]· {escape(gate)}[/dim]", classes="meta-ro"))
        return out, fraction

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
        if self.manager and self.task_data.filepath.parent != self.manager.tasks_dir:
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
        # Deferred-plan marker (t1603_1). Read-only by design: the field is
        # written and cleared exclusively by the task-workflow, so the board
        # offers no affordance to edit it. Absent marker => no row at all, and
        # the collapsible's `(<n>)` count adjusts for free. `escape` because
        # ReadOnlyField parses Rich markup: a hand-edited value containing `[`
        # would otherwise be swallowed. Wording matches `ait ls`, which renders
        # `Plan: approved <ts>` (aitask_ls.sh:853).
        plan_marker = _plan_approved_marker(meta)
        if plan_marker:
            out.append(ReadOnlyField(
                f"[b]Plan approved:[/b] {escape(plan_marker)}", classes="meta-ro"))
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
                tmux_session_provider=self._tmux_session_provider,
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
                    yield CycleField("Type", self._task_types_provider(),
                                     meta.get("issue_type", "feature"), "issue_type",
                                     id="cf_issue_type")
                # Follow-up provenance (t1468_8) -- the 5th row of the primary
                # block in BOTH modes, so a card's glyph is decodable the
                # moment the task is opened. Editable only on a live screen
                # with a manager (the post-write reload needs one); a
                # read-only screen shows the row ONLY when a kind is actually
                # set, since it offers no way to set one. Mirrors AnchorField.
                #
                # One widget class in both modes rather than a ReadOnlyField
                # for the read-only case: one render implementation, so the
                # read-only line cannot drift from the editable one.
                fk_read_only = is_done_or_ro or self.manager is None
                if not fk_read_only or _followup_marker(meta):
                    yield FollowupKindField(
                        meta.get("followup_kind"), self.manager,
                        self.task_data, read_only=fk_read_only,
                        id="ff_followup_kind", classes="meta-ro")

            # --- Grouped, collapsible secondary metadata ---
            # Risk (read-only) — only present when explicitly set in metadata.
            risk = self._build_risk_fields(meta)
            if risk:
                with Collapsible(title=f"Risk ({len(risk)})",
                                 collapsed=True, id="sec_risk", classes="meta-section"):
                    yield from risk

            # Gates (read-only) — the expanded counterpart to the In-Flight
            # card's compact chip. The title's fraction is the chip's fraction,
            # not a row count: filtered gates are listed but never counted, and
            # a task with no ledger gets no fraction at all rather than `0/N`.
            gates, gate_fraction = self._build_gate_fields()
            if gates:
                gate_title = ("Gates" if gate_fraction is None
                              else f"Gates ({gate_fraction[0]}/{gate_fraction[1]})")
                with Collapsible(title=gate_title,
                                 collapsed=True, id="sec_gates", classes="meta-section"):
                    yield from gates

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

    def has_unsaved_edits(self) -> bool:
        """True when a CycleField edit is pending an explicit Save.

        Named and field-agnostic on purpose: any field that persists
        IMMEDIATELY must consult it, because its post-write
        ``_reload_detail_screen`` REPLACES this screen with a fresh instance
        that re-seeds ``_original_values`` from disk -- silently dropping the
        pending values. ``AnchorField`` has the same exposure and should adopt
        this (tracked as an upstream defect; not fixed by t1468_8).
        """
        return self._current_values != self._original_values

    def _update_save_button(self):
        is_dirty = self.has_unsaved_edits()
        btn_save = self.query_one("#btn_save", Button)
        btn_save.disabled = not is_dirty
        # Immediate-write fields must not fire while a deferred edit is
        # pending. `query`, not `query_one`: the field is absent on a read-only
        # screen whose task carries no followup_kind.
        for field in self.query(FollowupKindField):
            field.set_blocked(is_dirty)

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
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as e:
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
        default_email = self._user_email_provider()

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
            try:
                result = subprocess.run(
                    ["./.aitask-scripts/aitask_lock.sh", "--lock", task_id, "--email", email],
                    capture_output=True, text=True, timeout=15
                )
            finally:
                # Dismiss LoadingOverlay. Scoped to the subprocess call, not the
                # whole body: pop_screen removes the TOP screen, so it must run
                # before any later push (see _do_unlock's ResetTaskConfirmScreen).
                # `finally` — not the `except` below — is what keeps the overlay
                # off-screen for an exception type this handler does not name.
                self.app.call_from_thread(self.app.pop_screen)
            if result.returncode == 0:
                self.app.call_from_thread(self.app.notify, f"Locked t{task_id}", severity="information")
                self.app.call_from_thread(self.dismiss, "locked")
            else:
                error = result.stderr.strip() or result.stdout.strip()
                self.app.call_from_thread(self.app.notify, f"Lock failed: {error}", severity="error")
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as e:
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
            my_email = self._user_email_provider()
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
            try:
                result = subprocess.run(
                    ["./.aitask-scripts/aitask_lock.sh", "--unlock", task_id],
                    capture_output=True, text=True, timeout=15
                )
            finally:
                # Dismiss LoadingOverlay before the ResetTaskConfirmScreen push
                # below — pop_screen removes the TOP screen, so a body-wide
                # `finally` here would pop the confirm dialog instead. See
                # _do_lock for the full rationale.
                self.app.call_from_thread(self.app.pop_screen)
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
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as e:
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
