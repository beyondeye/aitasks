"""settings_screens - Modal dialogs for the syncer's cross-repo settings push.

The push writes another repository's `codeagent_config*.json`. Unlike
`upgrade_screens` — a single destructive confirm, where Cancel deliberately
holds focus — this is a **multi-step wizard**, so it follows wizard conventions
instead:

* **Enter advances one step, Esc goes back one step.** Esc on the first step
  cancels the whole push; on later steps it returns to the previous dialog with
  the earlier choice still selected.
* **The choice widget holds focus on mount**, so ↑/↓ work immediately without
  clicking into the list first.
* **Nothing is preselected where a default would be wrong.** The layer step and
  the masked-resolution step both start with *no* radio pressed, so Enter on an
  untouched dialog reports "choose one" rather than picking for the user. That
  keeps the "layer is always asked, with no default" contract while still
  letting Enter mean "forward".
* **Nothing is persisted.** There is no "don't ask again" anywhere.

The screens are pure UI: they collect a decision and ``dismiss`` it. All policy
(source eligibility, destination exclusion, `plan_push` outcome routing, the
write itself) lives in ``syncer_app``.

Each dialog's body ``Static`` carries an explicit ``id="settings_text"``:
Textual's ``Label`` subclasses ``Static``, so an id-less ``query_one(Static)``
resolves to the dialog *title* instead of the body.
"""
from __future__ import annotations

from textual import on
from textual.binding import Binding
from textual.containers import Container, Horizontal, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import (
    Button,
    Label,
    RadioButton,
    RadioSet,
    SelectionList,
    Static,
)
from textual.widgets.selection_list import Selection

# Dismissed by every step except the first when the user goes back, so the
# caller can re-push the previous dialog instead of aborting the push. A
# sentinel rather than None: None already means "cancel the whole flow".
BACK = "__back__"

_DIALOG_CSS = """
#settings_dialog {
    width: 80%;
    height: auto;
    max-height: 80%;
    background: $surface;
    border: thick $warning;
    padding: 1 2;
}
#settings_title {
    text-align: center;
    padding: 0 0 1 0;
    text-style: bold;
}
#settings_body {
    padding: 0 1;
    height: auto;
    max-height: 20;
}
#settings_buttons {
    height: 3;
    align: center middle;
}
#settings_error {
    color: $error;
    padding: 0 1;
    height: auto;
}
#settings_dest_list {
    height: auto;
    max-height: 12;
    margin: 1 0 0 0;
}
"""

# Measured, not assumed: in this Textual version ↑/↓ move a RadioSet's
# highlight but leave `pressed_index` alone — Space is what commits the
# choice. The hint says so rather than implying Enter selects.
_NAV_HINT = "↑/↓ move · Space select · Enter continue · Esc back"


class _WizardScreen(ModalScreen):
    """Shared wizard behaviour: Enter advances, Esc goes back.

    ``enter`` is bound with ``priority=True`` so it reaches the screen even
    while a RadioSet or SelectionList holds focus (both consume Enter for
    their own selection semantics otherwise).
    """

    DEFAULT_CSS = _DIALOG_CSS

    BINDINGS = [
        Binding("escape", "back", "Back", show=False),
        Binding("enter", "advance", "Continue", show=False, priority=True),
    ]

    def action_advance(self) -> None:
        self._advance()

    def action_back(self) -> None:
        self.dismiss(self._back_result())

    def _advance(self) -> None:  # pragma: no cover — overridden
        raise NotImplementedError

    def _back_result(self):
        return BACK

    def _error(self, message: str) -> None:
        self.query_one("#settings_error", Static).update(message)


class SettingsSourceScreen(_WizardScreen):
    """Step 1 — pick which repo's value to propagate for one operation.

    ``options`` is ``(session_key, label, value)`` carrying ONLY eligible
    sources: a repo whose cell is ``conflict`` or ``unavailable`` has no
    coherent value to copy and is filtered out by the caller. ``initial``
    re-selects a previous choice when the user comes back from step 2;
    otherwise the first (and therefore first *eligible*) entry is selected, so
    an ineligible cwd repo does not leave the default on nothing.

    Dismisses the chosen ``session_key``, or ``None`` — this is step 1, so
    going back means cancelling the push.
    """

    def __init__(
        self, operation: str, options: list[tuple[str, str, str]],
        initial: str | None = None,
    ) -> None:
        super().__init__()
        self._operation = operation
        self._options = list(options)
        keys = [k for k, _l, _v in self._options]
        self._initial = keys.index(initial) if initial in keys else 0

    def compose(self):
        with Container(id="settings_dialog"):
            yield Label(f"Push `{self._operation}` — source", id="settings_title")
            with VerticalScroll(id="settings_body"):
                yield Static(
                    "Which repository's value should be propagated?\n"
                    f"{_NAV_HINT.replace('Esc back', 'Esc cancel')}",
                    id="settings_text",
                )
                with RadioSet(id="settings_source"):
                    for idx, (_key, label, value) in enumerate(self._options):
                        yield RadioButton(
                            f"{label} — {value}",
                            value=(idx == self._initial),
                            id=f"source_{idx}",
                        )
                yield Static("", id="settings_error")
            with Horizontal(id="settings_buttons"):
                yield Button("Cancel", variant="default", id="btn_source_cancel")
                yield Button("Continue", variant="warning", id="btn_source_ok")

    def on_mount(self) -> None:
        # The choice widget, not Cancel: otherwise ↑/↓ land on a Button that
        # ignores them and the list only responds after a click.
        self.query_one("#settings_source", RadioSet).focus()

    def _resolve(self) -> str | None:
        idx = self.query_one("#settings_source", RadioSet).pressed_index
        if idx is None or idx < 0 or idx >= len(self._options):
            return None
        return self._options[idx][0]

    def _advance(self) -> None:
        key = self._resolve()
        if key is None:
            self._error("Choose a source repository.")
            return
        self.dismiss(key)

    def _back_result(self):
        return None          # step 1: back == cancel the push

    @on(Button.Pressed, "#btn_source_ok")
    def _on_ok(self) -> None:
        self._advance()

    @on(Button.Pressed, "#btn_source_cancel")
    def _on_cancel(self) -> None:
        self.dismiss(None)


class SettingsDestinationsScreen(_WizardScreen):
    """Step 2 — choose which repos receive the value. Multi-select.

    ``destinations`` is ``(session_key, label)`` for every repo EXCEPT the
    chosen source — the caller removes it at construction time, so a repo can
    never be pushed into itself. Unlike the source list this is NOT filtered by
    source-eligibility: a repo whose own value is unusable is exactly the one
    most worth writing to, and an unreadable one earns an explicit
    ``dest_config_unreadable`` rejection rather than being silently dropped.

    Dismisses a tuple of chosen ``session_key``s, or ``BACK``.
    """

    def __init__(
        self, operation: str, value: str,
        destinations: list[tuple[str, str]],
        initial: tuple[str, ...] = (),
    ) -> None:
        super().__init__()
        self._operation = operation
        self._value = value
        self._destinations = list(destinations)
        self._initial = set(initial)

    def compose(self):
        with Container(id="settings_dialog"):
            yield Label(
                f"Push `{self._operation}` — destinations", id="settings_title"
            )
            with VerticalScroll(id="settings_body"):
                yield Static(
                    f"Write {self._value} to which repositories?\n"
                    "Space toggles · Enter continue · Esc back",
                    id="settings_text",
                )
                yield SelectionList[str](
                    *(
                        Selection(label, key, initial_state=key in self._initial)
                        for key, label in self._destinations
                    ),
                    id="settings_dest_list",
                )
                yield Static("", id="settings_error")
            with Horizontal(id="settings_buttons"):
                yield Button("Back", variant="default", id="btn_dest_back")
                yield Button("Continue", variant="warning", id="btn_dest_ok")

    def on_mount(self) -> None:
        self.query_one("#settings_dest_list", SelectionList).focus()

    def _chosen(self) -> tuple[str, ...]:
        checked = set(
            self.query_one("#settings_dest_list", SelectionList).selected
        )
        # Preserve the caller's column order rather than click order.
        return tuple(key for key, _ in self._destinations if key in checked)

    def _advance(self) -> None:
        picked = self._chosen()
        if not picked:
            self._error("Select at least one destination (space toggles).")
            return
        self.dismiss(picked)

    @on(Button.Pressed, "#btn_dest_ok")
    def _on_ok(self) -> None:
        self._advance()

    @on(Button.Pressed, "#btn_dest_back")
    def _on_back(self) -> None:
        self.dismiss(BACK)


class SettingsLayerScreen(_WizardScreen):
    """Step 3 — which config layer to write. Always asked, with NO default.

    Project vs local is a real semantic choice (team-shared and git-tracked vs
    personal and gitignored), so **neither radio starts pressed**: Enter on an
    untouched dialog reports "choose a layer" instead of picking one. That
    keeps the no-default contract while still letting Enter mean "forward".

    Dismisses ``"project"`` / ``"local"``, or ``BACK``.
    """

    _LAYERS = ("project", "local")

    def __init__(
        self, operation: str, value: str, dest_labels: list[str]
    ) -> None:
        super().__init__()
        self._operation = operation
        self._value = value
        self._dest_labels = list(dest_labels)

    def compose(self):
        listed = "\n".join(f"  • {lbl}" for lbl in self._dest_labels)
        with Container(id="settings_dialog"):
            yield Label("Which config layer?", id="settings_title")
            with VerticalScroll(id="settings_body"):
                yield Static(
                    f"Writing `{self._operation}` = {self._value} to:\n"
                    f"{listed}\n\n"
                    "The file is written but NOT committed — review and commit "
                    f"it in the destination repo yourself.\n{_NAV_HINT}",
                    id="settings_text",
                )
                with RadioSet(id="settings_layer"):
                    yield RadioButton(
                        "project — codeagent_config.json, git-tracked, shared "
                        "with the team",
                        id="layer_project",
                    )
                    yield RadioButton(
                        "local — codeagent_config.local.json, gitignored, "
                        "personal to that checkout",
                        id="layer_local",
                    )
                yield Static("", id="settings_error")
            with Horizontal(id="settings_buttons"):
                yield Button("Back", variant="default", id="btn_layer_back")
                yield Button("Continue", variant="warning", id="btn_layer_ok")

    def on_mount(self) -> None:
        self.query_one("#settings_layer", RadioSet).focus()

    def _resolve(self) -> str | None:
        idx = self.query_one("#settings_layer", RadioSet).pressed_index
        if idx is None or idx < 0 or idx >= len(self._LAYERS):
            return None
        return self._LAYERS[idx]

    def _advance(self) -> None:
        layer = self._resolve()
        if layer is None:
            self._error("Choose a layer — project or local.")
            return
        self.dismiss(layer)

    @on(Button.Pressed, "#btn_layer_ok")
    def _on_ok(self) -> None:
        self._advance()

    @on(Button.Pressed, "#btn_layer_back")
    def _on_back(self) -> None:
        self.dismiss(BACK)


class SettingsMaskedScreen(_WizardScreen):
    """Resolve a masked project write for ONE destination. No default.

    A project write into a repo that has a local override for the same
    operation changes a file and changes nothing the repo actually uses, so the
    masking value is named verbatim and exactly three resolutions are offered.

    Esc means **skip this destination**, not "go back": the masked prompts are
    drained one destination at a time after planning, so there is no coherent
    earlier step to return to mid-queue.

    Dismisses ``"cancel"`` / ``"local"`` / ``"clear"``.
    """

    _CHOICES = ("cancel", "local", "clear")

    def __init__(
        self, dest_label: str, operation: str, value: str,
        masking_value: str | None,
    ) -> None:
        super().__init__()
        self._dest_label = dest_label
        self._operation = operation
        self._value = value
        self._masking_value = masking_value

    def compose(self):
        masking = self._masking_value or "an unreadable value"
        with Container(id="settings_dialog"):
            yield Label(
                f"{self._dest_label}: project write would be masked",
                id="settings_title",
            )
            with VerticalScroll(id="settings_body"):
                yield Static(
                    f"{self._dest_label}'s local layer sets {masking} for "
                    f"`{self._operation}`; a project write would have no "
                    f"effect.\n\nYou are pushing {self._value}.\n"
                    "↑/↓ move · Space select · Enter continue · "
                    "Esc skip this repository",
                    id="settings_text",
                )
                with RadioSet(id="settings_masked"):
                    yield RadioButton(
                        "Skip — write nothing to this repository",
                        id="mask_cancel",
                    )
                    yield RadioButton(
                        "Write local — set its local layer instead",
                        id="mask_local",
                    )
                    yield RadioButton(
                        "Clear + project — remove the local override and "
                        "write the project layer",
                        id="mask_clear",
                    )
                yield Static("", id="settings_error")
            with Horizontal(id="settings_buttons"):
                yield Button("Skip", variant="default", id="btn_mask_skip")
                yield Button("Continue", variant="warning", id="btn_mask_ok")

    def on_mount(self) -> None:
        self.query_one("#settings_masked", RadioSet).focus()

    def _resolve(self) -> str | None:
        idx = self.query_one("#settings_masked", RadioSet).pressed_index
        if idx is None or idx < 0 or idx >= len(self._CHOICES):
            return None
        return self._CHOICES[idx]

    def _advance(self) -> None:
        choice = self._resolve()
        if choice is None:
            self._error("Choose how to resolve this repository.")
            return
        self.dismiss(choice)

    def _back_result(self):
        return "cancel"      # Esc skips this destination

    @on(Button.Pressed, "#btn_mask_ok")
    def _on_ok(self) -> None:
        self._advance()

    @on(Button.Pressed, "#btn_mask_skip")
    def _on_skip(self) -> None:
        self.dismiss("cancel")


class SettingsPushResultScreen(_WizardScreen):
    """Per-destination outcome summary. Enter or Esc closes it.

    Every destination gets a line. A single "done" is not enough: destinations
    diverge (applied, already-matching, rejected for distinct reasons, skipped,
    partially applied, failed) and the user has to be able to tell which repos
    actually changed.
    """

    DEFAULT_CSS = _DIALOG_CSS + """
    #settings_dialog {
        border: thick $accent;
    }
    """

    def __init__(self, operation: str, rows: list[tuple[str, str]]) -> None:
        super().__init__()
        self._operation = operation
        self._rows = list(rows)

    def compose(self):
        listed = "\n".join(f"  • {label}: {text}" for label, text in self._rows)
        with Container(id="settings_dialog"):
            yield Label(f"Push `{self._operation}` — results", id="settings_title")
            with VerticalScroll(id="settings_body"):
                yield Static(
                    f"{listed}\n\n"
                    "Nothing was committed — review and commit the changed "
                    "config in each destination repo.",
                    id="settings_text",
                )
            with Horizontal(id="settings_buttons"):
                yield Button("Close", variant="primary", id="btn_result_close")

    def on_mount(self) -> None:
        self.query_one("#btn_result_close", Button).focus()

    def _advance(self) -> None:
        self.dismiss(None)

    def _back_result(self):
        return None

    @on(Button.Pressed, "#btn_result_close")
    def _on_close(self) -> None:
        self.dismiss(None)
