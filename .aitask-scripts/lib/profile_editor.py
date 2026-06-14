"""profile_editor - Reusable execution-profile field editor.

Shared primitives used by both the Settings TUI Profiles tab and the
per-run profile editor in `AgentCommandScreen` (see t777_17).

Public API:
    - PROFILE_SCHEMA, PROFILE_FIELD_INFO, PROFILE_FIELD_GROUPS, _UNSET
    - CycleField, ConfigRow, EditStringScreen
    - compose_profile_fields(profile_data, *, id_prefix, expanded_field=None)
    - collect_profile_values(query_one, base_data, *, id_prefix)
    - ProfileEditScreen(ModalScreen)

Widget IDs follow the exact existing scheme used by `settings_app.py` so the
profile-string Enter handler and value collection stay compatible:
    bool/enum -> "profile_{key}__{id_prefix}"
    string    -> "profile_str_{key}__{id_prefix}"
    int       -> "profile_int_{key}__{id_prefix}"
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Callable, Iterator

# Add lib dir to path so the module is importable as `profile_editor` from
# any caller that has not already inserted .aitask-scripts/lib (mirrors the
# pattern in agent_command_screen.py).
_LIB_DIR = str(Path(__file__).resolve().parent)
if _LIB_DIR not in sys.path:
    sys.path.insert(0, _LIB_DIR)

from textual import on  # noqa: E402
from textual.app import ComposeResult  # noqa: E402
from textual.binding import Binding  # noqa: E402
from textual.containers import Container, Horizontal, VerticalScroll  # noqa: E402
from textual.message import Message  # noqa: E402
from textual.screen import ModalScreen  # noqa: E402
from textual.widgets import Button, Input, Label, Static  # noqa: E402


# ---------------------------------------------------------------------------
# Profile schema and metadata
# ---------------------------------------------------------------------------
# Profile schema: key -> (type, options)
# type: "bool", "enum", "string", "int"
PROFILE_SCHEMA: dict[str, tuple[str, list[str] | None]] = {
    "name": ("string", None),
    "description": ("string", None),
    "skip_task_confirmation": ("bool", None),
    "default_email": ("enum", ["userconfig", "first"]),
    "create_worktree": ("bool", None),
    "base_branch": ("string", None),
    "plan_preference": ("enum", ["use_current", "verify", "create_new"]),
    "plan_preference_child": ("enum", ["use_current", "verify", "create_new"]),
    "plan_verification_required": ("int", None),
    "plan_verification_stale_after_hours": ("int", None),
    "post_plan_action": ("enum", ["start_implementation", "ask"]),
    "post_plan_action_for_child": ("enum", ["start_implementation", "ask"]),
    "risk_evaluation": ("bool", None),
    "record_gates": ("bool", None),
    "enableFeedbackQuestions": ("bool", None),
    "manual_verification_followup_mode": ("enum", ["ask", "never"]),
    "manual_verification_mode": (
        "enum",
        ["ask", "manual", "autonomous", "autonomous_with_plan"],
    ),
    "explore_auto_continue": ("bool", None),
    "review_default_modes": ("string", None),
    "review_auto_continue": ("bool", None),
    "force_unlock_stale": ("bool", None),
    "done_task_action": ("enum", ["archive", "skip"]),
    "orphan_parent_action": ("enum", ["archive", "skip"]),
    "complexity_action": ("enum", ["single_task", "create_children"]),
    "review_action": ("enum", ["commit", "need_changes", "abort"]),
    "issue_action": ("enum", ["close_with_notes", "comment_only", "close_silently", "skip"]),
    "abort_plan_action": ("enum", ["keep", "discard"]),
    "abort_revert_status": ("enum", ["Ready", "Editing"]),
    "qa_mode": ("enum", ["ask", "create_task", "implement", "plan_only"]),
    "qa_run_tests": ("bool", None),
    "qa_tier": ("enum", ["q", "s", "e"]),
}

_UNSET = "(unset)"


class _NoArrowsVerticalScroll(VerticalScroll):
    """VerticalScroll with the left/right scroll bindings removed.

    Default VerticalScroll binds left/right to scroll_left/scroll_right and
    propagates them via ancestor binding-bubble even when CycleField's
    on_key fires first. Stripping the conflicting bindings lets CycleField
    cleanly own arrow keys for option cycling.
    """

    BINDINGS = [
        b for b in VerticalScroll.BINDINGS
        if b.key not in ("left", "right")
    ]

# Profile field info: key -> (short_description, detailed_description)
PROFILE_FIELD_INFO: dict[str, tuple[str, str]] = {
    "name": (
        "Display name shown when selecting a profile",
        "The profile name appears in the selection prompt when picking a task. "
        "Choose a short, descriptive name (e.g., 'fast', 'worktree', 'remote')."
    ),
    "description": (
        "Description shown below profile name during selection",
        "A brief sentence explaining the profile's purpose. Shown alongside the name "
        "in the profile selection prompt at the start of aitask-pick/aitask-explore."
    ),
    "skip_task_confirmation": (
        "Auto-confirm task selection without asking",
        "When true, skips the 'Is this the correct task?' confirmation in aitask-pick (Step 0b). "
        "The task summary is still displayed but the workflow proceeds immediately. "
        "When false or unset, the user must confirm before proceeding."
    ),
    "default_email": (
        "Email for task assignment: userconfig, first, or literal",
        "Controls how the email is resolved when claiming a task (Step 4):\n"
        "  'userconfig': from aitasks/metadata/userconfig.yaml (falls back to first in emails.txt)\n"
        "  'first': first email from aitasks/metadata/emails.txt\n"
        "  A literal email address: uses that exact email\n"
        "  (unset): prompts the user to select or enter an email"
    ),
    "create_worktree": (
        "Create a separate git worktree for the task",
        "When true, creates a new branch and worktree in aiwork/<task_name>/ (Step 5). "
        "When false, works directly on the current branch. "
        "Worktrees are useful for parallel work on multiple tasks."
    ),
    "base_branch": (
        "Branch to base new task branches on (e.g., main)",
        "Only used when create_worktree is true. Specifies the branch the new task branch "
        "is created from. Common values: 'main', 'develop'. "
        "When unset, the user is asked to choose."
    ),
    "plan_preference": (
        "Existing plan handling: use_current / verify / create_new",
        "Controls what happens when a plan file already exists (Step 6.0):\n"
        "  'use_current': skip planning, use existing plan as-is\n"
        "  'verify': enter plan mode to check if the plan is still valid\n"
        "  'create_new': discard existing plan and start fresh\n"
        "  (unset): ask the user interactively"
    ),
    "plan_preference_child": (
        "Override plan_preference for child tasks only",
        "Same values as plan_preference but only applies to child tasks. "
        "Takes priority over plan_preference when the current task is a child. "
        "Useful for e.g. always verifying child plans while reusing parent plans."
    ),
    "plan_verification_required": (
        "Fresh verifications needed to skip re-verification",
        "Number of fresh (non-stale) plan_verified entries that must exist in a "
        "plan file for the verify path to SKIP re-verification. Only consulted "
        "when plan_preference (or plan_preference_child) is 'verify'. Default: 1."
    ),
    "plan_verification_stale_after_hours": (
        "Hours before a verification is considered stale",
        "Age (in hours) after which a plan_verified entry is considered stale "
        "and no longer counts toward the required fresh count. Default: 24."
    ),
    "post_plan_action": (
        "After plan approval: start_implementation = skip checkpoint",
        "Controls what happens after the plan is approved (Step 6 checkpoint):\n"
        "  'start_implementation': proceed directly to implementation\n"
        "  'ask': always show the post-plan checkpoint (same as unset)\n"
        "  (unset): ask the user whether to start, revise, or abort\n"
        "Note: plan approval via ExitPlanMode is always required and cannot be skipped."
    ),
    "post_plan_action_for_child": (
        "Override post_plan_action for child tasks only",
        "Same values as post_plan_action ('start_implementation' or 'ask'), "
        "but only applies when the current task is a child. Takes priority over "
        "post_plan_action in that case. Omit to fall back to post_plan_action."
    ),
    "risk_evaluation": (
        "Enable risk evaluation during planning",
        "When true, the planning workflow assesses the task's code-health and "
        "goal-achievement risk at the end of planning and records it, then offers "
        "to spawn risk-mitigation follow-up tasks. Gates both the risk-evaluation "
        "step and the mitigation follow-up offer.\n"
        "  true    — run risk evaluation and offer mitigation follow-ups\n"
        "  false   — disabled\n"
        "  (unset) — disabled (opt-in feature)"
    ),
    "record_gates": (
        "Record approval checkpoints as gate runs",
        "When true, task-workflow records its approval checkpoints (plan, "
        "review, and merge approval — plus build and risk evaluation when they "
        "run) as gate-run entries in the task's '## Gate Runs' ledger, committed "
        "so the gate state is visible from every PC. The interactive prompts are "
        "unchanged; this only witnesses their outcome, enabling later resume.\n"
        "  true    — record checkpoints into the gate ledger\n"
        "  false   — disabled\n"
        "  (unset) — disabled (opt-in feature)"
    ),
    "enableFeedbackQuestions": (
        "Ask satisfaction feedback questions at the end of supported skills",
        "Controls whether supported skills ask for a quick satisfaction rating after completion. "
        "When false, the Satisfaction Feedback Procedure is skipped. "
        "When true or unset, feedback questions remain enabled. "
        "Use false for unattended or non-interactive workflows such as remote profiles."
    ),
    "manual_verification_followup_mode": (
        "Post-commit manual-verification follow-up prompt: ask or never",
        "Controls task-workflow Step 8c — whether to offer a manual-verification "
        "follow-up task after committing implementation changes:\n"
        "  'ask': prompt after commit to queue a manual-verification follow-up\n"
        "  'never': skip the prompt entirely\n"
        "  (unset): same as 'ask'\n"
        "Set to 'never' for non-interactive or remote profiles."
    ),
    "manual_verification_mode": (
        "Manual verification mode: how (or whether) to auto-run the checklist",
        "Controls Manual Verification Step 1.5 — the up-front offer to "
        "auto-run the verification checklist before the interactive "
        "Pass/Fail/Skip/Defer loop. The per-item `auto` action inside the "
        "interactive loop is always available, regardless of this setting.\n"
        "  ask                  — show the offer prompt (default)\n"
        "  manual               — skip the offer; go straight to interactive\n"
        "  autonomous           — auto-verify each item as the agent reaches it\n"
        "                         (no upfront plan-design step)\n"
        "  autonomous_with_plan — design the per-item plan up front, then enter\n"
        "                         plan mode for your approval before running\n"
        "  (unset) — same as `ask`"
    ),
    "explore_auto_continue": (
        "Auto-continue to implementation in exploration mode",
        "Used by aitask-explore. When true, automatically continues to the implementation "
        "phase after exploration completes. When false or unset, asks the user."
    ),
    "review_default_modes": (
        "Comma-separated review-guide names to auto-select",
        "Used by aitask-review. When set, auto-selects these review guides instead "
        "of prompting. Values are the 'name' field from each review guide's frontmatter, "
        "comma-separated (e.g., 'code_conventions,security'). Leave unset to be prompted."
    ),
    "review_auto_continue": (
        "Auto-continue to implementation in review mode",
        "Used by aitask-review. When true, automatically continues to the implementation "
        "phase after review completes. When false or unset, asks the user. Default: false."
    ),
    "force_unlock_stale": (
        "Auto force-unlock stale task locks without asking",
        "When true, automatically overrides stale locks held by other users/machines (Step 4). "
        "When false or unset, prompts the user to decide how to handle locked tasks."
    ),
    "done_task_action": (
        "(Remote) Done-but-unarchived tasks: archive or skip",
        "Only used by aitask-pickrem (remote/autonomous mode). Controls what happens "
        "when a picked task already has status 'Done' but hasn't been archived:\n"
        "  'archive': proceed to archive automatically\n"
        "  'skip': leave the task as-is and end the workflow"
    ),
    "orphan_parent_action": (
        "(Remote) Orphaned parent tasks: archive or skip",
        "Only used by aitask-pickrem. Controls what happens when a parent task has "
        "all children completed but the parent itself isn't archived:\n"
        "  'archive': archive the parent automatically\n"
        "  'skip': leave the parent as-is"
    ),
    "complexity_action": (
        "(Remote) Complex tasks: single_task or create_children",
        "Only used by aitask-pickrem. When a task is assessed as complex:\n"
        "  'single_task': implement as a single task regardless of complexity\n"
        "  'create_children': break into child subtasks automatically"
    ),
    "review_action": (
        "(Remote) Review decision: commit, need_changes, or abort",
        "Only used by aitask-pickrem. After implementation completes:\n"
        "  'commit': auto-commit changes without review\n"
        "  'need_changes': flag for additional changes (unusual for autonomous mode)\n"
        "  'abort': discard changes and revert task status"
    ),
    "issue_action": (
        "(Remote) Linked issue handling after archival",
        "Only used by aitask-pickrem. When the task has a linked issue:\n"
        "  'close_with_notes': post implementation notes and close the issue\n"
        "  'comment_only': post notes but leave the issue open\n"
        "  'close_silently': close without posting a comment\n"
        "  'skip': don't touch the linked issue"
    ),
    "abort_plan_action": (
        "(Remote) On abort: keep or discard plan file",
        "Only used by aitask-pickrem. When a task is aborted:\n"
        "  'keep': preserve the plan file for future reference\n"
        "  'discard': delete the plan file"
    ),
    "abort_revert_status": (
        "(Remote) Status to revert to on abort: Ready or Editing",
        "Only used by aitask-pickrem. When a task is aborted, the task status "
        "is reverted to this value:\n"
        "  'Ready': task goes back to the Ready queue\n"
        "  'Editing': task stays in Editing state"
    ),
    "qa_mode": (
        "Action after QA test plan proposal",
        "Controls what happens after /aitask-qa generates a test plan.\n"
        "  ask         — Prompt with AskUserQuestion (default)\n"
        "  create_task — Auto-create a follow-up test task\n"
        "  implement   — Implement proposed tests in current session\n"
        "  plan_only   — Export test plan to file without further action\n\n"
        "Omitting this key shows the interactive prompt.",
    ),
    "qa_run_tests": (
        "Run discovered tests during QA analysis",
        "When true (default), /aitask-qa executes discovered tests and lints.\n"
        "Set to false to skip test execution and only analyze coverage gaps.\n\n"
        "Useful when tests are slow or require special setup.",
    ),
    "qa_tier": (
        "QA analysis depth: q (quick), s (standard), e (exhaustive)",
        "Used by /aitask-qa Step 1c. When set, skips the tier selection prompt.\n"
        "  'q': Quick — existing tests + lint only\n"
        "  's': Standard — full analysis with test plan\n"
        "  'e': Exhaustive — full analysis + edge cases + verification gate\n"
        "  (unset): prompts the user"
    ),
}

# Logical grouping of profile fields for display
PROFILE_FIELD_GROUPS: list[tuple[str, list[str]]] = [
    ("Identity", ["name", "description"]),
    ("Task Selection", ["skip_task_confirmation", "default_email"]),
    ("Branch & Worktree", ["create_worktree", "base_branch"]),
    ("Planning", [
        "plan_preference",
        "plan_preference_child",
        "plan_verification_required",
        "plan_verification_stale_after_hours",
        "post_plan_action",
        "post_plan_action_for_child",
        "risk_evaluation",
    ]),
    ("Gates", ["record_gates"]),
    ("Feedback", ["enableFeedbackQuestions"]),
    ("Manual Verification", [
        "manual_verification_followup_mode",
        "manual_verification_mode",
    ]),
    ("QA Analysis", ["qa_mode", "qa_run_tests", "qa_tier"]),
    ("Exploration", ["explore_auto_continue"]),
    ("Review", ["review_default_modes", "review_auto_continue"]),
    ("Lock Management", ["force_unlock_stale"]),
    ("Remote Workflow", [
        "done_task_action", "orphan_parent_action", "complexity_action",
        "review_action", "issue_action", "abort_plan_action", "abort_revert_status",
    ]),
]


# ---------------------------------------------------------------------------
# Widgets
# ---------------------------------------------------------------------------
class CycleField(Static):
    """Focusable widget that cycles through options with Left/Right keys."""

    can_focus = True

    class Changed(Message):
        def __init__(self, field: "CycleField", value: str):
            super().__init__()
            self.field = field
            self.value = value

    def __init__(self, label: str, options: list, current: str, field_key: str,
                 id: str | None = None):
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
        return f"  {self.label}:  [dim]◀[/] {options_str} [dim]▶[/]"

    def cycle_prev(self):
        self.current_index = (self.current_index - 1) % len(self.options)
        self.refresh()
        self.post_message(self.Changed(self, self.current_value))

    def cycle_next(self):
        self.current_index = (self.current_index + 1) % len(self.options)
        self.refresh()
        self.post_message(self.Changed(self, self.current_value))

    def _option_index_at(self, cx: int) -> int | None:
        """Map content x-coordinate to option index, -1 for ◀, -2 for ▶."""
        prefix_len = len(f"  {self.label}:  ◀ ")
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

    def on_click(self, event) -> None:
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


class ConfigRow(Static):
    """Focusable config key-value display with layer badge."""

    can_focus = True

    def __init__(self, key: str, value: str, config_layer: str = "project",
                 row_key: str = "", id: str | None = None,
                 subordinate: bool = False, raw_value: str | None = None,
                 extra_indent: int = 0):
        super().__init__(id=id)
        self.key = key
        self.value = value
        self.raw_value = raw_value if raw_value is not None else value
        self.config_layer = config_layer
        self.row_key = row_key or key
        self.subordinate = subordinate
        self.extra_indent = extra_indent

    def render(self) -> str:
        if self.config_layer == "user":
            badge = "[#FFB86C][USER][/]"
        else:
            badge = "[#50FA7B][PROJECT][/]"

        pad = " " * self.extra_indent

        if self.subordinate:
            # Indented subordinate row (user override under project)
            has_override = self.value not in ("(inherits project)", "(not set)", "")
            clear_hint = "  [dim](d to remove)[/dim]" if has_override else ""
            return f"      {pad}└ {badge}  {self.value}{clear_hint}"

        return f"  {pad}{badge}  [bold]{self.key}:[/bold]  {self.value}"

    def on_focus(self):
        self.add_class("row-focused")

    def on_blur(self):
        self.remove_class("row-focused")


# ---------------------------------------------------------------------------
# Modal: edit a single string value
# ---------------------------------------------------------------------------
class EditStringScreen(ModalScreen):
    """Modal for editing a single string value (profile fields)."""

    BINDINGS = [Binding("escape", "cancel", "Cancel", show=False)]

    def __init__(self, key: str, current_value: str):
        super().__init__()
        self.key = key
        self.current_value = current_value

    def compose(self) -> ComposeResult:
        with Container(id="edit_dialog"):
            yield Label(f"Edit: [bold]{self.key}[/bold]", id="edit_title")
            yield Input(value=self.current_value, id="edit_input")
            with Horizontal(id="edit_buttons"):
                yield Button("Save", variant="success", id="btn_edit_save")
                yield Button("Cancel", variant="default", id="btn_edit_cancel")

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self.do_save()

    @on(Button.Pressed, "#btn_edit_save")
    def do_save(self):
        value = self.query_one("#edit_input", Input).value
        self.dismiss({"key": self.key, "value": value})

    @on(Button.Pressed, "#btn_edit_cancel")
    def do_cancel(self):
        self.dismiss(None)

    def action_cancel(self):
        self.dismiss(None)


# ---------------------------------------------------------------------------
# Shared field renderer + value collector
# ---------------------------------------------------------------------------
def compose_profile_fields(
    profile_data: dict,
    *,
    id_prefix: str,
    expanded_field: str | None = None,
) -> Iterator:
    """Yield grouped field widgets + description labels for a profile.

    Caller is expected to mount the yielded widgets (or use this with `yield
    from` inside a Textual `compose()`). Widget IDs use the exact scheme
    parsed by the profile-string Enter handler and `collect_profile_values()`:

        bool/enum -> CycleField id "profile_{key}__{id_prefix}"
        string    -> ConfigRow  id "profile_str_{key}__{id_prefix}"
        int       -> ConfigRow  id "profile_int_{key}__{id_prefix}"
    """
    for group_label, field_keys in PROFILE_FIELD_GROUPS:
        yield Label(f"  {group_label}", classes="section-header")
        for key in field_keys:
            if key not in PROFILE_SCHEMA:
                continue
            ktype, options = PROFILE_SCHEMA[key]
            current_raw = profile_data.get(key)
            widget_id = f"profile_{key}__{id_prefix}"

            if ktype == "bool":
                if current_raw is True:
                    current = "true"
                elif current_raw is False:
                    current = "false"
                else:
                    current = _UNSET
                yield CycleField(
                    key, ["true", "false", _UNSET], current,
                    key, id=widget_id,
                )
            elif ktype == "enum":
                opts = list(options or []) + [_UNSET]
                current = str(current_raw) if current_raw is not None else _UNSET
                if current not in opts:
                    opts.insert(0, current)
                yield CycleField(
                    key, opts, current, key, id=widget_id,
                )
            elif ktype == "string":
                current = str(current_raw) if current_raw is not None else ""
                yield ConfigRow(
                    key, current, config_layer="project", row_key=key,
                    id=f"profile_str_{key}__{id_prefix}",
                )
            elif ktype == "int":
                if isinstance(current_raw, bool):
                    current = ""
                elif isinstance(current_raw, (int, float)):
                    current = str(int(current_raw))
                elif current_raw is None:
                    current = ""
                else:
                    current = str(current_raw)
                yield ConfigRow(
                    key, current, config_layer="project", row_key=key,
                    id=f"profile_int_{key}__{id_prefix}",
                )

            info = PROFILE_FIELD_INFO.get(key)
            if info:
                if expanded_field == key:
                    yield Label(
                        f"      [dim]{info[1]}[/dim]",
                        classes="section-hint",
                    )
                else:
                    yield Label(
                        f"      [dim]{info[0]}[/dim]",
                        classes="section-hint",
                    )


def collect_profile_values(
    query_one: Callable,
    base_data: dict,
    *,
    id_prefix: str,
) -> tuple[dict, list[str]]:
    """Read field widget values back into a profile dict.

    Returns (updated_data, errors). Errors are human-readable strings for
    invalid int inputs; the caller is responsible for surfacing them (e.g.
    via `self.notify(..., severity="error")`).
    """
    data = dict(base_data)
    errors: list[str] = []

    for key, (ktype, options) in PROFILE_SCHEMA.items():
        widget_id = f"profile_{key}__{id_prefix}"
        str_widget_id = f"profile_str_{key}__{id_prefix}"
        int_widget_id = f"profile_int_{key}__{id_prefix}"

        if ktype in ("bool", "enum"):
            try:
                field = query_one(f"#{widget_id}", CycleField)
                val = field.current_value
                if val == _UNSET:
                    data.pop(key, None)
                elif ktype == "bool":
                    data[key] = val == "true"
                else:
                    data[key] = val
            except Exception:
                pass
        elif ktype == "string":
            try:
                row = query_one(f"#{str_widget_id}", ConfigRow)
                val = row.value
                if val:
                    data[key] = val
                else:
                    data.pop(key, None)
            except Exception:
                pass
        elif ktype == "int":
            try:
                row = query_one(f"#{int_widget_id}", ConfigRow)
                val = (row.value or "").strip()
                if not val:
                    data.pop(key, None)
                else:
                    try:
                        iv = int(val)
                        if iv < 0:
                            errors.append(
                                f"{key}: must be >= 0, got '{val}' — not saved"
                            )
                        else:
                            data[key] = iv
                    except ValueError:
                        errors.append(
                            f"{key}: '{val}' is not an integer — not saved"
                        )
            except Exception:
                pass

    return data, errors


# ---------------------------------------------------------------------------
# Modal: edit a profile per skill run (consumer: AgentCommandScreen, t777_17)
# ---------------------------------------------------------------------------
class ProfileEditScreen(ModalScreen):
    """Modal for editing an execution profile's fields.

    Usage (single-callback / legacy):
        def on_save(updated: dict) -> None:
            ...  # persist `updated` somewhere

        screen = ProfileEditScreen(profile_data, on_save, title="Edit fast")
        app.push_screen(screen)

    Usage (dual-save, e.g. AgentCommandScreen per-run editor):
        screen = ProfileEditScreen(
            profile_data,
            on_save_persistent=save_persistent,
            on_save_one_shot=save_one_shot,
        )

    When both `on_save_persistent` and `on_save_one_shot` are wired, two
    Save buttons are rendered and the dismiss payload becomes
    `(mode, updated)` where `mode` is `"persistent"` or `"one_shot"`. The
    single-callback shape (passing only `on_save=`) keeps the legacy
    dismiss payload (`updated` dict).
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=False),
        Binding("s", "save_persistent", "Save", show=False),
        Binding("S", "save_persistent", "Save", show=False),
        Binding("o", "save_one_shot", "Save as one-shot", show=False),
        Binding("O", "save_one_shot", "Save as one-shot", show=False),
    ]

    # Self-contained CSS so the modal looks/behaves the same regardless of
    # which App pushes it. SettingsApp has equivalent CSS at App level for
    # its inline Profiles tab; both must stay consistent because the same
    # CycleField/ConfigRow widgets back both surfaces.
    DEFAULT_CSS = """
    #profile_edit_dialog {
        width: 80%;
        height: 90%;
        background: $surface;
        border: thick $accent;
        padding: 1 2;
    }
    #profile_edit_title {
        text-align: center;
        height: 1;
        padding: 0 0 0 0;
    }
    #profile_edit_help {
        height: 1;
        padding: 0 0 1 0;
        color: $text-muted;
        text-align: center;
    }
    #profile_edit_scroll {
        height: 1fr;
        margin: 0 0 1 0;
    }
    #profile_edit_buttons {
        height: 3;
        width: 100%;
        align: center middle;
    }
    #profile_edit_buttons Button { margin: 0 1; }

    /* Row + cycle widgets — must match SettingsApp CSS so focus, section
       styling, and field heights render correctly when the modal is pushed
       from any App (e.g. ait board's AgentCommandScreen, not just settings). */
    ConfigRow { height: 1; width: 100%; padding: 0 1; }
    ConfigRow.row-focused { background: $primary 20%; }
    CycleField { height: 1; width: 100%; padding: 0 1; }
    CycleField.cycle-focused { background: $primary 20%; }
    .section-header {
        text-style: bold;
        padding: 1 0 0 1;
        color: $accent;
    }
    .section-hint {
        padding: 0 0 0 3;
        color: $text-muted;
    }
    """

    def __init__(
        self,
        profile_data: dict,
        on_save: Callable[[dict], None] | None = None,
        *,
        on_save_persistent: Callable[[dict], None] | None = None,
        on_save_one_shot: Callable[[dict], None] | None = None,
        title: str = "Edit Profile",
        persistent_button_label: str = "(S)ave",
        one_shot_button_label: str = "Save as (O)ne-shot",
    ):
        super().__init__()
        self.profile_data = dict(profile_data)
        # Legacy `on_save` maps to the persistent slot when explicit
        # persistent/one-shot callbacks were not provided.
        self._on_save_persistent = on_save_persistent or on_save
        self._on_save_one_shot = on_save_one_shot
        self._dual_mode = on_save_one_shot is not None
        self._title = title
        self._persistent_button_label = persistent_button_label
        self._one_shot_button_label = one_shot_button_label

    def compose(self) -> ComposeResult:
        with Container(id="profile_edit_dialog"):
            yield Label(f"[bold]{self._title}[/bold]", id="profile_edit_title")
            yield Label(
                "[dim]↑↓: navigate  |  ←→: cycle  |  Enter: edit string/int  "
                "|  S: save  |  O: save one-shot  |  Esc: cancel[/dim]",
                id="profile_edit_help",
            )
            with _NoArrowsVerticalScroll(id="profile_edit_scroll"):
                yield from compose_profile_fields(
                    self.profile_data, id_prefix="modal",
                )
            with Horizontal(id="profile_edit_buttons"):
                yield Button(
                    self._persistent_button_label, variant="success",
                    id="btn_profile_edit_save",
                )
                if self._dual_mode:
                    yield Button(
                        self._one_shot_button_label, variant="primary",
                        id="btn_profile_edit_save_oneshot",
                    )
                yield Button("Cancel", variant="default", id="btn_profile_edit_cancel")

    def on_mount(self) -> None:
        """Take VerticalScroll out of the focus chain and seed focus on the
        first editable field.

        VerticalScroll is focusable by default in Textual 8.x; leaving it in
        the focus chain causes initial focus to land on the scroll container
        instead of a field. The `_NoArrowsVerticalScroll` subclass also
        strips the Left/Right scroll bindings so they cannot eat arrow keys
        that should reach CycleField.
        """
        try:
            scroll = self.query_one("#profile_edit_scroll", _NoArrowsVerticalScroll)
            scroll.can_focus = False
        except Exception:
            pass
        try:
            for w in self.query("CycleField, ConfigRow"):
                w.focus()
                break
        except Exception:
            pass

    def on_key(self, event):
        """Enter on a profile string/int row -> push EditStringScreen."""
        if event.key != "enter":
            return
        focused = self.focused
        if not isinstance(focused, ConfigRow):
            return
        fid = focused.id or ""
        if not (fid.startswith("profile_str_") or fid.startswith("profile_int_")):
            return
        key = focused.row_key
        value = focused.value
        self.app.push_screen(
            EditStringScreen(key, value),
            callback=self._apply_string_edit,
        )
        event.prevent_default()
        event.stop()

    def _apply_string_edit(self, result):
        if result is None:
            return
        key = result["key"]
        value = result["value"]
        ktype = PROFILE_SCHEMA.get(key, ("string", None))[0]
        prefix = "profile_int_" if ktype == "int" else "profile_str_"
        widget_id = f"{prefix}{key}__modal"
        try:
            row = self.query_one(f"#{widget_id}", ConfigRow)
            row.value = value
            row.refresh()
        except Exception:
            pass

    @on(Button.Pressed, "#btn_profile_edit_save")
    def do_save_persistent(self):
        updated, errors = collect_profile_values(
            self.query_one, self.profile_data, id_prefix="modal",
        )
        if errors:
            for msg in errors:
                self.app.notify(msg, severity="error")
            return
        if self._on_save_persistent is not None:
            self._on_save_persistent(updated)
        # Preserve legacy dismiss payload (just `updated`) when only the
        # legacy single-callback shape is in use; emit (mode, updated) when
        # the caller opted into dual-save semantics.
        if self._dual_mode:
            self.dismiss(("persistent", updated))
        else:
            self.dismiss(updated)

    @on(Button.Pressed, "#btn_profile_edit_save_oneshot")
    def do_save_one_shot(self):
        updated, errors = collect_profile_values(
            self.query_one, self.profile_data, id_prefix="modal",
        )
        if errors:
            for msg in errors:
                self.app.notify(msg, severity="error")
            return
        if self._on_save_one_shot is not None:
            self._on_save_one_shot(updated)
        self.dismiss(("one_shot", updated))

    @on(Button.Pressed, "#btn_profile_edit_cancel")
    def do_cancel(self):
        self.dismiss(None)

    def action_cancel(self):
        self.dismiss(None)

    def action_save_persistent(self) -> None:
        self.do_save_persistent()

    def action_save_one_shot(self) -> None:
        if self._dual_mode:
            self.do_save_one_shot()
