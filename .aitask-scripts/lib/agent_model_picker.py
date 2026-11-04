"""agent_model_picker — Shared picker for code agent + LLM model selection.

Used by the settings TUI (to edit global defaults in codeagent_config.json)
and by the launch dialog (to override the agent/model for a single run).
The module is Textual-dependent but has no settings_app dependency.

Public API:
- AgentModelPickerScreen — ModalScreen with a single fuzzy list that cycles
  through six modes via Shift+Left / Shift+Right:
    top_all_ops, top_usage, all, codex, opencode, claudecode
  The two top lists rank by recorded usage in the date-correct recent window
  (current + previous calendar month, see model_stats_windows); the per-agent
  lists also show verified scores.
- FuzzySelect / FuzzyOption — reusable fuzzy-search list widget
- MODEL_FILES — {provider: Path} map of models_*.json files
- load_all_models(project_root) — load every models_*.json into a dict
"""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, VerticalScroll
from textual.message import Message
from textual.widgets import Button, Input, Label, Static

# Add sibling lib dir to path so config_utils resolves when this module is
# imported from outside .aitask-scripts/lib.
_LIB_DIR = str(Path(__file__).resolve().parent)
if _LIB_DIR not in sys.path:
    sys.path.insert(0, _LIB_DIR)

# MODEL_FILES / load_all_models live in config_utils so headless callers (e.g.
# cross_repo_settings) can reach the catalog without importing this
# Textual-dependent module. Re-exported here for the existing importers.
from guarded_dismiss import GuardedModalScreen  # noqa: E402
from config_utils import (  # noqa: E402,F401
    MODEL_FILES,
    _load_json,
    load_all_models,
    metadata_dir,
)
from model_stats_windows import (  # noqa: E402
    recent_aggregate,
    resolve_windows,
    stats_key_for_operation,
)


METADATA_DIR = metadata_dir()


def _bucket_avg(bucket: dict) -> int:
    """Compute rounded average from a verifiedstats bucket."""
    runs = bucket.get("runs", 0)
    if runs <= 0:
        return 0
    return round(bucket.get("score_sum", 0) / runs)


def _format_op_stats(buckets: dict, compact: bool = False,
                     today: date | None = None) -> str:
    """Format verifiedstats buckets for one operation into a display string.

    compact=True: '96 (9 runs, 2 this mo)' — for Agent Defaults labels
    compact=False: '96 (9 runs, 2 this month)' — for Models tab

    The "this month" / "last month" counts are resolved against `today`
    (default: the wall clock), so a bucket no run has rolled over yet is
    shown under the month it really holds, or not at all.
    """
    at = buckets.get("all_time", {})
    runs = at.get("runs", 0)
    if runs <= 0:
        return ""
    avg = _bucket_avg(at)
    windows = resolve_windows(buckets, today)
    mo_runs = windows["month"]["runs"]
    pm_runs = windows["prev_month"]["runs"]
    mo_label = "mo" if compact else "month"
    pm_label = "prev mo" if compact else "last month"
    parts = [f"{runs} runs"]
    if mo_runs > 0:
        parts.append(f"{mo_runs} this {mo_label}")
    if pm_runs > 0:
        parts.append(f"{pm_runs} {pm_label}")
    return f"{avg} ({', '.join(parts)})"


class FuzzyOption(Static):
    """A single option row in FuzzySelect."""

    def __init__(self, value: str, display: str, description: str = "",
                 id: str | None = None):
        super().__init__(id=id)
        self.option_value = value
        self.display_text = display
        self.description = description
        self.highlighted = False

    def render(self) -> str:
        prefix = " >> " if self.highlighted else "    "
        if self.highlighted:
            text = f"{prefix}[bold reverse]{self.display_text}[/]"
        else:
            text = f"{prefix}{self.display_text}"
        if self.description:
            text += f"  [dim]{self.description}[/dim]"
        return text


class FuzzySelect(Container):
    """Autocomplete picker: Input at top, filtered option list below."""

    class Selected(Message):
        """Posted when user selects an option (Enter)."""
        def __init__(self, value: str):
            super().__init__()
            self.value = value

    class Created(Message):
        """Posted (only when ``allow_create``) on Enter/accept with a non-empty
        query that matches no existing option — i.e. the user is creating a new
        value. The parent screen is responsible for validating it."""

        def __init__(self, value: str):
            super().__init__()
            self.value = value

    class Cancelled(Message):
        """Posted when user presses Escape."""
        pass

    class Highlighted(Message):
        """Posted when highlight changes (up/down arrow or filter)."""
        def __init__(self, value: str):
            super().__init__()
            self.value = value

    def __init__(self, options: list[dict], placeholder: str = "Type to filter...",
                 id: str | None = None, allow_create: bool = False):
        """
        options: list of {"value": str, "display": str, "description": str}
        allow_create: when True, accepting (Enter / accept()) with a non-empty
            query that matches no option posts a ``Created`` message instead of
            doing nothing — lets a combobox double as a "pick existing or create
            new" control. Default False keeps the pick-only behavior.
        """
        super().__init__(id=id)
        self.all_options = options
        self.filtered: list[dict] = list(options)
        self.highlight_index = 0
        self._placeholder = placeholder
        self.allow_create = allow_create

    @property
    def _input_id(self) -> str:
        return f"{self.id or 'fuzzy'}_input"

    @property
    def _list_id(self) -> str:
        return f"{self.id or 'fuzzy'}_list"

    def compose(self) -> ComposeResult:
        yield Input(placeholder=self._placeholder, id=self._input_id)
        yield VerticalScroll(id=self._list_id)

    def on_mount(self):
        self._render_options()
        try:
            self.query_one(f"#{self._input_id}", Input).focus()
        except Exception:
            pass

    def on_input_changed(self, event: Input.Changed) -> None:
        query = event.value.lower()
        self.filtered = [
            opt for opt in self.all_options
            if query in opt["display"].lower()
            or query in opt.get("description", "").lower()
        ]
        self.highlight_index = 0
        self._render_options()
        if self.filtered:
            self.post_message(self.Highlighted(self.filtered[0]["value"]))

    def update_options(self, options: list[dict],
                       placeholder: str | None = None) -> None:
        """Replace the option set in place (no remount).

        Used by parent screens that switch list contents on a key press —
        avoids the duplicate-id / focus race that occurs when re-mounting
        a FuzzySelect with the same id.
        """
        self.all_options = list(options)
        self.filtered = list(self.all_options)
        self.highlight_index = 0
        try:
            inp = self.query_one(f"#{self._input_id}", Input)
            inp.value = ""
            if placeholder is not None:
                inp.placeholder = placeholder
        except Exception:
            pass
        try:
            self._render_options()
        except Exception:
            pass

    def _render_options(self):
        container = self.query_one(f"#{self._list_id}", VerticalScroll)
        container.remove_children()
        for i, opt in enumerate(self.filtered):
            fo = FuzzyOption(
                value=opt["value"],
                display=opt["display"],
                description=opt.get("description", ""),
            )
            fo.highlighted = (i == self.highlight_index)
            container.mount(fo)

    def on_key(self, event):
        if event.key == "up":
            if self.highlight_index > 0:
                self.highlight_index -= 1
                self._update_highlight()
            event.prevent_default()
            event.stop()
        elif event.key == "down":
            if self.highlight_index < len(self.filtered) - 1:
                self.highlight_index += 1
                self._update_highlight()
            event.prevent_default()
            event.stop()
        elif event.key == "enter":
            self.accept()
            event.prevent_default()
            event.stop()
        elif event.key == "escape":
            self.post_message(self.Cancelled())
            event.prevent_default()
            event.stop()

    def accept(self) -> None:
        """Programmatic Enter: select the highlighted match, or — when
        ``allow_create`` — post ``Created`` for a non-empty unmatched query.
        Shared by the Enter key, Input submit, and any parent "OK" button so all
        accept paths behave identically."""
        if self.filtered:
            self.post_message(self.Selected(self.filtered[self.highlight_index]["value"]))
        elif self.allow_create:
            query = self.query_one(f"#{self._input_id}", Input).value.strip()
            if query:
                self.post_message(self.Created(query))

    def current_query(self) -> str:
        """The current filter text (trimmed)."""
        try:
            return self.query_one(f"#{self._input_id}", Input).value.strip()
        except Exception:
            return ""

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self.accept()

    def _update_highlight(self):
        """Update which option shows as highlighted."""
        options = list(self.query(FuzzyOption))
        for i, fo in enumerate(options):
            fo.highlighted = (i == self.highlight_index)
            fo.refresh()
        # Scroll highlighted item into view
        if options and 0 <= self.highlight_index < len(options):
            options[self.highlight_index].scroll_visible()
        if self.filtered and 0 <= self.highlight_index < len(self.filtered):
            self.post_message(self.Highlighted(self.filtered[self.highlight_index]["value"]))


class AgentModelPickerScreen(GuardedModalScreen):
    """Single-screen picker that cycles through six model lists.

    Lists are switched with Shift+Left / Shift+Right. The fuzzy-search Input
    inside the FuzzySelect remains usable for letter-based filtering.

    The two top lists rank models by recorded usage (usagestats) in the
    date-correct recent window — the current plus the previous calendar month,
    resolved against `today` by model_stats_windows:
      - top_all_ops: summed across every recorded op, so it is populated for
        ops that never record usage of their own (raw, shadow, discuss, ...);
      - top_usage: this op only (looked up under stats_key_for_operation).
    Only skills that run the Satisfaction Feedback procedure record usage.
    When a top list is empty, a wrapping hint (#picker_empty_hint) says why.
    """

    # (mode_key, header_label). Per-agent mode keys must match MODEL_FILES
    # so _build_options_for_agent can look up the JSON file directly.
    _MODES: list[tuple[str, str]] = [
        ("top_all_ops", "Top used models (recent, all ops)"),
        ("top_usage",   "Top by usage (recent, this op)"),
        ("all",         "All models"),
        ("codex",       "All codex models"),
        ("opencode",    "All opencode models"),
        ("claudecode",  "All Claude models"),
    ]

    # Shown in the one-row placeholder option of an empty top list. Kept short:
    # FuzzyOption is `height: 1`, so a longer text is clipped at every width.
    _EMPTY_ROW: dict[str, str] = {
        "top_all_ops": "(no recent usage)",
        "top_usage":   "(no recent usage for this op)",
    }
    # The explanation for an empty top list, in the wrapping #picker_empty_hint.
    _EMPTY_HINT: dict[str, str] = {
        "top_all_ops": "Nothing recorded for any op this month or last month.",
        "top_usage": (
            "Nothing recorded for this op this month or last month. Only skills "
            "that run satisfaction feedback record usage, so ops such as raw, "
            "shadow and discuss stay empty here."
        ),
    }

    # Pinned "today" for the date-correct windows; None means the wall clock.
    # A class attribute so instances built without __init__ (ad-hoc probes)
    # still resolve it.
    _today: date | None = None

    DEFAULT_CSS = """
    #picker_dialog {
        width: 65%;
        height: auto;
        max-height: 70%;
        background: $surface;
        border: thick $accent;
        padding: 1 2;
    }
    #picker_step_label { padding: 0 0 1 1; color: $accent; }
    #picker_empty_hint {
        width: 100%;
        height: auto;
        padding: 0 0 1 1;
        color: $text-muted;
        display: none;
    }
    FuzzySelect { height: auto; max-height: 20; }
    FuzzySelect VerticalScroll { height: auto; max-height: 15; }
    FuzzyOption { height: 1; width: 100%; padding: 0 1; }

    /* Narrow variant (minimonitor companion pane, ~40 cols): the default
       65%-wide dialog leaves too few columns for the "<agent>/<name>" option
       rows, clipping the model name after the long "claudecode/" prefix. Widen
       the dialog to full width so the name stays visible. Mirrors the narrow
       mode of AgentCommandScreen (agent_command_screen.py). */
    AgentModelPickerScreen.narrow #picker_dialog {
        width: 100%;
        min-width: 30;
        padding: 0 1;
        border: round $accent;
    }
    """

    BINDINGS = [
        Binding("escape", "go_back", "Back/Cancel", show=False),
        Binding("shift+left", "prev_list", "Prev list", show=True, priority=True),
        Binding("shift+right", "next_list", "Next list", show=True, priority=True),
    ]

    def __init__(self, operation: str, current_agent: str = "",
                 current_model: str = "",
                 all_models: dict[str, dict] | None = None,
                 narrow: bool = False,
                 today: date | None = None):
        super().__init__()
        self.operation = operation
        self.current_agent = current_agent
        self.current_model = current_model
        self.all_models = all_models or {}
        self._mode_idx = 0
        # Narrow layout for the minimonitor companion pane (~40 cols). When set,
        # on_mount adds the `narrow` CSS class that widens the dialog so option
        # rows are not clipped after the long "claudecode/" agent prefix.
        self._narrow = narrow
        self._today = today

    @property
    def stats_key(self) -> str:
        """The usagestats / verifiedstats key holding this operation's runs.

        Differs from `operation` only where the launched skill records under
        another name (batch-review -> review). Only stats lookups use it; the
        dismiss result keeps `operation` as its key.
        """
        return stats_key_for_operation(self.operation)

    def _build_top_all_ops(self) -> list[dict]:
        """Build ranked list of top-used models across every op, recent window."""
        candidates = []
        for agent, pdata in self.all_models.items():
            for m in pdata.get("models", []):
                if m.get("status", "active") == "unavailable":
                    continue
                name = m.get("name", "?")
                us = m.get("usagestats", {})
                if not isinstance(us, dict):
                    continue
                total = 0
                op_runs = 0
                for op, op_buckets in us.items():
                    runs, _ = recent_aggregate(op_buckets, self._today)
                    total += runs
                    if op == self.stats_key:
                        op_runs = runs
                if total <= 0:
                    continue
                detail = f"{total} runs recent, all ops"
                if op_runs > 0:
                    detail += f" · {op_runs} this op"
                candidates.append({
                    "agent": agent, "name": name,
                    "runs": total, "detail": detail,
                })
        candidates.sort(key=lambda c: (-c["runs"], c["agent"], c["name"]))
        return candidates[:5]

    def _build_top_usage(self) -> list[dict]:
        """Build ranked list of top-used models for this op, recent window."""
        candidates = []
        for agent, pdata in self.all_models.items():
            for m in pdata.get("models", []):
                if m.get("status", "active") == "unavailable":
                    continue
                name = m.get("name", "?")
                us = m.get("usagestats", {})
                if not isinstance(us, dict):
                    continue
                op_buckets = us.get(self.stats_key, {})
                recent_runs, _ = recent_aggregate(op_buckets, self._today)
                if recent_runs <= 0:
                    continue
                at_runs = op_buckets.get("all_time", {}).get("runs", 0)
                if at_runs > recent_runs:
                    detail = f"{recent_runs} runs recent · {at_runs} all-time"
                else:
                    detail = f"{recent_runs} runs recent"
                candidates.append({
                    "agent": agent, "name": name,
                    "runs": recent_runs, "detail": detail,
                })
        candidates.sort(key=lambda c: (-c["runs"], c["agent"], c["name"]))
        return candidates[:5]

    def compose(self) -> ComposeResult:
        with Container(id="picker_dialog"):
            yield Label(
                f"Select model for: [bold]{self.operation}[/bold]",
                id="picker_title",
            )
            yield Label("", id="picker_step_label")
            # Why an empty top list is empty. A wrapping Label rather than the
            # placeholder option: FuzzyOption rows are one line high.
            yield Label("", id="picker_empty_hint")
            # FuzzySelect is mounted in on_mount via _apply_mode so the
            # initial list reflects the active mode.

    def on_mount(self) -> None:
        if self._narrow:
            self.add_class("narrow")
        self._apply_mode(0)

    def action_go_back(self) -> None:
        self.dismiss(None)

    def action_prev_list(self) -> None:
        self._apply_mode((self._mode_idx - 1) % len(self._MODES))

    def action_next_list(self) -> None:
        self._apply_mode((self._mode_idx + 1) % len(self._MODES))

    def on_fuzzy_select_selected(self, event: FuzzySelect.Selected) -> None:
        if not event.value:
            return  # placeholder rows ("(no models found)", etc.)
        mode_key = self._MODES[self._mode_idx][0]
        if mode_key in ("top_all_ops", "top_usage", "all"):
            self.dismiss({"key": self.operation, "value": event.value})
        else:
            self.dismiss({
                "key": self.operation,
                "value": f"{mode_key}/{event.value}",
            })

    def on_fuzzy_select_cancelled(self, event: FuzzySelect.Cancelled) -> None:
        self.dismiss(None)

    def _apply_mode(self, idx: int) -> None:
        self._mode_idx = idx % len(self._MODES)
        mode_key, label_text = self._MODES[self._mode_idx]
        # On a narrow pane the mode label + hint on one line overflows and the
        # "Shift+←/→ to switch" hint gets clipped off the right; stack it on its
        # own line so it stays visible.
        hint = "[dim](Shift+←/→ to switch)[/dim]"
        sep = "\n" if self._narrow else "  "
        try:
            self.query_one("#picker_step_label", Label).update(
                f"{label_text}{sep}{hint}"
            )
        except Exception:
            pass
        options = self._build_options_for_mode(mode_key)
        placeholder = self._placeholder_for_mode(mode_key)
        self._update_empty_hint(mode_key, options)
        try:
            fs = self.query_one("#model_picker", FuzzySelect)
            fs.update_options(options, placeholder=placeholder)
        except Exception:
            container = self.query_one("#picker_dialog", Container)
            container.mount(FuzzySelect(
                options,
                placeholder=placeholder,
                id="model_picker",
            ))

    def _update_empty_hint(self, mode_key: str, options: list[dict]) -> None:
        """Show the mode's explanation only while its list is the placeholder."""
        is_placeholder = len(options) == 1 and not options[0].get("value")
        text = self._EMPTY_HINT.get(mode_key, "") if is_placeholder else ""
        try:
            hint = self.query_one("#picker_empty_hint", Label)
        except Exception:
            return
        hint.update(text)
        hint.display = bool(text)

    @staticmethod
    def _placeholder_for_mode(mode_key: str) -> str:
        if mode_key == "top_all_ops":
            return "Type to filter top-used models (all ops)..."
        if mode_key == "top_usage":
            return "Type to filter top-used models (this op)..."
        if mode_key == "all":
            return "Type agent/model..."
        return f"Type {mode_key} model name..."

    def _build_options_for_mode(self, mode_key: str) -> list[dict]:
        if mode_key == "top_all_ops":
            return self._build_options_top_all_ops()
        if mode_key == "top_usage":
            return self._build_options_top_usage()
        if mode_key == "all":
            return self._build_options_all()
        return self._build_options_for_agent(mode_key)

    def _ranked_options(self, mode_key: str, ranked: list[dict]) -> list[dict]:
        out = [
            {
                "value": f"{c['agent']}/{c['name']}",
                "display": f"{c['agent']}/{c['name']}",
                "description": c["detail"],
            }
            for c in ranked
        ]
        if not out:
            out.append({
                "value": "",
                "display": self._EMPTY_ROW[mode_key],
                "description": "",
            })
        return out

    def _build_options_top_all_ops(self) -> list[dict]:
        return self._ranked_options("top_all_ops", self._build_top_all_ops())

    def _build_options_top_usage(self) -> list[dict]:
        return self._ranked_options("top_usage", self._build_top_usage())

    def _build_options_all(self) -> list[dict]:
        out: list[dict] = []
        for agent in sorted(self.all_models.keys()):
            pdata = self.all_models[agent]
            for m in pdata.get("models", []):
                if m.get("status", "active") == "unavailable":
                    continue
                name = m.get("name", "?")
                notes = m.get("notes", "")
                out.append({
                    "value": f"{agent}/{name}",
                    "display": f"{agent}/{name}",
                    "description": notes,
                })
        out.sort(key=lambda o: o["display"])
        if not out:
            out.append({
                "value": "",
                "display": "(no models found)",
                "description": "",
            })
        return out

    def _build_options_for_agent(self, agent: str) -> list[dict]:
        model_path = MODEL_FILES.get(agent, Path("nonexistent"))
        model_data = _load_json(model_path)
        models = model_data.get("models", []) if model_data else []
        scored: list[tuple[int, dict]] = []
        unscored: list[tuple[int, dict]] = []
        for m in models:
            if m.get("status", "active") == "unavailable":
                continue
            name = m.get("name", "?")
            notes = m.get("notes", "")
            vs = m.get("verifiedstats", {})
            op_buckets = vs.get(self.stats_key, {})
            at = op_buckets.get("all_time", {})
            if at.get("runs", 0) > 0:
                detail = _format_op_stats(op_buckets, compact=True,
                                          today=self._today)
                sort_score = _bucket_avg(at)
                score_str = f"[{detail}]"
            else:
                verified = m.get("verified", {})
                op_score = verified.get(self.stats_key, 0)
                if op_score:
                    sort_score = op_score
                    score_str = f"[score: {op_score}]"
                elif self.stats_key in verified:
                    sort_score, score_str = 0, "(not verified)"
                else:
                    sort_score, score_str = -1, ""
            desc = f"{notes}  {score_str}".strip() if score_str else notes
            opt = {"value": name, "display": name, "description": desc}
            (scored if sort_score > 0 else unscored).append((sort_score, opt))
        scored.sort(key=lambda x: -x[0])
        out = [o for _, o in scored] + [o for _, o in unscored]
        if not out:
            out.append({
                "value": "",
                "display": "(no models found)",
                "description": "",
            })
        return out


class LaunchModePickerScreen(GuardedModalScreen):
    """Pick headless/interactive launch mode for a brainstorm agent type."""

    DEFAULT_CSS = """
    #lm_dialog {
        width: 50%;
        height: auto;
        background: $surface;
        border: thick $accent;
        padding: 1 2;
    }
    #lm_buttons { margin-top: 1; height: auto; }
    #lm_buttons Button { margin: 0 1; }
    """

    BINDINGS = [Binding("escape", "cancel", "Cancel", show=False)]

    def __init__(self, operation: str, current: str | None = None):
        super().__init__()
        from launch_modes import normalize_launch_mode
        self.operation = operation
        self.current = normalize_launch_mode(current)

    def compose(self) -> ComposeResult:
        from launch_modes import VALID_LAUNCH_MODES
        with Container(id="lm_dialog"):
            yield Label(
                f"Launch mode for: [bold]{self.operation}[/bold]",
                id="lm_title",
            )
            yield Label(
                f"Current: [#FFB86C]{self.current}[/]",
                id="lm_current",
            )
            with Horizontal(id="lm_buttons"):
                for mode in sorted(VALID_LAUNCH_MODES):
                    yield Button(
                        mode.replace("_", " ").title(),
                        variant=(
                            "primary" if self.current == mode else "default"
                        ),
                        id=f"lm_{mode}",
                    )
                yield Button("Cancel", variant="default", id="lm_cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        from launch_modes import VALID_LAUNCH_MODES
        bid = event.button.id or ""
        if bid == "lm_cancel":
            self.dismiss(None)
            return
        if bid.startswith("lm_"):
            mode = bid[len("lm_"):]
            if mode in VALID_LAUNCH_MODES:
                self.dismiss({"key": self.operation, "value": mode})
                return
        self.dismiss(None)

    def action_cancel(self) -> None:
        self.dismiss(None)
