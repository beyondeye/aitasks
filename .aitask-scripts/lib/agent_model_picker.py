"""agent_model_picker — Shared 3-step picker for code agent + LLM model selection.

Used by the settings TUI (to edit global defaults in codeagent_config.json)
and by the launch dialog (to override the agent/model for a single run).
The module is Textual-dependent but has no settings_app dependency.

Public API:
- AgentModelPickerScreen — ModalScreen presenting 3 steps:
    0: top-verified models for an operation
    1: browse all code agents
    2: browse models within a selected agent
- FuzzySelect / FuzzyOption — reusable fuzzy-search list widget
- MODEL_FILES — {provider: Path} map of models_*.json files
- load_all_models(project_root) — load every models_*.json into a dict
"""
from __future__ import annotations

import sys
from pathlib import Path

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, VerticalScroll
from textual.message import Message
from textual.screen import ModalScreen
from textual.widgets import Input, Label, Static

# Add sibling lib dir to path so config_utils resolves when this module is
# imported from outside .aitask-scripts/lib.
_LIB_DIR = str(Path(__file__).resolve().parent)
if _LIB_DIR not in sys.path:
    sys.path.insert(0, _LIB_DIR)

from config_utils import _load_json  # noqa: E402


METADATA_DIR = Path("aitasks") / "metadata"
MODEL_FILES = {
    "claudecode": METADATA_DIR / "models_claudecode.json",
    "codex": METADATA_DIR / "models_codex.json",
    "geminicli": METADATA_DIR / "models_geminicli.json",
    "opencode": METADATA_DIR / "models_opencode.json",
}


def load_all_models(project_root: Path | None = None) -> dict[str, dict]:
    """Load all models_*.json files into {provider: data}.

    Callers can use this instead of instantiating ConfigManager to get
    the all_models dict required by AgentModelPickerScreen.
    """
    root = project_root or Path.cwd()
    result: dict[str, dict] = {}
    for provider, rel in MODEL_FILES.items():
        data = _load_json(root / rel)
        if data:
            result[provider] = data
    return result


def _bucket_avg(bucket: dict) -> int:
    """Compute rounded average from a verifiedstats bucket."""
    runs = bucket.get("runs", 0)
    if runs <= 0:
        return 0
    return round(bucket.get("score_sum", 0) / runs)


def _format_op_stats(buckets: dict, compact: bool = False) -> str:
    """Format verifiedstats buckets for one operation into a display string.

    compact=True: '96 (9 runs, 2 this mo)' — for Agent Defaults labels
    compact=False: '96 (9 runs, 2 this month)' — for Models tab
    """
    at = buckets.get("all_time", {})
    runs = at.get("runs", 0)
    if runs <= 0:
        return ""
    avg = _bucket_avg(at)
    mo = buckets.get("month", {})
    mo_runs = mo.get("runs", 0)
    mo_label = "mo" if compact else "month"
    if mo_runs > 0:
        return f"{avg} ({runs} runs, {mo_runs} this {mo_label})"
    return f"{avg} ({runs} runs)"


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

    class Cancelled(Message):
        """Posted when user presses Escape."""
        pass

    class Highlighted(Message):
        """Posted when highlight changes (up/down arrow or filter)."""
        def __init__(self, value: str):
            super().__init__()
            self.value = value

    def __init__(self, options: list[dict], placeholder: str = "Type to filter...",
                 id: str | None = None):
        """
        options: list of {"value": str, "display": str, "description": str}
        """
        super().__init__(id=id)
        self.all_options = options
        self.filtered: list[dict] = list(options)
        self.highlight_index = 0
        self._placeholder = placeholder

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
            if self.filtered:
                selected = self.filtered[self.highlight_index]
                self.post_message(self.Selected(selected["value"]))
            event.prevent_default()
            event.stop()
        elif event.key == "escape":
            self.post_message(self.Cancelled())
            event.prevent_default()
            event.stop()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if self.filtered:
            selected = self.filtered[self.highlight_index]
            self.post_message(self.Selected(selected["value"]))

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


class AgentModelPickerScreen(ModalScreen):
    """Multi-step picker: top verified -> code agent -> model name."""

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
    FuzzySelect { height: auto; max-height: 20; }
    FuzzySelect VerticalScroll { height: auto; max-height: 15; }
    FuzzyOption { height: 1; width: 100%; padding: 0 1; }
    """

    BINDINGS = [Binding("escape", "go_back", "Back/Cancel", show=False)]

    def __init__(self, operation: str, current_agent: str = "",
                 current_model: str = "",
                 all_models: dict[str, dict] | None = None):
        super().__init__()
        self.operation = operation
        self.current_agent = current_agent
        self.current_model = current_model
        self.all_models = all_models or {}
        self.selected_agent: str | None = None
        self._step = 0

    def _build_top_verified(self) -> list[dict]:
        """Build ranked list of top verified models for the operation."""
        candidates = []
        for agent, pdata in self.all_models.items():
            for m in pdata.get("models", []):
                if m.get("status", "active") == "unavailable":
                    continue
                name = m.get("name", "?")
                vs = m.get("verifiedstats", {})
                op_buckets = vs.get(self.operation, {})
                at = op_buckets.get("all_time", {})
                runs = at.get("runs", 0)
                if runs <= 0:
                    # Fall back to flat verified
                    score = m.get("verified", {}).get(self.operation, 0)
                    if score > 0:
                        candidates.append({
                            "agent": agent, "name": name,
                            "score": score, "detail": f"score: {score}",
                        })
                    continue
                detail = _format_op_stats(op_buckets, compact=True)
                candidates.append({
                    "agent": agent, "name": name,
                    "score": _bucket_avg(at), "detail": detail,
                })
        candidates.sort(key=lambda c: (-c["score"], c["agent"], c["name"]))
        return candidates[:5]

    def compose(self) -> ComposeResult:
        with Container(id="picker_dialog"):
            yield Label(
                f"Select model for: [bold]{self.operation}[/bold]",
                id="picker_title",
            )
            # Build top-verified options
            top = self._build_top_verified()
            if top:
                yield Label(
                    "Top verified models (or browse all)",
                    id="picker_step_label",
                )
                options = []
                for c in top:
                    val = f"{c['agent']}/{c['name']}"
                    options.append({
                        "value": val,
                        "display": val,
                        "description": c["detail"],
                    })
                options.append({
                    "value": "__browse__",
                    "display": "Browse all models...",
                    "description": "Full agent/model browser",
                })
                yield FuzzySelect(
                    options,
                    placeholder="Type to filter...",
                    id="top_picker",
                )
            else:
                # No verified models — skip to step 1
                self._step = 1
                yield Label("Step 1: Choose code agent", id="picker_step_label")
                agent_options = [
                    {"value": a, "display": a, "description": ""}
                    for a in sorted(MODEL_FILES.keys())
                ]
                yield FuzzySelect(
                    agent_options,
                    placeholder="Type agent name...",
                    id="agent_picker",
                )

    def action_go_back(self):
        if self._step == 2:
            self._show_step1()
        elif self._step == 1:
            self._show_step0()
        else:
            self.dismiss(None)

    def on_fuzzy_select_selected(self, event: FuzzySelect.Selected) -> None:
        if self._step == 0:
            if event.value == "__browse__":
                self._show_step1()
            elif event.value:
                self.dismiss({
                    "key": self.operation,
                    "value": event.value,
                })
        elif self._step == 1:
            self.selected_agent = event.value
            self._show_step2()
        elif self._step == 2:
            if not event.value:
                return  # "(no models found)" guard
            self.dismiss({
                "key": self.operation,
                "value": f"{self.selected_agent}/{event.value}",
            })

    def on_fuzzy_select_cancelled(self, event: FuzzySelect.Cancelled) -> None:
        if self._step == 2:
            self._show_step1()
        elif self._step == 1:
            self._show_step0()
        else:
            self.dismiss(None)

    def _show_step0(self):
        """Re-show top verified selection."""
        self._step = 0
        self.query_one("#picker_step_label", Label).update(
            "Top verified models (or browse all)"
        )
        # Remove other pickers
        for pid in ("#agent_picker", "#model_picker"):
            try:
                self.query_one(pid, FuzzySelect).remove()
            except Exception:
                pass
        # Re-show or recreate top picker
        try:
            tp = self.query_one("#top_picker", FuzzySelect)
            tp.display = True
        except Exception:
            top = self._build_top_verified()
            options = []
            for c in top:
                val = f"{c['agent']}/{c['name']}"
                options.append({
                    "value": val, "display": val,
                    "description": c["detail"],
                })
            options.append({
                "value": "__browse__",
                "display": "Browse all models...",
                "description": "Full agent/model browser",
            })
            container = self.query_one("#picker_dialog", Container)
            fs = FuzzySelect(options, placeholder="Type to filter...",
                             id="top_picker")
            container.mount(fs)

    def _show_step1(self):
        """Re-show agent selection."""
        self._step = 1
        self.query_one("#picker_step_label", Label).update(
            "Step 1: Choose code agent"
        )
        # Remove other pickers
        for pid in ("#model_picker", "#top_picker"):
            try:
                self.query_one(pid, FuzzySelect).remove()
            except Exception:
                pass
        # Re-show or recreate agent picker
        try:
            ap = self.query_one("#agent_picker", FuzzySelect)
            ap.display = True
        except Exception:
            agent_options = [
                {"value": a, "display": a, "description": ""}
                for a in sorted(MODEL_FILES.keys())
            ]
            container = self.query_one("#picker_dialog", Container)
            fs = FuzzySelect(
                agent_options,
                placeholder="Type agent name...",
                id="agent_picker",
            )
            container.mount(fs)

    def _show_step2(self):
        """Switch to model selection for the chosen agent."""
        self._step = 2
        agent = self.selected_agent
        if not agent:
            return
        self.query_one("#picker_step_label", Label).update(
            f"Step 2: Choose model for [bold]{agent}[/bold]  "
            "[dim](Esc to go back)[/dim]"
        )
        # Hide agent picker
        try:
            self.query_one("#agent_picker", FuzzySelect).display = False
        except Exception:
            pass

        # Build model options from model file
        model_path = MODEL_FILES.get(agent, Path("nonexistent"))
        model_data = _load_json(model_path)
        models = model_data.get("models", []) if model_data else []
        scored_options = []
        unscored_options = []
        for m in models:
            if m.get("status", "active") == "unavailable":
                continue
            name = m.get("name", "?")
            notes = m.get("notes", "")
            # Try verifiedstats first
            vs = m.get("verifiedstats", {})
            op_buckets = vs.get(self.operation, {})
            at = op_buckets.get("all_time", {})
            if at.get("runs", 0) > 0:
                detail = _format_op_stats(op_buckets, compact=True)
                score_str = f"[{detail}]"
                sort_score = _bucket_avg(at)
            else:
                # Fall back to flat verified
                verified = m.get("verified", {})
                op_score = verified.get(self.operation, 0)
                if op_score:
                    score_str = f"[score: {op_score}]"
                    sort_score = op_score
                elif self.operation in verified:
                    score_str = "(not verified)"
                    sort_score = 0
                else:
                    score_str = ""
                    sort_score = -1
            desc = f"{notes}  {score_str}".strip() if score_str else notes
            opt = {"value": name, "display": name, "description": desc}
            if sort_score > 0:
                scored_options.append((sort_score, opt))
            else:
                unscored_options.append(opt)

        # Verified models first (sorted by score desc), then the rest
        scored_options.sort(key=lambda x: -x[0])
        model_options = [o for _, o in scored_options] + unscored_options

        if not model_options:
            model_options = [
                {"value": "", "display": "(no models found)", "description": ""}
            ]

        container = self.query_one("#picker_dialog", Container)
        fs = FuzzySelect(
            model_options,
            placeholder="Type model name...",
            id="model_picker",
        )
        container.mount(fs)

    # FuzzySelect.Selected and Cancelled are handled by
    # on_fuzzy_select_selected / on_fuzzy_select_cancelled above
