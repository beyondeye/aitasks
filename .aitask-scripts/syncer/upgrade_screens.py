"""upgrade_screens - Modal dialogs for the syncer's framework-upgrade action.

Every dialog here guards an action that rewrites framework files, so two
conventions are load-bearing and deliberate:

* **Cancel is always the focused default.** No dialog can be confirmed by a
  stray Enter.
* **Nothing is persisted.** There is no "don't ask again" state anywhere — the
  force-override in particular must be re-earned on every single use.

The screens are pure UI: they collect a decision and ``dismiss`` it. All
policy (self-target detection, the activity gate, the freshness re-probe before
a forced launch) lives in ``syncer_app`` so it is unit-testable without a
running app.
"""
from __future__ import annotations

import re

from textual import on
from textual.binding import Binding
from textual.containers import Container, Horizontal, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import (
    Button,
    Input,
    Label,
    RadioButton,
    RadioSet,
    Static,
)

# Kept in sync with framework_version.VERSION_RE by import at call time; the
# module-level fallback below is only used if that import is unavailable.
_DEFAULT_VERSION_RE = r"^(latest|[0-9]+\.[0-9]+(\.[0-9]+)?)$"

_DIALOG_CSS = """
#upgrade_dialog {
    width: 80%;
    height: auto;
    max-height: 80%;
    background: $surface;
    border: thick $warning;
    padding: 1 2;
}
#upgrade_title {
    text-align: center;
    padding: 0 0 1 0;
    text-style: bold;
}
#upgrade_body {
    padding: 0 1;
    height: auto;
    max-height: 20;
}
#upgrade_buttons {
    height: 3;
    align: center middle;
}
#upgrade_error {
    color: $error;
    padding: 0 1;
    height: auto;
}
"""


def describe_activity(activity: str) -> str:
    """Human-readable rendering of a ``detect_target_activity`` result.

    ``busy:<names>`` lists the offending windows verbatim (never summarised or
    truncated — the user needs to know exactly what to close), ``unknown:<r>``
    surfaces the reason, and ``idle`` renders as an explicit statement rather
    than an empty string so a dialog never silently omits the finding.
    """
    if activity == "idle":
        return "No framework windows detected."
    if activity.startswith("busy:"):
        names = [n for n in activity[len("busy:"):].split(",") if n]
        listed = "\n".join(f"  • {n}" for n in names)
        return f"Live framework windows detected:\n{listed}"
    if activity.startswith("unknown:"):
        return (
            "Could not determine what is running in the target "
            f"({activity[len('unknown:'):]})."
        )
    return activity


class UpgradeTargetScreen(ModalScreen):
    """Pick the upgrade version: ``latest`` or an explicitly pinned value.

    An explicit mode selector rather than a single free-text box whose magic
    value happens to be the word "latest": the two choices are semantically
    different (track the release vs. freeze on a version) and the UI says so.
    Dismisses the validated version string, or ``None`` on cancel.
    """

    DEFAULT_CSS = _DIALOG_CSS + """
    #upgrade_version_input {
        margin: 1 1 0 1;
    }
    """

    BINDINGS = [Binding("escape", "cancel", "Cancel", show=False)]

    def __init__(self, label: str, installed: str | None) -> None:
        super().__init__()
        self._label = label
        self._installed = installed

    def compose(self):
        with Container(id="upgrade_dialog"):
            yield Label(f"Upgrade {self._label}", id="upgrade_title")
            with VerticalScroll(id="upgrade_body"):
                yield Static(
                    f"Installed version: {self._installed or 'unknown'}\n\n"
                    "Choose the target version:"
                )
                with RadioSet(id="upgrade_mode"):
                    yield RadioButton("latest release", value=True, id="mode_latest")
                    yield RadioButton("pinned version", id="mode_pinned")
                yield Input(
                    placeholder="e.g. 0.28.0",
                    id="upgrade_version_input",
                    disabled=True,
                )
                yield Static("", id="upgrade_error")
            with Horizontal(id="upgrade_buttons"):
                yield Button("Cancel", variant="default", id="btn_version_cancel")
                yield Button("Continue", variant="warning", id="btn_version_ok")

    def on_mount(self) -> None:
        self.query_one("#btn_version_cancel", Button).focus()

    @on(RadioSet.Changed, "#upgrade_mode")
    def _on_mode(self, event: RadioSet.Changed) -> None:
        pinned = event.pressed.id == "mode_pinned"
        field = self.query_one("#upgrade_version_input", Input)
        field.disabled = not pinned
        if pinned:
            field.focus()

    def _pattern(self) -> str:
        try:
            from framework_version import VERSION_RE

            return VERSION_RE
        except Exception:  # pragma: no cover — defensive
            return _DEFAULT_VERSION_RE

    def _resolve(self) -> str | None:
        """Return the chosen version, or None after showing an inline error."""
        pressed = self.query_one("#upgrade_mode", RadioSet).pressed_button
        if pressed is not None and pressed.id == "mode_latest":
            return "latest"
        raw = self.query_one("#upgrade_version_input", Input).value.strip()
        if re.fullmatch(self._pattern(), raw):
            return raw
        # Rejected in the dialog: an invalid version never reaches the model.
        self.query_one("#upgrade_error", Static).update(
            f"Not a valid version: {raw!r} — use e.g. 0.28 or 0.28.0"
        )
        return None

    @on(Button.Pressed, "#btn_version_ok")
    def _on_ok(self) -> None:
        version = self._resolve()
        if version is not None:
            self.dismiss(version)

    @on(Input.Submitted, "#upgrade_version_input")
    def _on_submit(self) -> None:
        self._on_ok()

    @on(Button.Pressed, "#btn_version_cancel")
    def _on_cancel(self) -> None:
        self.dismiss(None)

    def action_cancel(self) -> None:
        self.dismiss(None)


class UpgradeConfirmScreen(ModalScreen):
    """Confirm a cross-repo upgrade spawn. Dismisses True/False.

    Names the project label AND the resolved root path: two checkouts of the
    same project are a normal setup, so the label alone does not identify what
    is about to be rewritten.
    """

    DEFAULT_CSS = _DIALOG_CSS

    BINDINGS = [Binding("escape", "cancel", "Cancel", show=False)]

    def __init__(self, label: str, root: str, version: str) -> None:
        super().__init__()
        self._label = label
        self._root = root
        self._version = version

    def compose(self):
        with Container(id="upgrade_dialog"):
            yield Label(f"Upgrade {self._label}?", id="upgrade_title")
            with VerticalScroll(id="upgrade_body"):
                yield Static(
                    f"Project: {self._label}\n"
                    f"Root:    {self._root}\n"
                    f"Version: {self._version}\n\n"
                    "A new tmux window will run:\n"
                    "  ./ait upgrade <version> && ./ait setup\n\n"
                    "This rewrites the framework files in that repository.",
                    id="upgrade_text",
                )
            with Horizontal(id="upgrade_buttons"):
                yield Button("Cancel", variant="default", id="btn_confirm_cancel")
                yield Button("Upgrade", variant="warning", id="btn_confirm_ok")

    def on_mount(self) -> None:
        self.query_one("#btn_confirm_cancel", Button).focus()

    @on(Button.Pressed, "#btn_confirm_ok")
    def _on_ok(self) -> None:
        self.dismiss(True)

    @on(Button.Pressed, "#btn_confirm_cancel")
    def _on_cancel(self) -> None:
        self.dismiss(False)

    def action_cancel(self) -> None:
        self.dismiss(False)


class HandoffConfirmScreen(ModalScreen):
    """Confirm the self-repo exit-then-upgrade handoff. Dismisses True/False.

    The syncer cannot upgrade its own repo by spawning: it would rewrite the
    scripts its own subprocesses resolve. Instead it exits first and the
    launcher runs the upgrade in the vacated window.

    The activity result is shown as an **advisory**, not a refusal. The repo the
    syncer runs from is where the user works, so it almost always has live
    framework windows; refusing on that basis would make the one safe
    self-upgrade path reachable only through the force-override, which would
    devalue that confirmation everywhere else. The user is told exactly what is
    live and decides.
    """

    DEFAULT_CSS = _DIALOG_CSS

    BINDINGS = [Binding("escape", "cancel", "Cancel", show=False)]

    def __init__(self, label: str, root: str, version: str, activity: str) -> None:
        super().__init__()
        self._label = label
        self._root = root
        self._version = version
        self._activity = activity

    def compose(self):
        advisory = ""
        if self._activity != "idle":
            advisory = (
                "\n\n"
                + describe_activity(self._activity)
                + "\nThey may break while the framework is replaced. This syncer "
                "is among them and exits before the upgrade starts; the others "
                "do not."
            )
        with Container(id="upgrade_dialog"):
            yield Label(
                f"Upgrade this repository ({self._label})?", id="upgrade_title"
            )
            with VerticalScroll(id="upgrade_body"):
                yield Static(
                    f"Root:    {self._root}\n"
                    f"Version: {self._version}\n\n"
                    "This is the repository the syncer is running from, so it "
                    "cannot be upgraded in the background. The syncer will exit "
                    "now and the upgrade will run in this window."
                    + advisory,
                    id="upgrade_text",
                )
            with Horizontal(id="upgrade_buttons"):
                yield Button("Cancel", variant="default", id="btn_handoff_cancel")
                yield Button(
                    "Exit and upgrade", variant="warning", id="btn_handoff_ok"
                )

    def on_mount(self) -> None:
        self.query_one("#btn_handoff_cancel", Button).focus()

    @on(Button.Pressed, "#btn_handoff_ok")
    def _on_ok(self) -> None:
        self.dismiss(True)

    @on(Button.Pressed, "#btn_handoff_cancel")
    def _on_cancel(self) -> None:
        self.dismiss(False)

    def action_cancel(self) -> None:
        self.dismiss(False)


class UpgradeRefusalScreen(ModalScreen):
    """Refuse a cross-repo upgrade whose target has live framework activity.

    Dismisses ``"cancel"`` or ``"force"``. Choosing force does NOT launch — the
    caller re-probes the target and, if the situation still warrants it, raises
    a separate destructive confirmation. Splitting the two means the option that
    actually starts the upgrade is never the same keystroke as the option that
    merely asks to consider it.
    """

    DEFAULT_CSS = _DIALOG_CSS

    BINDINGS = [Binding("escape", "cancel", "Cancel", show=False)]

    def __init__(self, label: str, activity: str) -> None:
        super().__init__()
        self._label = label
        self._activity = activity

    def compose(self):
        with Container(id="upgrade_dialog"):
            yield Label(f"Upgrade refused: {self._label}", id="upgrade_title")
            with VerticalScroll(id="upgrade_body"):
                yield Static(
                    describe_activity(self._activity)
                    + "\n\nUpgrading now would replace the framework underneath "
                    "them. Close them and try again.",
                    id="upgrade_text",
                )
            with Horizontal(id="upgrade_buttons"):
                yield Button("Cancel", variant="default", id="btn_refusal_cancel")
                yield Button(
                    "Force…", variant="error", id="btn_refusal_force"
                )

    def on_mount(self) -> None:
        self.query_one("#btn_refusal_cancel", Button).focus()

    @on(Button.Pressed, "#btn_refusal_force")
    def _on_force(self) -> None:
        self.dismiss("force")

    @on(Button.Pressed, "#btn_refusal_cancel")
    def _on_cancel(self) -> None:
        self.dismiss("cancel")

    def action_cancel(self) -> None:
        self.dismiss("cancel")


class ForceConfirmScreen(ModalScreen):
    """Destructive confirmation for a forced upgrade. Dismisses True/False.

    The body lists the FRESHLY re-probed activity verbatim, not what the
    refusal happened to show earlier — the caller aborts instead of reaching
    this screen if the two disagree.
    """

    DEFAULT_CSS = _DIALOG_CSS + """
    #upgrade_dialog {
        border: thick $error;
    }
    """

    BINDINGS = [Binding("escape", "cancel", "Cancel", show=False)]

    FORCE_LABEL = "Force upgrade anyway — I accept the listed windows may break"

    def __init__(self, label: str, root: str, version: str, activity: str) -> None:
        super().__init__()
        self._label = label
        self._root = root
        self._version = version
        self._activity = activity

    def compose(self):
        with Container(id="upgrade_dialog"):
            yield Label(f"Force upgrade {self._label}?", id="upgrade_title")
            with VerticalScroll(id="upgrade_body"):
                yield Static(
                    f"Root:    {self._root}\n"
                    f"Version: {self._version}\n\n"
                    + describe_activity(self._activity)
                    + "\n\nThese are running right now. Upgrading will replace "
                    "the framework scripts they are using, which can break them "
                    "mid-operation.",
                    id="upgrade_text",
                )
            with Horizontal(id="upgrade_buttons"):
                yield Button("Cancel", variant="default", id="btn_force_cancel")
                yield Button(
                    self.FORCE_LABEL, variant="error", id="btn_force_ok"
                )

    def on_mount(self) -> None:
        self.query_one("#btn_force_cancel", Button).focus()

    @on(Button.Pressed, "#btn_force_ok")
    def _on_ok(self) -> None:
        self.dismiss(True)

    @on(Button.Pressed, "#btn_force_cancel")
    def _on_cancel(self) -> None:
        self.dismiss(False)

    def action_cancel(self) -> None:
        self.dismiss(False)
