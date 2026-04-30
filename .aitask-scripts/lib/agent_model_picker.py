"""agent_model_picker — Shared picker for code agent + LLM model selection.

Used by the settings TUI (to edit global defaults in codeagent_config.json)
and by the launch dialog (to override the agent/model for a single run).
The module is Textual-dependent but has no settings_app dependency.

Public API:
- AgentModelPickerScreen — ModalScreen with a single fuzzy list that cycles
  through seven modes via Shift+Left / Shift+Right:
    top, top_usage, all, codex, opencode, claudecode, geminicli
- FuzzySelect / FuzzyOption — reusable fuzzy-search list widget
- MODEL_FILES — {provider: Path} map of models_*.json files
- load_all_models(project_root) — load every models_*.json into a dict
"""
from __future__ import annotations

import sys
from pathlib import Path

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, VerticalScroll
from textual.message import Message
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Static

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


def _recent_aggregate(op_buckets: dict) -> tuple[int, int]:
    """Return (runs, score_sum) summed across month + prev_month buckets."""
    month = op_buckets.get("month", {})
    prev = op_buckets.get("prev_month", {})
    runs = month.get("runs", 0) + prev.get("runs", 0)
    sum_ = month.get("score_sum", 0) + prev.get("score_sum", 0)
    return runs, sum_


def _recent_avg(op_buckets: dict) -> int:
    runs, sum_ = _recent_aggregate(op_buckets)
    if runs <= 0:
        return 0
    return round(sum_ / runs)


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
    pm = buckets.get("prev_month", {})
    mo_runs = mo.get("runs", 0)
    pm_runs = pm.get("runs", 0)
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
    """Single-screen picker that cycles through seven model lists.

    Lists are switched with Shift+Left / Shift+Right. The fuzzy-search Input
    inside the FuzzySelect remains usable for letter-based filtering.
    """

    # (mode_key, header_label). Per-agent mode keys must match MODEL_FILES
    # so _build_options_for_agent can look up the JSON file directly.
    _MODES: list[tuple[str, str]] = [
        ("top",        "Top verified models (recent)"),
        ("top_usage",  "Top by usage (recent)"),
        ("all",        "All models"),
        ("codex",      "All codex models"),
        ("opencode",   "All opencode models"),
        ("claudecode", "All Claude models"),
        ("geminicli",  "All Gemini models"),
    ]

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

    BINDINGS = [
        Binding("escape", "go_back", "Back/Cancel", show=False),
        Binding("shift+left", "prev_list", "Prev list", show=True, priority=True),
        Binding("shift+right", "next_list", "Next list", show=True, priority=True),
    ]

    def __init__(self, operation: str, current_agent: str = "",
                 current_model: str = "",
                 all_models: dict[str, dict] | None = None):
        super().__init__()
        self.operation = operation
        self.current_agent = current_agent
        self.current_model = current_model
        self.all_models = all_models or {}
        self._mode_idx = 0

    def _build_top_verified(self) -> list[dict]:
        """Build ranked list of top verified models, recent window."""
        candidates = []
        for agent, pdata in self.all_models.items():
            for m in pdata.get("models", []):
                if m.get("status", "active") == "unavailable":
                    continue
                name = m.get("name", "?")
                vs = m.get("verifiedstats", {})
                op_buckets = vs.get(self.operation, {})
                recent_runs, recent_sum = _recent_aggregate(op_buckets)
                if recent_runs <= 0:
                    score = m.get("verified", {}).get(self.operation, 0)
                    if score > 0:
                        candidates.append({
                            "agent": agent, "name": name,
                            "score": score,
                            "detail": f"score: {score} (no recent data)",
                        })
                    continue
                avg = round(recent_sum / recent_runs)
                detail = f"{avg} ({recent_runs} runs recent)"
                candidates.append({
                    "agent": agent, "name": name,
                    "score": avg, "detail": detail,
                })
        candidates.sort(key=lambda c: (-c["score"], c["agent"], c["name"]))
        return candidates[:5]

    def _build_top_usage(self) -> list[dict]:
        """Build ranked list of top-used models, recent window."""
        candidates = []
        for agent, pdata in self.all_models.items():
            for m in pdata.get("models", []):
                if m.get("status", "active") == "unavailable":
                    continue
                name = m.get("name", "?")
                us = m.get("usagestats", {})
                op_buckets = us.get(self.operation, {})
                recent_runs, _ = _recent_aggregate(op_buckets)
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
            # FuzzySelect is mounted in on_mount via _apply_mode so the
            # initial list reflects the active mode.

    def on_mount(self) -> None:
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
        if mode_key in ("top", "top_usage", "all"):
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
        try:
            self.query_one("#picker_step_label", Label).update(
                f"{label_text}  [dim](Shift+←/→ to switch)[/dim]"
            )
        except Exception:
            pass
        options = self._build_options_for_mode(mode_key)
        placeholder = self._placeholder_for_mode(mode_key)
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

    @staticmethod
    def _placeholder_for_mode(mode_key: str) -> str:
        if mode_key == "top":
            return "Type to filter top-verified models..."
        if mode_key == "top_usage":
            return "Type to filter top-used models..."
        if mode_key == "all":
            return "Type agent/model..."
        return f"Type {mode_key} model name..."

    def _build_options_for_mode(self, mode_key: str) -> list[dict]:
        if mode_key == "top":
            return self._build_options_top()
        if mode_key == "top_usage":
            return self._build_options_top_usage()
        if mode_key == "all":
            return self._build_options_all()
        return self._build_options_for_agent(mode_key)

    def _build_options_top(self) -> list[dict]:
        out: list[dict] = []
        for c in self._build_top_verified():
            val = f"{c['agent']}/{c['name']}"
            out.append({
                "value": val,
                "display": val,
                "description": c["detail"],
            })
        if not out:
            out.append({
                "value": "",
                "display": "(no top-verified models for this op)",
                "description": "",
            })
        return out

    def _build_options_top_usage(self) -> list[dict]:
        out: list[dict] = []
        for c in self._build_top_usage():
            val = f"{c['agent']}/{c['name']}"
            out.append({
                "value": val,
                "display": val,
                "description": c["detail"],
            })
        if not out:
            out.append({
                "value": "",
                "display": "(no recent usage for this op)",
                "description": "",
            })
        return out

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
            op_buckets = vs.get(self.operation, {})
            at = op_buckets.get("all_time", {})
            if at.get("runs", 0) > 0:
                detail = _format_op_stats(op_buckets, compact=True)
                sort_score = _bucket_avg(at)
                score_str = f"[{detail}]"
            else:
                verified = m.get("verified", {})
                op_score = verified.get(self.operation, 0)
                if op_score:
                    sort_score = op_score
                    score_str = f"[score: {op_score}]"
                elif self.operation in verified:
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


class LaunchModePickerScreen(ModalScreen):
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
